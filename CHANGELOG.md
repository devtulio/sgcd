# Changelog — SGCD
## Sistema de Gestão de Contratação Direta
> Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/)  
> Versionamento semântico: [SemVer](https://semver.org/lang/pt-BR/)

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
