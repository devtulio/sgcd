// Testes E2E do fluxo real no navegador (login, criar processo, gerar documento).
// Complementa tests/test_server.py (unittest, só backend) — aqui é HTML+JS+backend
// juntos, exatamente como um usuário usaria. Roda contra um banco/uploads/backups
// isolados (SGCD_DATA_DIR), nunca o sgcd.db real.
import { defineConfig } from '@playwright/test';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const dataDir = mkdtempSync(join(tmpdir(), 'sgcd-e2e-'));
const port = 3050;

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  // Assertions (toBeVisible/toBeHidden) que dependem de um round-trip ao servidor
  // Python ocasionalmente passam de 5s (default) sob carga nos runners Windows do
  // GitHub — ex.: o overlay de login some só após o POST voltar. 10s dá folga sem
  // mascarar travamento real (o timeout do teste inteiro continua 30s).
  expect: { timeout: 10_000 },
  fullyParallel: false, // um único servidor/banco compartilhado entre os specs
  workers: 1,
  use: {
    baseURL: `http://localhost:${port}`,
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'python server.py',
    url: `http://localhost:${port}/health`,
    reuseExistingServer: false,
    timeout: 15_000,
    env: { SGCD_DATA_DIR: dataDir, SGCD_PORT: String(port) },
  },
});
