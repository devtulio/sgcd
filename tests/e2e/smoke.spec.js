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

test('sanitizador de e-mail bloqueia javascript: mesmo com caractere de controle', async ({ page }) => {
  // Regressão: DANGEROUS_PROTOCOLS testava o valor cru do atributo, e TAB/LF/CR
  // dentro do esquema são ignorados pelo navegador ao resolver a URL — um
  // href="java<TAB>script:..." passava pelo filtro e virava javascript: de
  // verdade (verificado: a.protocol devolvia 'javascript:').
  await page.goto('/SGCD.html');

  const r = await page.evaluate(() => {
    const proto = html => {
      const limpo = _sanitizeEmailHtml(html);
      const el = new DOMParser().parseFromString(limpo, 'text/html').querySelector('a,img');
      return { limpo, protocolo: el ? el.protocol : '(sem elemento)' };
    };
    return {
      tab:      proto('<a href="java\tscript:alert(1)">x</a>'),
      lf:       proto('<a href="java\nscript:alert(1)">x</a>'),
      cr:       proto('<a href="java\rscript:alert(1)">x</a>'),
      vbs:      proto('<a href="vb\tscript:alert(1)">x</a>'),
      imgSrc:   proto('<img src="java\tscript:alert(1)">'),
      https:    proto('<a href="https://orindiuva.sp.gov.br/edital">edital</a>'),
      mailto:   proto('<a href="mailto:proc@orindiuva.sp.gov.br">e-mail</a>'),
    };
  });

  for (const chave of ['tab', 'lf', 'cr', 'vbs', 'imgSrc']) {
    expect(r[chave].limpo, `${chave} manteve o atributo`).not.toMatch(/href=|src=/);
    expect(r[chave].protocolo, `${chave} ainda resolve para javascript:`).not.toBe('javascript:');
  }
  // e o que é legítimo continua passando
  expect(r.https.protocolo).toBe('https:');
  expect(r.mailto.protocolo).toBe('mailto:');
});

