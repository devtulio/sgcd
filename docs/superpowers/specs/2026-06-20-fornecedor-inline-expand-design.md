# Fornecedor — Card Expansível Inline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o modal de visualização/edição de fornecedores por cards expansíveis inline na lista, com três estados: colapsado, visualização e edição.

**Architecture:** Toda a lógica vive nas funções existentes `renderFornecedores`, `_renderFornView`, `_renderFornEdit` e `openFornDetail`. A overlay modal (`forn-detail-overlay`) é removida. Os três estados são renderizados dentro do próprio card na lista via `innerHTML`, controlados por uma variável `_expandedFornId`.

**Tech Stack:** HTML/CSS/JS puro, sem dependências externas. IndexedDB via helpers existentes (`dbGet`, `dbPut`).

---

## Comportamento

### Estado 1 — Colapsado (default)
- Card compacto com: razão social, CNPJ, badge de situação, endereço resumido, porte, badges de certidões (vencidas / a vencer / válidas), link de processos vinculados.
- Clique em qualquer parte do card expande para visualização.
- Apenas **um card aberto por vez** — abrir outro fecha o anterior automaticamente.

### Estado 2 — Expandido / Visualização
- Header do card mostra razão social + CNPJ + situação (igual ao colapsado).
- Corpo renderiza as mesmas três abas já existentes: **Dados**, **Certidões**, **Processos**.
- Footer inline com botões: **Fechar** (colapsa) e **✏ Editar** (entra no estado 3).
- Clique no header colapsa o card (toggle).

### Estado 3 — Edição inline
- Header muda para: "Editando: {razão social}" com fundo `var(--color-background-secondary)` e borda laranja (`#e05c2a`).
- Corpo mostra o formulário de edição completo (mesmo conteúdo do `_renderFornEdit` atual).
- Footer inline com: **Cancelar** (volta ao estado 2) e **Salvar alterações** (salva e volta ao estado 2).
- Botão **🔄 Reconsultar CNPJ** permanece no topo do formulário.

---

## Mudanças de código

### Remover
- `<div class="overlay hidden" id="forn-detail-overlay">` e todo seu conteúdo HTML (~10 linhas).
- Funções `openFornDetail()` e `closeFornDetail()`.
- CSS de `.overlay` específico do forn-detail (manter overlays de outros modais intactos).

### Adicionar
- Variável global `let _expandedFornId = null` — rastreia qual card está aberto.
- Função `toggleFornCard(id)` — fecha o aberto (se houver outro), expande o clicado no estado 2.
- Função `_renderFornCardView(f)` — renderiza o card completo com header + body (estado 2), injetado no `div.forn-list-item[data-id="${id}"]`.
- Função `_renderFornCardEdit(f)` — renderiza o card em modo edição (estado 3), injetado no mesmo div.
- Função `_collapseFornCard(id)` — volta card ao estado 1 (re-renderiza o mini-card colapsado).

### Modificar
- `renderFornecedores()` — cada item da lista recebe `data-forn-id="${f.id}"` e `onclick="toggleFornCard('${f.id}')"`.
- `_saveFornEdit()` — após salvar, chama `_renderFornCardView(forn)` em vez de `_renderFornView()`.
- `_reconsultarForn()` — após reconsultar, chama `_renderFornCardEdit(forn)` em vez de `_renderFornEdit()`.
- Todos os lugares que chamam `openFornDetail(id)` ou `openFornDetail(id, true)` passam a chamar `toggleFornCard(id)` ou `toggleFornCard(id, true)` (com flag para abrir direto em edição).
- Links de processo dentro do card: `onclick` fecha o card e abre o processo (comportamento idêntico ao atual).

### CSS
- Adicionar `.forn-list-item.expanded` com `border-color: var(--color-border-primary)`.
- Adicionar `.forn-list-item.editing` com `border-color: #e05c2a`.
- Adicionar `.forn-card-edit-header` para o header do modo edição.
- Remover estilos do `#forn-detail-overlay` que não são compartilhados.

---

## Pontos de atenção

- **Abas (Dados / Certidões / Processos):** a função `_fornTabsHtml(activeTab)` e `_fornViewHtml(f)` já existem e podem ser reusadas diretamente no card inline. A troca de aba chama `_switchFornTab(tab)` que re-renderiza só o body.
- **Scroll:** ao expandir um card, fazer `scrollIntoView({ behavior: 'smooth', block: 'nearest' })` para garantir visibilidade.
- **Agenda de vencimentos:** o link de certidão vencida (`openFornDetail(id, false, 'certs')`) passa a chamar `toggleFornCard(id, false, 'certs')`.
- **Lookup no processo (etapa de habilitação):** o card de fornecedor dentro do processo (`renderFornecedorLookup`) não é afetado — continua como está.
