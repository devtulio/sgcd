// Capturas do README. Não é teste: não afirma nada sobre o sistema, só monta um
// cenário de demonstração e fotografa. Roda fora do CI, por configuração própria:
//
//     npx playwright test -c docs/screenshots.config.js
//
// TODO dado aqui é fictício, por decisão: as imagens vão para um repositório
// público e nada que saia daqui pode ser de um processo, fornecedor ou servidor
// real. O órgão é "Município de Exemplo/SP"; os CNPJs são válidos no dígito
// verificador mas de empresas inventadas; não há brasão (upload em Configurações,
// nunca embutido) — a instância nasce sem identidade visual de ninguém.
import { test, expect } from '@playwright/test';

const SHOTS = 'docs/screenshots';

const ORG = {
  orgao: 'Prefeitura Municipal de Exemplo',
  municipio: 'Município de Exemplo',
  uf: 'SP',
  aut_nome: 'Maria Aparecida Silva',
  aut_cargo: 'Prefeita Municipal',
  cnpj_orgao: '12.345.678/0001-95',
  nome: 'João Carlos Pereira',
  cargo: 'Agente de Contratação',
  matricula: '1234',
};

const LEGAL_VALOR = 'Art. 75, II — Valor (até R$ 62.725,29 — serviços e compras)';

// Valores somam ~50% do limite anual do Art. 75, II: o painel lateral acompanha
// o acumulado do exercicio e pinta de vermelho quando estoura — verdadeiro, mas
// um alerta de ilegalidade nao e o que a foto do README deve mostrar.
const PROCESSOS = [
  { num_proc: '2026/0142', num_dl: '018/2026', objeto: 'Aquisição de material de expediente para as unidades administrativas', valor: '12.450,00', unidade: 'Secretaria Municipal de Administração', concluir: 12, dias: 9 },
  { num_proc: '2026/0139', num_dl: '017/2026', objeto: 'Contratação de serviço de manutenção preventiva da frota municipal', valor: '8.700,00', unidade: 'Secretaria Municipal de Obras e Serviços', concluir: 8, dias: 14 },
  { num_proc: '2026/0131', num_dl: '015/2026', objeto: 'Aquisição de gêneros alimentícios para a merenda escolar', valor: '5.900,00', unidade: 'Secretaria Municipal de Educação', concluir: 5, dias: 21 },
  { num_proc: '2026/0128', num_dl: '014/2026', objeto: 'Contratação de empresa para manutenção de ar-condicionado', valor: '3.800,00', unidade: 'Secretaria Municipal de Administração', concluir: 3, dias: 26 },
  { num_proc: '2026/0125', num_dl: '013/2026', objeto: 'Aquisição de medicamentos de uso contínuo para a farmácia municipal', valor: '2.400,00', unidade: 'Secretaria Municipal de Saúde', concluir: 18, dias: 34 },
];