// Anexo baixado tem de passar pelo seletor "Salvar como" do navegador, não cair
// direto na pasta de downloads (relato de uso real: certidões da habilitação).
// Stuba window.showSaveFilePicker porque o diálogo nativo é do sistema
// operacional e o Playwright não o enxerga — o que importa provar é que
// downloadFile() consulta a API de gravação em vez de criar um <a download>.
test('baixar anexo abre o seletor de destino em vez de baixar direto', async ({ page }) => {
  await page.goto('/SGCD.html');
  await page.fill('#pin-username', 'admin');
  // Senha já trocada pelo primeiro teste (servidor/banco compartilhados na suíte).
  await page.fill('#pin-input', 'novaSenhaE2E123');
  await page.click('#overlay-pin button[onclick="verificarSenha()"]');
  await expect(page.locator('#overlay-pin')).toBeHidden();

  // Anexa um PDF pela propria API - o que se testa aqui e o caminho de
  // download, nao o de upload.
  const fileId = await page.evaluate(async () => {
    const fd = new FormData();
    fd.append('file', new Blob(['%PDF-1.4 certidao'], { type: 'application/pdf' }), 'certidao.pdf');
    const r = await fetch('/api/files', {
      method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('sgcd-token')}` },
      body: fd,
    });
    return (await r.json()).id;
  });
  expect(fileId).toBeTruthy();

  const salvo = await page.evaluate(async (id) => {
    const chamado = { picker: false, nome: null, bytes: 0 };
    window.showSaveFilePicker = async (opts) => {
      chamado.picker = true;
      chamado.nome = opts.suggestedName;
      return {
        createWritable: async () => ({
          write: async (blob) => { chamado.bytes = blob.size; },
          close: async () => {},
        }),
      };
    };
    await downloadFile(id);
    return chamado;
  }, fileId);

  expect(salvo.picker, 'downloadFile nao consultou showSaveFilePicker').toBe(true);
  expect(salvo.nome).toBe('certidao.pdf');
  expect(salvo.bytes).toBeGreaterThan(0);
});

// Os botoes da lista de anexos interpolavam o id do arquivo SEM aspas no
// onclick ("deleteFile(ba85ee05-e9c1-...)"), o que e JavaScript invalido: o
// clique morria com "Uncaught SyntaxError: Invalid or unexpected token" e nem
// baixar nem excluir funcionavam. Este teste clica nos botoes de verdade - se
// alguem tirar as aspas outra vez, ele cai.
test('botoes de baixar e excluir anexo funcionam pelo clique real', async ({ page }) => {
  await page.goto('/SGCD.html');
  await page.fill('#pin-username', 'admin');
  await page.fill('#pin-input', 'novaSenhaE2E123');
  await page.click('#overlay-pin button[onclick="verificarSenha()"]');
  await expect(page.locator('#overlay-pin')).toBeHidden();

  const erros = [];
  page.on('pageerror', e => erros.push(e.message));

  // Abre o processo do primeiro spec e anexa um PDF na etapa 1. O process_id
  // do anexo e composto (<processo>_<etapa>), como a tela monta.
  await page.evaluate(async () => {
    const ps = await listarProcessos();
    await openProcess(ps[0].id);
    const fd = new FormData();
    fd.append('file', new Blob(['%PDF-1.4 anexo'], { type: 'application/pdf' }), 'anexo do teste.pdf');
    fd.append('process_id', ps[0].id + '_0');
    fd.append('step_index', '0');
    await fetch('/api/files', {
      method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('sgcd-token')}` },
      body: fd,
    });
    expandedSteps.add(0);
    await renderSingleStep(0);
  });

  await expect(page.locator('.file-item')).toHaveCount(1);

  // Baixar: o clique tem de chegar em downloadFile e abrir o seletor de destino.
  const baixou = await page.evaluate(async () => {
    const chamado = { picker: false, nome: null, bytes: 0 };
    window.showSaveFilePicker = async (opts) => {
      chamado.picker = true;
      chamado.nome = opts.suggestedName;
      return { createWritable: async () => ({ write: async (b) => { chamado.bytes = b.size; }, close: async () => {} }) };
    };
    document.querySelector('.file-item button[title="Baixar"]').click();
    await new Promise(r => setTimeout(r, 800));
    return chamado;
  });
  expect(baixou.picker, 'o clique em Baixar nao chegou em downloadFile').toBe(true);
  expect(baixou.nome).toBe('anexo do teste.pdf');
  expect(baixou.bytes).toBeGreaterThan(0);

  // Excluir: o clique tem de remover o anexo de verdade.
  await page.evaluate(async () => {
    window.customConfirm = async () => true;
    document.querySelector('.file-item button[title="Remover"]').click();
    await new Promise(r => setTimeout(r, 1200));
  });
  await expect(page.locator('.file-item')).toHaveCount(0);

  expect(erros, 'houve erro de JavaScript na pagina').toEqual([]);
});

// Processo sem "steps" (backup malformado, ou registro criado por integracao)
// derrubava a lista inteira: processStatus/pct chamavam p.steps.filter direto e
// uma unica linha ruim quebrava o dashboard de todo mundo. O registro e criado
// ANTES de abrir a tela, para o teste exercitar a carga inicial da lista.
test('processo sem etapas nao derruba a lista', async ({ page, request }) => {
  const login = await request.post('/api/auth/login', {
    data: { username: 'admin', password: 'novaSenhaE2E123' },
  });
  const { token } = await login.json();
  const criado = await request.post('/api/processes', {
    headers: { Authorization: `Bearer ${token}` },
    data: { objeto: 'Processo sem etapas' },
  });
  const { id } = await criado.json();

  const erros = [];
  page.on('pageerror', e => erros.push(e.message));

  await page.goto('/SGCD.html');
  await page.fill('#pin-username', 'admin');
  await page.fill('#pin-input', 'novaSenhaE2E123');
  await page.click('#overlay-pin button[onclick="verificarSenha()"]');
  await expect(page.locator('#overlay-pin')).toBeHidden();

  await expect(page.locator('.process-card', { hasText: 'Processo sem etapas' })).toBeVisible();
  expect(erros, 'a lista quebrou com um processo sem etapas').toEqual([]);

  // nao deixa o registro degenerado para os proximos specs
  await request.delete(`/api/processes/${id}`, { headers: { Authorization: `Bearer ${token}` } });
});
