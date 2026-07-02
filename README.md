# SGCD — Sistema de Gestão de Contratação Direta

![Versão](https://img.shields.io/badge/versão-v2.11.1-blue) ![Lei](https://img.shields.io/badge/Lei-14.133%2F2021-green) ![Tecnologia](https://img.shields.io/badge/tecnologia-Python%20%2B%20SQLite-orange) ![Licença](https://img.shields.io/badge/licença-MIT-green) ![Multiusuário](https://img.shields.io/badge/acesso-multiusuário-blueviolet)

## Descrição

O **SGCD** é uma aplicação web multiusuário para gestão completa de processos de **Dispensa de Licitação** conforme a **Lei Federal nº 14.133/2021** (Nova Lei de Licitações e Contratos Administrativos). Desenvolvido para agentes de contratação pública, o sistema organiza todas as etapas do processo — da formalização da demanda até a publicação do contrato no PNCP — em um fluxo de trabalho guiado, com geração automática de documentos.

Funciona em rede local: um único computador executa o servidor e todos os usuários acessam pelo navegador via IP ou `localhost`.

---

## Funcionalidades Principais

- **Checklist estruturado com 17 etapas** do processo de Dispensa de Licitação, cada uma com fundamento legal e orientação de preenchimento
- **Geração automática de documentos** prontos para assinatura: Autorização de Abertura, Aviso de Dispensa, Ata de Sessão, Mapa de Preços, Despachos e Extrato de Contrato
- **Cadastro de fornecedores** com consulta automática de CNPJ via ReceitaWS/BrasilAPI e controle de certidões com alertas de vencimento
- **Gestão de propostas e cotações** com cálculo automático de média ou mediana como valor de referência
- **Dotação orçamentária** por processo — Programa/Ação, Elemento de Despesa, Fonte e Dotação Completa
- **Verificação de conformidade** automática: aponta pendências e inconsistências no processo
- **Alerta de fracionamento** — detecta processos com objetos similares e calcula soma dos valores no exercício
- **Controle de limites anuais** Art. 75, I e II com painel de acumulado e alerta ao atingir o teto legal
- **Cálculo automático de prazos** (Art. 75 §3°) — data mínima de encerramento com alerta visual
- **Trilha de auditoria global** com timeline agrupada por dia, filtros por tipo de evento, período e usuário
- **Agenda de Vencimentos** — prazos de propostas, contratos e processos parados em um único painel
- **Vinculação entre processos** — vínculos relacionais (renovação, aditivo, continuidade) bidirecionais e clicáveis
- **Visualização Kanban** por fase (Instrução / Publicado / Análise / Adjudicação / Contratação / Concluído)
- **Notificações por e-mail via SMTP** com editor rich text para fornecedor e equipe interna
- **Notificações in-app** — alertas de prazo, processos parados e certidões vencendo
- **Resumo diário por e-mail** — prazos e processos parados, enviado automaticamente pelo servidor sem depender de ninguém logado (requer SMTP configurado)
- **QR Code de autenticidade** em todos os documentos gerados com verificação online
- **Exportação PNCP** — JSON estruturado no formato da API do Portal Nacional de Contratações Públicas
- **Backup automático** ao encerrar o sistema (JSON + banco de dados SQLite) com rotação configurável
- **Lixeira** — processos excluídos ficam recuperáveis por 30 dias, incluindo arquivos anexados
- **Autenticação multiusuário** com hashing PBKDF2-HMAC-SHA256 e gestão de usuários pelo admin
- **Relatório executivo** com KPIs, gráfico de barras por status e alertas de processos parados
- **Diagnóstico de rede** — verifica IP, porta 3000, regras de firewall e acessibilidade pela LAN

---

## Requisitos

- **Python 3.7+** (apenas biblioteca padrão — sem dependências externas)
- **Google Chrome** ou **Microsoft Edge** (recomendado)
- Windows 10/11

---

## Instalação e uso

1. Copie a pasta `SGCD/` para o computador que atuará como servidor
2. Clique duas vezes em **`Iniciar SGCD.bat`**
3. Selecione o modo de operação no menu que aparecer
4. Faça login com as credenciais iniciais abaixo e **altere a senha imediatamente**

> ⚠️ **Importante:** abrir o `SGCD.html` diretamente pelo navegador (sem o servidor) impede o funcionamento do sistema. Use sempre o `Iniciar SGCD.bat`.

### Login inicial

| Campo   | Valor       |
|---------|-------------|
| Usuário | `admin`     |
| Senha   | `sgcd2024`  |

### Modo de operação

| Opção | Descrição |
|-------|-----------|
| **[1] Pessoal** | Uso individual — abre o navegador automaticamente e encerra ao sair |
| **[2] Servidor** | Máquina central em rede — fica rodando continuamente (Ctrl+C para parar) |
| **[3] Diagnóstico** | Verifica configurações de rede, porta e firewall |

### Acesso em rede local

Outros usuários acessam pelo IP do computador servidor:

```
http://192.168.x.x:3000/SGCD.html
```

Execute **`Diagnostico SGCD.bat`** para descobrir o IP e verificar se o acesso está funcionando.  
Execute **`Liberar Porta SGCD.bat`** como Administrador para abrir a porta 3000 no firewall.

---

## Estrutura de arquivos

```
SGCD/
├── SGCD.html                # Frontend — aplicação web completa
├── server.py                # Servidor Python (API REST + SQLite + uploads)
├── Iniciar SGCD.bat         # Inicializa o servidor
├── Criar Atalho SGCD.bat    # Cria atalho na área de trabalho com ícone
├── Criar Atalho SGCD.ps1    # Script PowerShell de criação do atalho
├── Diagnostico SGCD.bat     # Roda o diagnóstico de rede (clique duplo)
├── Liberar Porta SGCD.bat   # Cria regra de firewall para porta 3000 (Admin)
├── diagnostico.py           # Script de diagnóstico de rede e firewall
├── brasao.png               # Brasão do município (exibido na sidebar e documentos)
├── sgcd.ico                 # Ícone personalizado do sistema
├── sgcd.db                  # Banco de dados SQLite (criado automaticamente)
├── uploads/                 # Documentos anexados (criado automaticamente)
├── backups/                 # Backups automáticos (criado automaticamente)
├── README.md
├── CHANGELOG.md
└── MANUAL.html
```

---

## Documentos Gerados pelo Sistema

| Documento | Descrição |
|-----------|-----------|
| **Autorização de Abertura** | Despacho formal para início do processo, assinado pela autoridade competente |
| **Extrato de Publicação** | Texto formatado para publicação no Diário Oficial (Art. 54 §1º) |
| **Aviso de Dispensa** | Aviso formatado para publicação no PNCP (Art. 75, §3º) |
| **Ata de Sessão** | Documento completo do processo com propostas, certidões e espaço para assinaturas |
| **Mapa de Preços** | Tabela comparativa de propostas recebidas |
| **Justificativa de Enquadramento Legal** | Declaração formal do enquadramento na hipótese de dispensa (Art. 72, III) |
| **Despacho de Recusa / Desclassificação** | Decisão fundamentada de recusa de proposta (Art. 59) |
| **Despacho de Habilitação** | Decisão formal de habilitação do fornecedor (Art. 69) |
| **Despacho de Inabilitação** | Decisão fundamentada de inabilitação do fornecedor (Art. 69 e 72) |
| **Termo de Adjudicação** | Formalização da declaração do vencedor (Art. 18, §1º) |
| **Termo de Homologação** | Aprovação do procedimento pela autoridade competente (Art. 71) |
| **Extrato de Contrato** | Extrato para publicação no Diário Oficial e PNCP (Art. 94) |
| **Relatório Geral** | Visão consolidada de todos os processos com filtros aplicados |
| **Relatório Executivo** | KPIs, gráfico por status e alertas para gestores |

Todos os documentos abrem em janela separada com botão "🖨 Imprimir / Salvar PDF".

---

## Base Legal

- **Lei Federal nº 14.133/2021** — Nova Lei de Licitações e Contratos Administrativos (Art. 75 — hipóteses de dispensa)
- **Decreto nº 12.807/2025** — atualização dos limites de valor para dispensa (vigente desde 1º jan/2026)
  - Obras e engenharia: R$ 130.984,20
  - Bens e serviços: R$ 65.492,11
- **IN SEGES nº 65/2021** — pesquisa de preços para aquisições de bens e contratação de serviços
- **PNCP** — Portal Nacional de Contratações Públicas (prazo mínimo de 3 dias úteis, Art. 75 §3°)

---

## Segurança

- Senhas armazenadas com **PBKDF2-HMAC-SHA256** e salt aleatório por usuário
- Sessões server-side invalidadas automaticamente por inatividade
- Acesso à API exige token de sessão em todas as rotas (exceto login e verificação)
- Upload restrito a extensões seguras (PDF, DOCX, imagens, planilhas) com limite de 50 MB
- Trilha de auditoria imutável registra todas as ações com usuário e timestamp
- Verificação de integridade do banco de dados (SQLite `PRAGMA integrity_check`) na inicialização
- Recomenda-se uso em rede interna (LAN) apenas

---

## Tecnologias

| Tecnologia | Uso |
|-----------|-----|
| **HTML5 + CSS3** | Interface da aplicação, temas claro/escuro, layout responsivo |
| **JavaScript puro (ES6+)** | Toda a lógica de negócio, sem frameworks externos |
| **Python 3 (stdlib)** | Servidor local: REST API, SQLite, auth, SMTP, proxy CNPJ |
| **SQLite** | Armazenamento persistente dos dados (`sgcd.db`) |
| **ReceitaWS / BrasilAPI** | Consulta de CNPJ (primária + fallback automático) |
| **ViaCEP** | Preenchimento automático de endereço por CEP |

---

## Versionamento

Consulte o [CHANGELOG.md](CHANGELOG.md) para o histórico completo de versões e alterações.

---

## Licença

Distribuído sob a licença **MIT**. Veja [LICENSE](LICENSE) para o texto completo.

> **Aviso:** Os dados ficam armazenados no arquivo `sgcd.db` na pasta do sistema. Faça backups regulares em **Configurações → Backup de Dados** e mantenha cópia do `sgcd.db` em local seguro.
