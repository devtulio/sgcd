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

test('objeto/nº DL com payload de XSS não executa script no documento gerado', async ({ page, context }) => {
  // Regressão: _nomeArquivoDoc() monta o <title> do documento e os campos do
  // processo entram no corpo do documento sem escapar em ~15 geradores —
  // um <img onerror=...> em objeto/nº DL executava de verdade na janela do
  // documento, que tem acesso ao localStorage (token de sessão) e à API.
  page.on('dialog', dialog => dialog.accept());

  await page.goto('/SGCD.html');
  await page.fill('#pin-username', 'admin');
  await page.fill('#pin-input', 'novaSenhaE2E123');
  await page.click('#overlay-pin button[onclick="verificarSenha()"]');
  await expect(page.locator('#overlay-pin')).toBeHidden();

  await page.click('button:has-text("Novo Processo")');
  await page.fill('#m-obj', 'Objeto <img src=x onerror="window.__xssBody=true"> malicioso');
  await page.fill('#m-num-dl', '<img src=x onerror="window.__xssTitle=true">');
  await page.click('.modal-footer button:has-text("Criar Processo")');

  const card = page.locator('.process-card', { hasText: 'Objeto' });
  await card.click();

  const stepCard = page.locator('.step-card', { hasText: 'Autorização da Autoridade Competente' });
  await stepCard.locator('.step-row').click();

  const [popup] = await Promise.all([
    context.waitForEvent('page'),
    stepCard.getByRole('button', { name: /Gerar Autorização/ }).click(),
  ]);
  await popup.waitForLoadState();

  const xssTitle = await popup.evaluate(() => window.__xssTitle);
  const xssBody = await popup.evaluate(() => window.__xssBody);
  expect(xssTitle).toBeUndefined();
  expect(xssBody).toBeUndefined();
  await expect(popup.locator('.doc-title')).toContainText('img');
});
