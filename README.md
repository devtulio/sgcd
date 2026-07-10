# SGCD — Sistema de Gestão de Contratação Direta

![Versão](https://img.shields.io/badge/versão-v2.26.1-blue) ![Lei](https://img.shields.io/badge/Lei-14.133%2F2021-green) ![Tecnologia](https://img.shields.io/badge/tecnologia-Python%20%2B%20SQLite-orange) ![Licença](https://img.shields.io/badge/licença-MIT-green) ![Multiusuário](https://img.shields.io/badge/acesso-multiusuário-blueviolet)

## Descrição

O **SGCD** é uma aplicação web multiusuário para gestão completa de processos de **Dispensa de Licitação** conforme a **Lei Federal nº 14.133/2021** (Nova Lei de Licitações e Contratos Administrativos). Desenvolvido para agentes de contratação pública, o sistema organiza todas as etapas do processo — da formalização da demanda até a publicação do contrato no PNCP — em um fluxo de trabalho guiado, com geração automática de documentos.

Funciona em rede local: um único computador executa o servidor e todos os usuários acessam pelo navegador via IP ou `localhost`.

---

## Funcionalidades Principais

- **Checklist estruturado com 18 etapas** do processo de Dispensa de Licitação, cada uma com fundamento legal e orientação de preenchimento
- **Geração automática de documentos** prontos para assinatura: Autorização de Abertura, Aviso de Dispensa, Ata de Sessão, Mapa de Preços, Despachos e Extrato de Contrato
- **Cadastro de fornecedores** com consulta automática de CNPJ via ReceitaWS/BrasilAPI e controle de certidões com alertas de vencimento
- **Gestão de propostas e cotações** com cálculo automático de média ou mediana como valor de referência
- **Dotação orçamentária** por processo — Programa/Ação, Elemento de Despesa, Fonte e Dotação Completa
- **Verificação de conformidade** automática: aponta pendências e inconsistências no processo
- **Alerta de fracionamento** — detecta processos com objetos similares e calcula soma dos valores no exercício
- **Controle de limites anuais** Art. 75, I e II com painel de acumulado e alerta ao atingir o teto legal
- **Cálculo automático de prazos** (Art. 75 §3°) — data mínima de encerramento com alerta visual
- **Trilha de auditoria global** com timeline agrupada por dia, filtros por tipo de evento, período e usuário
- **Exportação para CSV** de processos, fornecedores e trilha de auditoria — respeita os filtros/busca ativos na tela
- **Agenda de Vencimentos** — prazos de propostas, contratos e processos parados em um único painel
- **Vinculação entre processos** — vínculos relacionais (renovação, aditivo, continuidade) bidirecionais e clicáveis
- **Visualização Kanban** por fase (Instrução / Publicado / Análise / Adjudicação / Contratação / Concluído)
- **Notificações por e-mail via SMTP** com editor rich text para fornecedor e equipe interna
- **Notificações in-app** — alertas de prazo, processos parados e certidões vencendo
- **Resumo diário por e-mail** — prazos e processos parados, enviado automaticamente pelo servidor sem depender de ninguém logado (requer SMTP configurado)
- **QR Code de autenticidade** em todos os documentos gerados com verificação online
- **Assinatura eletrônica de documentos** — 3 módulos à escolha: Simples (interna), gov.br (nível avançado) e certificado ICP-Brasil A1 (nível qualificado)
- **Exportação PNCP** — JSON estruturado no formato da API do Portal Nacional de Contratações Públicas
- **Backup automático** após o último usuário sair (JSON + banco de dados SQLite) com rotação configurável — o servidor continua no ar, pronto pro próximo login
- **Sincronização de backup entre agentes/máquinas** — mescla dados de outra instalação (soma o que é novo, revisa o que conflita) sem substituir o banco inteiro
- **Lixeira** — processos e fornecedores excluídos ficam recuperáveis por 30 dias (processos incluem os arquivos anexados). Exclusão de fornecedor bloqueada se ele estiver vinculado a algum processo
- **Autenticação multiusuário** com hashing PBKDF2-HMAC-SHA256 e gestão de usuários pelo admin
- **Relatório executivo** com KPIs, gráfico de barras por status e alertas de processos parados
- **Diagnóstico e correção automática de rede** — verifica IP, porta 3000, perfil de rede, regra de firewall, antivírus de terceiros e outros dispositivos alcançáveis na LAN; corrige automaticamente o que estiver ao alcance do Windows (com elevação de Administrador)

---

## Requisitos

- **Python 3.7+** (apenas biblioteca padrão — sem dependências externas)
- **Google Chrome** ou **Microsoft Edge** (recomendado)
- Windows 10/11
- Opcional: `pip install -r requirements.txt` — só necessário para o módulo de assinatura com certificado ICP-Brasil (`pyhanko`)

> **Servidor sem Python instalado (ex.: Windows Server bloqueado por política de TI):**
> o `Iniciar SGCD.bat` detecta automaticamente a ausência do Python e extrai uma versão portátil (embarcável, sem instalador) incluída no próprio projeto (`python-3.12.9-embed-amd64.zip`) para `C:\Python312-embed\` — não exige instalação nem privilégio de administrador. Isso resolve o caso comum de instaladores `.exe` bloqueados por AppLocker/antivírus corporativo em servidores.
>
> Essa versão portátil não vem com `pip` pronto (limitação do próprio pacote embarcável do Python). Se esse servidor precisar do módulo de assinatura ICP-Brasil, rode **`Instalar Assinatura ICP-Brasil.bat`** depois — ele habilita o pip e instala o `pyhanko` (requer acesso à internet só nesse momento, para baixar do PyPI). Validado de ponta a ponta (extração → habilitação do pip → instalação do pyhanko) numa cópia isolada do Python embarcável.

---

## Instalação e uso

1. Copie a pasta `SGCD/` para o computador que atuará como servidor
2. Clique duas vezes em **`Iniciar SGCD.bat`**
3. Escolha **[2] Iniciar Servidor** no menu que aparecer — o navegador abre automaticamente
4. Faça login com as credenciais iniciais abaixo e **altere a senha imediatamente**

> ⚠️ **Importante:** abrir o `SGCD.html` diretamente pelo navegador (sem o servidor) impede o funcionamento do sistema. Use sempre o `Iniciar SGCD.bat`.

### Login inicial

| Campo   | Valor       |
|---------|-------------|
| Usuário | `admin`     |
| Senha   | `admin123`  |

### Menu inicial

| Opção | Descrição |
|-------|-----------|
| **[1] Diagnóstico** | Verifica e corrige automaticamente rede, porta e firewall (pede elevação de Administrador quando necessário) |
| **[2] Iniciar Servidor** | Abre o navegador automaticamente e fica rodando continuamente — funciona tanto para uso individual quanto em rede. Só encerra com **Ctrl+C** no terminal |

### Acesso em rede local

Outros usuários acessam pelo IP do computador servidor:

```
http://192.168.x.x:3000/SGCD.html
```

Execute **`Diagnostico SGCD.bat`** (ou a opção **[3]** do `Iniciar SGCD.bat`) para descobrir o IP, verificar e corrigir automaticamente firewall, perfil de rede e antivírus de terceiros. Ele também testa se há outros dispositivos alcançáveis na rede — útil para identificar isolamento de cliente (Wi-Fi) ou VLANs separadas, casos que exigem intervenção do time de TI.

> Se o diagnóstico indicar tudo certo mas outra máquina ainda não conseguir acessar, é sinal de bloqueio fora do alcance do Windows (isolamento de rede corporativa, VLAN, ou firewall de outro dispositivo/roteador) — nesse caso, use o teste indicado pelo próprio diagnóstico (`ping` e `Test-NetConnection`) a partir da outra máquina para confirmar e leve essa evidência ao TI.

---

## Estrutura de arquivos

```
SGCD/
├── SGCD.html                # Frontend — aplicação web completa
├── server.py                # Servidor Python (API REST + SQLite + uploads)
├── tests/                   # Suíte de testes automatizados do backend
│   ├── test_server.py
│   └── e2e/                 # Testes E2E (Playwright) — navegador real de ponta a ponta
├── Iniciar SGCD.bat         # Inicializa o servidor
├── python-3.12.9-embed-amd64.zip  # Python portátil (fallback se não houver Python instalado)
├── Instalar Assinatura ICP-Brasil.bat  # Opcional — instala pip + pyhanko no Python embarcável
├── get-pip.py               # Usado só pelo script acima (Python embarcável não vem com pip)
├── Criar Atalho SGCD.bat    # Cria atalho na área de trabalho com ícone
├── Criar Atalho SGCD.ps1    # Script PowerShell de criação do atalho
├── Diagnostico SGCD.bat     # Roda o diagnóstico de rede (clique duplo)
├── Liberar Porta SGCD.bat   # Cria regra de firewall para porta 3000 (Admin)
├── diagnostico.py           # Script de diagnóstico de rede e firewall
├── brasao.png               # (legado — brasão agora fica salvo no banco, upload em Configurações)
├── sgcd.ico                 # Ícone personalizado do sistema
├── sgcd.db                  # Banco de dados SQLite (criado automaticamente)
├── uploads/                 # Documentos anexados (criado automaticamente)
├── backups/                 # Backups automáticos (criado automaticamente)
├── requirements.txt         # Dependência opcional (pyhanko — só p/ assinatura ICP-Brasil)
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

## Desenvolvimento

O sistema em si continua zero-dependência (Python stdlib + HTML puro). Para quem for alterar o código, há um lint opcional que verifica variáveis indefinidas no JavaScript de `SGCD.html`:

```bash
npm install   # uma vez, instala apenas o ESLint (ferramenta de dev, não é usada em produção)
npm run lint
```

Há também uma suíte de testes automatizados do backend (`server.py`), usando só `unittest` da stdlib — sobe o servidor real contra um banco e uploads temporários e testa os endpoints REST (login, processos, fornecedores, auditoria, configurações, usuários, backup):

```bash
python -m unittest discover -s tests -v
```

Há também uma suíte de testes E2E (`tests/e2e/`), usando Playwright — sobe o servidor real e dirige um Chromium de verdade pelo fluxo completo (login com troca de senha obrigatória, criar processo, gerar documento):

```bash
npm install
npx playwright install chromium   # uma vez, baixa o navegador de teste
npm run test:e2e
```

Roda contra um banco/uploads/backups temporários (nunca o `sgcd.db` real), criados e descartados automaticamente a cada execução.

---

## Versionamento

Consulte o [CHANGELOG.md](CHANGELOG.md) para o histórico completo de versões e alterações.

---

## Contribuição

Contribuições são bem-vindas! Veja o [CONTRIBUTING.md](CONTRIBUTING.md) para orientações sobre como reportar bugs, sugerir funcionalidades e enviar Pull Requests.

---

## Licença

Distribuído sob a licença **MIT**. Veja [LICENSE](LICENSE) para o texto completo.

> **Aviso:** Os dados ficam armazenados no arquivo `sgcd.db` na pasta do sistema. Faça backups regulares em **Configurações → Backup de Dados** e mantenha cópia do `sgcd.db` em local seguro.
