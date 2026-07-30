# Suíte de testes do backend (server.py) — sobe o servidor real contra um
# banco/uploads/backups temporários e bate nos endpoints REST via http.client.
# python -m unittest discover -s tests   (ou: python tests/test_server.py)
import base64
import http.client
import io
import json
import os
import shutil
import socketserver
import sqlite3
import sys
import tempfile
import threading
import time
import zipfile
import unittest
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402

PORT = 3091
# Capturado antes de o setUpModule limpar a flag, para que o teste da troca
# obrigatória continue verificando o que init_db() realmente cria.
_admin_nasceu_com_troca = None
_tmpdir = None
_httpd = None
_thread = None


def setUpModule():
    # Um único servidor para toda a suíte — DB_PATH/UPLOADS_DIR são globais do módulo
    # server.py, então instâncias por classe na mesma porta correm risco de uma classe
    # trocar esses globais enquanto uma thread de requisição da classe anterior ainda
    # está em voo, misturando os dados das duas.
    global _tmpdir, _httpd, _thread
    _tmpdir = tempfile.mkdtemp(prefix='sgcd_test_')
    server.DB_PATH = os.path.join(_tmpdir, 'sgcd.db')
    server.UPLOADS_DIR = os.path.join(_tmpdir, 'uploads')
    server.BACKUP_DIR = os.path.join(_tmpdir, 'backups')
    os.makedirs(server.UPLOADS_DIR, exist_ok=True)
    os.makedirs(server.BACKUP_DIR, exist_ok=True)
    # Motor de erros: redireciona o log para o dir temporário — sem isto os testes
    # escreveriam no <sigla>_errors.log do repositório (o handler é criado no import).
    server._DATA_DIR = _tmpdir
    server._log = server.sgx_base.configurar_log('SGCD', _tmpdir, forcar=True)
    server.init_db()
    # A suíte age como um sistema já instalado, com a senha padrão trocada: sem
    # isto todo login como admin/admin123 tomaria 403, porque o servidor passou a
    # recusar qualquer rota enquanto a troca obrigatória estiver pendente (o
    # bloqueio em si tem teste próprio, em TestSenhaPadraoObrigatoria).
    global _admin_nasceu_com_troca
    with server.get_db() as conn:
        _admin_nasceu_com_troca = conn.execute(
            "SELECT must_change_password FROM usuarios WHERE username='admin'").fetchone()['must_change_password']
        conn.execute("UPDATE usuarios SET must_change_password=0 WHERE username='admin'")
        conn.commit()

    # Serve via waitress (mesmo servidor do deploy) para validar o adaptador WSGI.
    import waitress
    app = server.sgx_base._wsgi_app(server.SGCDHandler)
    _httpd = waitress.create_server(app, host='127.0.0.1', port=PORT, threads=8)
    _thread = threading.Thread(target=_httpd.run, daemon=True)
    _thread.start()


def tearDownModule():
    try: _httpd.close()
    except Exception: pass
    shutil.rmtree(_tmpdir, ignore_errors=True)


