# SGCD — Sistema de Gestão de Contratação Direta

![Versão](https://img.shields.io/badge/versão-v1.10.1-blue) ![Lei](https://img.shields.io/badge/Lei-14.133%2F2021-green) ![Tecnologia](https://img.shields.io/badge/tecnologia-HTML5%20puro-orange) ![Licença](https://img.shields.io/badge/licença-uso%20interno-lightgrey)

## Descrição

O **SGCD** é uma aplicação web *single-file* (arquivo HTML único) para gestão completa de processos de **Dispensa de Licitação** conforme a **Lei Federal nº 14.133/2021** (Nova Lei de Licitações e Contratos Administrativos). Desenvolvido para agentes de contratação pública, o sistema organiza todas as etapas do processo — da formalização da demanda até a publicação do contrato no PNCP — em um fluxo de trabalho guiado, com geração automática de documentos.

Não requer instalação, servidor ou conexão à internet. Todos os dados ficam armazenados localmente no navegador via **IndexedDB**.

---

## Funcionalidades Principais

- **Checklist estruturado com 15 etapas** do processo de Dispensa de Licitação, cada uma com fundamento legal e orientação de preenchimento
- **Geração de documentos** prontos para assinatura e publicação: Autorização de Abertura, Aviso de Dispensa, Extrato para Diário Oficial, Ata de Sessão, Mapa de Preços e Extrato de Contrato
- **Relatório geral** de processos com filtros por status, unidade, período e faixa de valor
- **Cadastro de fornecedores** com consulta automática de CNPJ via BrasilAPI e controle de certidões
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
- **Visualização em cards ou tabela** com ordenação por coluna
- **Tema claro/escuro** configurável
- **Alertas visuais** para processos parados há mais de 15 dias e prazos vencidos
- **Brasão personalizado** exibido nos documentos gerados
- **Código de autenticidade** único no rodapé de cada documento gerado
- **Reordenação de etapas** por arrastar e soltar
- **Barra de progresso** por processo
- Configurações de perfil do agente de contratação usadas automaticamente em todos os documentos

---

## Requisitos

- **Navegador moderno** com suporte a IndexedDB e JavaScript ES6+
- **Recomendado:** Google Chrome (versão 90+) ou Microsoft Edge (versão 90+)
- Não requer instalação, servidor web, banco de dados externo ou conexão à internet

---

## Como Usar

### 1. Abrir o sistema
Abra o arquivo `SGCD.html` diretamente no navegador (clique duplo ou arraste para o navegador).

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
7. Siga o checklist das 16 etapas na ordem indicada

---

## Documentos Gerados pelo Sistema

| Documento | Descrição |
|-----------|-----------|
| **Autorização de Abertura** | Despacho formal para início do processo, assinado pela autoridade competente |
| **Extrato de Publicação** | Texto formatado para publicação no Diário Oficial (Art. 54 §1º) |
| **Ata de Sessão** | Documento completo do processo com propostas, certidões e espaço para assinaturas |
| **Mapa de Preços** | Tabela comparativa de propostas recebidas (Etapa 10) |
| **Aviso de Dispensa** | Aviso formatado para publicação no PNCP com objeto, valor, condições e critério de seleção (Art. 75, §3º) |
| **Despacho de Recusa / Desclassificação** | Decisão fundamentada de recusa de proposta (Art. 59 Lei 14.133/2021) |
| **Despacho de Habilitação** | Decisão formal de habilitação do fornecedor com lista das certidões verificadas (Art. 69 Lei 14.133/2021) |
| **Despacho de Inabilitação** | Decisão fundamentada de inabilitação do fornecedor (Art. 69 e 72 Lei 14.133/2021) |
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
| **IndexedDB** | Armazenamento local dos dados no navegador |
| **BrasilAPI** | Consulta de CNPJ (requer conexão à internet apenas nesta função) |

---

> **Aviso:** Os dados ficam armazenados exclusivamente no navegador local. Faça backups regulares em **Configurações → Backup de Dados** para evitar perda de informações ao limpar o cache do navegador.
