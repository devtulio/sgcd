# Changelog — SGCD
## Sistema de Gestão de Contratação Direta
> Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/)  
> Versionamento semântico: [SemVer](https://semver.org/lang/pt-BR/)

---

## [1.19.0] — 2026-06-27

### Melhorado
- **Cache de elementos DOM (`_dom()`)** — 34 elementos estáticos cacheados em inicialização lazy; elimina `getElementById` nos hot paths de `renderDash()`, `toast()`, `_showSaveIndicator()` e `_hideSaveIndicator()`
- **`_getDashFilters()`** — leitura única dos 7 filtros do dashboard por chamada a `renderDash()`, substituindo 21 chamadas individuais a `getElementById` distribuídas em três funções
- **`_applyDashFilters()`** — lógica de filtro centralizada; elimina 45 linhas duplicadas entre `renderDash()`, `gerarRelatorio()` e `exportarCSV()`
- **`_lastFiltered`** — cache do último array filtrado de `renderDash()`; `gerarRelatorio()` e `exportarCSV()` reutilizam o resultado sem refazer O(n) de filtro
- **Debounce nos inputs de busca** — `_debounce()` genérico aplicado: 150ms em `#search` e `#forn-search`, 100ms na busca global (Ctrl+K), 150ms no picker de fornecedor em propostas
- **O(n²) → O(1) em `renderFornecedores()`** — `processes.find()` dentro de `.map()` substituído por `Map` construído uma vez antes do loop
- **Lazy expand nos cards de fornecedor** — render inicial limitado ao header (razão social, CNPJ, situação, porte, botão); conteúdo completo (certidões, QSA, contato, endereço, processos) injetado no DOM apenas ao abrir o card; reduz HTML inicial em ~65% por card
- **Redesign do gráfico de processos por mês** — card container com borda e padding; legenda HTML fora do SVG; sumário de métricas abaixo (total criados, concluídos com %, pico mensal); escala Y com inteiros calculados por `step` (1/2/5/10/20); labels de valor sobre barras quando há espaço; mês atual destacado em negrito; Janeiro exibe ano abreviado (Jan '25) para identificar virada de exercício; cores #2a78d6 (criados) e #1baf7a (concluídos); barras com canto superior arredondado (rx=3) e base reta

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