class SGCDTestCase(unittest.TestCase):

    def request(self, method, path, body=None, token=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', PORT, timeout=5)
        hdrs = {'Content-Type': 'application/json'}
        if token:
            hdrs['Authorization'] = f'Bearer {token}'
        if headers:
            hdrs.update(headers)
        # Content-Length precisa ser em bytes, não em caracteres — corpo com acentos
        # (ex. "Aquisição") tem mais bytes que caracteres em UTF-8; passar a string
        # crua deixa o http.client contar caracteres e truncar o corpo na rede.
        payload = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
        conn.request(method, path, body=payload, headers=hdrs)
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        try:
            parsed = json.loads(data) if data else None
        except ValueError:
            parsed = data  # resposta binária (ex: download de arquivo)
        return resp.status, parsed

    def login(self, username='admin', password='admin123'):
        status, data = self.request('POST', '/api/auth/login', {'username': username, 'password': password})
        self.assertEqual(status, 200, data)
        return data['token']


class TestAuth(SGCDTestCase):

    def test_login_com_credenciais_corretas(self):
        status, data = self.request('POST', '/api/auth/login', {'username': 'admin', 'password': 'admin123'})
        self.assertEqual(status, 200)
        self.assertIn('token', data)
        self.assertTrue(data['user']['admin'])

    def test_login_com_senha_errada(self):
        status, data = self.request('POST', '/api/auth/login', {'username': 'admin', 'password': 'errada'})
        self.assertEqual(status, 401)

    def test_endpoint_protegido_sem_token(self):
        status, data = self.request('GET', '/api/processes')
        self.assertEqual(status, 401)

    def test_endpoint_protegido_com_token_invalido(self):
        status, data = self.request('GET', '/api/processes', token='token-que-nao-existe')
        self.assertEqual(status, 401)

    def test_me_retorna_usuario_da_sessao(self):
        token = self.login()
        status, data = self.request('GET', '/api/auth/me', token=token)
        self.assertEqual(status, 200)
        self.assertEqual(data['username'], 'admin')

    def test_admin_padrao_nasce_com_troca_de_senha_obrigatoria(self):
        # Valor de quando init_db() criou o admin — o setUpModule zera a flag
        # depois, para que o resto da suíte possa usar a conta.
        self.assertEqual(_admin_nasceu_com_troca, 1)


class TestForcaTrocaSenha(SGCDTestCase):

    def test_flag_e_limpa_apos_trocar_senha(self):
        # Usa um usuário próprio (não o admin compartilhado) para não afetar
        # o login('admin', 'admin123') usado pelas outras classes de teste.
        admin_token = self.login()
        status, created = self.request('POST', '/api/usuarios', {
            'username': 'precisa_trocar', 'nome': 'Precisa Trocar', 'password': 'senha123'
        }, token=admin_token)
        self.assertEqual(status, 200)
        uid = created['id']

        with server.get_db() as conn:
            conn.execute('UPDATE usuarios SET must_change_password=1 WHERE id=?', (uid,))

        status, data = self.request('POST', '/api/auth/login', {'username': 'precisa_trocar', 'password': 'senha123'})
        self.assertEqual(status, 200)
        self.assertTrue(data['user']['mustChangePassword'])
        token = data['token']

        status, _ = self.request('PUT', f'/api/usuarios/{uid}', {'password': 'novasenha456'}, token=token)
        self.assertEqual(status, 200)

        status, data = self.request('POST', '/api/auth/login', {'username': 'precisa_trocar', 'password': 'novasenha456'})
        self.assertEqual(status, 200)
        self.assertFalse(data['user']['mustChangePassword'])


class TestProcesses(SGCDTestCase):

    def test_criar_listar_atualizar_e_excluir_processo(self):
        token = self.login()

        status, created = self.request('POST', '/api/processes', {'objeto': 'Aquisição de teste', 'status': 'em_andamento'}, token=token)
        self.assertEqual(status, 200)
        pid = created['id']
        self.assertEqual(created['objeto'], 'Aquisição de teste')

        status, listed = self.request('GET', '/api/processes', token=token)
        self.assertEqual(status, 200)
        self.assertTrue(any(p['id'] == pid for p in listed['items']))

        status, updated = self.request('PUT', f'/api/processes/{pid}', {'status': 'concluido'}, token=token)
        self.assertEqual(status, 200)
        self.assertEqual(updated['status'], 'concluido')

        status, single = self.request('GET', f'/api/processes/{pid}', token=token)
        self.assertEqual(status, 200)
        self.assertEqual(single['status'], 'concluido')

        # soft-delete: some da listagem normal, aparece na lixeira
        status, _ = self.request('DELETE', f'/api/processes/{pid}', token=token)
        self.assertEqual(status, 200)
        status, listed = self.request('GET', '/api/processes', token=token)
        self.assertFalse(any(p['id'] == pid for p in listed['items']))
        status, trashed = self.request('GET', '/api/processes?trash=1', token=token)
        self.assertTrue(any(p['id'] == pid for p in trashed['items']))

        # restaurar da lixeira
        status, _ = self.request('PUT', f'/api/processes/{pid}/restore', token=token)
        self.assertEqual(status, 200)
        status, listed = self.request('GET', '/api/processes', token=token)
        self.assertTrue(any(p['id'] == pid for p in listed['items']))

    def test_busca_processo_inexistente_retorna_404(self):
        token = self.login()
        status, data = self.request('GET', '/api/processes/id-que-nao-existe', token=token)
        self.assertEqual(status, 404)

    def test_edicao_concorrente_detecta_conflito(self):
        # Simula dois usuários com o mesmo processo aberto: A carrega, B edita e
        # salva primeiro, depois A tenta salvar com o updatedAt que carregou —
        # deve ser recusado (409) em vez de sobrescrever a edição de B.
        token = self.login()
        status, created = self.request('POST', '/api/processes', {'objeto': 'Processo original'}, token=token)
        self.assertEqual(status, 200)
        pid = created['id']
        base_updated_at = created['updatedAt']
        time.sleep(0.01)  # updatedAt tem precisão de milissegundo — garante que o próximo save gere um valor diferente

        # Usuário B edita e salva primeiro
        status, _ = self.request('PUT', f'/api/processes/{pid}',
                                  {'objeto': 'Editado por B', '_baseUpdatedAt': base_updated_at}, token=token)
        self.assertEqual(status, 200)

        # Usuário A tenta salvar com o updatedAt antigo (de antes da edição de B)
        status, resp = self.request('PUT', f'/api/processes/{pid}',
                                     {'objeto': 'Editado por A', '_baseUpdatedAt': base_updated_at}, token=token)
        self.assertEqual(status, 409)
        self.assertEqual(resp['current']['objeto'], 'Editado por B')

        # Confirma que a edição de B não foi sobrescrita
        status, current = self.request('GET', f'/api/processes/{pid}', token=token)
        self.assertEqual(current['objeto'], 'Editado por B')

    def test_edicao_sem_baseUpdatedAt_nao_bloqueia(self):
        # Compatibilidade: chamadas que não mandam _baseUpdatedAt (ex. criação,
        # sincronização de backup) continuam funcionando sem checagem de conflito.
        token = self.login()
        status, created = self.request('POST', '/api/processes', {'objeto': 'Processo original'}, token=token)
        pid = created['id']
        status, updated = self.request('PUT', f'/api/processes/{pid}', {'objeto': 'Sem checagem'}, token=token)
        self.assertEqual(status, 200)
        self.assertEqual(updated['objeto'], 'Sem checagem')


class TestFornecedores(SGCDTestCase):

    def test_criar_e_atualizar_fornecedor(self):
        token = self.login()
        status, created = self.request('POST', '/api/fornecedores',
                                        {'cnpj': '00000000000191', 'razaoSocial': 'Fornecedor Teste LTDA'},
                                        token=token)
        self.assertEqual(status, 200)
        fid = created['id']

        status, updated = self.request('PUT', f'/api/fornecedores/{fid}', {'razaoSocial': 'Nome Atualizado'}, token=token)
        self.assertEqual(status, 200)
        self.assertEqual(updated['razaoSocial'], 'Nome Atualizado')

        status, listed = self.request('GET', '/api/fornecedores', token=token)
        self.assertTrue(any(f['id'] == fid for f in listed['items']))

    def test_excluir_restaurar_e_purgar_fornecedor(self):
        token = self.login()
        status, created = self.request('POST', '/api/fornecedores',
                                        {'cnpj': '33333333000191', 'razaoSocial': 'Fornecedor Para Excluir'},
                                        token=token)
        self.assertEqual(status, 200)
        fid = created['id']

        # soft-delete: some da listagem normal, aparece na lixeira
        status, _ = self.request('DELETE', f'/api/fornecedores/{fid}', token=token)
        self.assertEqual(status, 200)
        status, listed = self.request('GET', '/api/fornecedores', token=token)
        self.assertFalse(any(f['id'] == fid for f in listed['items']))
        status, trashed = self.request('GET', '/api/fornecedores?trash=1', token=token)
        self.assertTrue(any(f['id'] == fid for f in trashed['items']))

        # restaurar da lixeira
        status, _ = self.request('PUT', f'/api/fornecedores/{fid}/restore', token=token)
        self.assertEqual(status, 200)
        status, listed = self.request('GET', '/api/fornecedores', token=token)
        self.assertTrue(any(f['id'] == fid for f in listed['items']))

        # excluir definitivamente
        status, _ = self.request('DELETE', f'/api/fornecedores/{fid}', token=token)
        self.assertEqual(status, 200)
        status, _ = self.request('DELETE', f'/api/fornecedores/{fid}?purge=1', token=token)
        self.assertEqual(status, 200)
        status, _ = self.request('GET', f'/api/fornecedores/{fid}', token=token)
        self.assertEqual(status, 404)


class TestAudit(SGCDTestCase):

    def test_registra_e_lista_evento_de_auditoria(self):
        token = self.login()
        status, _ = self.request('POST', '/api/audit', {'type': 'TESTE', 'label': 'Evento de teste'}, token=token)
        self.assertEqual(status, 200)

        status, data = self.request('GET', '/api/audit', token=token)
        self.assertEqual(status, 200)
        self.assertTrue(any(e['type'] == 'TESTE' for e in data['items']))

    def test_bulk_de_auditoria_exige_admin(self):
        # cria usuário não-admin e confirma que /api/audit/bulk nega acesso
        admin_token = self.login()
        status, _ = self.request('POST', '/api/usuarios', {
            'username': 'comum', 'nome': 'Usuário Comum', 'password': 'senha123', 'admin': False
        }, token=admin_token)
        self.assertEqual(status, 200)

        user_token = self.login('comum', 'senha123')
        status, data = self.request('POST', '/api/audit/bulk', [{'type': 'X', 'label': 'Y'}], token=user_token)
        self.assertEqual(status, 403)


class TestSettingsAndUsers(SGCDTestCase):

    def test_settings_get_e_save_exige_admin(self):
        admin_token = self.login()
        status, _ = self.request('PUT', '/api/settings', {'tema': 'escuro'}, token=admin_token)
        self.assertEqual(status, 200)
        status, data = self.request('GET', '/api/settings', token=admin_token)
        self.assertEqual(status, 200)
        self.assertEqual(data.get('tema'), 'escuro')

    def test_usuario_comum_nao_pode_criar_usuario(self):
        admin_token = self.login()
        self.request('POST', '/api/usuarios', {
            'username': 'user2', 'nome': 'Outro Usuário', 'password': 'senha123', 'admin': False
        }, token=admin_token)
        user_token = self.login('user2', 'senha123')

        status, data = self.request('POST', '/api/usuarios', {
            'username': 'user3', 'nome': 'Terceiro', 'password': 'senha123', 'admin': False
        }, token=user_token)
        self.assertEqual(status, 403)


class TestBackup(SGCDTestCase):

    def test_export_backup_json_contem_dados_criados(self):
        token = self.login()
        self.request('POST', '/api/processes', {'objeto': 'Processo para backup'}, token=token)

        status, data = self.request('GET', '/api/backup', token=token)
        self.assertEqual(status, 200)
        self.assertEqual(data.get('_sgx'), 'SGCD')   # envelope padronizado da família
        self.assertNotIn('usuarios', data)           # SGCD não leva contas no JSON portátil
        self.assertTrue(any(p['objeto'] == 'Processo para backup' for p in data['processes']))

    def test_restore_com_item_malformado_nao_apaga_dados_existentes(self):
        # Regressão: _restore_backup fazia commit() dos DELETEs antes de validar
        # as inserções — um item malformado no meio do backup derrubava o banco
        # inteiro sem restaurar nada. Agora tudo é uma transação só (tudo ou nada).
        token = self.login()
        status, created = self.request('POST', '/api/processes', {'objeto': 'Processo que não pode sumir'}, token=token)
        self.assertEqual(status, 200)
        pid_original = created['id']

        backup_malformado = {
            '_sgcd': True,
            'processes': [
                {'id': 'novo-1', 'objeto': 'Processo válido do backup', 'steps': []},
                None,  # item malformado — quebra o loop de inserção no meio
            ],
        }
        status, resp = self.request('POST', '/api/backup/restore', backup_malformado, token=token)
        self.assertEqual(status, 500)
        self.assertIn('nenhuma alteração foi aplicada', resp['error'])

        status, listed = self.request('GET', '/api/processes', token=token)
        self.assertEqual(status, 200)
        self.assertTrue(any(p['id'] == pid_original for p in listed['items']),
                         'processo original sumiu — restore parcial vazou apesar do rollback')
        self.assertFalse(any(p.get('id') == 'novo-1' for p in listed['items']),
                          'processo do backup malformado foi aplicado parcialmente')


class TestHealth(SGCDTestCase):

    def test_health_check(self):
        status, data = self.request('GET', '/health')
        self.assertEqual(status, 200)
        self.assertTrue(data['ok'])


class TestErroNaoTratado(SGCDTestCase):

    def test_param_invalido_vira_400_e_nao_derruba_conexao(self):
        # Regressão + motor de erros: um parâmetro numérico inválido (page=texto)
        # era erro não-tratado -> 500. Agora o motor classifica como erro DE
        # CLIENTE (int_param -> ErroCliente) e responde 400 limpo, sem stack no log.
        # _safe_dispatch continua garantindo que a conexão nunca cai sem resposta.
        token = self.login()
        status, data = self.request('GET', '/api/processes?page=nao-e-um-numero', token=token)
        self.assertEqual(status, 400)
        self.assertIn('error', data)

        # Confirma que o servidor continua respondendo normalmente depois
        status, _ = self.request('GET', '/health')
        self.assertEqual(status, 200)


class TestNuncaEncerraSozinho(SGCDTestCase):

    def test_ultima_sessao_expirar_nao_derruba_o_processo(self):
        # Regressão: existia um modo "Pessoal" em que _check_shutdown() chamava
        # os._exit(0) quando a última sessão ativa expirava. os._exit(0) mata o
        # processo Python na hora, sem exceção capturável — se ainda existisse,
        # o processo deste teste morreria aqui e nada abaixo executaria.
        token = self.login()
        with server.get_db() as conn:
            conn.execute('DELETE FROM sessions')  # simula a última sessão expirando
        server._had_session = True
        server._backup_pos_sess = False
        server._check_shutdown()

        # Se chegou aqui, o processo sobreviveu — confirma que o servidor
        # ainda responde normalmente (não travou nem morreu).
        status, _ = self.request('GET', '/health')
        self.assertEqual(status, 200)

    def test_sessao_sobrevive_atraso_maior_que_o_ttl_antigo(self):
        # Regressão: SESSION_TTL era 15s (renovado pelo ping a cada 5s) — margem
        # curta o bastante para uma sessão expirar sozinha no uso normal (várias
        # chamadas de API concorrentes disputando conexão HTTP logo no login,
        # ou a aba principal perdendo foco ao abrir um popup de documento),
        # derrubando o usuário de volta pro login no meio do trabalho sem
        # ninguém ter saído de propósito.
        #
        # Simula 20s "consumidos" do TTL sem nenhum ping renovar a sessão —
        # sob o TTL antigo (15s) isso já teria expirado; sob o atual (60s)
        # ainda sobra bastante margem.
        self.assertGreater(server.SESSION_TTL, 20,
                            'SESSION_TTL muito curto — sessão expira sozinha em uso normal sem ping')
        token = self.login()
        with server.get_db() as conn:
            conn.execute('UPDATE sessions SET expires=expires-20 WHERE token=?', (token,))
        status, _ = self.request('GET', '/api/processes', token=token)
        self.assertEqual(status, 200, 'sessão expirou com atraso que o TTL antigo (15s) não sobreviveria')


class TestCeisCnep(SGCDTestCase):
    """Proxy CEIS/CNEP: valida os dois curtos-circuitos que não tocam a rede."""

    def test_cnpj_invalido_retorna_400(self):
        token = self.login()
        status, data = self.request('GET', '/api/ceis-cnep?cnpj=123', token=token)
        self.assertEqual(status, 400)
        self.assertIn('CNPJ', data.get('error', ''))

    def test_sem_chave_configurada_retorna_400(self):
        token = self.login()
        # DB de teste não tem portal_transparencia_key → não chega a chamar a API externa
        status, data = self.request('GET', '/api/ceis-cnep?cnpj=12345678000199', token=token)
        self.assertEqual(status, 400)
        self.assertIn('não configurada', data.get('error', ''))


class TestImportFornecedores(SGCDTestCase):
    """Importar fornecedores de um backup do SGCA: upsert por CNPJ."""

    def test_import_upsert_por_cnpj(self):
        token = self.login()
        cnpj = '12.345.678/0001-99'
        status, d = self.request('POST', '/api/fornecedores/import', {'fornecedores': [
            {'cnpj': cnpj, 'razao_social': 'Empresa Teste LTDA'},
            {'cnpj': '123', 'razao_social': 'CNPJ inválido — ignorar'},
        ]}, token=token)
        self.assertEqual(status, 200, d)
        self.assertEqual(d['novos'], 1)
        self.assertEqual(d['ignorados'], 1)

        # Re-importar o mesmo CNPJ atualiza, não duplica
        status, d2 = self.request('POST', '/api/fornecedores/import', {'fornecedores': [
            {'cnpj': cnpj, 'razao_social': 'Empresa Teste LTDA (novo nome)'},
        ]}, token=token)
        self.assertEqual(d2['atualizados'], 1)
        self.assertEqual(d2['novos'], 0)

        status, lst = self.request('GET', '/api/fornecedores', token=token)
        matches = [f for f in lst['items'] if f.get('cnpj') == cnpj]
        self.assertEqual(len(matches), 1, 'não deve duplicar por CNPJ')
        self.assertEqual(matches[0]['razao_social'], 'Empresa Teste LTDA (novo nome)')


class TestBackupPreservaColunasSql(SGCDTestCase):
    """Regressão do eixo perda de dado (auditoria 2026-07-24).

    `created_by` e `deleted_at` são colunas SQL que não existem dentro do blob
    JSON de cada registro. O backup levava só o blob, então restaurar apagava a
    autoria do processo e devolvia ao cadastro tudo o que estava na Lixeira.
    """

    def _criar_fornecedor(self, token, cnpj='11.222.333/0001-81'):
        status, f = self.request('POST', '/api/fornecedores',
                                 {'cnpj': cnpj, 'razao': 'Alfa Comércio Ltda'}, token=token)
        self.assertEqual(status, 200, f)
        return f['id']

    def _col(self, tabela, coluna, rid):
        with server.get_db() as conn:
            row = conn.execute(f'SELECT {coluna} FROM {tabela} WHERE id=?', (rid,)).fetchone()
        return row[coluna] if row else None

    def test_restaurar_preserva_autoria_do_processo(self):
        token = self.login()
        status, p = self.request('POST', '/api/processes',
                                 {'objeto': 'Aquisição de teste'}, token=token)
        self.assertEqual(status, 200, p)
        pid = p['id']
        autor = self._col('processes', 'created_by', pid)
        self.assertIsNotNone(autor, 'processo nasceu sem autoria — teste inválido')

        _, backup = self.request('GET', '/api/backup', token=token)
        self.assertEqual(self.request('POST', '/api/backup/restore', backup, token=token)[0], 200)
        self.assertEqual(self._col('processes', 'created_by', pid), autor,
                         'restaurar backup perdeu a autoria do processo')

    def test_restaurar_nao_ressuscita_item_da_lixeira(self):
        token = self.login()
        fid = self._criar_fornecedor(token, '22.333.444/0001-92')
        self.assertEqual(self.request('DELETE', f'/api/fornecedores/{fid}', token=token)[0], 200)
        excluido_em = self._col('fornecedores', 'deleted_at', fid)
        self.assertIsNotNone(excluido_em, 'exclusão não marcou deleted_at — teste inválido')

        _, backup = self.request('GET', '/api/backup', token=token)
        self.assertEqual(self.request('POST', '/api/backup/restore', backup, token=token)[0], 200)
        self.assertEqual(self._col('fornecedores', 'deleted_at', fid), excluido_em,
                         'restaurar backup tirou o fornecedor da Lixeira')

    def test_importar_nao_ressuscita_item_da_lixeira(self):
        token = self.login()
        fid = self._criar_fornecedor(token, '33.444.555/0001-03')
        self.request('DELETE', f'/api/fornecedores/{fid}', token=token)
        excluido_em = self._col('fornecedores', 'deleted_at', fid)

        status, _ = self.request('POST', '/api/fornecedores/import',
                                 {'fornecedores': [{'id': fid, 'cnpj': '33.444.555/0001-03',
                                                    'razao': 'Alfa Comércio Ltda'}]}, token=token)
        self.assertEqual(status, 200)
        self.assertEqual(self._col('fornecedores', 'deleted_at', fid), excluido_em,
                         'importar fornecedores tirou da Lixeira quem estava excluído')

    def test_criar_processo_com_id_de_um_na_lixeira_nao_o_ressuscita(self):
        # POST /api/processes aceita id explícito e usa INSERT OR REPLACE: sem a
        # subconsulta, o REPLACE zerava deleted_at e tirava o processo da Lixeira.
        token = self.login()
        status, p = self.request('POST', '/api/processes', {'objeto': 'Vai para a Lixeira'}, token=token)
        pid = p['id']
        self.assertEqual(self.request('DELETE', f'/api/processes/{pid}', token=token)[0], 200)
        excluido_em = self._col('processes', 'deleted_at', pid)
        self.assertIsNotNone(excluido_em, 'exclusão não marcou deleted_at — teste inválido')

        status, _ = self.request('POST', '/api/processes',
                                 {'id': pid, 'objeto': 'Tentando ressuscitar'}, token=token)
        self.assertEqual(status, 200)
        self.assertEqual(self._col('processes', 'deleted_at', pid), excluido_em,
                         'criar processo com o mesmo id tirou o anterior da Lixeira')

    def test_sql_extra_nao_polui_o_registro(self):
        # A chave '_sql' carrega as colunas no arquivo; não pode acabar dentro do
        # blob regravado, que é o que o front consome.
        token = self.login()
        status, p = self.request('POST', '/api/processes', {'objeto': 'Outro teste'}, token=token)
        pid = p['id']
        _, backup = self.request('GET', '/api/backup', token=token)
        self.request('POST', '/api/backup/restore', backup, token=token)
        with server.get_db() as conn:
            blob = json.loads(conn.execute('SELECT data FROM processes WHERE id=?', (pid,)).fetchone()['data'])
        self.assertNotIn('_sql', blob)


class TestBackupNaoVazaCredencial(SGCDTestCase):
    """Regressão do eixo perda de dado (auditoria 2026-07-24).

    O backup JSON exportava `sys_settings` inteiro, e ali mora a senha do SMTP
    do sistema (texto puro) e a chave do Portal da Transparência. O arquivo sai
    do servidor — o manual orienta enviá-lo a outra máquina —, então essas
    credenciais circulavam junto. Restaurar não as perde: o que o arquivo não
    traz é preservado como já está no banco.
    """

    SEGREDO = 'SENHA-SMTP-DO-SISTEMA-XYZ'

    def _gravar_segredo(self):
        with server.get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO sys_settings (key,value) VALUES ('smtp_pass',?)",
                         (self.SEGREDO,))
            conn.commit()

    def _ler_segredo(self):
        with server.get_db() as conn:
            row = conn.execute("SELECT value FROM sys_settings WHERE key='smtp_pass'").fetchone()
        return row['value'] if row else None

    def test_backup_nao_contem_a_senha_do_smtp(self):
        token = self.login()
        self._gravar_segredo()
        status, backup = self.request('GET', '/api/backup', token=token)
        self.assertEqual(status, 200)
        self.assertNotIn(self.SEGREDO, json.dumps(backup, ensure_ascii=False),
                         'senha do SMTP do sistema vazou no arquivo de backup')

    def test_restaurar_preserva_a_senha_do_smtp(self):
        token = self.login()
        self._gravar_segredo()
        _, backup = self.request('GET', '/api/backup', token=token)
        self.assertEqual(self.request('POST', '/api/backup/restore', backup, token=token)[0], 200)
        self.assertEqual(self._ler_segredo(), self.SEGREDO,
                         'restaurar backup apagou a senha do SMTP do sistema')


