# Changelog — SGCD
## Sistema de Gestão de Contratação Direta
> Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/)  
> Versionamento semântico: [SemVer](https://semver.org/lang/pt-BR/)

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
