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