class TestSenhaPadraoObrigatoria(SGCDTestCase):
    """Regressão do eixo permissão/sigilo (auditoria 2026-07-24).

    A troca de senha obrigatória existia só no navegador: quem falasse direto
    com a API entrava com a senha padrão (que está no README e no manual) e
    usava o sistema inteiro, rotas de administrador inclusive.
    """

    def _usuario_pendente(self):
        adm = self.login()
        self.request('POST', '/api/usuarios',
                     {'username': 'pendente', 'nome': 'Pendente',
                       'password': 'senha123', 'senha': 'senha123', 'admin': True}, token=adm)
        with server.get_db() as conn:
            uid = conn.execute("SELECT id FROM usuarios WHERE username='pendente'").fetchone()['id']
            conn.execute('UPDATE usuarios SET must_change_password=1 WHERE id=?', (uid,))
            conn.commit()
        st, log = self.request('POST', '/api/auth/login', {'username': 'pendente', 'password': 'senha123'})
        self.assertEqual(st, 200, log)
        return log['token'], uid

    def test_api_recusa_enquanto_a_senha_nao_for_trocada(self):
        tok, _ = self._usuario_pendente()
        for rota in ('/api/processes', '/api/usuarios', '/api/backup'):
            st, _ = self.request('GET', rota, token=tok)
            self.assertEqual(st, 403, f'{rota} respondeu {st} com a senha padrão pendente')

    def test_libera_o_que_a_tela_de_troca_precisa(self):
        tok, uid = self._usuario_pendente()
        self.assertEqual(self.request('GET', '/api/auth/me', token=tok)[0], 200)
        st, _ = self.request('PUT', f'/api/usuarios/{uid}', {'password': 'TrocadaAgora#2026'}, token=tok)
        self.assertEqual(st, 200, 'não deu para trocar a própria senha')
        st, log = self.request('POST', '/api/auth/login',
                               {'username': 'pendente', 'password': 'TrocadaAgora#2026'})
        self.assertEqual(st, 200)
        self.assertEqual(self.request('GET', '/api/processes', token=log['token'])[0], 200,
                         'sistema continuou bloqueado depois de trocar a senha')


