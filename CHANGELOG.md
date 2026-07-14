# Changelog — SGCD
## Sistema de Gestão de Contratação Direta
> Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/)  
> Versionamento semântico: [SemVer](https://semver.org/lang/pt-BR/)

---

## [2.29.7] — 2026-07-14

### Corrigido
- **Classe `.dash-top` (cabeçalho de título + ações de cada tela) não estava definida no esqueleto compartilhado (`_esqueleto/base.css`)** — só a classe morta `.view-top` (nunca usada em nenhum dos 4 sistemas) existia lá. Sem efeito visível em SGCD/SGCA/SGDP porque cada um definia `.dash-top` localmente (byte-idêntico entre os 3), mas deixava o SGEA com o cabeçalho de cada tela sem nenhum estilo (sem flex, sem espaçamento, título em fonte padrão do navegador) desde que uma correção anterior removeu a definição local de lá por engano. Corrigido movendo `.dash-top` para `base.css` e removendo as 3 cópias locais agora redundantes

## [2.29.6] — 2026-07-14

### Removido
- **Handlers locais de Tab-trap e Enter/Espaço em `role="button"`, duplicados dos listeners genéricos do esqueleto compartilhado (`base.js`)** — o handler local de Enter/Espaço estava embutido no mesmo listener de Ctrl+K/Escape (que continua local, pois fecha modais nomeados chamando suas funções próprias de fechamento); o handler local de Tab-trap era um bloco separado, cópia idêntica do genérico. Mesmo padrão já adotado pelo SGDP ao migrar para o esqueleto

## [2.29.5] — 2026-07-14

### Corrigido
- **`customConfirm()` travava para sempre ao fechar por Esc ou clique fora do overlay** — os dois atalhos de fechamento globais do esqueleto compartilhado (`base.js`) só escondiam `#confirm-overlay` sem resolver a Promise nem remover os listeners dos botões OK/Cancelar, deixando qualquer `await customConfirm(...)` pendurado e vazando listeners a cada abertura. Corrigido para clicar no botão Cancelar (que sempre resolve corretamente e limpa os listeners) em vez de só esconder o overlay. Corrigido na fonte compartilhada (`_esqueleto/base.js`) e propagado aos 4 sistemas via `sync.py`

## [2.29.4] — 2026-07-13

### Alterado
- **Migração para o esqueleto compartilhado da família** (`_esqueleto/base.css`/`base.js`/`sgx_base.py`, vendorizados via `sync.py`) — remove duplicação de CSS/JS/backend entre SGCD/SGCA/SGDP/SGEA (tokens, tema de cor, sidebar, modal, tela de login, toast, busca global, notificações, `get_db`, hashing, sessões, watchdog, e-mail). Sem mudança de comportamento visível; funções com divergência genuína (segurança de sessão, e-mail, configurações) continuam locais a cada sistema.

## [2.29.3] — 2026-07-13

### Adicionado
- **Relatório de Backup e Integridade** — novo botão na aba Dados de Configurações gera um documento imprimível com status do backup automático, tamanhos em disco, contagens gerais do sistema (processos, fornecedores, arquivos, usuários, etiquetas, assinaturas) e os eventos recentes de backup/restauração/reset, no mesmo padrão do SGDP
- **Auditoria de restauração e reset de fábrica** — restaurar um backup (JSON ou .db) e o reset de fábrica agora registram um evento na trilha de auditoria, o que antes não acontecia

## [2.29.2] — 2026-07-13

### Alterado
- **Modal de "Novo Usuário"/"Editar Usuário" sincronizado com o padrão do SGDP** — largura ampliada de 420px para 560px, e a opção "Ativo" agora fica escondida ao criar um usuário novo (só aparece ao editar), igual aos demais sistemas da família

## [2.29.1] — 2026-07-13

### Corrigido — Auditoria de consistência visual (P3)
- **Seletor de tema "Roxo" com anel de foco/check navy** — o `accent-color` do radio button apontava para o azul institucional (`#1a3a6b`) em vez do roxo (`#5E2750`) mostrado na amostra ao lado. Encontrado ao investigar a dívida estrutural de tokens; mesmo bug corrigido também no SGCA
- **Token `--gray-500` no lugar de `--text-secondary`** (indefinido) nos rótulos de "ignorar validação SSL" das Configurações — o token nunca foi definido em nenhum tema

## [2.29.0] — 2026-07-13

### Corrigido — Auditoria de consistência visual (P1)
- **Resquícios do laranja da marca antiga removidos** — 7 pontos ainda usavam `rgba(233,84,32,…)` (#E95420, identidade anterior) em anéis de foco e brilhos: pulso do botão Salvar em Configurações, foco dos filtros, card de etapa expandido (incl. fundos quentes claro/escuro) e foco do editor de e-mail. Agora derivam do brand via `color-mix(in srgb, var(--brand) N%, …)` — e passam a acompanhar automaticamente o tema de cor escolhido (azul/verde/roxo)

## [2.28.0] — 2026-07-11

### Corrigido
- **Painel de "Histórico do Registro" (e a lista da Agenda) apareciam transparentes** — o token `--bg-card` nunca tinha sido definido em nenhum tema (claro ou escuro), deixando esses painéis sem fundo. Mesmo bug corrigido antes no SGCA (v0.23.2); portado aqui para manter os 3 sistemas sincronizados

### Adicionado
- **Exportação PNCP ganha diálogo nativo de "Salvar como"** — `exportarPNCP()` agora usa a File System Access API (`showSaveFilePicker`) no Chrome/Edge para deixar escolher onde salvar o JSON, com fallback automático para o download tradicional em navegadores sem suporte. Mesma melhoria já aplicada às exportações PNCP do SGCA (v0.23.2)

## [2.27.0] — 2026-07-10

### Adicionado — Acessibilidade (WCAG 2.1 AA)
Correções de uma auditoria de acessibilidade dedicada (leitura de código + cálculo de contraste, 8 frentes: contraste de cor, texto alternativo, associação de rótulos, teclado, foco, alvo de toque, modais, landmarks). Mesma auditoria já aplicada ao SGDP e ao SGCA.

- **Navegação por teclado** — cards de estatística do dashboard, cards de processo, itens de fornecedor/notificação/busca global, linhas de agenda, itens de kanban e outros elementos que usavam `<div onclick>` agora têm `role="button"` + `tabindex="0"`, ativados por Enter/Espaço via um único listener delegado
- **Rótulos de formulário associados** — `<label for>` adicionado em mais de 100 campos que dependiam só de proximidade visual: modal de Novo Processo, Fornecedor, Usuário, Certidão, e-mail (Fornecedor/Interno), vínculo de processo, campos de etapa do checklist, propostas, cotações, dotação orçamentária, e todas as abas de Configurações
- **Contraste de texto corrigido** — `--gray-400` (usado como cor de texto em ~50 pontos) tinha 2,54:1 de contraste sobre branco; unificado com `--gray-500` (4,83:1) no modo claro. No modo escuro, `--gray-400`, `--gray-600` e `--gray-800` não tinham sobrescrita própria e ficavam praticamente ilegíveis (`--gray-600` chegava a ~1,9:1); corrigido reaproveitando os tons já usados por `--gray-500`/`--gray-900`. Texto secundário da barra lateral e ícones em `--gray-300` também ajustados
- **Indicador de foco visível** — adicionado `box-shadow` de foco nos campos que só trocavam a cor da borda ao focar (etapas do checklist, campos de informação, busca de fornecedor, filtros de auditoria, campo de confirmação de exclusão, busca global, campos em modo escuro)
- **Modais com semântica de diálogo** — `role="dialog"` + `aria-modal="true"` + `aria-labelledby` nos 14 modais do sistema; foco automático no primeiro campo ao abrir; Tab preso dentro do modal enquanto aberto; foco devolvido a quem acionou o modal ao fechar — via `MutationObserver` genérico, sem alterar as funções de abrir/fechar de cada modal
- **Alt text e área de toque** — imagem de prévia do brasão nas Configurações com texto alternativo; botões de fechar (✕), editar efeito de fundo e mostrar/ocultar senha com área clicável ampliada sem alterar o tamanho visual do ícone; região de conteúdo principal agora é um landmark `<main>`

## [2.26.1] — 2026-07-10

### Corrigido
- **Sessão expirava sozinha no meio do uso normal, voltando pra tela de login** — achado real reportado logo após a v2.26.0: abrir um processo e clicar na primeira etapa já bastava para cair de volta no login pedindo senha. Causa raiz: `SESSION_TTL=15s` era propositalmente curto para o antigo modo "Pessoal" detectar rápido que o navegador tinha fechado (mecanismo removido na v2.26.0) — sem esse motivo, 15s virou uma margem perigosamente curta para o uso normal: múltiplas chamadas de API concorrendo por conexão HTTP logo no login/abertura de processo, ou a aba principal perdendo foco ao abrir um popup de documento, já eram suficientes para a primeira renovação do ping (a cada 5s) atrasar além dos 15s e expirar a sessão sem ninguém ter saído de propósito. `SESSION_TTL` aumentado para **60s** (12× o intervalo do ping, folga generosa)

Validado ao vivo reproduzindo o cenário exato relatado: login → criar processo → esperar 20s (tempo que já derrubaria a sessão antiga) → abrir o processo → clicar na etapa 1 (DFD) — sessão sobrevive, sem redirecionar para o login. Teste novo em `tests/test_server.py` confirmado que falha sob o TTL antigo e passa sob o novo.

---

## [2.26.0] — 2026-07-10

### Corrigido
- **Servidor encerrava sozinho no meio do uso** — o antigo modo "Pessoal" chamava `os._exit(0)` em `_check_shutdown()` quando a última sessão ativa expirava (`SESSION_TTL=15s`, renovado por ping a cada 5s). Gerar um documento abre um popup e tira o foco da aba principal — navegadores throttlam `setInterval` em abas em segundo plano, o ping atrasa, a sessão expira sem ninguém ter saído de propósito, e o servidor se desligava sozinho no meio do uso. Corrigido removendo esse caminho inteiramente: o servidor agora só encerra via **Ctrl+C** no terminal, igual ao antigo modo "Servidor Contínuo" — `_check_shutdown()` só dispara o backup automático pós-sessão, nunca mais mata o processo

### Alterado
- **Menu inicial simplificado** — de 3 opções (Pessoal / Servidor / Diagnóstico) para 2: **[1] Diagnóstico** e **[2] Iniciar Servidor**. Não existe mais escolha de "modo" — iniciar o servidor sempre abre o navegador automaticamente (sem precisar clicar no link do terminal) e sempre fica rodando continuamente, mesclando o que havia de bom nos dois modos antigos
- Removido o botão **"Fechar Sistema"** (e a função `fecharSistema()`) — como o servidor nunca mais encerra sozinho, esse botão ficaria sempre escondido e sua promessa ("servidor desligado") nunca mais seria verdadeira. `/health` não retorna mais o campo `modo_servidor` (nada mais lê)

Validado ao vivo: sessão sem nenhum ping por 22s (bem além do TTL de 15s e de vários ciclos do watchdog) — servidor continua respondendo normalmente. Suíte de testes ganhou um teste dedicado chamando `_check_shutdown()` com zero sessões ativas — se o `os._exit(0)` antigo ainda existisse, o próprio processo de teste morreria nesse ponto.

---

## [2.25.0] — 2026-07-10

### Corrigido — Segurança
- **XSS armazenado nos ~17 geradores de documento** (`gerarAutorizacao`, `gerarAta`, `gerarDespacho*`, `gerarTermo*`, relatórios, etc.) — campos de texto livre do processo/fornecedor/usuário (objeto, nº PA/DL, matrícula, cargo, órgão, observações, CNPJ/valor de cotações e propostas) eram inseridos nos documentos HTML sem escapar. Documentos abrem em janela mesma-origem, com acesso a `localStorage` (token de sessão) e à API autenticada — um processo malicioso criado por qualquer usuário podia executar script na sessão de quem gerasse o documento (ex. um admin). Achado mais grave: o helper `blank()` (usado em 12 lugares) e a função `_nomeArquivoDoc()` (usada no `<title>` de todos os 17 documentos) não escapavam nada. Corrigido escapando na origem (`blank()` e `_nomeArquivoDoc()` nos usos de `<title>`) e em ~20 pontos que inseriam dados sem passar por nenhum dos dois, incluindo uma tabela inteira de cotações/propostas na Ata que nunca tinha sido escapada. Validado com payload real executando em navegador de verdade (Playwright) — não executa mais
- **Restauração de backup podia apagar tudo sem restaurar nada** — `_restore_backup` fazia `commit()` dos `DELETE` antes de validar as inserções; um item malformado no meio do JSON derrubava o banco inteiro. Agora é uma transação só (tudo ou nada), com erro claro ao cliente em vez de conexão cair
- **Vazamento de conexões SQLite nos caminhos de backup** — 4 pontos (`sqlite3.connect()` cru em `/api/backup/db`, `_restore_db_backup`, `_do_db_backup`) não passavam pelo `_ConnAutoClose` já usado em `get_db()`, reproduzindo o mesmo vazamento corrigido na v2.17.1

### Corrigido — Integridade de dados
- **Edição concorrente de processo/fornecedor sobrescrevia silenciosamente** — dois usuários com o mesmo registro aberto: quem salvasse por último apagava a edição do outro sem aviso. Servidor agora recusa (409) quando o `updatedAt` que o cliente carregou não bate mais com o salvo, em vez de aplicar last-write-wins cego. Nova função `_now_precise()` (precisão de milissegundo) — `_now()` (precisão de segundo) colidia facilmente entre edições rápidas em sequência
- **"✓ Salvo" aparecia mesmo quando o salvamento falhava** — `salvarProcesso()`/`salvarFornecedor()` engoliam erro de rede/servidor silenciosamente. Agora lançam exceção de verdade; indicador mostra "⚠ Não salvo" e a edição não é perdida sem aviso
- **Painel "Limite Anual Art. 75" sempre mostrava 0%** — parser de valor monetário local não removia o prefixo "R$" antes do `parseFloat`, sempre retornando `NaN`→0. O alerta de estouro do teto legal (R$ 130.984,20 / R$ 65.492,11) nunca disparava. Corrigido reaproveitando `parseValor()`, já correto
- **Exclusão de fornecedor não verificava propostas não-vencedoras** — só checava o fornecedor vencedor (`p.fornecedor.id`); um fornecedor com proposta em análise podia ser excluído sem aviso. Agora compara por CNPJ também dentro de `_propostas`

### Corrigido — Robustez do servidor
- **`handle_error` nunca era chamado** — estava definido na classe errada (é método de `socketserver.BaseServer`, não do request handler). Qualquer exceção não tratada em `do_GET`/`POST`/`PUT`/`DELETE` derrubava a conexão sem log nem resposta ao cliente, mascarando outros bugs. Novo `_safe_dispatch()` envolve os 4 handlers: loga em `sgcd_errors.log` e devolve um 500 JSON limpo
- **Thread de watchdog podia morrer para sempre** — se `auto_backup_keep` fosse salvo com valor não-numérico (só possível via chamada direta à API), o `int()` quebrava dentro da thread sem `try/except`, matando limpeza de sessões/lixeira/alertas até reiniciar o servidor. Corrigido na raiz (`_get_backup_cfg`) e com proteção adicional no loop do watchdog

Cobertura de teste ampliada: `tests/test_server.py` ganhou 4 testes novos (restore malformado, conflito de edição concorrente ×2, exceção não tratada); `tests/e2e/` ganhou um teste dedicado de XSS rodando payload real em Chromium.

---

## [2.24.1] — 2026-07-09

### Adicionado
- **Testes E2E ampliados** (`tests/e2e/smoke.spec.js`) — dois novos cenários, além do já existente (login/criar processo/gerar documento):
  - **Assinatura Simples de documento**: clica em "Assinar Documento" no popup do documento gerado, escolhe o nível Simples, confirma que o carimbo de assinatura aparece no documento e que a seção "Assinaturas" do processo é atualizada
  - **Sincronização de backup entre agentes**: injeta um backup JSON sintético (representando "outro agente", sem precisar de um segundo servidor real) com um processo novo, confirma o diálogo de mesclagem e verifica que o processo aparece no dashboard

Ambos os testes reutilizam o mesmo servidor/banco temporário da suíte já existente. Validado com 2 execuções consecutivas sem instabilidade.

---

## [2.24.0] — 2026-07-09

### Adicionado
- **Exclusão de fornecedor com verificação de vínculo** — nova opção "Excluir Fornecedor" na tela de edição (mesmo padrão já usado no SGDP/SGCA). Antes de excluir, verifica se o fornecedor está vinculado a algum processo (`p.fornecedor.id`); se estiver, bloqueia com aviso do número de processos vinculados, em vez de permitir uma exclusão que quebraria a referência. Sem vínculo, segue o mesmo padrão de soft-delete já usado em processos: vai para a Lixeira por 30 dias, com restauração ou exclusão definitiva
- **Lixeira agora lista fornecedores excluídos** — antes só mostrava processos, mesmo o backend já suportando lixeira/restauração para fornecedores desde antes. `restoreFornecedor()`/`purgeFornecedor()` seguem o mesmo padrão de `restoreProcess()`/`purgeProcess()`
- Novos tipos de evento de auditoria: `FORNECEDOR_EXCLUIDO`, `FORNECEDOR_RESTAURADO`, `FORNECEDOR_EXPURGADO`
- Cobertura de teste (`tests/test_server.py`): ciclo completo excluir → lixeira → restaurar → excluir definitivamente para fornecedores

### Removido
- `excluirFornecedor(id)` — função morta (nunca chamada por nenhum botão) que fazia `DELETE` direto sem nenhuma verificação de vínculo nem confirmação; substituída pela implementação segura acima

Validado ao vivo: fornecedor sem vínculo é excluído/restaurado/purgado corretamente; fornecedor vinculado a um processo é bloqueado com a mensagem correta.

---

## [2.23.0] — 2026-07-09

### Adicionado
- **Exportar CSV em Fornecedores e Auditoria** — as duas telas ganharam o mesmo botão "Exportar CSV" que já existia em Processos (`exportarFornecedoresCSV()`, `exportarAuditoriaCSV()`), reaproveitando a mesma lógica de escape/BOM e respeitando a busca/filtros já ativos na tela. Validado ao vivo, inclusive com nome de fornecedor contendo aspas e vírgula (escape correto)
- **`Instalar Assinatura ICP-Brasil.bat`** — script opcional que habilita o pip (via `get-pip.py`, agora incluído no projeto) e instala o `pyhanko` quando o servidor usa o Python embarcável (`Iniciar SGCD.bat`), que não vem com pip nem com `ensurepip`. `Iniciar SGCD.bat` agora também habilita o módulo `site` na extração do Python embarcável (pré-requisito para qualquer pacote instalado nele funcionar depois)

Validado de ponta a ponta numa cópia isolada do Python embarcável (não a instalação real do sistema): extração → habilitação de `site` → bootstrap do pip → `pip install pyhanko` → import real do `pyhanko`, tudo funcionando. Fica pendente apenas a validação no servidor Windows Server real da prefeitura (acesso à máquina não disponível nesta sessão).

---

## [2.22.0] — 2026-07-09

### Adicionado
- **Suíte de testes E2E** (`tests/e2e/`, Playwright) — sobe o servidor real e dirige um Chromium de verdade pelo fluxo completo: login → troca de senha obrigatória (banco novo a cada run) → criar processo → expandir etapa → gerar documento (Autorização de Abertura) → confirmar conteúdo do popup gerado. Roda contra banco/uploads/backups temporários, nunca o `sgcd.db` real. Instruções no README (`npm run test:e2e`)

### Corrigido
- **`server.py` não tinha como isolar dados de teste sem rodar a partir de outra pasta** — `DB_PATH`/`UPLOADS_DIR`/`BACKUP_DIR` agora respeitam a variável de ambiente opcional `SGCD_DATA_DIR` (usada pelos testes E2E); sem ela, comportamento idêntico ao de sempre. Porta também configurável via `SGCD_PORT` (default 3000, inalterado)

---

## [2.21.0] — 2026-07-09

### Adicionado
- **Troca de senha obrigatória no primeiro acesso** — o admin padrão (criado com `admin/admin123`) e qualquer usuário futuro marcado dessa forma agora são obrigados a definir uma nova senha antes de acessar o sistema, em vez de depender só do aviso impresso no terminal. Nova coluna `must_change_password` em `usuarios` (migração automática, instalações existentes não são afetadas — só novos usuários nascem com a flag ligada); nova tela bloqueante no frontend reaproveitando o endpoint de troca de senha já existente (`PUT /api/usuarios/:id`)
- Cobertura de teste (`tests/test_server.py`): flag nasce ligada no admin padrão, aparece no login, e é limpa automaticamente ao trocar a senha

---

## [2.20.4] — 2026-07-09

### Corrigido
- **Clicar fora de um modal fechava a janela e descartava os dados digitados** — todos os overlays (Fornecedor, Usuário, Certidão, Busca Global, Templates, CSV, E-mail, Vínculo, Fornecedor-picker, Conformidade) fechavam ao clicar no fundo escuro, mesmo com o formulário preenchido. Removido o fechamento por clique fora; agora só fecham pelo botão Cancelar/✕ ou pela tecla Esc

## [2.20.3] — 2026-07-09

### Corrigido
- **Backup/restore perdia as assinaturas digitais** — `_build_backup_payload`/`_restore_backup` não incluíam a tabela `signatures`; um backup exportado e depois restaurado apagava todas as assinaturas registradas nos processos. Corrigido para exportar e reimportar a tabela, igual ao SGCA

## [2.20.2] — 2026-07-09

### Alterado
- **Usuário admin padrão** — removido o cargo pré-preenchido ("Agente de Contratação") na criação do usuário admin de instalações novas; agora fica em branco por padrão, igual ao SGDP/SGCA. Instalações já existentes não são alteradas

## [2.20.1] — 2026-07-09

### Alterado
- **Modal de "Editar/Novo Usuário" reescrito** — substitui o overlay construído dinamicamente via JS por um modal estático (`.overlay`/`.modal-header`/`.info-field`/`.modal-footer`), o mesmo padrão já usado nos modais de Fornecedor, Contrato e Assinatura. Sem mudança de campos ou comportamento — só a estrutura interna, para consistência visual com o resto do sistema

## [2.20.0] — 2026-07-09

### Adicionado
- **CPF e E-mail no cadastro de usuário** — novos campos no modal Editar/Novo Usuário, posicionados junto do Nome (separados de Cargo/Matrícula), para uso futuro (ex. notificações, assinatura). Sincronizado com SGDP (já tinha E-mail) e SGCA

## [2.19.0] — 2026-07-08

### Adicionado
- **Etiquetas (tags) em processos** — tags livres por processo com autocomplete, exibidas como marcadores no card e incluídas na busca; sincronizado do modelo relacional já usado no SGDP (`tags` + `process_tags`)

### Corrigido
- **Contraste no tema escuro** — `#notif-panel` usava um seletor `[data-theme="dark"]` que nunca era ativado (a troca de tema usa a classe `body.dark`, não o atributo `data-theme`); `.table-wrap` não tinha nenhuma cobertura no tema escuro. Mesmo bug clonado no SGDP e já corrigido lá; achado ao comparar os 3 sistemas

## [2.18.4] — 2026-07-07

### Corrigido
- **Manual Operacional** — capa/sumário usavam cores roxas obsoletas (`#2C001E`/`#5E2750`), resíduo de antes da unificação de tokens de marca; atualizadas para azul-marinho (`#1a3a6b`/`#2a5298`), igual ao app e ao SGCA. Removida regra CSS morta `.toc-num` (nunca usada no corpo do documento)

## [2.18.3] — 2026-07-06

### Adicionado
- **Rate limit de login** — bloqueia com HTTP 429 após 5 tentativas falhas em 5 minutos (janela deslizante, por usuário); login correto limpa o contador. Gap encontrado na auditoria de servidor: nenhum dos 3 sistemas tinha proteção contra força bruta

## [2.18.2] — 2026-07-06

### Corrigido
- **Mapa de rótulos de auditoria incompleto** — faltavam `PNCP_EXPORT` e `SYNC_BACKUP`
- **Dropdown de filtro "Tipo de evento" desincronizado** — lista fixa no HTML não incluía `DOCUMENTO_ASSINADO`, `PROCESSO_RESTAURADO`, `PROCESSO_EXPURGADO` (apareciam na tabela mas não podiam ser filtrados); trocado para gerar as opções dinamicamente a partir do mapa de rótulos

### Alterado
- Coluna "Tipo" renomeada para "Ação" na Trilha de Auditoria, alinhando com o SGDP

## [2.18.1] — 2026-07-06

### Corrigido
- **Item de menu ficava destacado junto com outros ao navegar** — `setNavActive()` procurava elementos `.nav-btn` para remover a classe `active`, mas os botões da sidebar usam `.nav-item`; o seletor nunca encontrava nada, então o item anterior nunca era desmarcado. SGCA já usava o seletor correto

### Alterado
- **Trilha de Auditoria** — timeline agrupada por dia (buscava até 2000 registros de uma vez, filtro 100% no cliente) substituída por tabela com filtros server-side (busca, tipo, período) e paginação via servidor, igual ao SGDP
  - Menu "Auditoria" agora só aparece para administradores
  - `/api/audit` ganhou filtros (q/tipo/de/ate), mas continua sem restrição de admin — usado também pelo histórico de alterações por campo, aberto a qualquer usuário logado

## [2.18.0] — 2026-07-06

### Alterado — padronização arquitetural com o SGDP (mudança grande)
- **Design tokens CSS** — `--aubergine`/`--aubergine-mid` renomeados para `--accent`/`--accent-light`; completada a escala de cinza (`--gray-600`/`--gray-800`, usados em 19 lugares mas nunca definidos) e adicionadas `--green`/`--red`/`--yellow`/`--shadow-lg`
- **Sidebar** — `<nav id="sidebar">` virou `<aside id="sidebar">` com `<nav class="sidebar-nav">` interno (landmark semântico correto); busca global (Ctrl+K) preservada
- **Mensagens de erro** — "Acesso negado" padronizado para "Acesso restrito" nos 403 de admin
- **Tabela e rota de usuários** — `users` → `usuarios`, `/api/users` → `/api/usuarios`; colunas `cargo`/`matricula` preservadas; migração automática e silenciosa na inicialização, sem perda de dado
- **Camada de acesso a dados** — removida a indireção `dbGetAll/dbGet/dbPut/dbDelete/dbGetByIndex/dbGetByIndexPrefix`; dividida em 14 funções nomeadas por entidade (processos, fornecedores, auditoria, arquivos) chamando `API.get/put/post/del` direto, sem duplicar a lógica não-trivial de cada uma (ex: upload multipart de arquivos)
- **Busca server-side (Fase 7)** — avaliada e **não aplicada** ao Dashboard: a tela combina 6 filtros (texto, status, unidade, datas, valores, ordenação) sobre o array de processos em memória, que também alimenta análise de fracionamento, badges e notificações — mover para o servidor exigiria uma reestruturação bem maior, fora do escopo desta rodada

### Corrigido
- **Seleção de modo travava em ambiente não-interativo** — `_selecionar_modo()` esperava input do teclado mesmo quando stdin não é um terminal (scripts, automação); SGDP e SGCA já tinham o fallback `if not sys.stdin.isatty(): op = '2'`; SGCD era o único sem essa proteção
- **`API_BASE` com porta fixa** — tinha `http://localhost:3000` fixo no código; quebrava se o servidor rodasse em outra porta. Como o SGCD usa `API_BASE` também para montar o texto do QR Code de verificação de assinatura (lido por celular) e alguns links de download, não deu para usar caminhos relativos como no SGCA — corrigido trocando para `window.location.origin`, absoluto e correto em qualquer porta
- **Histórico de edições por campo sempre vazio** — `abrirFieldHist()` chamava uma função de busca por índice que só tratava arquivos, não auditoria; o painel "Histórico de edições por campo" mostrava "Nenhuma alteração registrada" mesmo quando havia. Corrigido buscando todos os eventos de auditoria e filtrando por processo no cliente

Todas as mudanças foram testadas em ambiente isolado (cópia do projeto, banco de teste, porta separada) antes de aplicar — o banco de produção não foi tocado em nenhuma etapa. 14/14 testes automatizados passando.

## [2.17.5] — 2026-07-04

### Corrigido
- **Descrições de arquitetura desatualizadas no manual** — seções sobre anexar documentos, backup/restauração, auto-backup, templates de processo e controle de acesso ainda descreviam a arquitetura antiga (dados/senha no `localStorage`/IndexedDB do navegador), desatualizada desde a migração para servidor Python + SQLite. Textos corrigidos para refletir `sgcd.db`, pasta `uploads/` e login com sessão de servidor; Seção 22 renomeada para "Login e Controle de Acesso".

---

## [2.17.4] — 2026-07-04

### Corrigido
- **Manual desatualizado** — o corpo do `MANUAL.html` não descrevia Notificações por E-mail (SMTP/resumo diário), Assinatura Eletrônica de Documentos, Vinculação entre Processos, Agenda de Vencimentos, Lixeira e Exportação PNCP, embora já lançados. Seções 24–29 adicionadas; seções 21–23 (que existiam no corpo mas não apareciam no sumário) corrigidas; Histórico de Versões passa a ser a Seção 30 e aparece no sumário.
- README: adicionada seção "Contribuição" apontando para `CONTRIBUTING.md`

---

## [2.17.3] — 2026-07-04

### Corrigido
- **Brasão da sidebar não refletia o customizado** — a `<img>` da sidebar sempre exibia o arquivo estático `brasao.png`, mesmo com um brasão customizado já sincronizado com o servidor (usado nos relatórios PDF e na prévia de Configurações). Agora a sidebar é dinâmica e atualizada a partir do brasão sincronizado, com atualização imediata ao fazer upload/remover, sem esperar novo login.
- Adicionado `GET /api/settings/brasao` (o `PUT` já existia) — mesma rota usada pelo SGDP, que agora compartilha a mesma lógica de armazenamento server-side.

---

## [2.17.2] — 2026-07-04

### Adicionado
- **Tela de encerramento** — ao clicar em "Fechar sistema", a página exibe uma tela de confirmação visual ("Sistema encerrado") antes de tentar fechar a aba, cobrindo o caso em que `window.close()` é bloqueado pelo navegador (aba não aberta via script). Paridade com o SGDP.

---

## [2.17.1] — 2026-07-04

### Corrigido
- **Vazamento de conexões SQLite** — `with get_db() as conn:` (63 pontos em `server.py`) gerencia commit/rollback da transação, mas o `__exit__` padrão de `sqlite3.Connection` não fecha a conexão. Cada requisição deixava uma conexão aberta até o garbage collector limpar. Corrigido no ponto único de origem: `get_db()` agora usa uma subclasse `_ConnAutoClose` cujo `__exit__` fecha a conexão depois do commit/rollback — nenhum dos 63 call sites precisou mudar. Confirmado sem nenhum `ResourceWarning` mesmo promovendo-os a erro fatal (`python -W error::ResourceWarning`) rodando a suíte completa de testes

---

## [2.17.0] — 2026-07-04

### Adicionado
- **Suíte de testes automatizados do backend** (`tests/test_server.py`), usando só `unittest` da stdlib — mantém o zero-dependência do sistema. Sobe o servidor real contra banco/uploads/backups em diretório temporário e testa via HTTP real: login (sucesso/falha), acesso negado sem token/token inválido, CRUD de processos (criar, listar, atualizar, lixeira, restaurar), CRUD de fornecedores, auditoria (registro + bulk restrito a admin), configurações, gestão de usuários (usuário comum não pode criar outro usuário), e exportação de backup
- Instruções de execução (`python -m unittest discover -s tests -v`) documentadas no README, seção Desenvolvimento

### Corrigido
- **`server.py` executava o menu interativo e subia o servidor no nível do módulo** — um simples `import server` (necessário para os testes) disparava o prompt de terminal e travava. Todo esse bloco foi movido para dentro de `if __name__ == '__main__':`; `python server.py` continua idêntico, mas o módulo agora pode ser importado com segurança

### Observado (não corrigido nesta versão)
- Todo `with get_db() as conn:` no `server.py` só gerencia a transação (commit/rollback) — não fecha a conexão SQLite, pegadinha conhecida do módulo `sqlite3` (o `with` de uma `Connection` não é um context manager de fechamento). É um vazamento de recursos pré-existente em dezenas de pontos do arquivo; ficou visível nos `ResourceWarning` durante os testes por causa do volume de requisições em sequência rápida. Correção ampla o suficiente para tratar à parte, fora do escopo desta suíte de testes.

---

## [2.16.3] — 2026-07-04

### Removido
- **Web Worker de serialização morto** (`_WORKER_CODE`, `_getSerializeWorker()`, `_workerRun()`, `_bufToBase64()`) — servia para serializar backups fora da thread principal; ficou órfão desde que o backup passou a ser feito via API do servidor. Zero pontos de chamada
- **`dbClearStore()`, `_renderFornView()`, `_renderFornEdit()`** — funções/wrappers sem nenhuma chamada, resquícios de refatorações anteriores
- **`dbGetByIndexRange()`** — stub que sempre retornava `[]`. Os 2 pontos de chamada (filtro de auditoria por data) sempre caíam no fallback sem filtro nenhum, então **o filtro de período no relatório de auditoria nunca funcionava de fato**; corrigido para filtrar de verdade sobre a lista completa
- **Duplicação entre `_export_backup()` e `_do_json_backup()`** (server.py) — as duas montavam o mesmo payload de backup quase byte a byte; extraído para `_build_backup_payload()` compartilhado

Achados de uma varredura dedicada de over-engineering/código morto no sistema. Redução líquida de ~91 linhas em SGCD.html.

---

## [2.16.2] — 2026-07-04

### Melhorado
- **`_DOC_CSS` aplicado a todos os geradores de documento** — a constante compartilhada de CSS base, antes usada apenas em 2 funções, agora substitui o bloco duplicado em todas as 15 funções `gerar*`. Redução de ~100 linhas de CSS repetido. Cada função mantém apenas seu CSS específico adicional após `${_DOC_CSS}`

---

## [2.16.1] — 2026-07-04

### Corrigido
- **`eslint.config.js` mantinha à mão uma lista de ~35 globais de navegador** — achado no `/ponytail-review` desta sessão. Substituído por `globals.browser` do pacote `globals` (já dependência transitiva do ESLint, promovida a dependência direta), evitando manter essa lista manualmente e cobrindo mais globais de navegador do que a lista anterior
- **CSS duplicado entre `gerarEnquadramentoLegal()` e `gerarJustificativaEscolha()`** — as duas funções repetiam o mesmo bloco de ~25 linhas de estilo do documento. Extraído para uma constante `_DOC_CSS` compartilhada. Escopo limitado a essas duas funções (o mesmo bloco também se repete em outras ~13 funções `gerar*` pré-existentes no arquivo — refatorar todas seria uma mudança maior e mais arriscada, fora do escopo desta correção pontual)

Validado: lint passa, e o HTML gerado pelas duas funções continua com o CSS idêntico ao de antes (testado ao vivo capturando o HTML de ambas e comparando byte a byte o conteúdo do `<style>`).

---

## [2.16.0] — 2026-07-04

### Adicionado
- **Python portátil embutido como fallback no `Iniciar SGCD.bat`** — usuário relatou que, ao tentar instalar o SGCD no servidor da prefeitura (Windows Server), o instalador do Python não rodava (típico de bloqueio por AppLocker/política de grupo, antivírus corporativo, ou arquivo "bloqueado" pelo Windows por vir da internet). O `Iniciar SGCD.bat` agora detecta a ausência do Python no PATH e, nesse caso, extrai automaticamente uma distribuição Python embarcável (portátil, sem instalador, incluída no projeto como `python-3.12.9-embed-amd64.zip`) para `C:\Python312-embed\` — não exige privilégio de administrador nem executar nenhum instalador, contornando os bloqueios comuns em servidores corporativos travados
- Em execuções seguintes, o `.bat` detecta o Python já extraído em `C:\Python312-embed\` e o usa diretamente, sem repetir a extração

Testado: extração real via PowerShell (`System.IO.Compression.ZipFile`, compatível com versões antigas do PowerShell — não depende do `Expand-Archive`, que exige PowerShell 5+), confirmado que todos os módulos usados pelo `server.py` (incluindo `sqlite3`, `ssl`, `http.server`) funcionam nessa distribuição embarcável, e que o servidor sobe e responde normalmente rodando com esse Python. Validado também que o `.bat` detecta e reutiliza corretamente uma instalação já extraída quando `python` não está no PATH do sistema. No caminho, encontrado e corrigido um bug real na primeira versão do script: a continuação de linha `^` usada para quebrar o comando PowerShell em várias linhas, quando colocada *dentro* de uma string entre aspas, fica literal em vez de ser removida pelo `cmd.exe` — quebrava o comando com `'^' não é reconhecido como cmdlet`. Corrigido reescrevendo o comando inteiro em uma única linha.

---

## [2.15.2] — 2026-07-03

### Corrigido
- **Coluna "Objeto" cortada no Relatório Executivo** — `gerarRelatorioExecutivo()` truncava o texto do objeto em 55 (lista de processos) e 60 caracteres (processos parados) com `.slice()`, sem reticências, cortando no meio da palavra mesmo a tabela tendo espaço de sobra para quebrar linha. Reportado pelo usuário com captura de tela. Removida a truncagem — mesmo padrão já usado no Relatório Geral, que sempre mostrou o objeto completo

---

## [2.15.1] — 2026-07-03

### Adicionado
- **Favicon na aba do navegador** — `SGCD.html` não declarava nenhum `<link rel="icon">`, então a barra superior do navegador ficava sem ícone. Adicionado apontando para `sgcd.ico` (já existente no projeto, usado no atalho da área de trabalho). Testado: servidor já serve `.ico` estático corretamente (`Content-Type: image/x-icon`)

---

## [2.15.0] — 2026-07-03

### Adicionado
- **Sincronização (merge) de backup entre agentes** — usuário pediu uma forma de exportar o backup de uma máquina e mesclar (não substituir) na de outro agente, somando o que é novo e mantendo o que já existe. A função já existia (`sincronizarBackup()`), mas nunca tinha sido ligada a nenhum botão — código morto, nunca testado, com bugs reais. Corrigido e ligado à interface (Configurações → Dados → novo cartão "Sincronizar com outro agente"):
  - Corrigido merge de arquivos: usava `f.processId` (deveria ser `f.process_id`, nome da coluna exportada) e uma checagem de decodificação (`_enc`/`data`) que nunca correspondia ao formato real exportado (`data_b64`) — nenhum arquivo era mesclado, silenciosamente
  - Adicionada deduplicação de arquivos: antes de reenviar um arquivo, verifica se já existe no processo de destino (por nome+tamanho) — sem isso, cada sincronização repetida duplicaria os arquivos
  - Adicionada tela de revisão de conflitos: quando o mesmo processo/fornecedor existe nos dois lados com data de alteração diferente, mostra os dois lado a lado (objeto, valor, status, datas) com marcação por item — antes disso, o sistema aplicava "mais recente vence" silenciosamente, sem deixar o usuário escolher
  - Corrigida corrupção de autoria na auditoria: o merge enviava eventos do outro agente para `POST /api/audit`, que sempre grava o usuário logado como autor (correto para lançar eventos ao vivo, errado para importar histórico de outra máquina) — novo endpoint `POST /api/audit/bulk` (admin, com `_insert_audit_raw()` extraído de `_restore_backup()`) preserva o autor original
  - Adicionado backup de segurança automático antes de aplicar qualquer mesclagem (reaproveita `/api/backups/db/now`, já existente)
  - Adicionada detecção de números de processo duplicados (`num_proc`/`num_dl`) entre registros com `id` diferente após a mesclagem — cada máquina sugere numeração sequencial própria, então duas máquinas podem coincidentemente usar o mesmo número oficial para processos diferentes; o sistema avisa para renumeração manual (não bloqueia nem renumera sozinho)
  - Falhas parciais (ex.: um processo falha ao mesclar) agora são contadas e reportadas por categoria, em vez de abortar com uma mensagem genérica que escondia o que já tinha sido gravado

### Corrigido
- **Restauração completa via JSON (`_restore_backup()`) não criava backup de segurança antes de apagar tudo** — diferente da restauração via arquivo `.db`, que já fazia isso. Corrigido adicionando a mesma chamada de segurança

Validado em ambiente isolado simulando duas máquinas independentes (processos exclusivos, um conflito real de `updatedAt`, e uma colisão proposital de número de processo): registros novos mesclados automaticamente, conflito detectado corretamente, arquivo mesclado e não duplicado numa segunda sincronização, autoria de auditoria preservada, números duplicados detectados nos dois casos esperados.

---

## [2.14.0] — 2026-07-03

### Adicionado
- **`diagnostico.py` reescrito: diagnóstico e correção automática de rede** — usuário reportou que outras máquinas não conseguiam acessar o SGCD mesmo com o servidor no modo 2 e o diagnóstico antigo dizendo que estava tudo certo. Investigação encontrou falsos positivos conhecidos no diagnóstico anterior: ele só testava a própria máquina se conectando a si mesma, e a checagem de firewall era um `findstr "3000"` frouxo que não confirmava se a regra estava habilitada, no perfil de rede certo, nem em modo "allow". Reescrito para verificar de verdade:
  - **Perfil de rede** (Domínio/Privada/Pública) — Windows bloqueia entrada por padrão em rede "Pública"; corrige automaticamente para "Privada" mediante confirmação
  - **Regra de firewall completa** — checa habilitada + allow + TCP + porta 3000 + perfil, via `Get-NetFirewallRule`/`Get-NetFirewallPortFilter` (PowerShell, mais confiável que parsing de texto do `netsh`); remove regras antigas/quebradas e recria corretamente
  - **Antivírus de terceiros** — detecta produtos além do Windows Defender (que têm firewall próprio, fora do alcance deste script) e avisa
  - **Outros dispositivos na rede local** — varredura + tabela ARP; se nenhum outro dispositivo for encontrado, aponta isolamento de cliente (AP isolation) ou VLAN separada como causa provável — cenário comum em redes corporativas geridas por TI, que não pode ser corrigido por software nesta máquina
  - **IP via DHCP** — avisa que o endereço pode mudar e quebrar atalhos salvos em outras máquinas; sugere pedir reserva de IP fixo ao TI, já informando o MAC address
  - **Elevação automática** — se rodado sem privilégio de Administrador (necessário para corrigir firewall/perfil de rede), oferece reabrir elevado via UAC automaticamente
- Testado em ambiente isolado: todas as seções executam corretamente, incluindo a varredura de rede (29 dispositivos encontrados) e o auto-teste de conexão pelo IP local

---

## [2.13.5] — 2026-07-03

### Adicionado
- **Lint de desenvolvimento (`npm run lint`)** — script que extrai o JS de `SGCD.html` e roda ESLint com a regra `no-undef`, para pegar bugs de variável indefinida (como os corrigidos em `fSt`/`proc` nas versões anteriores) antes do commit. Não afeta o runtime do sistema — é uma ferramenta de desenvolvimento isolada (`package.json`, `eslint.config.js`, `scripts/lint.mjs`), o servidor e o cliente continuam zero-dependência

### Corrigido
- **Importação de fornecedores via CSV com consulta de CNPJ ativada quebrava silenciosamente ao final da importação** — `importarCsv()` chamava `parseCnpjData(d)`, função que nunca existiu no sistema (a consulta de CNPJ real usa `fetchCnpjData()`, com fallback ReceitaWS → BrasilAPI e normalização adequada dos campos). O `ReferenceError` correspondente não estava dentro do try/catch da requisição, então a exceção escapava e interrompia a função antes de recarregar a lista de fornecedores e exibir o toast de conclusão — a importação funcionava (os fornecedores eram salvos), mas a tela ficava travada em "Importando X de Y…" sem feedback final. Corrigido reaproveitando `fetchCnpjData()`, já usada e testada no cadastro manual de fornecedores. Encontrado pelo novo lint automatizado, não reportado por usuário
- **Chamada a `loadFornecedores()` (função inexistente) na mesma função** — código morto que nunca executava com sucesso; removido, já que `renderFornecedores()` (chamada logo em seguida) já recarrega os dados do banco

### Corrigido
- **Geração da Ata de Sessão gerava `Uncaught ReferenceError: proc is not defined` quando havia proposta vencedora registrada** — em `gerarAta()`, a linha que monta o rótulo "Vencedora — {critério}" referenciava `proc.criterio_selecao`, mas a variável do processo nessa função se chama `p` (resíduo de código copiado de outra função que usa `proc`). Como o rótulo é montado dentro de um objeto literal avaliado para toda linha da tabela de propostas — não só quando a situação é "vencedora" —, o erro ocorria sempre que havia ao menos uma proposta cadastrada. Reportado pelo usuário. Corrigido para `p.criterio_selecao`

---

## [2.13.3] — 2026-07-03

### Corrigido
- **Botão "Relatório" no Dashboard gerava erro `Uncaught ReferenceError: fSt is not defined`** — `gerarRelatorio()` usava as variáveis de filtro (`fSt`, `fUn`, `fDe`, `fAte`, `fVmin`, `fVmax`, `q`) sem nunca obtê-las de `_getDashFilters()` no escopo da função. Reportado pelo usuário ao clicar em "Relatório" no Dashboard. Corrigido obtendo os filtros no início da função

---

## [2.13.2] — 2026-07-03

### Corrigido
- **Janela de "Justificativa da Escolha do Fornecedor" abria em tamanho fixo pequeno (900x700), diferente do esperado** — removida a dimensão fixa de `window.open()`, passando a herdar o tamanho da janela do navegador, mesmo padrão já usado no gerador de "Processo Completo"

---

## [2.13.1] — 2026-07-03

### Adicionado
- **Geração de documento para a etapa "Justificativa da Escolha do Fornecedor"** — botão "📄 Gerar Justificativa da Escolha do Fornecedor" na Etapa 13, seguindo o mesmo padrão visual e de nomenclatura dos demais documentos do sistema (`gerarJustificativaEscolha()`). O documento traz processo, fornecedor escolhido, CNPJ, o texto da justificativa registrado na etapa e a base legal (Art. 72, VI da Lei 14.133/2021). MANUAL.html atualizado (Seção 6 e tabela de "Documentos Gerados" na Seção 9)

---

## [2.13.0] — 2026-07-03

### Adicionado
- **Nova etapa de checklist: "Justificativa da Escolha do Fornecedor"** — sugestão do Controle Interno, com base no **Art. 72, VI da Lei 14.133/2021**, que exige que o processo de contratação direta seja instruído com a "razão da escolha do contratado", item distinto da habilitação (regularidade fiscal/jurídica) e da justificativa de preço (pesquisa de preços). Inserida entre **Habilitação do Fornecedor** e **Adjudicação**, seguindo a ordem do Art. 72 (V-habilitação, VI-razão da escolha) e o fluxo lógico do processo. O checklist passa de 17 para **18 etapas**
- Migração automática para processos já existentes: ao abrir um processo antigo (17 etapas), a nova etapa é inserida em branco na posição correta, mesmo padrão já usado nas inserções anteriores (v2.3.0 — Dotação Orçamentária, v2.8.0 — Parecer do Controle Interno)

### Corrigido
- **Cálculo automático da data mínima de encerramento do Aviso de Dispensa estava morto desde o v2.8.0** — o código verificava `if (i === 7 && f === 'data_publicacao')` para acionar o cálculo automático dos 3 dias úteis mínimos (Art. 75, §3º), mas o índice real da etapa "Aviso de Dispensa" havia mudado de 7 para 9 quando a etapa "Parecer do Controle Interno" foi inserida (v2.8.0) — a condição nunca mais era verdadeira. Corrigido substituindo o índice fixo por busca dinâmica (`STEPS.findIndex(s => s.avisoDispensa)`), imune a futuras inserções de etapas
- **Classificação de fase no Kanban (`processoFase`) desalinhada desde a mesma mudança do v2.8.0** — os limiares fixos (`i<=7` Instrução, `i===8` Publicado etc.) também dependiam da posição antiga das etapas e ficaram incorretos após o deslocamento de índices. Reescrito para usar os mesmos flags de identificação das etapas (`avisoDispensa`, `certidoes`, `adjudicacao`) em vez de números fixos
- **`renderSignatures(id)` referenciava variável inexistente** — em `renderDetail()`, gerava erro `id is not defined` (visível como toast) toda vez que um processo era aberto, embora não impedisse o restante da tela de carregar. Corrigido para `renderSignatures(p.id)`
- **MANUAL.html estava sem a descrição da etapa "Indicação de Dotação Orçamentária"** desde que ela foi adicionada ao sistema (v2.3.0) — a caixa de descrição nunca existia na Seção 6, e toda a numeração de etapas a partir dali (Enquadramento Legal em diante) estava um número atrasada em relação ao app real. Adicionada a caixa faltante e renumeradas as 18 etapas e todas as referências cruzadas ("Etapa N") no manual
- **Linha corrompida na tabela de "Documentos Gerados"** (Seção 9) — resíduo de uma edição malsucedida anterior deixou o texto `Botão "📄 $110)` no lugar da descrição do botão "Despacho de Recusa/Desclassificação". Corrigido

---

## [2.12.3] — 2026-07-03

### Corrigido
- **Sincronização de Organização/SMTP/brasão abortava silenciosamente com `localStorage` corrompido** — testando o acesso via IP de rede com um navegador real (Chrome), encontrei um valor corrompido em `localStorage['sgcd-user']` (literalmente a string `"[object Object]"`, resíduo de alguma versão anterior do sistema). O `JSON.parse` sem proteção nessa leitura lançava exceção e abortava **toda** a sincronização em `_onLoginSuccess()` — Organização, SMTP e brasão ficavam em branco mesmo com o servidor respondendo corretamente (confirmado via console: `GET /api/settings` retornava 200 com 25 chaves, mas o processamento local quebrava logo em seguida)
- Corrigido com parse defensivo (try/catch, cai para `{}` em caso de corrupção) — mesmo padrão já usado em `getUser()`. Testado de ponta a ponta com navegador real: antes da correção, campos em branco; depois, todos os campos de Organização e SMTP carregando corretamente

---

## [2.12.2] — 2026-07-02

### Corrigido
- **Link do gov.br corrigido e confirmado** — o catálogo de serviços gov.br (v2.12.1) retornou "página não existe". Com base na URL de redirecionamento do SSO observada pelo usuário (`sso.acesso.gov.br/login?client_id=assinador.iti.br...`), o endereço correto é `assinador.iti.br` — testado pelo usuário e confirmado funcionando (login gov.br já autenticado, tela "Assinar arquivo" com upload)

---

## [2.12.1] — 2026-07-02

### Corrigido
- **Modal de assinatura escondido atrás da janela do documento** — o modal era inserido na janela principal do SGCD, mas o documento gerado abre maximizado, cobrindo a janela principal e obrigando a redimensionar manualmente para ver o modal. Corrigido: o modal agora vive dentro da própria janela do documento (com estilos próprios, já que essa janela não tem a folha de estilo principal do app), sempre visível assim que o botão "Assinar Documento" é clicado
- **Link do gov.br não abria** — `assinador.iti.gov.br` retornava erro. Substituído pelo catálogo oficial de serviços `gov.br/pt-br/servicos/assinar-documentos-digitalmente`, que aponta para a ferramenta correta mesmo que o endereço interno da ferramenta mude no futuro

---

## [2.12.0] — 2026-07-02

### Adicionado — Assinatura Eletrônica de Documentos (3 módulos)
- Novo botão **"Assinar Documento"** em todos os ~15 documentos gerados pelo sistema, abrindo um modal para escolher o módulo de assinatura:
  1. **Assinatura Simples** — hash SHA-256 real do conteúdo do documento + identidade do usuário logado, registrado no servidor. Rápido, sem upload. **Não substitui** assinatura física em atos que exigem nível avançado/qualificado (Lei 14.063/2020) — serve como controle interno / trilha de auditoria reforçada.
  2. **gov.br (nível avançado)** — link direto para o portal público `assinador.iti.gov.br` (mesmo padrão dos links de certidão já usados na etapa de Habilitação); usuário assina lá com login gov.br e reenvia o PDF assinado, que fica anexado ao processo.
  3. **Certificado ICP-Brasil A1 — .pfx (nível qualificado)** — assinatura digital real do PDF no servidor, usando a nova dependência `pyHanko` (`requirements.txt`, opcional — só necessária para este módulo). A senha do certificado nunca é armazenada, usada uma única vez em memória durante a assinatura.
- **Nomenclatura padronizada dos PDFs** — todos os documentos gerados agora sugerem o nome `PA {num_proc} DL {num_dl} - {TIPO DO DOCUMENTO}` ao salvar como PDF (via tag `<title>`, que o Chrome/Edge usam como nome sugerido), no mesmo espírito dos nomes de backup já existentes
- Nova seção **"Assinaturas"** na tela de detalhe do processo, listando quem assinou, quando e por qual módulo, com link de download do PDF assinado quando houver
- Nova tabela `signatures` no banco (migração automática e segura para banco já existente)
- A página de verificação `/verificar/<código>` agora consulta a tabela `signatures` de verdade, em vez de recalcular um hash fraco de 32 bits no navegador — corrige também um bug pré-existente onde a URL de consulta estava fixa em `http://localhost:3000`, o que nunca funcionava para quem acessava via IP de rede

### Corrigido
- **Bug pré-existente de travamento em uploads via multipart** — `do_POST` sempre lia o corpo inteiro da requisição antes de despachar a rota, e o handler de upload de arquivos (`_upload_file_direct`, usado por todo anexo de processo) tentava ler o corpo *de novo*, travando a conexão sob certas condições (confirmado com `curl -F`, resultando em `ConnectionResetError`). Corrigido evitando a leitura antecipada para requisições multipart — o handler correspondente agora é o único a consumir o corpo

### Validado com testes reais (não apenas leitura de código)
- Certificado ICP-Brasil de teste (auto-assinado) e PDF de teste gerados especificamente para validar a assinatura — PDF resultante confirmado com campo `Signature1` do tipo `/Sig` real
- Módulo 1 (Simples): criação e verificação por código funcionando via API
- Módulo 2 (gov.br): upload de PDF via multipart funcionando, arquivo anexado ao processo
- Módulo 3 (ICP-Brasil): assinatura real via `pyHanko`, PDF assinado baixado e confirmado válido; senha incorreta tratada com erro claro, sem travar o servidor
- Migração de schema testada contra cópia do banco de produção, sem perda de dados

---

## [2.11.2] — 2026-07-02

### Adicionado
- **Clique na notificação navega até o item** — clicar num alerta em Notificações agora leva direto para o processo (prazo, vencido, parado, vigência) ou para a aba de certidões do fornecedor (certidão vencendo), em vez de só fechar o painel

### Corrigido
- **Alerta de "vigência contratual vencendo" nunca disparava** — `_buildNotificacoes()` lia `vigencia_final` da etapa "Homologação" (índice 13, que não tem esse campo) em vez de "Instrumento Contratual" (índice 15). Mesma classe de bug já corrigida nos geradores de documento (v2.10.0), presente também aqui

---

## [2.11.1] — 2026-07-02

### Adicionado
- **Alertas por e-mail automáticos** — antes, os alertas de prazo e processos parados só existiam dentro do navegador (não eram vistos se ninguém abrisse o sistema naquele dia). Agora, com o SMTP configurado (Configurações → Comunicação), o servidor envia sozinho, uma vez por dia, um resumo por e-mail com prazos vencendo/vencidos e processos sem atualização há 15+ dias — sem depender de ninguém estar logado
- Roda na mesma thread de manutenção que já existia (expira sessões, esvazia lixeira antiga); só dispara envio real quando há algo a reportar, e nunca reenvia no mesmo dia
- Extraída a lógica de envio de e-mail (`_send_email_raw`) para reuso entre o teste manual de SMTP e o novo job automático, eliminando duplicação

Testado com servidor real: sem SMTP configurado, não dispara; com SMTP configurado (mesmo inválido), detecta corretamente prazo vencido e processo parado, tenta enviar, registra falha sem derrubar o servidor, e marca o dia como já processado para não repetir a cada 5s.

---

## [2.11.0] — 2026-07-02

### Adicionado
- **Lixeira** — excluir um processo agora move para uma lixeira (nova aba "Lixeira" em Administração) em vez de apagar direto. Fica recuperável por 30 dias, incluindo os arquivos anexados; depois disso é expurgado automaticamente. Restauração com um clique
- Exclusão permanente ("Excluir definitivamente") continua existindo, restrita a admin, com a mesma confirmação em duas etapas (digitar o número do processo) que a exclusão simples tinha antes
- Nova coluna `deleted_at` em `processes` e `fornecedores` (migração automática e segura para bancos já existentes)
- Novos endpoints: `GET /api/processes?trash=1` (lista a lixeira), `PUT /api/processes/<id>/restore`, `DELETE /api/processes/<id>?purge=1` (expurgo definitivo, admin-only) — mesmo padrão para fornecedores
- Expurgo automático diário de itens com mais de 30 dias na lixeira (thread de manutenção já existente)

### Corrigido
- Excluir um processo apagava os arquivos anexados imediatamente, mesmo antes desta versão — o que já tornava a "lixeira" inútil para recuperar documentos. Corrigido: arquivos só são removidos de fato no expurgo definitivo, nunca na exclusão simples

Validado com testes reais: criar → excluir → listar lixeira → restaurar → excluir de novo → expurgar → confirmar remoção definitiva; bloqueio de expurgo para não-admin; migração de schema testada contra cópia do banco de produção sem perda de dados.

---

## [2.10.3] — 2026-07-01

### Corrigido
- **Botão "Encerrar sistema" enganoso em modo Servidor Contínuo** — o botão pedia confirmação "Deseja encerrar o sistema?" mas, nesse modo, `_check_shutdown()` nunca desliga o processo (por design — só faz backup). Resultado: o usuário confirmava o encerramento e nada acontecia além de deslogar, sem nenhum aviso. Agora o botão fica oculto quando o servidor está em modo Servidor Contínuo (novo campo `modo_servidor` em `GET /health`), já que nesse modo o encerramento só deve acontecer por quem tem acesso físico ao console (Ctrl+C)
- Removido `fetch('/shutdown')` em `fecharSistema()` — rota inexistente no servidor, sempre retornava 404 silenciosamente (código morto desde sempre; o encerramento real já acontecia via `_check_shutdown()` disparado pelo logout)

---

## [2.10.2] — 2026-07-01

### Corrigido
- **Ata de Sessão sem fallback no Enquadramento Legal** — diferente da Justificativa de Enquadramento Legal e do Aviso de Dispensa (que já caem de volta na hipótese legal selecionada quando o campo livre "Fundamento legal específico" está em branco), a Ata mostrava só sublinhados nesse caso. Corrigido para usar o mesmo padrão

### Observação
- O texto "Decreto nº 11.317/2022" que aparecia numa Ata gerada **não é um bug de código** — é texto digitado manualmente no campo "Fundamento legal específico" daquele processo específico, antes do decreto ser atualizado. Para corrigir processos já existentes: abra o processo → etapa Enquadramento Legal → apague ou atualize o campo "Fundamento legal específico". Novos processos usam automaticamente o decreto configurado em Configurações → Organização

---

## [2.10.1] — 2026-07-01

### Corrigido
- **Grafia "Formalização da Demanda" → "Formalização de Demanda"** — nome oficial correto do DFD (Art. 12, §1º, Lei 14.133/2021), corrigido no nome da etapa, na Autorização, na Ata e no Manual
- **Ata de Sessão**: "referente à contratação de" → "referente à:", conforme padrão de redação solicitado
- **Decreto de atualização de limites desatualizado e incompleto** — a Justificativa de Enquadramento Legal citava "Decreto Federal nº 11.317/2022" (defasado; o vigente é o nº 12.807/2025) e só aparecia para o limite de bens/serviços (R$ 65.492,11), nunca para obras (R$ 130.984,20)

### Adicionado
- **Campo "Decreto de Atualização dos Limites de Dispensa"** em Configurações → Organização — como o decreto muda todo ano, esse texto agora é editável pelo usuário e usado nos documentos gerados, com o decreto vigente (nº 12.807/2025) como valor padrão caso o campo fique em branco. Sincroniza entre máquinas pelo mesmo endpoint já usado para os demais dados de Organização

---

## [2.10.0] — 2026-07-01

### Corrigido — 2 bugs ativos encontrados durante auditoria de índices hardcoded
- **Justificativa de Enquadramento Legal com dados da etapa errada** — `gerarEnquadramentoLegal()` lia responsável/data/observações da etapa "Indicação de Dotação Orçamentária" (índice 4) em vez de "Enquadramento Legal" (índice 5). O campo `fundamento` nunca existiu na etapa errada, então sempre caía no fallback `p.legal`, mascarando o problema
- **Extrato de Contrato com dados da etapa errada** — `gerarExtratoContrato()` lia número do contrato, contratante, contratado, CNPJ, vigência e valor da etapa "Homologação" (índice 13) em vez de "Instrumento Contratual" (índice 15), onde esses campos realmente existem. Documento usado para publicação no Diário Oficial e PNCP gerando com campos essenciais em branco
- **Aviso de Dispensa** tinha a mesma confusão de índice 4×5 para o campo `fundamento` (`gerarAvisoDispensa()`)

### Alterado — eliminada a classe inteira de bug por índice hardcoded
- Substituídas **todas** as ~30 referências numéricas a `steps[N]` nos geradores de documento (`gerarEnquadramentoLegal`, `gerarAvisoDispensa`, `gerarExtratoContrato`, `gerarAutorizacao`, `gerarProcessoCompleto`, `gerarAta`) por `STEPS.findIndex(s => s.marcador)`, seguindo o padrão que já existia parcialmente em `gerarAta()`
- Adicionados marcadores booleanos (`dfd`, `etp`, `termoReferencia`, `controleInterno`, `parecerJuridico`, `notaEmpenho`) às etapas do array `STEPS` que ainda não tinham
- Motivação: essa classe de bug já havia causado a inserção incorreta da etapa "Controle Interno" quebrar múltiplos documentos na v2.8.0. Agora, inserir, remover ou reordenar uma etapa não quebra mais nenhum gerador de documento — a referência é sempre por nome, nunca por posição
- Validado com teste funcional em Node.js: processo simulado com valor rastreável em cada uma das 17 etapas, confirmando que cada gerador lê exatamente o campo da etapa correta

---

## [2.9.6] — 2026-07-01

### Removido
- **Sistema de "senha de acesso" local morto** — `_verificarSenhaComMigracao()`, `_hashSenha()`, `_getPassSalt()` e as chaves `sgcd-access-hash`/`sgcd-passwd-salt` eram resquício da arquitetura anterior à autenticação server-side (hash SHA-256 verificado no navegador). Confirmado que não eram chamados em nenhum lugar do fluxo de login atual (`verificarSenha()` vai direto para `/api/auth/login`). Também removida referência órfã a um botão (`btn-remover-senha`) que não existe mais no HTML
- Nenhuma mudança de comportamento — código morto, sem uso ativo. Validado subindo o servidor e testando login antes do commit

---

## [2.9.5] — 2026-07-01

### Adicionado
- **Sincronização do brasão customizado entre máquinas** — o brasão customizado (upload em Configurações → Organização) agora é salvo no servidor via `PUT /api/settings/brasao` (qualquer usuário autenticado) e sincronizado automaticamente no login, junto com Organização e SMTP
- Remover o brasão customizado agora propaga para todos os navegadores (endpoint trata remoção como ação explícita — diferente de Organização/SMTP, aqui vazio realmente significa "apagar", não "campo não preenchido ainda")
- Validado com teste real: salvar, ler via `GET /api/settings`, remover e confirmar que a chave desaparece de fato

---

## [2.9.4] — 2026-07-01

### Corrigido — causa raiz definitiva do SMTP
- **`crypto.subtle` indisponível em contexto inseguro** — a criptografia AES-GCM da senha SMTP usa a Web Crypto API, que só existe em contexto seguro (HTTPS ou `localhost`). Acesso via IP puro em rede local (`http://192.168.x.x`, o uso normal do "modo Servidor") é contexto inseguro por definição do navegador — `crypto.subtle` fica `undefined`, e toda tentativa de criptografar/descriptografar a senha lançava exceção silenciosa. Isso já era um bug **preexistente** na função de SMTP (mesmo antes da sincronização entre máquinas), só nunca testado nesse cenário. Explica por que Organização sincronizou (sem criptografia) e SMTP não (quebrava ao tentar criptografar a senha recebida do servidor)
- Corrigido com fallback: quando `crypto.subtle` não está disponível, usa-se codificação base64 simples (prefixo `b64:`) em vez de AES-GCM — mesmo nível de proteção prática de antes, já que a chave de criptografia também ficava salva ao lado no `localStorage`, então nunca foi proteção contra acesso à máquina, apenas ofuscação contra leitura casual
- Validado isoladamente em Node.js simulando contexto inseguro (sem `crypto.subtle`): criptografa, descriptografa e sincroniza corretamente, inclusive com acentuação

### Identificado (não corrigido nesta versão)
- **Brasão customizado não sincroniza entre máquinas** — diferente de Organização/SMTP, o brasão customizado (upload em Configurações) é salvo apenas como imagem em base64 no `localStorage`, nunca enviado ao servidor. É um problema da mesma família, mas com arquitetura diferente (arquivo binário vs texto) — requer uma correção própria, ainda não implementada

---

## [2.9.3] — 2026-07-01

### Adicionado (diagnóstico)
- Testei isoladamente a lógica exata de `_syncSmtpFromServer()` (Node.js, `localStorage` vazio simulando navegador novo, resposta real do servidor incluindo senha) — sincronizou, criptografou e descriptografou corretamente. A lógica em si está correta
- Faltava instrumentação no lado da **leitura**: só o `PUT` tinha log; o `GET /api/settings` (que dispara a sincronização no login) não tinha nenhum. Um teste sem log nenhum no console do servidor não permitia saber se o navegador sequer chegou a pedir os dados
- Adicionado log no servidor: `[SETTINGS] GET /api/settings de <usuário> — chaves retornadas: [...]`
- Adicionado log no console do navegador em cada etapa do `_onLoginSuccess()`: antes do GET, status da resposta, chaves recebidas, e o conteúdo de `sgcd-smtp` após a sincronização

**Próximo teste:** repita o acesso pela janela anônima e observe **as duas pontas ao mesmo tempo** — a linha `[SETTINGS] GET /api/settings ...` na janela do servidor, e no navegador abra o DevTools (F12) → Console e procure as linhas `[SGCD] ...`. Isso vai mostrar exatamente se a requisição saiu do navegador, chegou ao servidor, e o que veio de volta.

---

## [2.9.2] — 2026-07-01

### Adicionado (diagnóstico)
- Mesmo após a correção da v2.9.1, o problema persistiu no ambiente real do usuário: o banco de produção continuou com os campos de Organização vazios após seguir os passos indicados. O log de requisições HTTP estava completamente desativado (`log_message` fazia `pass`) e não havia nenhum registro do que de fato chegava ao servidor — impossível diagnosticar às cegas
- Adicionado log visível no console do servidor (`[SETTINGS] ...`) toda vez que `/api/settings/org` é chamado e o que foi de fato gravado/ignorado
- Adicionado log no console do navegador (`[SGCD] Enviando/Resposta /api/settings/org`) e um `alert()` bloqueante caso a sincronização com o servidor falhe — antes só havia um toast de 3 segundos, fácil de não notar

**Próximo teste:** repita os mesmos passos observando a janela do servidor (deve aparecer uma linha `[SETTINGS]`) e preste atenção a qualquer alerta bloqueante no navegador. Isso vai mostrar exatamente onde a falha está ocorrendo.

---

## [2.9.1] — 2026-07-01

### Corrigido — causa raiz definitiva (encontrada via code review + evidência direta no banco)
- **Servidor gravava campo vazio por cima de valor real** — `_save_settings()` fazia `INSERT OR REPLACE` cego para qualquer valor recebido, inclusive string vazia. A proteção da v2.8.7 cobria apenas a leitura (merge no login); a escrita continuava desprotegida. Bastava um único "Salvar" em **qualquer** navegador com os campos em branco (ex.: testando o acesso via IP antes dos dados chegarem lá) para apagar o dado real do banco — confirmado inspecionando `sys_settings` diretamente: todas as chaves de Organização estavam gravadas como `''` mesmo após instruções anteriores terem sido seguidas. Corrigido: `_save_settings()` agora ignora qualquer valor vazio recebido, não sobrescreve o que já está salvo, para todos os endpoints (`/api/settings`, `/api/settings/org`, `/api/settings/smtp`)
- **Risco de cache do navegador** — `server.py` nunca enviava `Cache-Control` ao servir `SGCD.html`/JS/CSS, permitindo que o navegador usasse uma versão em cache sem revalidar com o servidor após uma atualização. Adicionado `Cache-Control: no-cache, must-revalidate` para arquivos `.html`, `.js` e `.css`

**Ação necessária (última vez):** no navegador com os dados corretos, abra Configurações → Organização e clique em Salvar mais uma vez. A partir de agora, nenhum navegador com campos em branco vai conseguir apagar esse dado por engano.

---

## [2.9.0] — 2026-07-01

### Adicionado
- **Sincronização de SMTP entre máquinas** — a configuração de e-mail (host, porta, usuário, senha, remetente, destinatário padrão) agora é persistida no servidor via `PUT /api/settings/smtp` (restrito a admin, mesmo nível de sensibilidade do backup) e sincronizada automaticamente para qualquer navegador/máquina que fizer login, eliminando a necessidade de reconfigurar SMTP em cada computador
- A senha SMTP é armazenada no banco do servidor e, ao chegar em cada navegador, é recriptografada com a chave local (AES-GCM) antes de ir para o `localStorage` — o fluxo de envio de e-mail (que já transmitia a senha em texto claro ao servidor a cada disparo) não muda
- Salvar SMTP com o campo de senha em branco mantém a senha já configurada (não apaga)
- Usuários não-admin continuam podendo ler a configuração SMTP sincronizada (necessário para disparar e-mails), mas não podem alterá-la

### Corrigido
- Nada nesta versão além do exposto acima; validado com testes reais (login, salvar como admin, tentativa de salvar como não-admin, leitura, preservação de senha em branco) antes do commit

---

## [2.8.7] — 2026-07-01

### Corrigido
- **Valor vazio do servidor sobrescrevia dado real do navegador** — o fix da v2.8.5 fez o servidor sempre vencer o merge em `_onLoginSuccess()`. Como o banco tinha as chaves de Organização gravadas como string vazia (de um salvamento anterior com campos em branco), esse vazio passou a sobrescrever os dados reais já preenchidos no navegador do modo Pessoal, fazendo-os "desaparecer" ao logar em outra máquina. Corrigido: o merge agora é campo a campo — vazio nunca sobrescreve um valor real, de nenhum dos dois lados; entre dois valores reais, o servidor vence
- **SMTP continua armazenado só no navegador** (não corrigido nesta versão) — diferente da aba Organização, as credenciais SMTP nunca foram enviadas ao servidor por design (evita salvar senha em texto simples no banco). Isso significa que a aba Comunicação/SMTP precisa ser configurada em cada navegador/máquina separadamente. Avise se quiser que isso também sincronize entre máquinas — requer armazenamento criptografado da senha no servidor

**Ação necessária:** no navegador que já tem os dados corretos (modo Pessoal), abra Configurações → Organização e clique em Salvar novamente para sobrescrever os valores vazios gravados anteriormente no banco.

---

## [2.8.6] — 2026-07-01

### Corrigido
- **Crash do servidor ao iniciar (`UnicodeEncodeError`)** — em algumas instalações do Windows, o console usa codificação `cp1252`/`cp850` em vez de UTF-8, e os caracteres de caixa (`╔═╗`) usados no cabeçalho do menu de inicialização não existem nessa codificação, derrubando o processo assim que `server.py` era executado. Isso explicava falhas anteriores relatadas: se o servidor nunca chegava a iniciar, nenhuma configuração — Organização, SMTP ou qualquer outra — ficava disponível. Corrigido forçando `stdout`/`stderr` para UTF-8 logo no início do script
- Validado em teste real (não apenas leitura de código): login, `PUT /api/settings/org` como usuário não-admin, `GET /api/settings` e `GET /api/public/org-info` — todos funcionando conforme esperado após a correção

---

## [2.8.5] — 2026-07-01

### Corrigido
- **Causa raiz definitiva: `PUT /api/settings` exigia admin** — a aba Organização é preenchida por qualquer agente de contratação, não apenas pelo admin, mas o endpoint usado para salvá-la (`/api/settings`) retornava 403 para usuários não-admin. Como `saveSettings()` não verificava a resposta, a falha era silenciosa: o usuário via "Configurações salvas!" mas o dado nunca chegava ao banco quando a sessão não era admin
- Criado endpoint `PUT /api/settings/org`, acessível a qualquer usuário autenticado, restrito às chaves de Organização (orgao, município, autoridade, CNPJ, IBGE, UF); configurações administrativas (backup) continuam exigindo admin em `/api/settings`
- `saveSettings()` agora avisa na tela se a sincronização com o servidor falhar, em vez de falhar em silêncio
- Corrigida ordem do merge em `_onLoginSuccess()`: dados do servidor agora têm prioridade sobre cache local desatualizado/vazio (antes, um `sgcd-user` local vazio sobrescrevia o valor correto vindo do servidor)
- Removida troca automática e indesejada para a aba Configurações a cada login

---

## [2.8.4] — 2026-07-01

### Corrigido
- **Causa raiz: dados de Organização nunca eram salvos no servidor** — `saveSettings()` gravava órgão, município, autoridade competente, CNPJ, código IBGE e UF apenas em `localStorage`, sem enviar ao servidor via `PUT /api/settings`. O fix da v2.8.3 (buscar `/api/settings` no login) não resolvia porque o dado nunca havia chegado ao banco. Agora esses campos são enviados ao servidor junto com as demais configurações, tornando-os visíveis em qualquer navegador/máquina que acessar o sistema. **Ação necessária:** reabra Configurações → Organização e clique em Salvar uma vez para sincronizar dados já preenchidos anteriormente

---

## [2.8.3] — 2026-07-01

### Corrigido
- **Dados de Organização ausentes em outros navegadores/máquinas** — a aba Configurações → Organização exibia campos em branco ao logar de um navegador que nunca havia salvo as configurações localmente (ex.: acesso via IP em modo servidor, opção [2]); `getUser()` dependia apenas do `localStorage`, que é isolado por origem/navegador. Agora, após login bem-sucedido, o sistema busca `/api/settings` e mescla com o cache local, garantindo que os dados salvos no servidor apareçam em qualquer navegador

---

## [2.8.2] — 2026-06-29

### Alterado
- **Tela de login: tema Ardósia fixo** — fundo da tela de login alterado para cinza ardósia (`#1a1f2e`) com partículas prateadas, independente da cor de destaque configurada pelo usuário em Configurações → Interface

### Corrigido
- **Nome do órgão ausente no modo servidor** — ao acessar o sistema via IP (modo servidor em rede local), o card da tela de login não exibia o nome do órgão pois o `localStorage` estava vazio no primeiro acesso; adicionado endpoint público `/api/public/org-info` que retorna o nome do órgão diretamente do banco de dados, utilizado como fallback automático

---

## [2.8.1] — 2026-06-29

### Adicionado
- **Efeito de rede de nós na tela de login** — animação de partículas flutuantes interligadas por linhas, com reação ao movimento do mouse; executada em `<canvas>` via `requestAnimationFrame`
- **Painel de configuração do efeito de nós** — botão de engrenagem (⚙) no canto inferior direito da tela de login abre painel com três controles deslizantes: quantidade de nós (20–120), distância de conexão (60–200 px) e velocidade (1–10); configurações salvas em `localStorage` e aplicadas automaticamente na próxima abertura

---

## [2.8.0] — 2026-06-29

### Adicionado
- **Etapa: Parecer do Controle Interno** — nova etapa no checklist do processo, inserida após o Enquadramento Legal e antes do Parecer Jurídico, conforme fluxo municipal; campos: Responsável, Data de conclusão, Nº do Parecer do Controle Interno e Observações
- **Documento: Ata de Sessão atualizada** — inclui referência ao Parecer do Controle Interno na seção de instrução do processo (Seção III)
- **Sincronização de tema na tela de login** — a cor de destaque escolhida em Configurações → Interface é aplicada automaticamente na tela de login (cabeçalho, avatar, labels, campos de entrada e botão de acesso)

### Corrigido
- **Referências de etapas nos geradores de documentos** — índices de step desatualizados desde a inserção da Dotação Orçamentária (v2.3.0) causavam campos em branco nos documentos gerados; todos os índices foram corrigidos (Enquadramento Legal, Parecer Jurídico, Autorização, Aviso de Dispensa, Propostas, Habilitação, Adjudicação, Homologação, Nota de Empenho, Instrumento Contratual)

---

## [2.7.0] — 2026-06-29

### Adicionado
- **Diagnóstico de rede e servidor** — ferramenta completa de verificação acessível por `Diagnostico SGCD.bat` ou pela opção `[3]` no menu de inicialização:
  - Detecta IP local e exibe o endereço de acesso pela rede
  - Verifica se a porta 3000 está em uso e qual processo a ocupa
  - Testa se o servidor responde em localhost
  - Verifica regras de firewall do Windows para a porta 3000
  - Testa conectividade pelo IP da rede
  - Exibe resumo com problemas encontrados e instruções de correção
- **`Liberar Porta SGCD.bat`** — cria automaticamente a regra de firewall para a porta 3000 (requer execução como Administrador)
- **Novo ícone** — ícone do sistema redesenhado com tema de licitação (documento + lupa), mesma identidade visual do SGDP; versões adaptadas por tamanho (16/32/48/64/128/256px)

---

## [2.6.0] — 2026-06-28

### Adicionado
- **Modo de operação na inicialização** — ao abrir o `Iniciar SGCD.bat`, a janela do servidor exibe um menu de seleção:
  - **[1] Pessoal** — abre o app automaticamente no navegador, encerra quando o último usuário sair
  - **[2] Servidor** — modo contínuo para máquina central/rede, exibe o IP da rede, não encerra automaticamente

### Corrigido
- **Loop de backup no modo Servidor** — ao fechar a última sessão, o backup era executado repetidamente a cada 5 segundos; agora roda uma única vez e aguarda novo login para resetar
- **Nome do arquivo de backup manual** — data gerada sem hifens (`20260628`); corrigido para o formato padrão (`2026-06-28`)
- **Acesso por rede** — `SGCD.html` usava `localhost:3000` fixo; substituído por `API_BASE` dinâmico que detecta automaticamente o host correto ao ser acessado por outro computador na rede

---

## [2.5.0] — 2026-06-28

### Adicionado
- **Certidão do dashboard abre fornecedor** — clicar num card de "Certidões que precisam de atenção" navega para a tela de Fornecedores e abre o cadastro diretamente na aba Certidões

### Corrigido
- **Opção de tema "Laranja" renomeada para "Institucional"** — o sistema usa navy `#1a3a6b` como padrão desde a migração visual; o rótulo agora reflete a cor real exibida
- **Tema "Azul" diferenciado** — antes duplicava o institucional (`#1a3a6b`); agora usa `#0066CC` (azul distinto)

---

## [2.4.0] — 2026-06-28

### Segurança
- **XSS `/verificar/`** — código do documento agora escapado via `json.dumps()` antes de ser emitido no JS gerado pelo servidor (era injetado raw na string JS)
- **XSS notificações** — `it.titulo` e `it.sub` passam por `escHtml()` antes de ir para `innerHTML`
- **XSS editor de e-mail** — URL validada (`https?://` apenas) e texto do link escapado com `escHtml()` antes de `execCommand('insertHTML')`
- **XSS modal de exclusão** — `frase` (num_proc) escapada com `escHtml()` antes de ir para `innerHTML`
- **Falsificação de auditoria** — `_add_audit` ignora `user_id`/`user_nome` do body e usa sempre os dados da sessão autenticada (`s['user_id']`, `s['nome']`)
- **Settings sem auth** — `POST /api/settings` e `PUT /api/settings` agora exigem `admin`; não-admins recebem 403
- **Whitelist de extensões no upload** — extensões não permitidas retornam 400; bloqueia `.exe`, `.bat`, `.ps1` e similares
- **Limite de tamanho de upload** — `Content-Length > 50 MB` retorna 413 antes de ler o body
- **`Content-Disposition` sanitizado** — `nome_original` tem `"`, `\n`, `\r` substituídos por `_` para não quebrar headers HTTP

### Corrigido
- **`NameError` em `_route_delete`** — `parsed` não estava definido no escopo; corrigido para `urlparse(self.path).query`
- **`saveProcess` sem tratamento de erro** — adicionado `try/catch` com toast de erro e `finally` para garantir que o indicador de salvamento some mesmo em caso de falha
- **Race condition em `infoNaturezaChange`/`infoCategoriaChange`** — funções convertidas para `async/await` para evitar salvamento no processo errado ao navegar rapidamente
- **Limite de `per` nos endpoints de listagem** — `per` limitado a 1000 (arquivos/auditoria) e 2000 (processos/fornecedores) para evitar carga excessiva de memória
- **Comentário de intervalo de ping** — atualizado para refletir 5s correto

---

## [2.3.0] — 2026-06-28

### Adicionado
- **Etapa "Indicação de Dotação Orçamentária"** inserida entre a Pesquisa de Preços (etapa 4) e o Enquadramento Legal (agora etapa 6) — Art. 12, inciso VII da Lei 14.133/2021
- **Migração automática de processos existentes** — ao abrir um processo criado antes da v2.3.0, o sistema insere a nova etapa na posição correta (splice em índice 4) sem perda de dados das demais etapas

---

## [2.2.0] — 2026-06-28

### Adicionado
- **Brasão municipal na sidebar** — `brasao.png` exibido centralizado no topo da sidebar acima do título SGCD; some silenciosamente se o arquivo não estiver presente (`onerror`)
- **Data e busca na sidebar** — data atual e botão de busca global (Ctrl+K) movidos para a sidebar, abaixo do logo e acima da navegação

### Melhorado
- **Barra superior removida** — header fixo eliminado; sidebar agora ocupa toda a altura da tela (`top: 0`); layout mais limpo e alinhado ao visual do SGDP
- **Tema do login totalmente institucional** — fundo `#0d1b35` (navy escuro) substituindo o `#1a0e14` legado Ubuntu/Canonical; glow azul no lugar do laranja; ícone e badge da Lei 14.133/2021 com tinta branca translúcida
- **Encerramento do servidor mais rápido** — `SESSION_TTL` reduzido de 30s para 15s, watchdog de 10s para 5s e ping do browser de 10s para 5s; servidor encerra em ~20s após o último browser fechar (antes ~40s)

---

## [2.1.0] — 2026-06-28

### Adicionado
- **Sistema de backup completo redesenhado** — aba "Backup de Dados" com seleção de pasta via diálogo nativo do Windows (FolderBrowserDialog via PowerShell), dois grupos de backup manual (Sistema JSON e Banco .db), backup automático ao fechar o sistema com campo de quantidade de arquivos mantidos e exibição do último backup
- **Backup automático ao fechar** — ao encerrar o sistema (botão "Fechar Sistema" ou timeout de heartbeat), cria automaticamente `SIS_SGCD_BACKUP_YYYY-MM-DD_HH-MM-SS.json` e `DB_SGCD_BACKUP_YYYY-MM-DD_HH-MM-SS.db` se a opção estiver habilitada
- **Rotação de backups** — executada na inicialização do servidor, remove arquivos excedentes da sessão anterior (compatível com pastas no OneDrive, onde arquivos recém-criados ficam bloqueados durante sincronização)
- **Backup manual do banco de dados** — `GET /api/backup/db` cria cópia SQLite via `src.backup()` e envia diretamente ao browser (mesmo padrão do export JSON, abre diálogo "Salvar como")
- **Restauração do banco de dados** — `POST /api/backups/db/restore` valida magic bytes SQLite, cria backup de segurança e restaura via API de backup do SQLite sem encerrar o servidor
- **Nomenclatura padronizada de backups** — sistema: `SIS_SGCD_BACKUP_*`, banco: `DB_SGCD_BACKUP_*`; endpoint `GET /api/backups/db/download?name=xxx` para download de backup específico
- **Diálogo de seleção de pasta** — `GET /api/dialog/folder` abre FolderBrowserDialog nativo do Windows via PowerShell; watchdog pausado durante abertura do diálogo para evitar timeout
- **Log de erros persistente** — `sgcd_errors.log` captura todas as exceções do servidor com traceback completo via módulo `logging`; erros de remoção de backup logados com nome do arquivo e motivo
- **Aviso de CapsLock no login** — banner amarelo exibido abaixo do campo senha quando CapsLock está ativo; detectado via `getModifierState` nos eventos `keydown`, `keyup` e `focus`
- **Endpoint público `/api/public/last-backup`** — retorna timestamp do último backup automático sem autenticação; usado na tela de login para exibir data real do último backup

### Melhorado
- **Backup na tela de login** — widget "Último backup exportado" agora exibe o mais recente entre export manual (localStorage) e backup automático (servidor); reflete corretamente os backups feitos ao fechar o sistema
- **Heartbeat apenas quando autenticado** — JS só envia `/heartbeat` quando `_apiToken` está definido; servidor não considera sessão ativa durante tela de login; watchdog respeita sessão real de uso
- **Backup automático só após sessão autenticada** — flag `_session_active` marcada no primeiro heartbeat; backup do watchdog não roda se nenhum login foi feito na sessão
- **Diálogo de confirmação no export do banco** — `exportarBackupDB()` exibe o mesmo modal de confirmação do export do sistema antes de prosseguir
- **Configurações de backup salvas em `sys_settings`** — `backup_path`, `auto_backup_enabled` e `auto_backup_keep` persistidos no banco; rotação aplicada imediatamente ao salvar nova quantidade de arquivos mantidos
- **Token via query string em todos os endpoints** — `_token()` aceita `?token=xxx` além do header `Authorization: Bearer`; necessário para upload multipart e operações de restore

### Corrigido
- **Servidor encerrava ao selecionar pasta de backup** — watchdog pausado (`_watchdog_paused`) enquanto FolderBrowserDialog está aberto; timeout aumentado para 120s
- **Erro `NameError: sessions`** em `/shutdown` e `/send-email` — substituído dict inexistente por `get_session()`
- **Erro `OperationalError: no such column: criado_em`** — coluna renomeada para `uploaded_em` em todos os SELECTs de `/api/files`
- **Datas "Invalid Date" na auditoria** — `_add_audit` aceita campos tanto no formato novo (`ts`, `type`, `user_nome`) quanto no legado (`at`, `evento`, `usuario`); mapeamento reverso adicionado no `dbGetAll('auditGlobal')`
- **Rotação de backups falhava silenciosamente no OneDrive** — `os.remove` com retry de até 6 tentativas (2s entre cada) e log de erro em caso de falha persistente; rotação movida para startup (quando arquivos da sessão anterior já estão sincronizados)
- **F5 encerrava o servidor** — `beforeunload` esvaziado; sessões invalidadas automaticamente pelo servidor ao reiniciar; F5 mantém o servidor ativo

---

## [2.0.0] — 2026-06-27

### Adicionado
- **Nova arquitetura: SQLite + REST API + autenticação server-side** — `server.py` completamente reescrito; dados migrados do IndexedDB para SQLite (`sgcd.db`); cada operação de leitura/escrita é uma chamada REST autenticada com Bearer token; IndexedDB removido do frontend
- **Autenticação multiusuário** — login com `username` + `senha`; hashing PBKDF2-HMAC-SHA256 com 100.000 iterações e salt aleatório por usuário; sessões em memória com tokens UUID; logout explícito via `POST /api/auth/logout`; fechar o app invalida todos os tokens automaticamente
- **Gestão de usuários (aba Configurações — admin)** — administradores podem criar, editar e desativar usuários; campos: username, senha, nome, cargo, matrícula, admin, ativo; aba visível somente para admins; proteção no servidor em todos os endpoints `/api/users`
- **Aba Segurança → Alterar minha senha** — substituiu a senha local por troca de senha server-side; verifica senha atual antes de aceitar a nova; não-admins só podem alterar a própria senha
- **Sidebar estilo SGDP** — barra lateral redesenhada com 220px fixo, seções "Principal / Contratações / Administração", badge de contagem de processos e alertas de agenda, rodapé com avatar, nome, cargo e botões de sair/fechar sistema
- **Botão "Fechar Sistema"** — no rodapé do sidebar; faz logout no servidor e encerra o processo Python (`/shutdown`) antes de fechar a janela
- **Último usuário pré-preenchido no login** — `username` do último login bem-sucedido é salvo em `localStorage` e restaurado automaticamente no overlay; foco vai direto para o campo senha
- **Upload de arquivos via REST** — arquivos enviados por multipart/form-data para `POST /api/files`; download via `GET /api/files/:id`; metadados via `GET /api/files/:id/meta`
- **Backup e restore server-side** — `GET /api/backup` exporta todos os dados; `POST /api/backup/restore` restaura; `DELETE /api/wipe` apaga tudo (admin)
- **Servidor com suporte a conexões concorrentes** — `ThreadingTCPServer` com `allow_reuse_address` correto; cada requisição em thread separada

### Melhorado
- **Camada de compatibilidade IDB → API** — funções `dbGet`, `dbGetAll`, `dbPut`, `dbDelete`, `dbGetByIndex` mantidas com assinaturas idênticas; roteadas para REST API sem alterar call sites existentes
- **Logout no `_apiLogout()`** — chama `POST /api/auth/logout` para invalidar o token no servidor antes de limpar o estado local
- **Controle de acesso server-side** — não-admin recebe 403 em `GET/POST /api/users`, `DELETE /api/users/:id` e `PUT /api/users/:id` de outro usuário; só pode alterar a própria senha via `PUT /api/users/:id` com `old_password`

### Corrigido
- **`SyntaxError` por `let db` duplicado** — declaração duplicada impedia execução de todo o JavaScript; removida a declaração do bloco IDB legado
- **`allow_reuse_address` aplicado tarde demais** — servidor falhava silenciosamente ao reiniciar na mesma porta; corrigido como atributo de classe antes do `__init__`
- **`sessionStorage` vs `localStorage` no logout** — flag `sgcd-session-auth` estava sendo removida do storage errado

---

## [1.19.0] — 2026-06-27

### Adicionado
- **Sincronização de backup entre agentes** — botão "Sincronizar Backup" importa arquivo exportado por outro agente; processos e fornecedores são mesclados por ID usando `updatedAt` como critério de conflito (registro mais recente vence); configurações do sistema não são sobrescritas
- **Criptografia AES-GCM das credenciais SMTP** — senha nunca armazenada em texto claro; chave de 256 bits gerada aleatoriamente por instalação em `sgcd-enc-key` (localStorage); campo de senha exibe placeholder "••••••••  (senha salva — deixe em branco para manter)" quando já há credencial; ao importar backup de outra máquina, toast orienta a reinformar a senha
- **Opção "Ignorar verificação SSL" no SMTP** — checkbox nas configurações SMTP para servidores com certificado autoassinado (ex: webmail institucional); quando desmarcado, verificação segura é exigida por padrão; mensagem de erro descritiva orienta o usuário em caso de falha SSL
- **Hash de senha com salt por instalação** — `_hashSenha()` agora usa salt aleatório gerado uma vez em `sgcd-passwd-salt` (localStorage), eliminando o salt fixo anterior; migração automática: na primeira autenticação com hash antigo, o sistema re-salva com o novo salt sem interromper o acesso
- **Sessão autenticada persiste após F5** — flag `sgcd-session-auth` em `sessionStorage` evita que o overlay de login seja exibido novamente após recarregamento de página; ao fechar o navegador a sessão é encerrada normalmente

### Melhorado
- **Cache de elementos DOM (`_dom()`)** — 34 elementos estáticos cacheados em inicialização lazy; elimina `getElementById` nos hot paths de `renderDash()`, `toast()`, `_showSaveIndicator()` e `_hideSaveIndicator()`
- **`_getDashFilters()`** — leitura única dos 7 filtros do dashboard por chamada a `renderDash()`, substituindo 21 chamadas individuais a `getElementById` distribuídas em três funções
- **`_applyDashFilters()`** — lógica de filtro centralizada; elimina 45 linhas duplicadas entre `renderDash()`, `gerarRelatorio()` e `exportarCSV()`
- **`_lastFiltered`** — cache do último array filtrado de `renderDash()`; `gerarRelatorio()` e `exportarCSV()` reutilizam o resultado sem refazer O(n) de filtro
- **Debounce nos inputs de busca** — `_debounce()` genérico aplicado: 150ms em `#search` e `#forn-search`, 100ms na busca global (Ctrl+K), 150ms no picker de fornecedor em propostas
- **O(n²) → O(1) em `renderFornecedores()`** — `processes.find()` dentro de `.map()` substituído por `Map` construído uma vez antes do loop
- **Lazy expand nos cards de fornecedor** — render inicial limitado ao header (razão social, CNPJ, situação, porte, botão); conteúdo completo (certidões, QSA, contato, endereço, processos) injetado no DOM apenas ao abrir o card; reduz HTML inicial em ~65% por card
- **Redesign do gráfico de processos por mês** — card container com borda e padding; legenda HTML fora do SVG; sumário de métricas abaixo (total criados, concluídos com %, pico mensal); escala Y com inteiros calculados por `step` (1/2/5/10/20); labels de valor sobre barras quando há espaço; mês atual destacado em negrito; Janeiro exibe ano abreviado (Jan '25) para identificar virada de exercício; cores #2a78d6 (criados) e #1baf7a (concluídos); barras com canto superior arredondado (rx=3) e base reta
- **Exportar Backup — diálogo antes do download** — ao clicar em "Exportar Backup", o sistema exibe diálogo com aviso de armazenamento externo antes de iniciar o download; usuário deve confirmar "Salvar arquivo" para prosseguir; cancelar descarta sem salvar
- **Configurações — layout responsivo** — página de configurações passa a respeitar o modo compacto/expandido do usuário; largura dos cards alinhada à largura das abas de navegação; conteúdo do painel preenche a altura disponível da tela

### Corrigido
- **Verificação SSL habilitada por padrão no server.py** — `ctx.check_hostname = False` e `ctx.verify_mode = ssl.CERT_NONE` removidos; verificação de certificado agora segue o comportamento padrão do Python; servidores com certificado autoassinado devem usar a nova opção "Ignorar verificação SSL" nas configurações

---

## [1.18.0] — 2026-06-26

### Adicionado
- **Controle de acesso por senha** — nova aba "Segurança" nas Configurações; senha armazenada como hash SHA-256 via Web Crypto API; overlay de acesso restrito exibido ao carregar quando senha está ativa; funções `alterarSenha()`, `removerSenha()` e `verificarSenha()`
- **Tela de login redesenhada** — identidade visual institucional com header aubergine, brasão SVG, badge "Lei 14.133/2021", card do órgão com sigla gerada automaticamente, campo de senha com toggle mostrar/ocultar, animação de shake em senha incorreta, painel de último backup e versão no rodapé
- **Painel de Diagnóstico** — nova aba "Diagnóstico" nas Configurações; analisa todos os processos e fornecedores do banco; classifica resultados em Erros críticos / Avisos / Informações; verifica: processos concluídos sem fornecedor ou base legal, homologação ausente, aviso sem data de publicação, habilitação sem fornecedor, CNPJs duplicados e inválidos, campos de configuração PNCP ausentes
- **Campos PNCP no perfil do órgão** — CNPJ do órgão, Código IBGE do município e UF adicionados em Configurações → Organização; utilizados automaticamente no JSON de exportação PNCP
- **Validação ao concluir etapa** — ao marcar etapa como "Concluída", verifica campos obrigatórios da etapa e exibe confirmação não-bloqueante listando os campos faltantes; usuário pode concluir mesmo assim ou voltar para preencher

### Melhorado
- **Backup automático por salvamento** — `saveProcess()` agora dispara `_autoBackupSnapshot()` com debounce de 3 segundos após cada alteração, sem dependência da configuração "Snapshot ao fechar"
- **Banner de alerta de backup** — faixa laranja persistente no rodapé exibida quando o último backup manual foi exportado há mais de 7 dias ou nunca foi realizado; dispensada automaticamente após exportar
- **exportBackup()** registra timestamp do último export em `sgcd-last-manual-export` para alimentar o banner de alerta e a tela de login
- **customConfirm()** estendido com parâmetro `cancelLabel` para personalizar o texto do botão de cancelamento
- **Exportação PNCP** usa CNPJ e código IBGE reais do órgão (configurados nas Configurações) em vez de `null`

### Corrigido
- **Índice hardcoded no Relatório de Fornecedores** — `p.steps?.[10]` substituído por `STEPS.findIndex(s => s.adjudicacao)`, eliminando dependência de posição fixa da etapa de Adjudicação
- **`showToast` inexistente** — chamada em `setStepStatus` substituída por `toast()` (função correta do sistema)

---

## [1.17.0] — 2026-06-26

### Adicionado
- **Exportação PNCP** — botão "📤 Exportar PNCP" na etapa Aviso de Dispensa gera arquivo JSON estruturado no formato da API do Portal Nacional de Contratações Públicas com os dados do processo pré-preenchidos; inclui modalidade, critério de julgamento, amparo legal, valores, datas, órgão e item
- **Validação de base legal** — Termo de Adjudicação e Termo de Homologação agora exibem aviso não-bloqueante quando o campo de enquadramento legal (Art. 75, inciso) não estiver preenchido no processo

### Melhorado
- **Ata de Procedimento** — índices de etapas substituídos por `STEPS.findIndex()` dinâmico, corrigindo bugs nos campos de Propostas (era índice 9, correto 8) e Habilitação/Certidões (era índice 10, correto 9)
- **Referência normativa dos limites de dispensa** — Decreto nº 11.317/2022 substituído pelo Decreto nº 12.807/2025 (vigente desde 1º jan/2026) em todos os documentos e textos do sistema; valores (R$ 130.984,20 e R$ 65.492,11) permanecem inalterados

### Corrigido
- **Artigos nos documentos gerados** — revisão geral em todos os 16 modelos: arts. 3º/9º Lei 9.784/99 nos Despachos de Recusa e Inabilitação; art. 72, VII na Justificativa de Enquadramento Legal; art. 94 c/c art. 91 §4º no Extrato de Contrato; art. 72, parágrafo único no Aviso de Dispensa; concordâncias gramaticais e parágrafos duplicados removidos
- **Ata — número da DL** — `blank(p.num)` substituído por `blank(p.num_dl || p.num)` para priorizar o campo correto

---

## [1.16.0] — 2026-06-26

### Adicionado
- **Relatório de Fornecedores** — relatório global com indicadores de participação, vitórias, aprovação/reprovação por fornecedor e ranking dos 5 principais; inclui QR Code de autenticidade via `_qrFooterReport()`
- **Relatório Executivo** — relatório consolidado de contratações diretas com 4 KPIs, gráfico de barras de valores por processo, tabela de alertas e lista dos últimos processos
- **Aba Participações no cadastro de fornecedores** — histórico de todos os processos em que o fornecedor participou com status colorido, valor adjudicado e link direto para o processo
- **Processo Completo (PDF único)** — botão "📦 Processo Completo" gera documento único agregando todos os atos do processo com QR Code de autenticidade e numeração de seções; erro de `<script>` embutido em template literal corrigido
- **`_qrFooterReport(label)`** — função para rodapé QR em relatórios globais (sem objeto de processo), complementando a `_qrFooter(p)` existente

### Corrigido
- **QR Code ausente em documentos** — varredura geral; todos os 16 geradores de documento agora incluem QR Code no rodapé
- **Rodapé duplicado no Processo Completo** — removido `<div class="footer">` legado que coexistia com o `_qrFooter(p)`
- **StatusMap em Participações do fornecedor** — mapa de status corrigido para exibir rótulos corretos (Não iniciado, Em andamento, Concluído, Bloqueado)

---

## [1.15.0] — 2026-06-25

### Adicionado
- **Paginação no dashboard** — listagem de processos exibe resultados paginados com controles de navegação; melhora performance com grande volume de processos
- **Lazy loading das etapas** — cards de etapa renderizados sob demanda ao expandir, reduzindo tempo de abertura do painel de processo
- **Filtros avançados ampliados no dashboard** — filtros por valor mínimo/máximo, período de criação e combinação de critérios; persistência dos filtros ativos entre navegações

---

## [1.14.0] — 2026-06-25

### Adicionado
- **Notificações in-app** — ícone de sino na barra lateral com badge vermelho de contagem; painel dropdown exibe alertas automáticos: prazos vencendo em ≤7 dias, prazos já vencidos, processos parados há ≥15 dias e certidões de fornecedores vencendo em ≤30 dias; clicar em um alerta navega diretamente para o processo correspondente; badge atualizado automaticamente ao carregar dados
- **Templates de processo** — botão "⊞ Modelo" no cabeçalho do processo salva os campos principais (objeto, base legal, critério, valor, unidade, natureza/categoria) como modelo reutilizável em `localStorage`; ao abrir "Novo Processo", barra de chips aparece com os modelos salvos para aplicação com um clique; chips com botão ✕ para excluir modelo individual
- **Importação CSV de fornecedores** — botão "Importar CSV" na tela de Fornecedores; aceita separador `,` ou `;`; exibe pré-visualização das primeiras 8 linhas antes de confirmar; opção de consultar CNPJ automaticamente na Receita Federal durante a importação; barra de progresso por registro; modelo padrão disponível para download com todos os 23 campos do cadastro (`cnpj`, `razao_social`, `nome_fantasia`, `email`, `telefone`, `telefone2`, `cep`, `logradouro`, `numero`, `complemento`, `bairro`, `municipio`, `uf`, `natureza_juridica`, `porte`, `abertura`, `capital_social`, `situacao`, `cnae_cod`, `cnae`, `opcao_simples`, `opcao_mei`, `matriz_filial`)
- **Relatório executivo** — botão "Executivo" no dashboard gera documento com: cabeçalho institucional, 4 KPIs em destaque (total, concluídos, em andamento, valor total estimado), gráfico de barras por status, tabela de alertas para processos parados ≥15 dias e lista dos últimos 20 processos com status colorido e valor; abre em janela separada com botão "🖨 Imprimir / PDF"
- **Histórico de edições por campo** — ícone 🕐 ao lado do rótulo de cada campo editável no painel lateral do processo; clique exibe painel flutuante com todas as alterações registradas para aquele campo (data/hora + valor anterior → novo valor); alimentado pelos eventos `CAMPO_ALTERADO` da trilha de auditoria global
- **QR Code de autenticidade nos documentos** — gerador QR puro em JavaScript (sem dependências externas, ~200 linhas), modo byte, ECC nível M, versões 1–10; todos os documentos gerados (Autorização, Ata, Aviso, Extrato de Contrato, Despachos, Termos de Adjudicação/Homologação, Mapa de Preços, Justificativa) incluem QR no rodapé apontando para `http://localhost:3000/verificar/{cod}`
- **Página de verificação de autenticidade** (`/verificar/{cod}`) — nova rota no `server.py`; ao escanear o QR, o navegador abre uma página que consulta o IndexedDB `dispensaDB` diretamente (mesmo origin) e exibe: ✓ Documento Autêntico com objeto, nº PA/DL, unidade, valor e data de criação; ou ✗ Documento não encontrado com aviso de possível adulteração
- **Editor rich text de e-mail** — toolbar de formatação completa nas abas Fornecedor e Interno da janela de e-mail: negrito, itálico, sublinhado, alinhamento (esquerda/centro/direita/justificado), seletor de fonte (Verdana/Arial/Times/Calibri), seletor de tamanho (8–36pt), listas ordenada/não-ordenada, inserção de link com texto âncora, desfazer/refazer; conteúdo HTML completo preservado no envio via SMTP

### Melhorado
- **Janela de e-mail** — largura ampliada; foco retido na janela ao rolar a página com o mouse por fora; `overflow` do body bloqueado enquanto o modal está aberto
- **Template de e-mail para fornecedor** — personalização automática por destinatário: substitui `Prezado(a) X,` pelo nome do sócio cadastrado no QSA de cada fornecedor; campos `Órgão` e assinatura sem sufixo de município
- **Barra de progresso do processo** — ocupa 100% da largura do card; dots (etapas) distribuídos com `space-between` para preencher uniformemente o espaço disponível
- **Painel de alertas** — posicionamento dinâmico à direita da sidebar (`sidebar.getBoundingClientRect().width + 12px`), funcionando corretamente tanto com sidebar colapsada (48px) quanto expandida (110px); fundo sólido corrigido (sem transparência)
- **Servidor local** — encerramento reduzido para ~6 s após fechar a janela do app (via manipulação do `_last_heartbeat`)

### Corrigido
- **Erro de inicialização** — `renderNotificacoes()` chamada durante `loadProcesses()` antes de `fornecedores` estar disponível; corrigido tornando a função `async` e lendo diretamente do IndexedDB com `dbGetAll('fornecedores')`
- **Seletores de fonte/tamanho cortados na toolbar de e-mail** — `height:28px` muito pequeno; corrigido com `height:auto;line-height:1.4` e `width:120px` no seletor de fonte

---

## [1.13.0] — 2026-06-20

### Adicionado
- **Dashboard com cards de métricas enriquecidos** — 6 cards de KPI substituem os 4 cards anteriores: Total, Em andamento, Concluídos, Não iniciados, Bloqueados e Valor total estimado; cada card exibe badge de percentual, subtítulo contextual e borda colorida lateral; hover com elevação suave
- **Badge de alertas na Agenda** — bolinha vermelha com contagem sobre o ícone da Agenda na barra lateral quando há eventos urgentes: prazos vencidos, processos com prazo nos próximos 3 dias e processos parados há mais de 15 dias; atualiza automaticamente ao salvar qualquer processo
- **Skeleton loading no dashboard** — blocos cinza pulsantes animados substituem a tela em branco enquanto os dados carregam do IndexedDB; transição suave com fade-out do skeleton e fade-in do conteúdo real
- **Painel de informações ocultável no processo** — botão "⊟ Painel" no cabeçalho do processo alterna a visibilidade da coluna lateral de informações; preferência salva em Configurações → Interface; coluna oculta por padrão pode ser ativada individualmente por processo
- **Confirmação em duas etapas para exclusão de processo** — clique em "Excluir" exige: (1) aviso geral com botão "Continuar" e (2) digitação do número do processo para confirmar; padrão idêntico ao factory reset

### Melhorado
- **Modo escuro sincronizado com Configurações** — toggle de Claro/Escuro adicionado em Configurações → Interface → Tema de aparência; o botão rápido na sidebar e a configuração ficam sempre em sincronia; `brand-light` agora adapta a tonalidade correta para cada tema de cor (azul, verde, roxo) em modo escuro
- **Barra lateral expandida responsiva à fonte** — largura da sidebar expandida usa unidade fixa de 110 px para acomodar o rótulo "FORNECEDORES" completo em qualquer tamanho de fonte; rótulos nunca truncam
- **Configurações não redireciona ao salvar** — ao clicar em Salvar nas Configurações, o sistema permanece na mesma aba em vez de redirecionar para o dashboard

### Corrigido
- **Conteúdo expandido sobrepunha a sidebar** — ao ativar largura expandida + sidebar expandida simultaneamente, o `padding-left` do conteúdo não respeitava os 110 px da sidebar; corrigido com regra CSS específica para a combinação das duas classes

---

## [1.12.2] — 2026-06-20

### Adicionado
- **Card de fornecedor expansível inline** — clique no card da lista expande o cadastro completo diretamente na lista, sem abrir modal. Três estados: colapsado, visualização (abas Dados/Certidões) e edição. Apenas um card aberto por vez; abrir outro fecha o anterior automaticamente
- **Certidão inline no card** — "+ Adicionar Certidão" e "✏" dentro do card renderizam o formulário diretamente no próprio card, sem modal separado; ao salvar ou cancelar, volta para a aba Certidões
- **Proxy ReceitaWS via server.py** — novo endpoint `GET /cnpj/{digits}` no servidor local que consulta a ReceitaWS server-side, contornando a restrição de CORS do browser. A busca de CNPJ agora usa: proxy local → ReceitaWS direto → BrasilAPI como fallback
- **Licença MIT** — repositório GitHub agora possui licença MIT explícita

### Melhorado
- **Iniciar SGCD.bat** — janela CMD abre minimizada na barra de tarefas e fecha automaticamente ao encerrar o sistema
- **Watchdog do servidor** — timeout reduzido de 60 s para 8 s; o CMD fecha em no máximo 8 s caso o beacon `/shutdown` não chegue ao servidor
- **Consulta de CNPJ** — ReceitaWS é agora a fonte primária (traz e-mail, telefone formatado, QSA com data de entrada); BrasilAPI é fallback automático

### Corrigido
- **Data de Abertura do CNPJ exibia "Invalid Date"** — ReceitaWS retorna a data no formato `DD/MM/YYYY`; o visualizador do card agora converte para ISO antes de parsear
- **Botões Fechar/Editar dentro do card não funcionavam** — cliques dentro do corpo expandido propagavam para o `onclick` do card pai e causavam toggle indesejado; corrigido com `event.stopPropagation()`
- **Campo CEP pequeno demais no formulário de edição** — coluna do grid ampliada de 90 px para 170 px para acomodar input + botão "🔍 CEP"
- **Campo Entrada do QSA cortado** — coluna ampliada de 110 px para 150 px para exibir `dd/mm/aaaa` completo
- **Relatório de fornecedores com colunas desalinhadas** — adicionado `table-layout: fixed` e `<colgroup>` com larguras explícitas; o `colspan="4"` nas linhas de cabeçalho do fornecedor não quebra mais o layout das colunas Situação, Porte e Município

---

## [1.12.1] — 2026-06-20

### Adicionado
- **Bloqueio de acesso direto via `file://`** — ao abrir o SGCD.html diretamente (fora do servidor local), o sistema exibe uma tela de aviso e bloqueia o acesso para evitar a criação acidental de uma base de dados separada

### Melhorado
- **Encerramento do servidor reescrito — arquitetura baseada em PID** — o `server.py` agora localiza o Chrome/Edge, lança o navegador internamente via `subprocess.Popen()` e monitora o processo com `proc.wait()`; quando o usuário fecha a janela do app, o Python detecta o encerramento do processo e chama `os._exit(0)` imediatamente, sem depender de beacons JS ou heartbeat. O `Iniciar SGCD.bat` foi simplificado para apenas verificar o Python e executar o servidor
- **Heartbeat** mantido como fallback de 60s para o cenário em que nenhum navegador compatível é encontrado e o sistema usa o navegador padrão
- **Fusão das etapas "Aviso de Dispensa" e "Publicação"** — as antigas etapas 8 e 9 foram unificadas em uma única etapa com todos os campos combinados; migração automática para processos existentes com 16 etapas
- **Remoção do documento "Extrato para Diário Oficial"** — removido por ser redundante com o Aviso de Dispensa (Prefeitura de Orindiúva publica o aviso completo no D.O.)
- **Extrato de Contrato — correção de texto** — "O presente instrumento tem por objeto a contratação de [objeto]" corrigido para "O presente instrumento tem por objeto: [objeto]" eliminando redundância
- **Ata de Sessão — correção de número da DL** — o número da Dispensa de Licitação na seção "Abertura da Sessão" agora usa corretamente `num_dl` em vez de `num`

### Corrigido
- Todos os índices de etapas em geradores de documentos (Ata, Documento Consolidado, Extrato de Contrato, Agenda, Modal de E-mail) atualizados para refletir a fusão das etapas 8 e 9
- Migração automática `_migrarFusaoAvisoPublicacao()` adicionada ao startup para preservar dados de processos existentes

---

## [1.12.0] — 2026-06-20

### Adicionado
- **Notas internas por etapa** — campo de texto amarelo ao final de cada etapa para anotações internas; não aparece em nenhum documento gerado
- **Dotação orçamentária a nível de processo** — quatro novos campos (Programa/Ação, Elemento de Despesa, Fonte de Recursos, Dotação Completa) visíveis na aba de informações; preenchidos automaticamente na Autorização de Abertura e no Extrato de Contrato; copiados ao duplicar processo
- **Cálculo automático de prazos (Art. 75, §3°)** — ao preencher a data de publicação no PNCP (etapa 9), o sistema calcula automaticamente a data mínima de encerramento de propostas (3 dias úteis, descontando fins de semana e feriados nacionais brasileiros); aviso visual em vermelho caso a data informada seja inferior ao mínimo legal
- **Controle de limite anual — Art. 75, I e II** — painel lateral no processo exibe o valor acumulado no exercício corrente para o inciso aplicável, com barra de progresso e alerta quando o limite legal é atingido (I: R$ 130.984,20; II: R$ 65.492,11)
- **Agenda de Vencimentos** — nova tela na barra lateral (ícone de calendário) listando encerramentos de propostas, vencimentos de contratos, prazos de processos e processos parados há mais de 15 dias, agrupados por proximidade temporal; clicar em qualquer evento abre o processo correspondente
- **Vinculação entre processos** — campo na aba de informações do processo para vincular processos relacionados (Renovação de, Aditivo de, Continuidade de, Processo anterior); vínculos são bidirecionais automáticos; chips clicáveis no painel de informações permitem navegar entre processos vinculados
- **Documento consolidado (PDF único)** — botão "📦 Processo Completo" no cabeçalho do processo gera um documento único com todas as seções preenchidas (Autorização, Publicação, Adjudicação, Homologação, Empenho e Instrumento Contratual) em uma única janela de impressão
- **Visualização Kanban** — botão de alternância no dashboard agrupa processos em colunas por fase processual: Instrução, Publicado, Análise, Adjudicação, Contratação e Concluído; filtros do dashboard aplicam-se ao Kanban
- **Notificações por e-mail via SMTP** — botão "✉ Notificar" no processo abre modal com dois templates (Fornecedor e Interno); envio direto via servidor local (server.py); configurações SMTP (host, porta, TLS/SSL, usuário, senha, destinatário interno) disponíveis em Configurações

### Melhorado
- `server.py` reescrito como servidor HTTP com suporte a CORS, endpoint `/health` e `/send-email` via `smtplib` (stdlib Python, sem dependências externas)
- Processo duplicado agora copia os campos de dotação orçamentária

---

## [1.11.8] — 2026-06-17

### Melhorado
- **Etapa 9 renomeada para "Publicação no PNCP / Diário Oficial"** — subtítulo atualizado com referência ao Art. 54, §1º além do Art. 75, §3º
- **Extrato para Diário Oficial movido para a Etapa 9** — o botão "Gerar Extrato para Diário Oficial" saiu do cabeçalho do processo e passou a aparecer dentro da etapa de publicação, que é o momento correto de sua geração (publicação simultânea PNCP + Diário Oficial)

---

## [1.11.7] — 2026-06-17

### Melhorado
- **Aviso de Dispensa — ajustes de texto e campos configuráveis:**
  - Parágrafo de abertura inclui agora "e no Termo de Referência" ao final
  - "Das Condições de Participação" — participação condicionada ao Aviso **e ao Termo de Referência**
  - Desclassificação (iii) ampliada para "neste Aviso e no Termo de Referência"
  - Referência ao TR disponível agora inclui o site oficial do município (quando configurado)
  - Divulgação do resultado agora inclui URLs do site oficial e do Diário Oficial Eletrônico (quando configurados)
- **Configurações — novos campos de publicidade digital:**
  - **Site Oficial** (`site_oficial`) — URL do portal da transparência/prefeitura
  - **URL do Diário Oficial Eletrônico** (`diario_url`) — usados automaticamente no Aviso de Dispensa

---

## [1.11.6] — 2026-06-17

### Melhorado
- **Aviso de Dispensa de Licitação — conteúdo jurídico aprimorado** com base no modelo em uso pelo Município de Orindiúva e na Lei 14.133/2021:
  - **Parágrafo de abertura** ("torna público") com referência explícita ao §3º do Art. 75 e à solicitação de "propostas adicionais"
  - **"Da Participação"** — adicionada cláusula de que não haverá sessão pública presencial nem eletrônica; canal de esclarecimentos e acesso ao TR
  - **"Do Critério de Julgamento e da Proposta Mais Vantajosa"** (nova seção, substituindo "Do Critério de Seleção") — texto juridicamente robusto declarando que o menor preço por si só não é suficiente; propostas que não atendam às especificações do TR são desclassificadas (Art. 59); inciso do Art. 33 referenciado conforme critério selecionado; texto da "proposta mais vantajosa" adaptado dinamicamente para cada critério (menor preço, maior desconto, melhor técnica, técnica e preço, maior retorno econômico)
  - **"Do Resultado e Da Habilitação"** (nova seção) — convocação da proposta mais vantajosa em 2 dias úteis (Art. 62) e divulgação do resultado nos meios oficiais

---

## [1.11.5] — 2026-06-17

### Adicionado
- **Documento: Justificativa de Enquadramento Legal (Etapa 5)** — novo documento gerado na etapa de Enquadramento Legal, conforme exigência do Art. 72, III da Lei 14.133/2021 ("justificativa para a contratação direta"). O documento inclui tabela de identificação do processo, corpo jurídico declarando o enquadramento no inciso do Art. 75 aplicável, campo de observações complementares, referência expressa à base legal (Art. 72, III) e bloco de assinatura do Agente de Contratação. O texto é gerado automaticamente com os dados do processo, fundamento legal selecionado e responsável preenchido na etapa.

---

## [1.11.4] — 2026-06-17

### Melhorado
- **Texto do objeto justificado em todos os contextos** — `text-align: justify` aplicado em todas as ocorrências do objeto: impressão do processo (PDF), Relatório Geral, Mapa de Preços, tabela de processos (visão lista), Ata de Sessão e todos os documentos gerados com tabelas de campos

---

## [1.11.3] — 2026-06-17

### Adicionado
- **Etapa 6 — Parecer Jurídico da Procuradoria-Geral** — nova etapa inserida entre Enquadramento Legal e Autorização da Autoridade Competente, conforme Art. 53 da Lei 14.133/2021. Campo "Nº do Parecer Jurídico" disponível. Todos os índices de etapas subsequentes foram atualizados nos geradores de documentos (Aviso de Dispensa, Ata de Sessão, Extrato de Contrato). Migração automática insere a etapa vazia em processos existentes sem necessidade de ação manual.

### Melhorado
- **Texto do objeto justificado nos cards do dashboard e na tela de detalhe do processo**

---

## [1.11.2] — 2026-06-15

### Adicionado
- **Critério de Seleção por processo (Art. 33, Lei 14.133/2021)** — novo campo no cadastro e na tela de detalhe do processo com as cinco opções previstas em lei: Menor preço (I), Maior desconto (II), Melhor técnica ou conteúdo artístico (III), Técnica e preço (IV) e Maior retorno econômico (VI). O critério selecionado é exibido automaticamente no Aviso de Dispensa (seção "Do Critério de Seleção") e na Ata de Sessão (coluna Situação da proposta vencedora). Processos existentes assumem "Menor preço" como padrão retroativo.

### Corrigido
- **Race condition na seleção de método de cotação (média/mediana)** — o `onchange` inline dos radio buttons disparava `saveProcess` e `_autoFillValorEstimado` (que também chama `saveProcess`) de forma concorrente, causando saves sobrepostos e re-renders embaralhados. Substituído por função dedicada `setCotacaoMetodo()` que executa a sequência de forma serializada (await)
- **`renderChecklist` adiava re-render indevidamente para radio buttons** — a lógica de deferral (que protege texto em digitação) incluía `type="radio"` e `type="checkbox"`, fazendo o re-render aguardar o blur do radio selecionado e acumular renders duplicados. Deferral agora aplicado apenas a `text`, `textarea` e `select`
- **Variável `hasFilters` declarada duas vezes no mesmo escopo** — `SyntaxError` impedindo a inicialização do sistema; declaração duplicada na linha 2696 removida (a declaração na linha 2662 já era suficiente)

### Documentação
- **README.md** — adicionadas funcionalidades: alertas de validade de certidões, auto-backup automático com proteção de quota, Factory Reset com 3 etapas de confirmação, detecção de primeiro uso, método de cotação por processo; Decreto nº 11.317/2022 incluído na Base Legal
- **MANUAL.html** — atualizado de v1.9.0 para v1.11.1: nota de onboarding na seção 2.1; ciclo de 3 estados das etapas corrigido (Pendente → Concluída → Bloqueada) na seção 7.2; alertas visuais de validade de certidões documentados na seção 8B.1; Despacho de Habilitação, Termo de Adjudicação e Termo de Homologação adicionados à tabela de documentos; Factory Reset e auto-backup documentados na seção 12

---

## [1.11.1] — 2026-06-15

### Corrigido
- **[M2] Termo de Adjudicação usava fornecedor vinculado ao invés da proposta vencedora** — nome e CNPJ agora são lidos diretamente de `propVencedora.fornecedor` e `propVencedora.cnpj`, com fallback para `proc.fornecedor`
- **[M6] Auto-backup sem tratamento de quota do localStorage** — verificação de tamanho antes de salvar (aviso ao usuário se >4 MB); captura `QuotaExceededError` com toast de orientação para backup manual
- **[M10] Re-render do checklist destruía campo em edição** — `renderChecklist` agora detecta se há input/textarea/select com foco dentro do checklist e adia o render para o evento `blur`; preserva o conteúdo digitado
- **[B1] Filtro "De" do dashboard com fuso horário incorreto** — `new Date(fDe)` tratava a data como UTC meia-noite, excluindo processos criados no dia selecionado antes das 21h (UTC-3); corrigido para `new Date(fDe + 'T00:00:00')` em todos os filtros de data do sistema
- **[B5] Estado "bloqueada" inacessível pelo clique no círculo de status** — ciclo alterado de `pending ↔ done` para `pending → done → blocked → pending`; tooltip atualizado
- **[B6] Campos críticos aceitos em branco nas configurações** — `saveSettings` agora exibe aviso específico quando Órgão, Município ou Nome da Autoridade Competente estão em branco ao salvar
- **[B7] Upload de brasão falha silenciosamente para imagens grandes** — validação de tamanho (máx. 3 MB) antes da leitura; captura de `QuotaExceededError` do localStorage com mensagem orientando o usuário; handler `onerror` no FileReader
- **[B8] Busca global limitada a 20 resultados sem indicação** — limite aumentado para 50; quando truncado, exibe rodapé "Exibindo 50 de X resultados — refine a busca"
- **[B9] Tecla Escape não fechava modais de certidão e fornecedor** — handler global de `Escape` agora fecha em cascata: busca global → certidão → fornecedor → modal de criação
- **[B12] Ata seção VII usava `v(9,'cnpj')` que nunca existe** — campo `cnpj` não faz parte de `STEPS[9].fields`; substituído por `vencedora.cnpj || proc.fornecedor?.cnpj`

---

## [1.11.0] — 2026-06-15

### Corrigido
- **[Alto] Textos dos fundamentos legais Art. 75, I e II com valores desatualizados** — limites anteriores (R$ 30.000 e R$ 50.000 da Lei 8.666) substituídos pelos valores vigentes do Decreto nº 11.317/2022 (R$ 130.984,20 para obras/engenharia; R$ 65.492,11 para bens e serviços); referência ao Decreto incluída no texto do fundamento que é inserido nos documentos
- **[Alto] Despacho de Inabilitação listava certidões de engenharia não aplicáveis como pendentes** — certidões com flag `engenharia: true` eram incluídas no motivo de inabilitação mesmo quando o processo não era de engenharia; corrigido com verificação de `saved._engenharia` espelhando a lógica da UI
- **[Alto] Valor adjudicado não propagado automaticamente ao Termo de Adjudicação** — ao marcar uma proposta como vencedora, o campo `valor_adjudicado` da etapa de Adjudicação agora é preenchido automaticamente com o valor da proposta (somente se ainda estiver vazio, preservando edições manuais)
- **[Alto] Cards de estatísticas não refletiam filtros ativos do dashboard** — Total, Em andamento, Concluídos e Não iniciados eram calculados sobre todos os processos independentemente dos filtros; agora refletem a lista filtrada; o campo Total exibe tooltip com o total global quando há filtros ativos
- **[Alto] Painel de fracionamento exibia "—" para todos os processos relacionados** — campo `q.num` inexistente no modelo de dados; substituído pela mesma lógica de exibição usada no restante do sistema (`DL {num_dl}` ou `PA {num_proc}`)
- **[Alto] Certidões vencidas ou próximas do vencimento sem alerta visual** — certidões com `data_validade` já expirada agora exibem badge "⚠ Vencida" em vermelho e barra lateral vermelha; certidões vencendo em até 30 dias exibem badge "⚠ Vence em breve" em âmbar; campo de data de validade é destacado na mesma cor

### Melhorado
- **Método de cálculo de cotações (média/mediana) salvo por processo** — o método agora é persistido em `currentProcess.cotacao_metodo` além do `localStorage`; ao abrir um processo, o método selecionado anteriormente para aquele processo específico é restaurado automaticamente, sem afetar outros processos abertos no mesmo navegador
- **Backup completo inclui configurações e brasão** — `exportBackup` passa a incluir `sgcd-user` e `sgcd-brasao-dataurl` do `localStorage` no arquivo exportado (formato v3); `importBackup` restaura ambos automaticamente ao importar backups v3+

---

## [1.10.9] — 2026-06-15

### Corrigido
- **[Crítico] Termos de Adjudicação e Homologação gerados em branco** — `gerarTermoAdjudicacao` e `gerarTermoHomologacao` buscavam a etapa por `s.name === 'Adjudicação'` em `proc.steps`, mas o nome vive em `STEPS[]` e não no objeto salvo; `findIndex` sempre retornava `-1` e todos os campos dos documentos saíam vazios. Corrigido para usar a flag booleana `STEPS.findIndex(s => s.adjudicacao)` e `STEPS.findIndex(s => s.homologacao)`
- **[Crítico] Trilha de auditoria excluída do backup** — `exportBackup` e `importBackup` não incluíam o store `auditGlobal`; um ciclo de exportar/importar destruía permanentemente toda a rastreabilidade dos atos administrativos. Auditoria agora incluída no backup (versão do formato atualizada para `2`)
- **[Crítico] Alterações de campos das etapas sem registro na trilha de auditoria** — `updateField` salvava valores (responsável, datas, observações, valor estimado, fundamentação) sem gerar nenhum evento de auditoria. Agora registra evento `CAMPO_ALTERADO` para todos os campos não-internos (exceto `_propostas`, `_cotacoes`)
- **[Crítico] Alerta de processos parados ignorava data da última etapa concluída** — `completedAt` era salvo como string `"YYYY-MM-DD"` e passado para `Math.max`, retornando sempre `NaN`; o alerta usava apenas a data de criação do processo. `completedAt` agora é salvo como timestamp numérico (`Date.now()`); `fmtDate` e `renderStallAlerts` atualizados para suportar tanto o novo formato quanto o legado
- **[Crítico] Onboarding ausente no primeiro uso** — ao abrir o sistema pela primeira vez com `localStorage` vazio, o usuário entrava direto no dashboard podendo gerar documentos com nome, órgão e autoridade em branco. Agora detecta ausência de `u.nome` e redireciona automaticamente para as Configurações com mensagem de boas-vindas

---

## [1.10.8] — 2026-06-15

### Corrigido
- **Modais do Factory Reset com fundo opaco** — os painéis das confirmações 2 e 3 usavam `var(--bg-card)` (variável CSS não definida no SGCD), o que resultava em fundo transparente; substituído por cores absolutas detectadas dinamicamente conforme o tema (`#2a2a2a` no modo escuro, `#ffffff` no modo claro)
- **Botão Cancelar visível em todas as 3 etapas** — as confirmações 2 e 3 agora exibem botão "✕ Cancelar" com estilo distinto e claramente visível; a confirmação 1 (via `customConfirm`) já possuía cancel nativo
- **Botão final da confirmação 3 desabilitado visualmente** — durante a contagem regressiva o botão exibe `opacity: 0.5` e cursor `not-allowed`, tornando claro que ele está aguardando; ao zerar o contador fica totalmente habilitado
- **Botão confirmar da etapa 2 desabilitado visualmente** — `opacity: 0.5` e cursor `not-allowed` enquanto a frase digitada não coincide exatamente com "APAGAR TUDO"
- **Indicadores de etapa** — os cabeçalhos das confirmações 2 e 3 indicam a etapa atual (ex.: "🔐 Confirmação de segurança (2/3)")

---

## [1.10.7] — 2026-06-15

### Adicionado
- **Factory Reset / Wipe Data** — novo botão na "Zona de Perigo" das Configurações; apaga permanentemente todos os processos, fornecedores, arquivos, trilha de auditoria e configurações do sistema; protegido por 3 confirmações distintas: (1) aviso geral com lista do que será apagado, (2) digitação obrigatória da frase "APAGAR TUDO", (3) contagem regressiva de 5 segundos antes do botão final ser habilitado; um backup completo é exportado automaticamente antes do wipe ser executado; ao concluir, a página é recarregada

---

## [1.10.6] — 2026-06-15

### Corrigido
- **Data final da Ata alinhada à direita** — linha de local e data no encerramento da Ata agora usa `.city-date` (alinhada à direita, margem e fonte idênticas aos demais documentos)

---

## [1.10.5] — 2026-06-15

### Corrigido
- **Ata de Sessão alinhada ao padrão dos demais documentos** — cabeçalho reestruturado com div `.header` (bordas, espaçamento e brasão no padrão), município exibido abaixo do órgão, título da ata em `<h3>` consistente com os outros documentos, e nomes dos signatários (agente, autoridade e representante do fornecedor) agora exibidos em negrito nas assinaturas

---

## [1.10.4] — 2026-06-15

### Corrigido
- **Nomes em negrito nas assinaturas** — em todos os documentos gerados (Autorização, Extrato, Ata, Despacho de Inabilitação, Despacho de Habilitação, Aviso de Dispensa, Termo de Adjudicação, Termo de Homologação, Extrato de Contrato e Relatório), o nome do signatário agora aparece em negrito no bloco de assinatura

---

## [1.10.3] — 2026-06-15

### Corrigido
- **Assinatura do Termo de Adjudicação** — removida linha duplicada "Agente de Contratação" que aparecia abaixo do cargo; matrícula agora fica na mesma linha do cargo
- **Valor no Termo de Adjudicação** — usa o valor da proposta marcada como "Vencedora" na etapa de recebimento de propostas; recorre ao campo `valor_adjudicado` ou ao valor do processo apenas se não houver proposta vencedora cadastrada
- **Sublinhado nas decisões** — termos **AUTORIZO**, **ADJUDICO** e **HOMOLOGO** agora aparecem sublinhados em seus respectivos documentos (Autorização, Termo de Adjudicação e Termo de Homologação)
- **Autoridade no Termo de Homologação** — usa corretamente `aut_nome` e `aut_cargo` das configurações; o campo Autoridade da Etapa 12 já é preenchido automaticamente com `aut_nome` ao abrir o processo

---

## [1.10.2] — 2026-06-15

### Adicionado
- **Sincronização do Valor Estimado (Etapa 4 → painel lateral)** — ao calcular a média ou mediana das cotações, o campo "Valor Estimado (R$)" nas Informações do Processo é atualizado automaticamente, mantendo consistência entre a etapa de pesquisa de preços e os demais documentos gerados
- **Termo de Adjudicação** — novo documento gerado pela Etapa 11 (Adjudicação); formaliza a declaração do vencedor pelo agente de contratação com identificação do processo, fornecedor adjudicatário, valor e texto de decisão fundamentado no art. 18, §1º da Lei 14.133/2021
- **Termo de Homologação** — novo documento gerado pela Etapa 12 (Homologação); formaliza a aprovação do procedimento pela autoridade competente com resumo de todo o trâmite, valor homologado e assinatura do ordenador de despesa (Art. 71 da Lei 14.133/2021)

---

## [1.10.1] — 2026-06-15

### Corrigido
- **Cálculo de média das cotações** — `fmtMoney()` recebia um número JS puro (ex: `47386.6`) e removia o ponto decimal ao tratar como separador de milhar, resultando em valor 10× maior (ex: R$ 473.866,00 em vez de R$ 47.386,60); corrigido usando `toLocaleString('pt-BR')` diretamente
- **Radio Média/Mediana recalcula valor estimado** — ao clicar em Média ou Mediana, o campo "Valor Estimado" agora é atualizado imediatamente (anteriormente só atualizava ao adicionar/remover cotações)
- **Data no Aviso de Dispensa** — prazo para propostas era exibido no formato `YYYY-MM-DD`; agora formatado como `DD/MM/AAAA` em português brasileiro
- **Botão Gerar Autorização movido** — saiu do cabeçalho do processo e passou para dentro da Etapa 6 (Autorização da Autoridade Competente), junto com os demais botões de geração de documentos contextuais

---

## [1.10.0] — 2026-06-15

### Adicionado
- **Cálculo automático de valor de referência (Etapa 4)** — ao cadastrar, alterar ou remover cotações, o campo "Valor Estimado" é preenchido automaticamente com a média aritmética ou mediana das cotações com situação "Válida"; o método é selecionável por radio button e persistido localmente; a etapa exibe um resumo "Valor de referência calculado" em tempo real
- **Fundamento Legal como seleção (Etapa 5)** — campo substituído por `<select>` com todos os 16 incisos do Art. 75 da Lei 14.133/2021; valor salvo como texto completo para compatibilidade com documentos gerados
- **Aviso de Dispensa** — novo documento gerado pela Etapa 7 ("Elaboração do Aviso de Dispensa"); inclui seções de objeto, fundamentação, condições de participação, critério de seleção e assinatura da autoridade competente; campos `prazo_propostas` e `endereco_envio` adicionados à etapa
- **Despacho de Habilitação** — novo documento na Etapa 10; complementa o Despacho de Inabilitação existente; gerado quando o fornecedor apresenta toda a documentação de regularidade; lista as certidões verificadas com datas de validade e declara formalmente o fornecedor habilitado
- **Extrato de Contrato** — novo documento gerado pela Etapa 14; formatado para publicação no Diário Oficial e PNCP; contém todos os dados contratuais, identificação das partes, objeto, vigência, valor e espaço para assinatura bilateral
- **Campos ampliados no Instrumento Contratual (Etapa 14)** — novos campos: Data de Assinatura, Vigência Inicial, Vigência Final, Valor do Contrato, Contratante, Contratado, CNPJ do Contratado, Gestor do Contrato, Fiscal do Contrato; contratante e contratado são pré-preenchidos automaticamente das configurações e do fornecedor vencedor

---

## [1.9.0] — 2026-06-15

### Alterado
- **Etapas 4 e 5 unificadas** — as etapas "Pesquisa de Preços" e "Pesquisa de Preços / Estimativa de Valor" foram fundidas em uma única etapa **"Pesquisa de Preços / Estimativa do Valor"**, eliminando redundância no checklist (de 16 para 15 etapas)
- **Cadastro de cotações na etapa unificada** — nova seção de cotações dentro da etapa com campos: fornecedor, CNPJ, valor cotado, data da cotação, situação (Válida / Descartada) e observações; suporta múltiplas cotações com adição e remoção individuais
- **Ata de Sessão atualizada** — nova seção "IV — Cotações Recebidas" com tabela das cotações registradas; seções renumeradas (Propostas passa a ser seção V); referências de índice de etapas ajustadas em toda a geração de documentos

---

## [1.8.1] — 2026-06-14

### Corrigido
- **Crash em todos os geradores de documento** — `window.open` retorna `null` quando bloqueador de popup está ativo; adicionada verificação com toast de aviso ao usuário
- **Brasão personalizado ignorado na Ata de Sessão** — `gerarAta` embutia o base64 do brasão diretamente sem o marcador `__BRASAO_PLACEHOLDER__`; `_gerarDocumento` agora detecta esse caso e substitui qualquer base64 longo de imagem pelo brasão personalizado
- **"Carregar mais" na auditoria duplicava linhas** — `renderAudit(true)` fatiava `filtered` de índice 0 (não do offset corrente) e anexava todas as linhas novamente; corrigido para fatiar apenas o bloco novo
- **Clique duplo no checkbox de etapa podia corromper o status** — `cycleStatus` é async mas chamado de `onclick` sem await; adicionado lock `_cycleStatusLock` para impedir chamadas concorrentes
- **Race condition ao alterar dois campos de data de certidão em sequência** — `updateCertidao` chamava `_syncCertToForn` diretamente (read-modify-write concorrente); substituído por `_debouncedSyncCertToForn` (400 ms de inatividade antes de sincronizar)
- **Limpar data de certidão no processo não limpava no fornecedor** — `_syncCertToForn` usava `||` para emissão/validade, tornando string vazia falsy; substituído por `??` (nullish coalescing)
- **Marcar certidão como N/A deixava datas fantasmas no fornecedor** — `cycleCertidao` excluía datas localmente mas não chamava `_syncCertToForn`; ao sair de 'obtida', as datas agora são limpas também no cadastro do fornecedor
- **Falha silenciosa ao remover arquivo** — `dbGet` antes do `dbDelete` em `deleteFile` podia lançar exceção e abortar a deleção sem feedback; o `dbGet` agora está em `try/catch` e a deleção prossegue mesmo que a leitura falhe
- **Edições no QSA do fornecedor não eram registradas na auditoria** — `_camposForn` não incluía `qsa`; adicionada comparação separada via `JSON.stringify` para detectar e auditar alterações societárias
- **Scan completo do IndexedDB a cada tecla no filtro de usuário da auditoria** — `oninput` chamava `renderAudit()` sem debounce; substituído por `renderAuditDebounced()` com atraso de 300 ms

---

## [1.8.0] — 2026-06-14

### Adicionado
- **Store `auditGlobal` no IndexedDB** — trilha de auditoria global independente dos processos; sobrevive à exclusão de processos; DB_VER atualizado para 3
- **`_auditEvento(evento, detalhe, processId)`** — função central de auditoria que grava no store `auditGlobal`; falha silenciosa (não interrompe o fluxo do sistema)
- **`_getAuditor()`** — identifica o usuário com nome + matrícula (ex.: `João Silva (mat. 1234)`); usado em todos os registros de auditoria
- **Cobertura de eventos auditados (Nível 1 e 2):**
  - `ETAPA_DONE / ETAPA_BLOCKED / ETAPA_PENDING` — mudanças de status de etapa com usuário
  - `ARQUIVO_ANEXADO` — nomes dos arquivos + etapa
  - `ARQUIVO_REMOVIDO` — nome do arquivo + etapa; timeline do processo atualizada
  - `DOCUMENTO_GERADO` — todos os 8 documentos do sistema (Ata, Autorização, Extrato, Mapa de Preços, Despacho de Recusa, Despacho de Inabilitação, Relatório Geral, Relatório de Fornecedores) + Relatório de Auditoria
  - `PROCESSO_EXCLUIDO` — PA, DL e objeto gravados antes da exclusão
  - `CERTIDAO_ATUALIZADA` — campo alterado com valor anterior e novo
  - `CERTIDAO_SINCRONIZADA` — sincronização certidão ↔ fornecedor
  - `FORNECEDOR_ALTERADO` — lista de campos alterados no cadastro do fornecedor
  - `CAMPO_ALTERADO` — campos do painel de informações e edição inline do objeto
- **Usuário na timeline do processo** — entradas de timeline agora registram `user` (nome + matrícula); exibido no histórico do processo
- **View de Auditoria** — nova seção acessível pela sidebar com ícone de trilha; filtros por tipo de evento, período (de/até) e usuário; paginação de 50 registros por vez
- **Relatório de Auditoria imprimível** — gerado pela view de auditoria respeitando filtros ativos; mesmo padrão visual dos demais documentos; registra a própria geração no log

### Alterado
- **`showDash`, `showFornecedores`, `showSettings`, `openProcess`** — refatorados para usar `_hideAllViews()` (garante que a nova view-audit seja ocultada corretamente na navegação)
- **Log de auditoria por campo** — campo `user` agora usa `_getAuditor()` (inclui matrícula); certidões auditadas incluem nome da certidão e campo alterado no formato legível

## [1.7.0] — 2026-06-14

### Adicionado
- **Despacho de Recusa / Desclassificação de Proposta** — documento jurídico gerado na etapa 10 para propostas marcadas como "Recusada"; fundamentado no Art. 59 da Lei 14.133/2021 e Art. 50 da Lei 9.784/1999; inclui seção "Do Direito de Manifestação" e código de autenticidade
- **Despacho de Inabilitação** — documento jurídico gerado na etapa 11 quando o fornecedor é inabilitado; lista as certidões pendentes como motivação; fundamentado no Art. 69 e Art. 72 da Lei 14.133/2021
- **Datas de emissão e validade nas certidões da etapa 11** — cada certidão com status "Obtida" exibe campos de emissão e validade, alinhados ao cadastro de fornecedores
- **Sincronização bidirecional certidões ↔ fornecedor** — datas informadas na etapa 11 são automaticamente gravadas no cadastro do fornecedor vinculado, e vice-versa; indicador "⇄ fornecedor" exibido nas certidões sincronizáveis
- **Lista unificada de certidões** — CERTIDOES e CERT_TIPOS fundidos em uma única lista mestra de 21 itens, cobrindo: CNPJ, QSA, SICAF, TCU, CGU, CNJ, TCESP, Portal Transparência, CND Federal, CND Estadual, CND Municipal, FGTS, CNDT, Simples Nacional, Certidão de Falência e documentos de engenharia (SUSEP)
- **Migração automática de dados** — ao iniciar, o sistema converte automaticamente IDs antigos de certidões (`cnd_federal`, `cnd_estadual`, `crf_fgts`) para os novos IDs unificados

### Alterado
- **Configurações migradas para view inline** — a tela de configurações deixou de ser um modal flutuante e passou a ser uma view dedicada na navegação principal, com comportamento consistente com as demais seções
- **Constante `SGCD_VERSION`** — versão centralizada em uma única constante JS; título da aba do navegador e rodapé da página inicial passaram a usar a constante (eliminando valores literais desatualizados)
- **Configurações aplicadas em todos os documentos** — nome, cargo, matrícula do agente e dados da autoridade competente são sempre lidos das configurações; nenhum dado pessoal está mais fixado no código

### Corrigido
- **Título da aba do navegador** exibia `v${SGCD_VERSION}` literal em vez do valor real
- **Rodapé da página inicial** exibia `v${SGCD_VERSION}` literal em vez do valor real
- **Badge "⇄ fornecedor"** aparecia em consultas sem validade (CNPJ, QSA, TCU); restringido a certidões com `diasPadrao` definido
- **Sincronização indevida** de certidões sem validade (ex.: consultas TCU, "Outra") para o cadastro do fornecedor
- **Falha silenciosa no startup**: erro na migração de dados não impedia mais o carregamento da aplicação; erros fatais de inicialização exibem alerta ao usuário

---

## [1.6.0] — 2026-06-13

### Adicionado
- **Numeração automática (PA/DL)** — ao abrir o modal de novo processo, os campos são pré-preenchidos com o próximo número disponível para o ano corrente (editável)
- **Duplicar processo** — botão "⎘ Duplicar" no cabeçalho copia dados do processo com checklist zerado; solicita confirmação
- **Edição inline do objeto no card** — duplo clique no título do card permite editar o objeto diretamente na listagem
- **Reordenação de etapas por arrastar** — alça de arraste (⠿) em cada etapa do checklist; botão "↺ Ordem padrão" aparece ao reordenar
- **Busca global (Ctrl+K)** — pesquisa simultânea por PA, DL, objeto, fornecedor, unidade e status em todos os processos; acessível pelo atalho de teclado
- **Brasão personalizado** — opção nas configurações para substituir o brasão padrão pela imagem do município; aplicado em todos os documentos gerados
- **Código de autenticidade** — todos os documentos gerados (Extrato, Autorização, Mapa de Preços, ATA) exibem código único no rodapé baseado em hash do processo
- **Snapshot automático** — opção nas configurações para salvar cópia local (sem anexos) ao fechar a aba; sistema oferece restaurar na próxima abertura se os dados estiverem desatualizados
- **Log de auditoria por campo** — toda alteração de campo no painel de informações é registrada com valor anterior, novo valor, data/hora e usuário; exibido em card colapsável no detalhe do processo

### Alterado
- **Nomenclatura da etapa 5** — renomeada de "Mapa de Preços / Estimativa de Valor" para "Pesquisa de Preços / Estimativa de Valor" para diferenciar da etapa 10

---

## [1.5.0] — 2026-06-13

### Adicionado
- **Vínculo de fornecedor do cadastro às propostas** — botão 📋 em cada proposta abre modal de busca no cadastro de fornecedores; ao selecionar, preenche razão social e CNPJ automaticamente
- **Mapa de Preços** — documento imprimível com tabela comparativa de propostas, valor de referência (média das válidas) e assinatura do agente de contratação
- **Campos adicionais nas propostas** — Data da proposta e Validade por proposta
- **Resumo automático de propostas** — exibe total de propostas, vencedora com valor e valor de referência diretamente na etapa
- **Verificação de conformidade** — botão "✔ Conformidade" no cabeçalho do processo verifica: objeto, fundamentação, valor, unidade, número, fornecedor vinculado, quantidade de propostas, proposta vencedora, certidões e checklist
- **Visualização em tabela** — alternativa aos cards no dashboard; exibe PA/DL, objeto, unidade, fornecedor, valor, prazo, progresso e status; preferência salva em `localStorage`
- **Exportar CSV** — exporta processos visíveis (respeitando filtros ativos) com BOM UTF-8 para compatibilidade com Excel

### Alterado
- **Proposta vencedora** — ao marcar uma proposta como "Vencedora": garante unicidade (demais viram "Aceita"), sincroniza automaticamente `p.fornecedor` com o vencedor (do cadastro ou manual), e atualiza o cabeçalho do processo

---

## [1.4.0] — 2026-06-13

### Adicionado
- **Prazo para conclusão** — campo de data nos processos com alerta visual (vermelho) no card e no cabeçalho do detalhe quando vencido
- **Notificações de processos parados** — painel amarelo no dashboard quando há processos em andamento sem movimentação há mais de 15 dias ou com prazo vencido; clicável para abrir o processo
- **Extrato de publicação** — documento para o Diário Oficial com fundamento no Art. 54, §1º da Lei 14.133/2021; botão "📰 Extrato" no cabeçalho do processo
- **Ordenação da lista** — select no painel de filtros com opções: Data (recente/antigo), Prazo (urgente), Progresso (↑/↓) e Valor (↑/↓)
- **Fornecedor no card** — razão social do fornecedor vencedor exibida na linha de meta do card do processo
- **Dois números de controle** — campos separados para Processo Administrativo (PA) e Dispensa de Licitação (DL) em substituição ao campo único de número

### Alterado
- **Impressão do processo** — `printProcess()` gera janela dedicada com cabeçalho institucional, grid de informações, barra de progresso, checklist completo com campos preenchidos por etapa, e impressão automática
- **Etapa em destaque** — ao expandir uma etapa do checklist, o card recebe borda laranja + halo + fundo aquecido para facilitar a visualização

### Corrigido
- **Ordenação por valor** — `p.valor` era string formatada (`"R$ 1.234,56"`); adicionada função `parseValor()` que converte corretamente antes de comparar
- **Filtros de faixa de valor** — mesma correção aplicada aos filtros mín/máx do dashboard e do relatório

---

## [1.3.0] — 2026-06-13

### Adicionado
- **Filtros avançados no dashboard** — filtro por unidade/secretaria (dropdown automático), período de criação (de/até) e faixa de valor (mín/máx); botão "✕ Limpar filtros" aparece quando há filtros ativos
- **Relatório resumido** — relatório imprimível agrupado por status com subtotais e total geral; respeita os filtros ativos do dashboard
- **Verificação de impedimento (CEIS/CNEP)** — botões de acesso rápido no detalhe do fornecedor: CEIS, CNEP (portal TCU) e Sanções (Portal da Transparência com CNPJ pré-preenchido)
- **Backup e restauração de dados** — exporta todos os processos, fornecedores e arquivos para `.json`; restauração com confirmação e validação de formato; arquivos serializados em Base64
- **Autorização de Abertura** — documento formal conforme Lei 14.133/2021 com brasão, despacho, tabela de dados e assinatura da autoridade competente

### Alterado
- **Campo responsável por etapa** — confirmado como já presente em todos os 16 passos do checklist com label "Responsável"

---

## [1.2.0] — 2026-06-13

### Adicionado
- **Sidebar de navegação** — barra lateral fixa com ícones para Processos, Fornecedores, Configurações e alternância de tema; tooltip ao hover
- **Stat cards com ícones SVG** — ícones ilustrativos nos cards de estatística do dashboard; cor de fundo diferenciada por status (verde = concluídos, amarelo = em andamento)
- **Barra de progresso nos cards** — barra visual de progresso das etapas no rodapé de cada card do processo
- **Sistema de ícones SVG** — constante `ICONS` com ícones Lucide-style (pasta, relógio, check, pausa, prédio, engrenagem, lua, sol, moeda, calendário); substitui emojis em toda a interface
- **Skip link de acessibilidade** — link "Ir ao conteúdo principal" para navegação por teclado
- **Cursor pointer** — aplicado a todos os elementos clicáveis (cards, etapas, certidões, fornecedores)

### Alterado
- **Título centralizado** — "SGCD — Sistema de Gestão de Contratação Direta" posicionado ao centro do cabeçalho via `position: absolute`
- **Remoção do uppercase universal** — `text-transform: uppercase` removido de `*` e `body`; mantido apenas onde intencional (labels, badges)
- **Cards com borda lateral colorida** — substituição do design anterior por `pc-stripe` (4px colorida) + `pc-body`; badge de status movido inline ao número
- **Alternância de tema** — botão de tema migrado para a sidebar; ícone atualiza entre lua/sol via `ICONS`

---

## [1.1.0] — 2026-06

### Adicionado
- **Cadastro de fornecedores** — consulta automática de CNPJ via BrasilAPI; armazena razão social, nome fantasia, situação cadastral, endereço, porte, CNAE, natureza jurídica e QSA
- **Certidões do fornecedor** — controle de certidões negativas com status (Pendente / Obtida / N/A), datas, anexos e alertas de vencimento no dashboard
- **Detecção de fracionamento** — análise automática de processos com objetos similares que somados possam configurar fracionamento ilegal; alertas visuais nos cards
- **Geração da Ata de Sessão** — documento completo com brasão, identificação do processo, fornecedor, certidões, valores e assinatura
- **Mapa de preços (propostas)** — etapa de avaliação com múltiplas propostas, situações e observações
- **Upload de arquivos por etapa** — anexar documentos PDF/DOCX/imagens em cada etapa do checklist; download e remoção
- **Histórico/timeline** — registro automático de ações no processo (criação, conclusão de etapa, etc.)
- **Classificação do objeto** — categorização por natureza, categoria e subcategoria para controle de fracionamento

---

## [1.0.0] — 2026-06

### Adicionado
- **Estrutura base SPA** — aplicação single-file HTML com IndexedDB (stores: `processes`, `files`, `fornecedores`)
- **Dashboard de processos** — listagem com cards, busca textual, filtro por status e estatísticas (total, em andamento, concluídos, não iniciados)
- **Checklist de 16 etapas** — fluxo completo de instrução processual conforme Lei 14.133/2021: DFD, TR, pesquisa de preços, seleção do fornecedor, habilitação, autorização, publicação, assinatura, execução e encerramento
- **Status por etapa** — ciclo Pendente → Em andamento → Concluído → Bloqueado
- **Campos por etapa** — responsável, datas, observações e campos específicos por etapa
- **Tema claro/escuro** — alternância com persistência em `localStorage`
- **Modal de novo processo** — objeto, fundamentação legal (Art. 75 incisos I–IV), valor estimado e unidade solicitante
- **Painel de informações editável** — edição inline dos metadados do processo diretamente no detalhe
- **Configurações** — nome do agente, cargo, matrícula, órgão, município e dados da autoridade competente
- **Impressão básica** — `window.print()` com CSS de impressão que oculta controles
- **Toasts de notificação** — mensagens de sucesso/erro com auto-dismiss
- **Confirmação de ações destrutivas** — modal customizado para exclusão de processos e arquivos

---

> **Legenda de tipos de mudança:**  
> `Adicionado` — nova funcionalidade  
> `Alterado` — mudança em funcionalidade existente  
> `Corrigido` — correção de bug  
> `Removido` — funcionalidade removida  
> `Segurança` — correção de vulnerabilidade
