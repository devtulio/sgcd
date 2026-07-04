# Contribuindo com o SGCD

Obrigado pelo interesse em contribuir com o **SGCD — Sistema de Gestão de Contratação Direta**!

## Reportando bugs

Abra uma [issue](https://github.com/devtulio/sgcd/issues/new) com:

- **Passos para reproduzir** o problema
- **Comportamento esperado** vs. **comportamento observado**
- Versão do sistema (visível no rodapé da tela de login) e navegador usado
- Prints de tela, se ajudar a ilustrar o problema

## Sugerindo funcionalidades

Abra uma issue descrevendo o caso de uso — que etapa real do processo de Dispensa de Licitação (Lei 14.133/2021) a funcionalidade resolveria.

## Enviando um Pull Request

1. Faça um fork do repositório
2. Crie uma branch a partir da `main`: `git checkout -b minha-feature`
3. Faça suas alterações em `SGCD.html` (frontend) e/ou `server.py` (backend)
4. Teste localmente rodando `python server.py` e usando o sistema pelo navegador
5. Atualize a documentação quando a mudança for relevante para o usuário final:
   - `CHANGELOG.md` — nova entrada no formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/)
   - `README.md` — se a lista de funcionalidades mudar
   - `MANUAL.html` — nova seção no histórico de versões (Seção 21)
   - `SGCD_VERSION` em `SGCD.html` e comentário de versão no topo de `server.py`
6. Abra o Pull Request descrevendo o que mudou e por quê

## Padrões do projeto

- **Sem dependências externas** no backend — apenas biblioteca padrão do Python (`http.server`, `sqlite3`, etc.), exceto o módulo opcional `pyhanko` para assinatura ICP-Brasil
- **Frontend single-file** — `SGCD.html` contém HTML, CSS e JS num único arquivo, sem build step
- **SQLite** como único banco de dados, com migrações simples via `ALTER TABLE` em `init_db()`
- IDs de `processes`/`fornecedores` são **UUID** (não autoincrement) — isso permite sincronizar backups entre instalações diferentes sem colisão; mantenha esse padrão em novas tabelas que precisem do mesmo tipo de sincronização
- Siga o estilo de código já presente no arquivo (nomes de função em português, comentários apenas quando o "porquê" não é óbvio)

## Segurança

Encontrou uma vulnerabilidade de segurança? Não abra uma issue pública — entre em contato diretamente com o mantenedor do repositório.

## Licença

Ao contribuir, você concorda que suas alterações serão licenciadas sob a mesma [licença MIT](LICENSE) do projeto.