class TestAuditoriaDeConfiguracao(SGCDTestCase):
    """Achado 9 do eixo permissão/sigilo (auditoria 2026-07-24).

    Dados de Organização e brasão seguem abertos a qualquer usuário autenticado
    — decisão de projeto —, mas saem em todo documento gerado. Sem registro na
    trilha, uma alteração no nome do órgão ou no brasão aparecia em documento
    oficial sem rastro de quem fez.
    """
    def _ids_config(self):
        with server.get_db() as conn:
            return {r['id'] for r in conn.execute(
                "SELECT id FROM audit_global WHERE type='CONFIG_ALTERADA'")}

    def _novos_desde(self, ids_antes):
        # Compara por conjunto de ids, não por contagem: o banco é compartilhado
        # pela suíte e outros testes também mexem em configuração.
        with server.get_db() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM audit_global WHERE type='CONFIG_ALTERADA'")
                if r['id'] not in ids_antes]

    def test_alterar_dados_da_organizacao_gera_evento(self):
        token = self.login()
        antes = self._ids_config()
        st, _ = self.request('PUT', '/api/settings/org',
                             {'orgao': f'Prefeitura {uuid.uuid4().hex[:8]}'}, token=token)
        self.assertEqual(st, 200)
        novos = self._novos_desde(antes)
        self.assertEqual(len(novos), 1, 'alteração não entrou na trilha')
        self.assertIn('orgao', novos[0]['detail'])
        self.assertEqual(novos[0]['label'], 'Dados da organização alterados')

    def test_reenviar_os_mesmos_valores_nao_polui_a_trilha(self):
        # A tela reenvia todos os campos a cada "Salvar"; sem alteração real não
        # deve virar evento.
        token = self.login()
        fixo = f'Prefeitura {uuid.uuid4().hex[:8]}'
        self.request('PUT', '/api/settings/org', {'orgao': fixo}, token=token)
        antes = self._ids_config()
        self.request('PUT', '/api/settings/org', {'orgao': fixo}, token=token)
        self.assertEqual(self._novos_desde(antes), [], 'reenvio sem alteração gerou evento')

    def test_alterar_brasao_gera_evento(self):
        token = self.login()
        antes = self._ids_config()
        st, _ = self.request('PUT', '/api/settings/brasao',
                             {'brasao_dataurl': 'data:image/png;base64,' + uuid.uuid4().hex}, token=token)
        self.assertEqual(st, 200)
        novos = self._novos_desde(antes)
        self.assertEqual(len(novos), 1)
        self.assertEqual(novos[0]['label'], 'Brasão alterado')


