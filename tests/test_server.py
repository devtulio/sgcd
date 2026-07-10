# Suíte de testes do backend (server.py) — sobe o servidor real contra um
# banco/uploads/backups temporários e bate nos endpoints REST via http.client.
# python -m unittest discover -s tests   (ou: python tests/test_server.py)
import base64
import http.client
import json
import os
import shutil
import socketserver
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402

PORT = 3091
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
    server.init_db()

    socketserver.ThreadingTCPServer.allow_reuse_address = True
    _httpd = socketserver.ThreadingTCPServer(('127.0.0.1', PORT), server.SGCDHandler)
    _thread = threading.Thread(target=_httpd.serve_forever, daemon=True)
    _thread.start()


def tearDownModule():
    _httpd.shutdown()
    _httpd.server_close()
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
        with server.get_db() as conn:
            row = conn.execute('SELECT must_change_password FROM usuarios WHERE username=?', ('admin',)).fetchone()
        self.assertEqual(row['must_change_password'], 1)


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
        self.assertTrue(data['_sgcd'])
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

    def test_excecao_nao_tratada_retorna_500_em_vez_de_derrubar_conexao(self):
        # Regressão: handle_error estava definido na classe errada (nunca era
        # chamado de verdade) — qualquer exceção não tratada derrubava a conexão
        # sem resposta nenhuma. Agora _safe_dispatch garante um 500 JSON limpo.
        token = self.login()
        status, data = self.request('GET', '/api/processes?page=nao-e-um-numero', token=token)
        self.assertEqual(status, 500)
        self.assertIn('error', data)

        # Confirma que o servidor continua respondendo normalmente depois
        status, _ = self.request('GET', '/health')
        self.assertEqual(status, 200)


class TestNuncaEncerraSozinho(SGCDTestCase):

    def test_ultima_sessao_expirar_nao_derruba_o_processo(self):
        # Regressão: existia um modo "Pessoal" em que _check_shutdown() chamava
        # os._exit(0) quando a última sessão ativa expirava — SESSION_TTL=15s é
        # curto o bastante para isso disparar sozinho (aba em 2º plano ao abrir
        # um popup de documento sofre throttling do ping). os._exit(0) mata o
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


if __name__ == '__main__':
    unittest.main()
