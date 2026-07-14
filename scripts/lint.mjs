// Extrai os <script> do SGCD.html e roda ESLint (no-undef) sobre o resultado.
// Não faz parte do runtime do sistema — é só uma checagem de desenvolvimento.
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { ESLint } from 'eslint';

const htmlPath = join(import.meta.dirname, '..', 'SGCD.html');
const html = readFileSync(htmlPath, 'utf-8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);

if (!scripts.length) {
  console.error('Nenhum <script> encontrado em SGCD.html');
  process.exit(1);
}

// base.js (esqueleto compartilhado, ver _esqueleto/README.md) é carregado via
// <script src="base.js">, então o regex acima não pega — inclui o arquivo de
// verdade no bundle lintado, senão toda função que ele define (API, toast,
// customConfirm, etc.) aparece como "no-undef" no script principal.
const baseJsPath = join(import.meta.dirname, '..', 'base.js');
scripts.unshift(readFileSync(baseJsPath, 'utf-8'));

const tmpDir = mkdtempSync(join(tmpdir(), 'sgcd-lint-'));
const tmpFile = join(tmpDir, 'sgcd.js');
writeFileSync(tmpFile, scripts.join('\n;\n'));

const eslint = new ESLint({
  cwd: tmpDir,
  overrideConfigFile: join(import.meta.dirname, '..', 'eslint.config.js'),
});
const results = await eslint.lintFiles([tmpFile]);
const formatter = await eslint.loadFormatter('stylish');
const output = formatter.format(results.map(r => ({ ...r, filePath: 'SGCD.html (script extraído)' })));

const errorCount = results.reduce((n, r) => n + r.errorCount, 0);
if (output.trim()) console.log(output);
console.log(errorCount === 0 ? '✔ Nenhum erro encontrado.' : `✖ ${errorCount} erro(s) encontrado(s).`);
process.exit(errorCount === 0 ? 0 : 1);