class TestSenhaPadraoMarcadaNoBoot(SGCDTestCase):
    """Regressão do eixo permissão/sigilo (auditoria 2026-07-24).

    Quem instalou antes da coluna must_change_password existir recebeu 0 pelo
    DEFAULT do ALTER TABLE: ficou com a senha do manual e sem o bloqueio do
    servidor, porque a marca de troca só é gravada na criação do admin. O boot
    precisa remarcar quem continua na senha padrão.
    """

    def _limpa(self):
        with server.get_db() as conn:
            conn.execute("DELETE FROM usuarios WHERE username='antigo'")
            conn.execute("UPDATE usuarios SET must_change_password=0 WHERE username='admin'")
            conn.commit()

    def _cria_e_reinicia(self, senha):
        self.addCleanup(self._limpa)
        with server.get_db() as conn:
            conn.execute(
                'INSERT INTO usuarios (username,nome,senha_hash,admin,ativo,must_change_password)'
                ' VALUES (?,?,?,0,1,0)',
                ('antigo', 'Instalacao antiga', server._hash_password(senha)))
            conn.commit()
        server.init_db()   # o que acontece a cada início do servidor
        with server.get_db() as conn:
            return conn.execute(
                "SELECT must_change_password FROM usuarios WHERE username='antigo'"
            ).fetchone()['must_change_password']

    def test_boot_marca_quem_ficou_na_senha_padrao(self):
        self.assertEqual(self._cria_e_reinicia('admin123'), 1,
                         'conta com a senha padrão seguiu sem exigir troca')

    def test_boot_nao_mexe_em_quem_ja_trocou(self):
        self.assertEqual(self._cria_e_reinicia('OutraSenha#2026'), 0,
                         'exigiu troca de quem já tinha saído da senha padrão')


