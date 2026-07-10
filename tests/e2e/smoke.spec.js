// Caminho feliz de ponta a ponta: login (com troca de senha obrigatória, já que
// o banco é novo a cada run) → criar processo → gerar um documento.
import { test, expect } from '@playwright/test';

test('login força troca de senha, cria processo e gera documento', async ({ page, context }) => {
  // Gerar documento com campos opcionais (base legal, nº DL) vazios dispara um
  // confirm() nativo perguntando se quer continuar mesmo assim — sem handler,
  // o Playwright descarta diálogos não tratados e a geração nunca prossegue.
  page.on('dialog', dialog => dialog.accept());

  await page.goto('/SGCD.html');

  await page.fill('#pin-username', 'admin');
  await page.fill('#pin-input', 'admin123');
  await page.click('#overlay-pin button[onclick="verificarSenha()"]');

  // Banco novo → admin padrão nasce com troca de senha obrigatória (v2.21.0)
  await expect(page.locator('#overlay-force-pwd')).toBeVisible();
  await page.fill('#fp-nova', 'novaSenhaE2E123');
  await page.fill('#fp-confirma', 'novaSenhaE2E123');
  await page.click('#overlay-force-pwd button');

  await expect(page.locator('#overlay-pin')).toBeHidden();
  await expect(page.getByText('Nenhum processo cadastrado')).toBeVisible();

  await page.click('button:has-text("Novo Processo")');
  await page.fill('#m-obj', 'Aquisição de material de teste E2E');
  await page.click('.modal-footer button:has-text("Criar Processo")');

  const card = page.locator('.process-card', { hasText: 'Aquisição de material de teste E2E' });
  await expect(card).toBeVisible();
  await card.click();

  const stepCard = page.locator('.step-card', { hasText: 'Autorização da Autoridade Competente' });
  await stepCard.locator('.step-row').click();

  const [popup] = await Promise.all([
    context.waitForEvent('page'),
    stepCard.getByRole('button', { name: /Gerar Autorização/ }).click(),
  ]);
  await popup.waitForLoadState();
  await expect(popup.locator('.doc-title')).toContainText('Autorização de Abertura');

  // Assinatura Simples: não depende de gov.br nem de certificado ICP-Brasil,
  // só grava hash + identidade no servidor — testável de ponta a ponta sem mock.
  await popup.getByRole('button', { name: /Assinar Documento/ }).click();
  await popup.locator('#sig-card-simples').click();
  await expect(popup.getByText(/Assinado eletronicamente por/)).toBeVisible();

  await expect(page.locator('#sig-list')).toContainText('Autorização de Abertura');
  await expect(page.locator('#sig-list')).toContainText('Simples');
});

test('gera PDF consolidado numerado do processo', async ({ page }) => {
  // Roda depois do teste de login (que já trocou a senha do admin) no mesmo
  // servidor/banco — usa a nova senha, sem tela de troca obrigatória.
  await page.goto('/SGCD.html');
  await page.fill('#pin-username', 'admin');
  await page.fill('#pin-input', 'novaSenhaE2E123');
  await page.click('#overlay-pin button[onclick="verificarSenha()"]');
  await expect(page.locator('#overlay-pin')).toBeHidden();

  // Monta um processo com só a Autorização preenchida — a capa e a Autorização
  // bastam para provar o pipeline completo (headless print + merge + numeração
  // via pyHanko) sem precisar montar as 18 etapas manualmente.
  const procId = await page.evaluate(async () => {
    const r = await API.post('/api/processes', {
      id: 'e2e-consolidado-' + Date.now(),
      objeto: 'Processo de teste do PDF consolidado',
      num_dl: '99/2026',
      legal: 'Art. 75, II — Lei 14.133/2021',
      createdAt: Date.now(), updatedAt: Date.now(), steps: [],
    });
    const proc = await r.json();
    proc.steps = new Array(18).fill(null).map(() => ({ status: 'pending', fields: {}, completedAt: null }));
    proc.steps[8] = { status: 'done', fields: { responsavel: 'Fulano', data_conclusao: '2026-01-10' }, completedAt: Date.now() };
    await salvarProcesso(proc);
    return proc.id;
  });

  const result = await page.evaluate(async (id) => {
    const r = await API.get(`/api/processes/${id}`);
    // gerarProcessoCompleto() e as _htmlXxx() que ela chama leem o processo
    // aberto via currentProcess (mesma variável que a tela de detalhe usa) —
    // não é só um parâmetro, precisa estar setada como na navegação real.
    currentProcess = await r.json();
    const slots = await _montarSlotsConsolidado(currentProcess);
    const rr = await API.post(`/api/processes/${currentProcess.id}/pdf-consolidado`, { slots });
    if (!rr) return { ok: false, error: 'sem resposta' };
    if (!rr.ok) return { ok: false, status: rr.status, error: (await API.json(rr))?.error };
    const blob = await rr.blob();
    return { ok: true, status: rr.status, contentType: blob.type, size: blob.size };
  }, procId);

  expect(result.ok, result.error).toBe(true);
  expect(result.status).toBe(200);
  expect(result.contentType).toBe('application/pdf');
  expect(result.size).toBeGreaterThan(1000);
});

test('sincroniza backup de outro agente e mescla processo novo', async ({ page }) => {
  // Roda depois do teste acima no mesmo servidor/banco (webServer é compartilhado
  // para toda a suíte) — a senha do admin já foi trocada lá, então usamos a nova.
  await page.goto('/SGCD.html');
  await page.fill('#pin-username', 'admin');
  await page.fill('#pin-input', 'novaSenhaE2E123');
  await page.click('#overlay-pin button[onclick="verificarSenha()"]');
  await expect(page.locator('#overlay-pin')).toBeHidden();

  // Backup sintético de um "outro agente" com um processo que não existe aqui —
  // testa o caminho de mesclagem sem precisar de um segundo servidor de verdade.
  const backupSintetico = {
    _sgcd: true,
    version: 4,
    exportedAt: new Date().toISOString(),
    processes: [{
      id: 'sync-e2e-' + Date.now(),
      objeto: 'Processo de outro agente (sync E2E)',
      steps: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }],
    fornecedores: [],
    files: [],
    auditGlobal: [],
    settings: {},
  };

  await page.click('#nav-settings');
  await page.click('button[onclick="switchCfgTab(\'dados\',this)"]');
  await page.setInputFiles('input[onchange^="sincronizarBackup"]', {
    name: 'backup-outro-agente.json',
    mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify(backupSintetico)),
  });

  await expect(page.locator('#confirm-overlay')).toBeVisible();
  await page.click('#confirm-ok');

  await page.click('#nav-dash');
  await expect(page.locator('.process-card', { hasText: 'Processo de outro agente (sync E2E)' })).toBeVisible();
});
