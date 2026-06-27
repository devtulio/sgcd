# SGCD — Sistema de Gestão de Contratação Direta

![Versão](https://img.shields.io/badge/versão-v2.0.0-blue) ![Lei](https://img.shields.io/badge/Lei-14.133%2F2021-green) ![Tecnologia](https://img.shields.io/badge/tecnologia-SQLite%20%2B%20REST%20API-orange) ![Licença](https://img.shields.io/badge/licença-MIT-green)

## Descrição

O **SGCD** é uma aplicação web multiusuário para gestão completa de processos de **Dispensa de Licitação** conforme a **Lei Federal nº 14.133/2021** (Nova Lei de Licitações e Contratos Administrativos). Desenvolvido para agentes de contratação pública, o sistema organiza todas as etapas do processo — da formalização da demanda até a publicação do contrato no PNCP — em um fluxo de trabalho guiado, com geração automática de documentos.

A partir da versão 2.0, os dados são armazenados em **SQLite** via servidor local (`server.py`) com autenticação multiusuário. Não requer instalação de dependências externas além do Python.

---

## Funcionalidades Principais

- **Checklist estruturado com 15 etapas** do processo de Dispensa de Licitação, cada uma com fundamento legal e orientação de preenchimento
- **Geração de documentos** prontos para assinatura e publicação: Autorização de Abertura, Aviso de Dispensa, Ata de Sessão, Mapa de Preços e Extrato de Contrato
- **Relatório geral** de processos com filtros por status, unidade, período e faixa de valor
- **Cadastro de fornecedores** com card expansível inline (visualização e edição sem modal), consulta automática de CNPJ via ReceitaWS/BrasilAPI e controle de certidões inline
- **Gestão de propostas** com mapa de preços comparativo e vínculo automático do fornecedor vencedor
- **Gestão de cotações** na etapa de pesquisa de preços com cálculo automático de média ou mediana como valor de referência
- **Fundamento legal** como seleção dos 16 incisos do Art. 75 da Lei 14.133/2021
- **Despacho de Recusa / Desclassificação** — gerado automaticamente na etapa 9 para propostas recusadas, com fundamentação jurídica e direito de manifestação
- **Despacho de Habilitação** — gerado na etapa 10 quando o fornecedor apresenta toda a documentação de regularidade, com lista das certidões verificadas
- **Despacho de Inabilitação** — gerado na etapa 10 quando o fornecedor é inabilitado, listando as certidões pendentes como motivação
- **Certidões unificadas** — lista de 21 certidões e consultas oficiais compartilhada entre a etapa 11 e o cadastro de fornecedores; sincronização automática bidirecional de datas de emissão e validade
- **Verificação de conformidade** automática: o sistema analisa o processo e aponta pendências e inconsistências
- **Alerta de fracionamento**: detecta processos com objetos similares e calcula a soma dos valores no exercício
- **Numeração automática** de Processo Administrativo (PA) e Dispensa de Licitação (DL)
- **Filtros avançados** no dashboard: busca textual, status, unidade, período, faixa de valor e ordenação múltipla
- **Exportação CSV** da lista de processos com filtros ativos
- **Busca global** (Ctrl+K) em todos os campos de todos os processos
- **Trilha de auditoria global** com timeline vertical agrupada por dia, ícones coloridos por categoria e filtros por tipo de evento, período e usuário — acessível pelo ícone de auditoria na barra lateral
- **Responsável preenchido automaticamente** — ao abrir um processo, o campo Responsável das etapas é preenchido automaticamente com o Agente de Contratação configurado nas configurações
- **Histórico e log de auditoria** com registro de data/hora de cada alteração
- **Anexo de documentos** por etapa (PDF, DOCX, imagens)
- **Backup e restauração** de dados em arquivo JSON
- **Notas internas por etapa** — campo de texto para anotações internas que não aparecem em nenhum documento gerado
- **Dotação orçamentária** — campos de Programa/Ação, Elemento de Despesa, Fonte e Dotação Completa por processo, preenchidos automaticamente nos documentos gerados
- **Cálculo automático de prazos (Art. 75 §3°)** — ao informar a data de publicação no PNCP, o sistema calcula automaticamente a data mínima de encerramento (3 dias úteis); alerta visual caso a data seja inferior ao mínimo legal
- **Controle de limite anual Art. 75, I e II** — painel lateral com acumulado do exercício e alerta quando o limite legal for atingido
- **Agenda de Vencimentos** — tela com encerramentos, vencimentos de contratos e prazos críticos agrupados por proximidade temporal
- **Vinculação entre processos** — vínculos relacionais entre processos (renovação, aditivo, continuidade); bidirecionais e clicáveis
- **Documento consolidado (PDF único)** — botão "📦 Processo Completo" gera um documento com todas as seções do processo
- **Visualização Kanban** — agrupa processos em colunas por fase (Instrução / Publicado / Análise / Adjudicação / Contratação / Concluído)
- **Notificações por e-mail via SMTP** — botão "✉ Notificar" com templates para fornecedor e interno; requer `server.py` local em execução
- **Editor rich text de e-mail** — toolbar de formatação (negrito, itálico, sublinhado, alinhamento, fonte, tamanho, listas, link) nas abas Fornecedor e Interno da janela de e-mail; conteúdo HTML preservado no envio
- **Notificações in-app** — sino na barra lateral com badge de contagem; painel lista alertas de prazo vencendo (≤7 dias), processos parados (≥15 dias) e certidões vencendo (≤30 dias); clique no alerta abre o processo diretamente
- **Templates de processo** — botão "⊞ Modelo" salva os dados de um processo como modelo reutilizável; ao criar novo processo, chips dos modelos aparecem para aplicação com um clique
- **Importação CSV de fornecedores** — botão "Importar CSV" na tela de Fornecedores; suporta separador `,` ou `;`, consulta CNPJ automaticamente, exibe pré-visualização antes de importar; modelo de arquivo disponível para download com todos os 23 campos do cadastro
- **Relatório executivo** — botão "Executivo" no dashboard gera documento com KPIs, gráfico de barras por status, alertas de processos parados e lista dos últimos 20 processos; abre em janela separada com botão de impressão
- **Histórico de edições por campo** — ícone 🕐 ao lado de cada campo editável no painel lateral do processo exibe histórico de alterações com data/hora e valor anterior → novo; baseado na trilha de auditoria
- **QR Code de autenticidade nos documentos** — todos os documentos gerados incluem QR Code no rodapé apontando para `http://localhost:3000/verificar/{cod}`; ao escanear, o `server.py` serve página de verificação que consulta o IndexedDB local e confirma ou rejeita a autenticidade do documento
- **Visualização em cards ou tabela** com ordenação por coluna
- **Tema claro/escuro** configurável
- **Alertas visuais** para processos parados há mais de 15 dias e prazos vencidos
- **Alertas de validade de certidões** — badges visuais indicando certidões vencidas (borda vermelha) ou próximas do vencimento em 30 dias (borda amarela) diretamente na lista de certidões
- **Brasão personalizado** exibido nos documentos gerados
- **Auto-backup automático** — snapshot gravado no localStorage 3 segundos após cada salvamento; banner de alerta laranja exibido quando o último backup manual tem mais de 7 dias
- **Validação ao concluir etapa** — ao marcar uma etapa como concluída, o sistema verifica campos obrigatórios e exibe confirmação listando os campos faltantes (não bloqueante)
- **Autenticação multiusuário** — login com usuário e senha; hashing PBKDF2-HMAC-SHA256; sessões server-side; admin pode criar, editar e desativar usuários; aba "Segurança" permite alterar a própria senha
- **Painel de Diagnóstico** — aba "Diagnóstico" nas Configurações analisa todos os processos e fornecedores, classificando inconsistências em Erros críticos, Avisos e Informações
- **Exportação PNCP** — botão na etapa Aviso de Dispensa gera JSON estruturado no formato da API do Portal Nacional de Contratações Públicas com os dados do processo
- **Factory Reset / Limpeza total** — apaga todos os dados do sistema com confirmação em 3 etapas de segurança (acessível em Configurações)
- **Detecção de primeiro uso** — ao abrir o sistema sem perfil configurado, direciona automaticamente para as Configurações com mensagem de boas-vindas
- **Método de cotação por processo** — cada processo pode ter seu próprio método de cálculo (média ou mediana) independente da configuração global
- **Código de autenticidade** único no rodapé de cada documento gerado
- **Reordenação de etapas** por arrastar e soltar
- **Barra de progresso** por processo
- Configurações de perfil do agente de contratação usadas automaticamente em todos os documentos

---

## Requisitos

- **Navegador moderno** com JavaScript ES6+ — Google Chrome (90+) ou Microsoft Edge (90+)
- **Python 3.7+** para executar o servidor local (`server.py`); usa apenas stdlib, sem dependências externas
- Não requer banco de dados externo ou conexão à internet (exceto para consulta de CNPJ)
- Configure as credenciais SMTP em Configurações para habilitar o envio de e-mails

> ⚠️ **Importante:** o sistema deve ser aberto exclusivamente pelo `Iniciar SGCD.bat`. Abrir o `SGCD.html` diretamente pelo navegador cria uma base de dados separada e impede o envio de e-mails.

---

## Como Usar

### 1. Abrir o sistema
Execute o arquivo `Iniciar SGCD.bat`. O sistema verificará o Python, iniciará o servidor local e abrirá o SGCD automaticamente no Chrome ou Edge em modo de aplicativo.

### 2. Configuração inicial
Ao abrir pela primeira vez, clique no ícone de **engrenagem (⚙)** na barra lateral e preencha:
- Nome completo do agente de contratação
- Cargo e matrícula
- Nome do órgão/entidade
- Município e UF
- Nome da autoridade competente (ordenador de despesa)
- Brasão institucional (opcional)

Essas informações serão usadas automaticamente em todos os documentos gerados.

### 3. Criar um novo processo
1. Clique no botão **"+ Novo Processo"** no dashboard
2. Informe o objeto da contratação (campo obrigatório)
3. Preencha os números de PA e DL (ou use a numeração sugerida automaticamente)
4. Selecione a fundamentação legal (inciso do Art. 75)
5. Informe o valor estimado, unidade solicitante e prazo
6. Clique em **"Criar"**
7. Siga o checklist das 15 etapas na ordem indicada

---

## Documentos Gerados pelo Sistema

| Documento | Descrição |
|-----------|-----------|
| **Autorização de Abertura** | Despacho formal para início do processo, assinado pela autoridade competente |
| **Extrato de Publicação** | Texto formatado para publicação no Diário Oficial (Art. 54 §1º) |
| **Ata de Sessão** | Documento completo do processo com propostas, certidões e espaço para assinaturas |
| **Mapa de Preços** | Tabela comparativa de propostas recebidas (Etapa 10) |
| **Justificativa de Enquadramento Legal** | Declaração formal do enquadramento na hipótese de dispensa, com referência ao inciso do Art. 75 aplicável (Art. 72, III Lei 14.133/2021) |
| **Aviso de Dispensa** | Aviso formatado para publicação no PNCP com objeto, valor, condições e critério de seleção (Art. 75, §3º) |
| **Despacho de Recusa / Desclassificação** | Decisão fundamentada de recusa de proposta (Art. 59 Lei 14.133/2021) |
| **Despacho de Habilitação** | Decisão formal de habilitação do fornecedor com lista das certidões verificadas (Art. 69 Lei 14.133/2021) |
| **Despacho de Inabilitação** | Decisão fundamentada de inabilitação do fornecedor (Art. 69 e 72 Lei 14.133/2021) |
| **Termo de Adjudicação** | Formalização da declaração do vencedor pelo agente de contratação (Art. 18, §1º Lei 14.133/2021) |
| **Termo de Homologação** | Aprovação do procedimento pela autoridade competente / ordenador de despesa (Art. 71 Lei 14.133/2021) |
| **Extrato de Contrato** | Extrato para publicação no Diário Oficial e PNCP com todos os dados contratuais (Art. 94 Lei 14.133/2021) |
| **Relatório Geral** | Visão consolidada de todos os processos com filtros aplicados |
| **Impressão do Processo** | Checklist completo com todos os campos preenchidos |

Todos os documentos abrem em janela separada com botão "🖨 Imprimir / Salvar PDF".

---

## Base Legal

- **Lei Federal nº 14.133/2021** — Nova Lei de Licitações e Contratos Administrativos
  - Art. 6º, XXIII — definição de Termo de Referência
  - Art. 12, §1º — Documento de Formalização da Demanda
  - Art. 18, §2º — Estudo Técnico Preliminar
  - Art. 54, §1º — publicação de extrato no Diário Oficial
  - Art. 71 — homologação
  - Art. 75 — hipóteses de dispensa de licitação (incisos I a XVI)
  - Art. 94 — publicação do contrato no PNCP
  - Art. 95 — instrumento contratual
- **Decreto nº 12.807/2025** — atualização dos limites de valor para dispensa (Art. 75, I e II), vigente desde 1º jan/2026 (R$ 130.984,20 para obras/engenharia; R$ 65.492,11 para bens e serviços)
- **IN SEGES nº 65/2021** — pesquisa de preços para aquisições de bens e contratação de serviços
- **PNCP** — Portal Nacional de Contratações Públicas (prazo mínimo de 3 dias úteis)

---

## Versionamento

Consulte o [CHANGELOG.md](CHANGELOG.md) para o histórico completo de versões e alterações.

---

## Tecnologias

| Tecnologia | Uso |
|-----------|-----|
| **HTML5** | Estrutura e interface da aplicação |
| **CSS3** | Estilização, temas claro/escuro, layout responsivo |
| **JavaScript puro (ES6+)** | Toda a lógica de negócio, sem frameworks externos |
| **SQLite** | Armazenamento dos dados no servidor local (`sgcd.db`) |
| **ReceitaWS** | Consulta de CNPJ — fonte primária (via proxy local no server.py) |
| **BrasilAPI** | Consulta de CNPJ — fallback automático |
| **ViaCEP** | Preenchimento automático de endereço por CEP |
| **Python 3 (stdlib)** | Servidor local (`server.py`): REST API, SQLite, auth, proxy CNPJ, SMTP, heartbeat |

---

## Licença

Distribuído sob a licença **MIT**. Veja [LICENSE](LICENSE) para detalhes.

---

> **Aviso:** Os dados ficam armazenados no arquivo `sgcd.db` na pasta do sistema. Faça backups regulares em **Configurações → Backup de Dados** e mantenha cópia do `sgcd.db` em local seguro.