test('capturas do README', async ({ page, context }) => {
  page.on('dialog', d => d.accept());

  await page.goto('/SGCD.html');
  await page.fill('#pin-username', 'admin');
  await page.fill('#pin-input', 'admin123');
  await page.click('#overlay-pin button[onclick="verificarSenha()"]');
  await expect(page.locator('#overlay-force-pwd')).toBeVisible();
  await page.fill('#fp-nova', 'demoSGCD2026');
  await page.fill('#fp-confirma', 'demoSGCD2026');
  await page.click('#overlay-force-pwd button');
  await expect(page.locator('#overlay-pin')).toBeHidden();

  // O nome do usuário logado aparece na barra lateral e assina as etapas — vem
  // da conta, não das settings, então também precisa ser fictício.
  await page.evaluate(async org => {
    const lista = await API.json(await API.get('/api/usuarios'));   // devolve array puro
    const eu = lista.find(u => u.username === 'admin');
    await API.put(`/api/usuarios/${eu.id}`, { nome: org.nome, cargo: org.cargo, matricula: org.matricula });
  }, ORG);

  // Órgão fictício. Vai para o localStorage, que é de onde getUser() lê — o
  // mesmo caminho do formulário de Configurações, sem precisar preenchê-lo.
  await page.evaluate(org => {
    localStorage.setItem('sgcd-user', JSON.stringify({ ...org, tema_cor: 'laranja' }));
  }, ORG);

  const ids = await page.evaluate(async ({ lista, org, legalValor }) => {
    const criados = [];
    for (const p of lista) {
      const r = await API.post('/api/processes', {
        num_proc: p.num_proc, num_dl: p.num_dl, objeto: p.objeto, valor: p.valor, unidade: p.unidade,
        legal: legalValor, criterio_selecao: 'menor_preco',
        createdAt: Date.now() - p.dias * 86400000,
      });
      const novo = await API.json(r);
      criados.push({ id: novo.id, concluir: p.concluir });
    }
    await loadProcesses();

    // Avança cada processo até a etapa combinada, para o painel mostrar barras
    // de progresso diferentes em vez de cinco processos zerados.
    for (const { id, concluir } of criados) {
      await openProcess(id);
      for (let i = 0; i < concluir && i < currentProcess.steps.length; i++) {
        currentProcess.steps[i].status = 'done';
        currentProcess.steps[i].completedAt = Date.now();
        currentProcess.steps[i].fields.responsavel = org.nome;
      }
      await saveProcess(currentProcess);
    }
    await loadProcesses();
    return criados.map(c => c.id);
  }, { lista: PROCESSOS, org: ORG, legalValor: LEGAL_VALOR });

  // ── 1. Painel ──────────────────────────────────────────────────────────────
  // recarrega para a interface reler o orgao do localStorage (a sessao continua
  // valida: o token fica no proprio localStorage, entao nao ha login de novo)
  await page.reload();
  await expect(page.locator('#overlay-pin')).toBeHidden();
  await expect(page.locator('.process-card').first()).toBeVisible();
  await page.waitForTimeout(600);                       // graficos do painel
  await page.screenshot({ path: `${SHOTS}/painel.png` });

  // ── 2. Etapas do processo ─────────────────────────────────────────────────
  // O fluxo guiado é o que distingue o sistema: 18 etapas, cada uma com seus
  // campos, documentos e anexos. A foto mostra uma concluída, a corrente aberta
  // e uma marcada como "não se aplica" (a Nota de Empenho, que aqui vive na
  // contabilidade e não volta ao processo).
  await page.evaluate(async id => {
    await openProcess(id);
    const iEmpenho = STEPS.findIndex(s => /Nota de Empenho/i.test(s.name));
    currentProcess.steps[iEmpenho].status = 'na';
    currentProcess.steps[iEmpenho].fields._naoSeAplica = {
      motivo: 'Empenho por pedido, emitido pela contabilidade',
      em: _isoLocal(), por: 'João Carlos Pereira (mat. 1234)',
    };
    await saveProcess(currentProcess);
    await openProcess(id);
    const iAtual = STEPS.findIndex((s, i) => currentProcess.steps[i].status === 'pending');
    expandedSteps.add(iAtual);
    await renderSingleStep(iAtual);
  }, ids[0]);
  // rolar pelo Playwright (o scrollIntoView dentro do evaluate corre antes do
  // re-render terminar e o container volta ao topo)
  const iNa = await page.evaluate(() => STEPS.findIndex(s => /Nota de Empenho/i.test(s.name)));
  await page.waitForTimeout(600);                       // o re-render ainda troca os nos
  await expect(page.locator(`#step-card-${iNa} .step-na-badge`)).toBeVisible();
  await page.evaluate(() => {
    const i = currentProcess.steps.findIndex(s => s.status === 'pending');
    document.getElementById(`step-card-${i}`).scrollIntoView({ block: 'start' });
    window.scrollBy(0, -110);           // respiro acima do titulo da etapa aberta
  });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${SHOTS}/etapas.png` });

  // ── 3. Documento gerado ───────────────────────────────────────────────────
  const [doc] = await Promise.all([
    context.waitForEvent('page'),
    page.evaluate(async id => {
      await openProcess(id);
      const i = STEPS.findIndex(s => s.autorizacao);
      expandedSteps.add(i);
      await renderSingleStep(i);
      document.querySelector(`#step-card-${i} button[onclick="gerarAutorizacao()"]`).click();
    }, ids[0]),
  ]);
  await doc.waitForLoadState();
  await doc.setViewportSize({ width: 1100, height: 1000 });
  await doc.waitForTimeout(400);
  await doc.screenshot({ path: `${SHOTS}/documento.png` });
  await doc.close();
});