class TestMotorErros(SGCDTestCase):
    """Motor de captura e tratamento de erros (piloto SGCD, 2026-07): classificação
    cliente(400)/servidor(500), report de erro do navegador, e tela admin de erros."""

    def _raw(self, method, path, data, token=None):
        conn = http.client.HTTPConnection('127.0.0.1', PORT, timeout=10)
        hdrs = {'Content-Type': 'application/json'}
        if token: hdrs['Authorization'] = f'Bearer {token}'
        conn.request(method, path, body=data, headers=hdrs)
        resp = conn.getresponse(); body = resp.read(); conn.close()
        try: return resp.status, json.loads(body) if body else None
        except ValueError: return resp.status, body

    def test_param_invalido_400(self):
        tok = self.login()
        self.assertEqual(self.request('GET', '/api/processes?per=abc', token=tok)[0], 400)

    def test_log_client_sem_auth_204(self):
        # Endpoint público (erro pode ser antes do login), fire-and-forget -> 204
        st, _ = self._raw('POST', '/api/log/client',
                          json.dumps({'msg': 'boom no teste', 'view': 'view-x', 'stack': 'a\nb'}).encode())
        self.assertEqual(st, 204)

    def test_log_client_chega_no_log_e_no_diagnostico(self):
        tok = self.login()
        marca = f'erro-teste-{uuid.uuid4().hex[:8]}'
        self._raw('POST', '/api/log/client', json.dumps({'msg': marca, 'view': 'view-y'}).encode())
        # prova order-independent: o erro do cliente foi parar no log do servidor
        caminho = server.sgx_base.caminho_log_erros(server._DATA_DIR, 'SGCD')
        # errors='replace': o log pode ter linhas antigas em cp1252 misturadas com
        # as novas UTF-8 (transição). A marca é ASCII, então aparece de qualquer forma.
        with open(caminho, encoding='utf-8', errors='replace') as f:
            self.assertIn(marca, f.read())
        # e o diagnóstico expõe um grupo de erro de navegador (cliente-js)
        st, d = self.request('GET', '/api/diagnostico/erros', token=tok)
        self.assertEqual(st, 200)
        self.assertTrue(any('cliente-js' in g.get('tipo', '') for g in d['erros']),
                        'nenhum grupo cliente-js no diagnóstico')

    def test_diagnostico_so_mostra_a_janela_recente(self):
        """A tela se chama "Erros recentes": defeito ja corrigido nao pode ficar
        la para sempre (o log so rotaciona aos 2 MB). O que e mais antigo que a
        janela vira contagem em 'anteriores' — sem apagar nada do arquivo."""
        import datetime, tempfile, shutil
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        agora = datetime.datetime.now()
        def ts(dias): return (agora - datetime.timedelta(days=dias)).isoformat(timespec='seconds')
        linhas = [
            f"{ts(30)} | ERROR | operacional | rota-x | antigo",
            f"{ts(8)} | WARNING | operacional | cliente-js | fora da janela por 1 dia",
            f"{ts(6)} | WARNING | operacional | cliente-js | dentro",
            f"{ts(1)} | ERROR | operacional | rota-y | ontem",
            "    at algo (arquivo.html:1:1)",
        ]
        caminho = server.sgx_base.caminho_log_erros(d, 'SGCD')
        with open(caminho, 'w', encoding='utf-8', newline='') as f:
            f.write('\n'.join(linhas) + '\n')

        r = server.sgx_base.ler_diagnostico_erros(d, 'SGCD')
        self.assertEqual(r['dias'], 7)
        self.assertEqual(r['anteriores'], 2, 'os dois mais velhos deviam ficar fora da janela')
        self.assertEqual(sum(g['count'] for g in r['erros']), 2)

        # a janela e parametrizavel, e com ela larga nada fica de fora
        r30 = server.sgx_base.ler_diagnostico_erros(d, 'SGCD', dias=31)
        self.assertEqual(r30['anteriores'], 0)
        self.assertEqual(sum(g['count'] for g in r30['erros']), 4)

        # o arquivo continua intacto: filtrar nao apaga
        with open(caminho, encoding='utf-8') as f:
            self.assertEqual(len(f.readlines()), 5)

    def test_diagnostico_erros_so_admin(self):
        admin = self.login()
        self.request('POST', '/api/usuarios', {'username': 'u_diag', 'nome': 'U', 'password': 'senha123'}, token=admin)
        comum = self.request('POST', '/api/auth/login', {'username': 'u_diag', 'password': 'senha123'})[1]['token']
        self.assertEqual(self.request('GET', '/api/diagnostico/erros', token=comum)[0], 403)


class TestRecusaSenhaPadrao(SGCDTestCase):
    """Não deixa definir a senha de fábrica como NOVA senha — senão a troca
    obrigatória vira contornável (digitar admin123 zera must_change_password sem
    trocar nada de fato). Ver sgx_base.eh_senha_padrao."""

    def test_recusa_admin123_como_nova_senha(self):
        tok = self.login()
        with server.get_db() as conn:
            uid = conn.execute("SELECT id FROM usuarios WHERE username='admin'").fetchone()['id']
        st, r = self.request('PUT', f'/api/usuarios/{uid}', {'password': 'admin123'}, token=tok)
        self.assertEqual(st, 400, r)
        self.assertIn('padrão', (r or {}).get('error', ''))


class TestSyncFornecedor(SGCDTestCase):
    """Cadastro de fornecedor compartilhado (2026-07): export + sync peer por CNPJ
    com last-write-wins e revisão manual (marca d'água syncedAt). Endpoints
    destrutivos do cadastro — cada teste usa CNPJs próprios e confere só o que escreveu."""

    def _forn(self, cnpj, razao, updated):
        return {'cnpj': cnpj, 'razao_social': razao, 'updatedAt': updated}

    def _set_data(self, cnpj_like, **kv):
        with server.get_db() as conn:
            row = conn.execute("SELECT id,data FROM fornecedores WHERE cnpj LIKE ?", (cnpj_like,)).fetchone()
            d = json.loads(row['data']); d.update(kv)
            conn.execute("UPDATE fornecedores SET data=? WHERE id=?", (json.dumps(d), row['id'])); conn.commit()
            return d

    def test_export_envelope_e_compliance(self):
        tok = self.login()
        self.request('POST', '/api/fornecedores', {'cnpj': '90.001.001/0001-00', 'razao_social': 'ExpTest',
                                                    'ceis': 'SIM', 'updatedAt': 1000}, token=tok)
        st, d = self.request('GET', '/api/fornecedores/export', token=tok)
        self.assertEqual(st, 200)
        self.assertEqual(d['_sgx'], 'SGCD')
        self.assertEqual(d['tipo'], 'fornecedores')
        alvo = next(f for f in d['fornecedores'] if f['cnpj'].startswith('90.001'))
        self.assertEqual(alvo.get('ceis'), 'SIM')   # SGCD é dono do compliance — exporta

    def test_preview_classifica_e_apply_grava(self):
        tok = self.login()
        self.request('POST', '/api/fornecedores', {'cnpj': '90.002.001/0001-00', 'razao_social': 'Base', 'updatedAt': 1000}, token=tok)
        self._set_data('90.002.001%', syncedAt=1000)   # sincronizado, intocado -> update limpo
        arq = {'tipo': 'fornecedores', 'fornecedores': [
            self._forn('90.002.002/0001-00', 'Novo', 2000),              # inserir
            self._forn('90.002.001/0001-00', 'Base Ltda', 5000),        # atualizar (só remoto)
        ]}
        st, prev = self.request('POST', '/api/fornecedores/sync/preview', arq, token=tok)
        self.assertEqual(st, 200)
        self.assertEqual((prev['inserir'], prev['atualizar'], len(prev['conflitos'])), (1, 1, 0))
        st, ap = self.request('POST', '/api/fornecedores/sync/apply', arq, token=tok)
        self.assertEqual((ap['novos'], ap['atualizados']), (1, 1))
        st, lst = self.request('GET', '/api/fornecedores?per=2000', token=tok)
        nomes = {f.get('cnpj'): f.get('razao_social') for f in lst['items']}
        self.assertEqual(nomes.get('90.002.001/0001-00'), 'Base Ltda')   # atualizado
        self.assertEqual(nomes.get('90.002.002/0001-00'), 'Novo')        # inserido

    def test_conflito_vai_para_revisao_e_resolve(self):
        tok = self.login()
        self.request('POST', '/api/fornecedores', {'cnpj': '90.003.001/0001-00', 'razao_social': 'Local', 'updatedAt': 5000}, token=tok)
        self._set_data('90.003.001%', syncedAt=1000)   # local mexeu depois do sync (5000 > 1000)
        arq = {'tipo': 'fornecedores', 'fornecedores': [self._forn('90.003.001/0001-00', 'Remoto', 3000)]}  # remoto tb mexeu (3000 > 1000)
        st, prev = self.request('POST', '/api/fornecedores/sync/preview', arq, token=tok)
        self.assertEqual(len(prev['conflitos']), 1)
        self.assertEqual(prev['conflitos'][0]['cnpj'], '90003001000100')
        # resolve a favor do arquivo
        st, ap = self.request('POST', '/api/fornecedores/sync/apply',
                              {**arq, 'resolver': {'90003001000100': 'arquivo'}}, token=tok)
        self.assertEqual(ap['conflitos_aplicados'], 1)
        st, lst = self.request('GET', '/api/fornecedores?per=2000', token=tok)
        alvo = next(f for f in lst['items'] if (f.get('cnpj') or '').startswith('90.003.001'))
        self.assertEqual(alvo['razao_social'], 'Remoto')

    def test_sync_e_idempotente(self):
        tok = self.login()
        self.request('POST', '/api/fornecedores', {'cnpj': '90.004.001/0001-00', 'razao_social': 'X', 'updatedAt': 1000}, token=tok)
        self._set_data('90.004.001%', syncedAt=1000)
        arq = {'tipo': 'fornecedores', 'fornecedores': [self._forn('90.004.001/0001-00', 'X2', 5000)]}
        self.request('POST', '/api/fornecedores/sync/apply', arq, token=tok)
        st, prev = self.request('POST', '/api/fornecedores/sync/preview', arq, token=tok)
        self.assertEqual((prev['inserir'], prev['atualizar'], len(prev['conflitos'])), (0, 0, 0))

    def test_arquivo_invalido_recusado(self):
        tok = self.login()
        st, _ = self.request('POST', '/api/fornecedores/sync/preview', {'foo': 1}, token=tok)
        self.assertEqual(st, 400)


class TestBackupCofre(SGCDTestCase):
    """Padronização do backup (2026-07): Cofre .zip (banco + anexos) via sgx_base,
    com leitura retrocompatível do .db legado. O round-trip de anexos em si é
    coberto pela suíte do SGDP (mesmo helper compartilhado)."""

    def _raw(self, method, path, data, token):
        conn = http.client.HTTPConnection('127.0.0.1', PORT, timeout=15)
        hdrs = {'Content-Length': str(len(data))}
        if token: hdrs['Authorization'] = f'Bearer {token}'
        conn.request(method, path, body=data, headers=hdrs)
        resp = conn.getresponse(); body = resp.read(); conn.close()
        try: return resp.status, json.loads(body)
        except ValueError: return resp.status, body

    def test_cofre_e_zip_com_banco(self):
        token = self.login()
        self.request('POST', '/api/processes', {'objeto': 'Proc do Cofre'}, token=token)
        st, raw = self.request('GET', '/api/backup/db', token=token)
        self.assertEqual(st, 200)
        self.assertEqual(raw[:4], b'PK\x03\x04')
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            self.assertIn('banco.db', z.namelist())

    def test_restaura_cofre_zip(self):
        token = self.login()
        self.request('POST', '/api/processes', {'objeto': 'Proc que volta do Cofre'}, token=token)
        _, raw = self.request('GET', '/api/backup/db', token=token)
        st, d = self._raw('POST', '/api/backups/db/restore', raw, token)
        self.assertEqual(st, 200, d)
        st, listado = self.request('GET', '/api/processes', token=token)
        self.assertTrue(any(p['objeto'] == 'Proc que volta do Cofre' for p in listado['items']))

    def test_restore_aceita_db_legado(self):
        token = self.login()
        legado = os.path.join(server.BACKUP_DIR, 'legado.db')
        s = sqlite3.connect(server.DB_PATH); k = sqlite3.connect(legado)
        try:
            with k: s.backup(k)
        finally:
            s.close(); k.close()
        with open(legado, 'rb') as f: db_bytes = f.read()
        os.remove(legado)
        st, d = self._raw('POST', '/api/backups/db/restore', db_bytes, token)
        self.assertEqual(st, 200, d)

    def test_arquivos_invalidos_recusados(self):
        token = self.login()
        self.assertEqual(self.request('POST', '/api/backup/restore', {'foo': 1}, token=token)[0], 400)
        self.assertEqual(self._raw('POST', '/api/backups/db/restore', b'lixo', token)[0], 400)


class TestImportFornecedoresSoAdmin(SGCDTestCase):
    """A importação de CSV de fornecedores passou a usar a rota /import (restrita
    ao administrador), que grava em lote e faz upsert por CNPJ. Antes o navegador
    gravava um a um pela rota comum de edição: qualquer usuário importava, e
    reimportar o mesmo arquivo duplicava o cadastro."""

    def _linhas(self, cnpj, razao):
        return {'fornecedores': [{'cnpj': cnpj, 'razao': razao, 'razao_social': razao}]}

    def test_usuario_comum_nao_importa(self):
        admin = self.login()
        st, u = self.request('POST', '/api/usuarios',
                             {'username': 'u_import_sgcd', 'nome': 'Comum', 'password': 'senha123'}, token=admin)
        self.assertEqual(st, 200, u)
        comum = self.request('POST', '/api/auth/login',
                             {'username': 'u_import_sgcd', 'password': 'senha123'})[1]['token']
        st, d = self.request('POST', '/api/fornecedores/import',
                             self._linhas('55666777000188', 'Fornecedor CSV LTDA'), token=comum)
        self.assertEqual(st, 403, d)

    def test_reimportar_nao_duplica(self):
        admin = self.login()
        payload = self._linhas('99888777000166', 'Fornecedor Repetido LTDA')
        st, d1 = self.request('POST', '/api/fornecedores/import', payload, token=admin)
        self.assertEqual(st, 200, d1)
        self.assertEqual((d1['novos'], d1['atualizados']), (1, 0))
        st, d2 = self.request('POST', '/api/fornecedores/import', payload, token=admin)
        self.assertEqual(st, 200, d2)
        self.assertEqual((d2['novos'], d2['atualizados']), (0, 1))
        st, lista = self.request('GET', '/api/fornecedores', token=admin)
        iguais = [f for f in lista['items'] if (f.get('cnpj') or '').replace('.', '').replace('/', '').replace('-', '') == '99888777000166']
        self.assertEqual(len(iguais), 1, 'reimportar não pode duplicar o fornecedor')


class TestGuardaExclusaoFornecedor(SGCDTestCase):
    """A recusa de excluir fornecedor vinculado a processo vivia só na tela: a
    exclusão em massa chamava a rota direto e passava por cima dela. A regra
    agora é do servidor, então vale para qualquer caminho."""

    def _forn(self, token, cnpj, razao):
        st, d = self.request('POST', '/api/fornecedores', {'cnpj': cnpj, 'razaoSocial': razao}, token=token)
        self.assertEqual(st, 200, d)
        return d['id']

    def test_bloqueia_fornecedor_vencedor_de_processo(self):
        token = self.login()
        fid = self._forn(token, '11222333000181', 'Fornecedor Vencedor LTDA')
        st, proc = self.request('POST', '/api/processes',
                                {'objeto': 'Processo com vencedor', 'fornecedor': {'id': fid}}, token=token)
        self.assertEqual(st, 200, proc)
        st, d = self.request('DELETE', f'/api/fornecedores/{fid}', token=token)
        self.assertEqual(st, 409, d)
        self.assertIn('vinculado a 1 processo', d['error'])

    def test_bloqueia_fornecedor_so_com_proposta(self):
        """Proposta guarda só o CNPJ digitado na etapa — não o id do fornecedor."""
        token = self.login()
        fid = self._forn(token, '44555666000177', 'Fornecedor Proponente LTDA')
        propostas = json.dumps([{'cnpj': '44.555.666/0001-77', 'valor': 100}])
        st, proc = self.request('POST', '/api/processes', {
            'objeto': 'Processo com proposta',
            'steps': [{'fields': {'_propostas': propostas}}]}, token=token)
        self.assertEqual(st, 200, proc)
        st, d = self.request('DELETE', f'/api/fornecedores/{fid}', token=token)
        self.assertEqual(st, 409, d)

    def test_permite_excluir_fornecedor_sem_vinculo(self):
        token = self.login()
        fid = self._forn(token, '77888999000155', 'Fornecedor Livre LTDA')
        st, _ = self.request('DELETE', f'/api/fornecedores/{fid}', token=token)
        self.assertEqual(st, 200)

    def test_so_a_purga_libera_o_fornecedor(self):
        """A Lixeira não basta: o processo pode voltar, e o fornecedor excluído
        nesse meio-tempo deixaria o processo restaurado apontando para o vazio.
        (Esta regra mudou: antes bastava mandar o processo à Lixeira.)"""
        token = self.login()
        fid = self._forn(token, '22333444000166', 'Fornecedor de Processo Excluido')
        st, proc = self.request('POST', '/api/processes',
                                {'objeto': 'Processo que vai pra lixeira', 'fornecedor': {'id': fid}}, token=token)
        self.assertEqual(st, 200, proc)
        self.assertEqual(self.request('DELETE', f'/api/fornecedores/{fid}', token=token)[0], 409)
        self.request('DELETE', f"/api/processes/{proc['id']}", token=token)          # -> Lixeira
        self.assertEqual(self.request('DELETE', f'/api/fornecedores/{fid}', token=token)[0], 409)
        self.request('DELETE', f"/api/processes/{proc['id']}?purge=1", token=token)  # -> definitivo
        self.assertEqual(self.request('DELETE', f'/api/fornecedores/{fid}', token=token)[0], 200)


class TestVinculosEFornecedorNaLixeira(SGCDTestCase):
    """Dois efeitos colaterais da exclusão que passavam despercebidos: o vínculo
    entre processos ficava apontando para o registro apagado, e a proteção do
    fornecedor ignorava os processos que estão na Lixeira (e podem voltar)."""

    def _processo(self, token, objeto, **extra):
        st, p = self.request('POST', '/api/processes', {'objeto': objeto, **extra}, token=token)
        self.assertEqual(st, 200, p)
        return p['id']

    def test_purga_remove_o_vinculo_do_outro_processo(self):
        token = self.login()
        a = self._processo(token, 'Processo A')
        b = self._processo(token, 'Processo B',
                           processos_relacionados=[{'id': a, 'num': '1/2026', 'tipo': 'renovacao'}])
        # o vínculo existe antes
        st, doc = self.request('GET', f'/api/processes/{b}', token=token)
        self.assertEqual([v['id'] for v in doc['processos_relacionados']], [a])

        # na Lixeira o vínculo permanece (o processo pode ser restaurado)
        self.assertEqual(self.request('DELETE', f'/api/processes/{a}', token=token)[0], 200)
        st, doc = self.request('GET', f'/api/processes/{b}', token=token)
        self.assertEqual([v['id'] for v in doc['processos_relacionados']], [a],
                         'exclusão reversível não pode apagar o vínculo do outro lado')

        # a purga definitiva limpa
        self.assertEqual(self.request('DELETE', f'/api/processes/{a}?purge=1', token=token)[0], 200)
        st, doc = self.request('GET', f'/api/processes/{b}', token=token)
        self.assertEqual(doc.get('processos_relacionados'), [])

    def test_fornecedor_segue_bloqueado_com_processo_na_lixeira(self):
        token = self.login()
        st, f = self.request('POST', '/api/fornecedores',
                             {'cnpj': '88999000000111', 'razaoSocial': 'Fornecedor da Lixeira'}, token=token)
        self.assertEqual(st, 200, f)
        pid = self._processo(token, 'Processo que vai para a lixeira', fornecedor={'id': f['id']})

        self.assertEqual(self.request('DELETE', f'/api/processes/{pid}', token=token)[0], 200)
        st, d = self.request('DELETE', f"/api/fornecedores/{f['id']}", token=token)
        self.assertEqual(st, 409, d)
        self.assertIn('na Lixeira', d['error'])

        # purgado o processo, o fornecedor libera
        self.assertEqual(self.request('DELETE', f'/api/processes/{pid}?purge=1', token=token)[0], 200)
        self.assertEqual(self.request('DELETE', f"/api/fornecedores/{f['id']}", token=token)[0], 200)


class TestAnexoProcesso(SGCDTestCase):
    """Anexo de etapa. O front grava um process_id COMPOSTO ("<id>_<etapa>") para
    buscar os anexos de uma etapa por prefixo; a tabela files chegou a declarar uma
    foreign key para processes(id), o que fazia todo upload falhar em banco novo."""

    def _upload(self, process_id, token, nome='doc.pdf'):
        boundary = '----sgcdtest'
        corpo = (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="step_index"\r\n\r\n0\r\n'
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="file"; filename="{nome}"\r\n'
            f'Content-Type: application/pdf\r\n\r\n'
        ).encode() + b'%PDF-1.4 conteudo de teste\r\n' + f'--{boundary}--\r\n'.encode()
        conn = http.client.HTTPConnection('127.0.0.1', PORT, timeout=10)
        conn.request('POST', f'/api/processes/{process_id}/files', body=corpo, headers={
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Authorization': f'Bearer {token}'})
        resp = conn.getresponse(); body = resp.read(); conn.close()
        try: return resp.status, json.loads(body) if body else None
        except ValueError: return resp.status, body

    def test_anexo_com_process_id_composto(self):
        token = self.login()
        st, proc = self.request('POST', '/api/processes', {'objeto': 'Processo com anexo'}, token=token)
        self.assertEqual(st, 200, proc)
        pid = proc['id']
        st, d = self._upload(f'{pid}_0', token)
        self.assertEqual(st, 200, d)          # antes: 500 por FOREIGN KEY constraint failed
        self.assertEqual(d['process_id'], f'{pid}_0')
        # e a busca por prefixo, que é o motivo do id composto, encontra o anexo
        st, lista = self.request('GET', f'/api/files?process_id={pid}&prefix=1', token=token)
        self.assertEqual(st, 200, lista)
        self.assertEqual([f['process_id'] for f in lista['items']], [f'{pid}_0'])

    def test_files_sem_foreign_key_para_processes(self):
        """Trava a regressão no schema, não só no efeito."""
        import sqlite3
        with sqlite3.connect(server.DB_PATH) as conn:
            fks = [f[2] for f in conn.execute('PRAGMA foreign_key_list(files)').fetchall()]
        self.assertNotIn('processes', fks)


if __name__ == '__main__':
    unittest.main()
