# SGCD v2.36.2 — Servidor local: SQLite, autenticação, REST API, proxy CNPJ, e-mail SMTP, backup automático
import http.server
import socketserver
import os
import json
import sqlite3
import hashlib
import secrets
import ssl
import smtplib
import threading
import time
import subprocess
import sys
import urllib.request
import logging
import urllib.error
import uuid
import re
import base64

# Windows: console pode usar cp1252/cp850 em vez de UTF-8, quebrando prints
# com caracteres especiais (╔═╗, emojis). Força UTF-8 para evitar UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        try:
            _stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
import html as html_mod
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlparse, parse_qs

import sgx_base   # esqueleto compartilhado da família — ver _esqueleto/README.md

# Versão do servidor — DEVE acompanhar o SGCD_VERSION do SGCD.html a cada release.
# Exposta em /health para o frontend detectar quando o processo em execução está
# desatualizado (HTML novo servido, mas server.py antigo ainda rodando em memória).
SERVER_VERSION = '2.36.2'

PORT          = int(os.environ.get('SGCD_PORT', 3000))
_BASE         = os.path.dirname(os.path.abspath(__file__))
# SGCD_DATA_DIR: usado pelos testes E2E para isolar banco/uploads/backups do
# sgcd.db real sem precisar rodar o servidor a partir de outra pasta (os
# arquivos estáticos como SGCD.html continuam servidos a partir de _BASE).
_DATA_DIR     = os.environ.get('SGCD_DATA_DIR', _BASE)
DB_PATH       = os.path.join(_DATA_DIR, 'sgcd.db')
UPLOADS_DIR   = os.path.join(_DATA_DIR, 'uploads')
BACKUP_DIR    = os.path.join(_DATA_DIR, 'backups')
LOG_PATH      = os.path.join(_DATA_DIR, 'sgcd_errors.log')
BACKUP_KEEP   = 7        # número de backups automáticos mantidos
SESSION_TTL   = 60   # renovado pelo ping a cada 5s (ver comentário em _watchdog mais abaixo)
MAX_UPLOAD    = 50 * 1024 * 1024   # 50 MB — limite de tamanho por upload
ALLOWED_EXTS  = {'.pdf','.docx','.doc','.xlsx','.xls','.odt','.ods','.png','.jpg','.jpeg','.gif','.webp','.txt','.csv','.zip'}

os.makedirs(_DATA_DIR, exist_ok=True)
logging.basicConfig(
    filename=LOG_PATH, level=logging.ERROR,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
_log = logging.getLogger('sgcd')

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(UPLOADS_DIR, exist_ok=True)

_watchdog_paused  = False   # pausa o watchdog durante diálogos bloqueantes (ex: FolderBrowser)
_had_session      = False   # True após primeiro login; controla quando o backup pós-sessão pode disparar
_backup_pos_sess  = False   # True = backup pós-sessão já executado; aguarda nova sessão para resetar

# ── Banco de dados ────────────────────────────────────────────────────────────
# _ConnAutoClose vem do sgx_base (esqueleto compartilhado da família) — mantido
# como alias de módulo porque o nome é referenciado diretamente em vários pontos
# do arquivo (backup/restore/integrity check), não só dentro de get_db().
_ConnAutoClose = sgx_base.ConnAutoClose

# get_db() fica local (não um valor capturado no import) porque os testes
# reatribuem DB_PATH depois do import (setUpModule isola o banco num dir
# temporário) — get_db() precisa reler esse global a cada chamada, não uma
# closure de DB_PATH.
def get_db():
    return sgx_base.connect_db(DB_PATH)

def init_db():
    with get_db() as conn:
        # Migração: tabela 'users' (nome antigo) → 'usuarios' (padrão SGDP).
        # SQLite atualiza sozinho as FKs de sessions/processes/files/signatures
        # que apontavam para users(id); preserva cargo/matricula e demais dados.
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'users' in tables and 'usuarios' not in tables:
            conn.execute('ALTER TABLE users RENAME TO usuarios')
            conn.commit()
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT NOT NULL UNIQUE COLLATE NOCASE,
                nome       TEXT NOT NULL,
                cpf        TEXT,
                email      TEXT,
                cargo      TEXT,
                matricula  TEXT,
                senha_hash TEXT NOT NULL,
                admin      INTEGER DEFAULT 0,
                ativo      INTEGER DEFAULT 1,
                criado_em  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token    TEXT PRIMARY KEY,
                user_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
                expires  REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS processes (
                id         TEXT PRIMARY KEY,
                data       TEXT NOT NULL,
                objeto     TEXT,
                status     TEXT DEFAULT 'em_andamento',
                unidade    TEXT,
                valor      REAL,
                num_proc   TEXT,
                num_dl     TEXT,
                created_at TEXT,
                updated_at TEXT,
                created_by INTEGER REFERENCES usuarios(id)
            );
            CREATE TABLE IF NOT EXISTS fornecedores (
                id           TEXT PRIMARY KEY,
                data         TEXT NOT NULL,
                cnpj         TEXT,
                razao_social TEXT,
                updated_at   TEXT
            );
            CREATE TABLE IF NOT EXISTS files (
                id            TEXT PRIMARY KEY,
                process_id    TEXT REFERENCES processes(id) ON DELETE CASCADE,
                step_index    INTEGER,
                nome_original TEXT NOT NULL,
                nome_disco    TEXT NOT NULL,
                tamanho       INTEGER,
                mime          TEXT,
                uploaded_by   INTEGER REFERENCES usuarios(id),
                uploaded_em   TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS audit_global (
                id          TEXT PRIMARY KEY,
                ts          TEXT NOT NULL,
                user_id     INTEGER,
                user_nome   TEXT,
                type        TEXT,
                label       TEXT,
                detail      TEXT,
                process_id  TEXT,
                process_obj TEXT
            );
            CREATE TABLE IF NOT EXISTS sys_settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS tags (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE COLLATE NOCASE
            );
            CREATE TABLE IF NOT EXISTS process_tags (
                process_id TEXT NOT NULL REFERENCES processes(id) ON DELETE CASCADE,
                tag_id     INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (process_id, tag_id)
            );
            CREATE INDEX IF NOT EXISTS idx_proc_status   ON processes(status);
            CREATE INDEX IF NOT EXISTS idx_proc_unidade  ON processes(unidade);
            CREATE INDEX IF NOT EXISTS idx_proc_updated  ON processes(updated_at);
            CREATE INDEX IF NOT EXISTS idx_files_proc    ON files(process_id);
            CREATE INDEX IF NOT EXISTS idx_forn_cnpj     ON fornecedores(cnpj);
            CREATE INDEX IF NOT EXISTS idx_audit_ts      ON audit_global(ts);
            CREATE INDEX IF NOT EXISTS idx_proc_tags_tag ON process_tags(tag_id);
        ''')
        # Assinatura digital (Simples/gov.br/ICP) removida — descarta a tabela e seus dados.
        conn.execute('DROP TABLE IF EXISTS signatures')
        # Migração: coluna deleted_at para lixeira (soft-delete) — SQLite não suporta
        # ADD COLUMN IF NOT EXISTS, então tentamos e ignoramos se já existir
        for tbl in ('processes', 'fornecedores'):
            try:
                conn.execute(f'ALTER TABLE {tbl} ADD COLUMN deleted_at TEXT')
            except sqlite3.OperationalError:
                pass
        conn.execute('CREATE INDEX IF NOT EXISTS idx_proc_deleted ON processes(deleted_at)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_forn_deleted ON fornecedores(deleted_at)')
        # Migração: colunas cpf/email em usuarios (cadastro de dados de contato)
        # + config SMTP por usuário (vazio = herda a config do sistema em sys_settings)
        for col in ('cpf', 'email', 'smtp_host', 'smtp_port', 'smtp_secure', 'smtp_require_tls',
                    'smtp_ignore_ssl', 'smtp_user', 'smtp_pass', 'smtp_from_name'):
            try:
                conn.execute(f'ALTER TABLE usuarios ADD COLUMN {col} TEXT')
            except sqlite3.OperationalError:
                pass
        try:
            conn.execute('ALTER TABLE usuarios ADD COLUMN must_change_password INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        # Sessões são descartadas a cada início do servidor (logout automático ao fechar janela)
        conn.execute('DELETE FROM sessions')
        # Cria admin padrão se não houver usuários
        if conn.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0] == 0:
            conn.execute(
                'INSERT INTO usuarios (username,nome,senha_hash,admin,must_change_password) VALUES (?,?,?,1,1)',
                ('admin', 'Administrador', _hash_password('admin123'))
            )
            conn.commit()
            print('Usuário padrão criado: admin / admin123 — troque a senha no primeiro acesso.')

# ── Segurança ─────────────────────────────────────────────────────────────────
# hash/verify de senha vêm do sgx_base (esqueleto compartilhado da família)
_hash_password   = sgx_base.hash_password
_verify_password = sgx_base.verify_password

# ── Rate limit de login (vem do sgx_base) ───────────────────────────────────
_rate_limiter = sgx_base.LoginRateLimiter(max_attempts=5, lockout_window=300)
_login_rate_limited   = _rate_limiter.is_locked
_record_login_failure = _rate_limiter.record_failure
_clear_login_failures = _rate_limiter.clear

# ── Sessões ──────────────────────────────────────────────────────────────────
# create_session/delete_session/renew_session/active_sessions delegam pro
# sgx_base (mecânica idêntica nos 4 sistemas). get_session() fica local: faz
# um SELECT de colunas explícito (não u.*) por segurança — nunca deve devolver
# a coluna de hash de senha junto com os dados da sessão — e as colunas
# selecionadas divergem por sistema (schema de usuarios não é idêntico).
def create_session(user_id):
    return sgx_base.create_session(get_db, user_id, SESSION_TTL)

def get_session(token):
    if not token:
        return None
    with get_db() as conn:
        row = conn.execute(
            '''SELECT s.token, s.user_id, s.expires,
                      u.nome, u.username, u.cpf, u.email, u.cargo, u.matricula, u.admin, u.ativo
               FROM sessions s JOIN usuarios u ON u.id=s.user_id
               WHERE s.token=? AND s.expires>? AND u.ativo=1''',
            (token, time.time())
        ).fetchone()
    return dict(row) if row else None

_USER_SMTP_COLS = ('smtp_host', 'smtp_port', 'smtp_secure', 'smtp_require_tls',
                   'smtp_ignore_ssl', 'smtp_user', 'smtp_pass', 'smtp_from_name')

def get_user_smtp(user_id):
    """Config SMTP (chaves smtp_*) do usuário; se ele não tiver host próprio,
    herda a config do sistema (sys_settings) — a mesma usada pelos alertas."""
    with get_db() as conn:
        row = conn.execute(f"SELECT {', '.join(_USER_SMTP_COLS)} FROM usuarios WHERE id=?", (user_id,)).fetchone()
        if row and (row['smtp_host'] or '').strip():
            return {c: (row[c] or '') for c in _USER_SMTP_COLS}
        rows = conn.execute("SELECT key,value FROM sys_settings WHERE key LIKE 'smtp_%'").fetchall()
    return {r['key']: r['value'] for r in rows}

def _smtp_cfg_build(cfg, default_name='SGCD'):
    """Converte chaves smtp_* no par (smtp_cfg, from) que _send_email_raw espera."""
    smtp_cfg = {
        'host': cfg.get('smtp_host', ''), 'port': int(cfg.get('smtp_port') or 587),
        'secure': cfg.get('smtp_secure') == '1', 'requireTLS': cfg.get('smtp_require_tls') != '0',
        'ignoreSSL': cfg.get('smtp_ignore_ssl') == '1',
        'auth': {'user': cfg.get('smtp_user', ''), 'pass': cfg.get('smtp_pass', '')},
    }
    frm = {'name': cfg.get('smtp_from_name') or default_name, 'email': cfg.get('smtp_user', '')}
    return smtp_cfg, frm

def delete_session(token):
    sgx_base.delete_session(get_db, token)

def renew_session(token):
    sgx_base.renew_session(get_db, token, SESSION_TTL)

def active_sessions():
    return sgx_base.active_sessions(get_db)

def _check_shutdown():
    """O servidor nunca encerra sozinho por contagem de sessões — só via Ctrl+C
    no terminal (ver bloco principal). Aqui só dispara um backup automático,
    uma única vez, depois que a última sessão ativa termina.

    ponytail: existia um modo "Pessoal" que fazia os._exit(0) nesta função
    quando a última sessão caía — a ideia era encerrar sozinho ao fechar a
    janela do navegador. Removido — se o encerramento automático por
    inatividade real for necessário de novo, a forma correta é um timeout bem
    mais longo (minutos, não segundos), não a contagem de sessões do ping."""
    global _backup_pos_sess
    if _had_session and active_sessions() == 0 and not _backup_pos_sess:
        _backup_pos_sess = True
        cfg = _get_backup_cfg()
        if cfg['enabled']:
            print('\nÚltima sessão encerrada. Executando backup automático...')
            _do_json_backup(cfg)
            _do_db_backup(cfg)

# ── HTTP Handler ──────────────────────────────────────────────────────────────

class SGCDHandler(http.server.SimpleHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def end_headers(self):
        # SGCD.html/JS mudam com frequência entre versões; sem isso o navegador
        # pode servir do cache sem revalidar com o servidor (heurística por Last-Modified).
        if self.command == 'GET' and urlparse(self.path).path.rstrip('/').endswith(('.html', '.js', '.css')):
            self.send_header('Cache-Control', 'no-cache, must-revalidate')
        super().end_headers()

    def _safe_dispatch(self, inner):
        # handle_error (mais abaixo) nunca era chamado de verdade — é método de
        # socketserver.BaseServer, não do request handler, então exceções não
        # tratadas em qualquer do_GET/POST/PUT/DELETE só apareciam no console
        # (nada no log, cliente só via a conexão cair). Isso escondia bugs reais.
        try:
            inner()
        except Exception as e:
            _log.error('Erro não tratado em %s %s: %s', self.command, self.path, e)
            try:
                self._json(500, {'error': 'Erro interno no servidor.'})
            except Exception:
                pass  # resposta já pode ter começado a ser enviada

    def do_GET(self):
        self._safe_dispatch(self._do_GET)

    def _do_GET(self):
        parsed = urlparse(self.path)
        p  = parsed.path.rstrip('/')
        qs = parse_qs(parsed.query)

        if p == '/health':
            self._json(200, {'ok': True, 'version': SERVER_VERSION})
        elif p == '/api/public/org-info':
            try:
                with get_db() as conn:
                    rows = conn.execute(
                        "SELECT key,value FROM sys_settings WHERE key IN ('orgao','municipio','cnpj_orgao')"
                    ).fetchall()
                info = {r['key']: r['value'] for r in rows}
                self._json(200, info)
            except Exception:
                self._json(200, {})
        elif p == '/api/public/last-backup':
            try:
                with get_db() as conn:
                    row = conn.execute("SELECT value FROM sys_settings WHERE key='auto_backup_last'").fetchone()
                self._json(200, {'ts': row['value'] if row else None})
            except Exception:
                self._json(200, {'ts': None})
        elif p == '/api/auth/logout':
            # Aceita token via query string para suportar sendBeacon
            tok = qs.get('token', [None])[0] or self._token()
            delete_session(tok)
            self._json(200, {'ok': True})
            threading.Thread(target=_check_shutdown, daemon=True).start()
        elif p.startswith('/cnpj/'):
            self._proxy_cnpj(p[6:].strip('/'))
        elif p.startswith('/api/'):
            s = self._auth()
            if s: self._route_get(p, qs, s)
        else:
            super().do_GET()

    def do_POST(self):
        self._safe_dispatch(self._do_POST)

    def _do_POST(self):
        parsed = urlparse(self.path)
        p = parsed.path.rstrip('/')

        if p == '/api/auth/login':
            self._login(self._body())
            return

        # Logout via beacon (sem Authorization header — lê token do query string)
        if p == '/api/auth/logout':
            qs_tok = parse_qs(parsed.query).get('token', [None])[0]
            delete_session(qs_tok or self._token())
            self._json(200, {'ok': True})
            threading.Thread(target=_check_shutdown, daemon=True).start()
            return

        if p == '/send-email':
            sess = get_session(self._token())
            if not sess:
                self._json(401, {'error': 'Não autenticado'}); return
            try:
                self._send_email(json.loads(self._body()), sess)
                self._json(200, {'ok': True})
            except Exception as e:
                self._json(500, {'ok': False, 'error': str(e)})
            return

        s = self._auth()
        if not s: return
        # BUG (corrigido): _upload_file_direct/_create_signature_upload leem o corpo
        # de novo via self.rfile.read() para multipart — ler aqui também esvaziaria o
        # socket e travaria a segunda leitura (ConnectionResetError sob curl -F, e
        # potencialmente sob navegador também). Multipart é lido só pelo handler.
        ct = self.headers.get('Content-Type', '')
        body = b'' if 'multipart/form-data' in ct else self._body()
        self._route_post(p, body, s)

    def do_PUT(self):
        self._safe_dispatch(self._do_PUT)

    def _do_PUT(self):
        p = urlparse(self.path).path.rstrip('/')
        s = self._auth()
        if not s: return
        self._route_put(p, self._body(), s)

    def do_DELETE(self):
        self._safe_dispatch(self._do_DELETE)

    def _do_DELETE(self):
        parsed = urlparse(self.path)
        p = parsed.path.rstrip('/')
        qs = parse_qs(parsed.query)
        s = self._auth()
        if not s: return
        self._route_delete(p, qs, s)

    # ── Roteamento ────────────────────────────────────────────────────────────

    def _route_get(self, p, qs, s):
        def qp(k, d=None): v = qs.get(k); return v[0] if v else d

        # Auth
        if p == '/api/auth/logout':
            tok = qs.get('token', [None])[0] or self._token()
            delete_session(tok)
            self._json(200, {'ok': True})
            threading.Thread(target=_check_shutdown, daemon=True).start()

        elif p == '/api/auth/ping':
            renew_session(self._token())
            self._json(200, {'ok': True})

        elif p == '/api/auth/me':
            self._json(200, self._user_dict(s))

        # Processos
        elif p == '/api/processes':
            self._list_processes(qs, s)
        elif re.fullmatch(r'/api/processes/[^/]+', p):
            self._get_process(p.split('/')[-1])

        # Fornecedores
        elif p == '/api/fornecedores':
            self._list_fornecedores(qs)
        elif re.fullmatch(r'/api/fornecedores/[^/]+', p):
            self._get_fornecedor(p.split('/')[-1])

        # CEIS/CNEP (sanções federais por CNPJ, via Portal da Transparência)
        elif p == '/api/ceis-cnep':
            self._proxy_ceis_cnep(qs)

        # Etiquetas
        elif p == '/api/tags':
            self._list_tags()

        # Arquivos
        elif p == '/api/files':
            pid    = qp('process_id')
            prefix = qp('prefix') == '1'
            per    = min(int(qp('per', 200)), 1000)
            with get_db() as conn:
                if pid and prefix:
                    total = conn.execute('SELECT COUNT(*) FROM files WHERE process_id LIKE ?', (pid + '%',)).fetchone()[0]
                    rows  = conn.execute('SELECT id,process_id,step_index,nome_original,mime,tamanho,uploaded_em FROM files WHERE process_id LIKE ? LIMIT ?', (pid + '%', per)).fetchall()
                elif pid:
                    total = conn.execute('SELECT COUNT(*) FROM files WHERE process_id=?', (pid,)).fetchone()[0]
                    rows  = conn.execute('SELECT id,process_id,step_index,nome_original,mime,tamanho,uploaded_em FROM files WHERE process_id=? LIMIT ?', (pid, per)).fetchall()
                else:
                    total = conn.execute('SELECT COUNT(*) FROM files').fetchone()[0]
                    rows  = conn.execute('SELECT id,process_id,step_index,nome_original,mime,tamanho,uploaded_em FROM files LIMIT ?', (per,)).fetchall()
            self._json(200, {'total': total, 'items': [dict(r) for r in rows]})
        elif re.fullmatch(r'/api/files/[^/]+/meta', p):
            fid = p.split('/')[3]
            with get_db() as conn:
                row = conn.execute('SELECT id,process_id,step_index,nome_original,mime,tamanho FROM files WHERE id=?', (fid,)).fetchone()
            if not row: self._json(404, {'error': 'Arquivo não encontrado'}); return
            self._json(200, {'id': row['id'], 'name': row['nome_original'], 'type': row['mime'], 'size': row['tamanho']})
        elif re.fullmatch(r'/api/files/[^/]+', p):
            self._serve_file(p.split('/')[-1])

        # Auditoria
        # Sem restrição de admin: também usado pelo histórico de alterações por
        # campo (abrirFieldHist), acessível a qualquer usuário logado. A tela
        # "Auditoria" do menu é que fica restrita a admin, só no frontend.
        elif p == '/api/audit':
            page = int(qp('page', 1)); per = min(int(qp('per', 50)), 2000)
            q    = (qp('q') or '').strip()
            tipo = qp('tipo') or ''
            de   = qp('de') or ''
            ate  = qp('ate') or ''
            where, params = [], []
            if q:    where.append('(user_nome LIKE ? OR detail LIKE ?)'); params += [f'%{q}%', f'%{q}%']
            if tipo: where.append('type=?'); params.append(tipo)
            if de:   where.append('ts >= ?'); params.append(de)
            if ate:  where.append('ts <= ?'); params.append(ate + 'T23:59:59')
            w = ('WHERE ' + ' AND '.join(where)) if where else ''
            with get_db() as conn:
                total = conn.execute(f'SELECT COUNT(*) FROM audit_global {w}', params).fetchone()[0]
                rows  = conn.execute(
                    f'SELECT * FROM audit_global {w} ORDER BY ts DESC LIMIT ? OFFSET ?',
                    params + [per, (page-1)*per]
                ).fetchall()
            self._json(200, {'total': total, 'page': page, 'per': per, 'items': [dict(r) for r in rows]})

        # Configurações do sistema
        elif p == '/api/settings':
            with get_db() as conn:
                rows = conn.execute('SELECT key,value FROM sys_settings').fetchall()
            result = {r['key']: r['value'] for r in rows}
            # A senha SMTP fica só no servidor (o envio resolve a config server-side).
            result['smtp_pass_set'] = '1' if (result.pop('smtp_pass', '') or '').strip() else '0'
            print(f"  [SETTINGS] GET /api/settings de {s.get('nome') or s.get('user_id')} — chaves retornadas: {sorted(result.keys())}", flush=True)
            self._json(200, result)

        elif p in ('/api/settings/brasao', '/api/settings/brasao/'):
            with get_db() as conn:
                row = conn.execute("SELECT value FROM sys_settings WHERE key='brasao_dataurl'").fetchone()
            self._json(200, {'brasao_dataurl': row['value'] if row else ''})

        # Usuários (admin)
        elif p == '/api/usuarios':
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            with get_db() as conn:
                rows = conn.execute(
                    'SELECT id,username,nome,cpf,email,cargo,matricula,admin,ativo,criado_em FROM usuarios'
                ).fetchall()
            self._json(200, [dict(r) for r in rows])

        elif re.fullmatch(r'/api/usuarios/\d+/smtp', p):
            # Config SMTP de um usuário (sem a senha): o próprio usuário ou admin
            uid = int(p.split('/')[3])
            if uid != s['user_id'] and not s['admin']:
                self._json(403, {'error': 'Acesso restrito'}); return
            with get_db() as conn:
                row = conn.execute(f"SELECT {', '.join(_USER_SMTP_COLS)} FROM usuarios WHERE id=?", (uid,)).fetchone()
                if not row: self._json(404, {'error': 'Usuário não encontrado'}); return
                sysc = {r['key']: r['value'] for r in conn.execute("SELECT key,value FROM sys_settings WHERE key LIKE 'smtp_%'").fetchall()}
            out = {c: (row[c] or '') for c in _USER_SMTP_COLS if c != 'smtp_pass'}
            out['smtp_pass_set'] = bool((row['smtp_pass'] or '').strip())
            # defaults do sistema para o "Copiar do sistema" (sem a senha)
            out['system'] = {c: sysc.get(c, '') for c in ('smtp_host', 'smtp_port', 'smtp_secure', 'smtp_require_tls', 'smtp_ignore_ssl', 'smtp_from_name')}
            self._json(200, out)

        elif p == '/api/relatorio/integridade':
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            self._relatorio_integridade()

        # Backup
        elif p == '/api/backup':
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            self._export_backup()

        elif p == '/api/backup/db':
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            import tempfile as _tf
            tmp = _tf.NamedTemporaryFile(suffix='.db', delete=False)
            tmp.close()
            try:
                with sqlite3.connect(DB_PATH, factory=_ConnAutoClose) as src, sqlite3.connect(tmp.name, factory=_ConnAutoClose) as bk:
                    src.backup(bk)
                with open(tmp.name, 'rb') as f:
                    data_bytes = f.read()
                name = time.strftime('DB_SGCD_BACKUP_%Y-%m-%d_%H-%M-%S.db')
                self.send_response(200); self._cors()
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Length', str(len(data_bytes)))
                self.send_header('Content-Disposition', f'attachment; filename="{name}"')
                self.end_headers()
                self.wfile.write(data_bytes)
            finally:
                try: os.remove(tmp.name)
                except: pass

        elif p == '/api/backups/cfg':
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            self._json(200, _get_backup_cfg())

        elif p == '/api/dialog/folder':
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            global _watchdog_paused
            _watchdog_paused = True
            try:
                path = sgx_base.pick_folder_dialog("Selecione a pasta de backup do SGCD")
                self._json(200, {'path': path or None})
            except Exception as e:
                self._json(500, {'error': str(e)})
            finally:
                _watchdog_paused = False

        elif p == '/api/backups/db':
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            cfg = _get_backup_cfg()
            bdir = cfg['path']
            files = sorted(
                (f for f in os.listdir(bdir) if f.startswith('DB_SGCD_BACKUP_') and f.endswith('.db')),
                reverse=True
            ) if os.path.isdir(bdir) else []
            items = [{'name': f, 'size': os.path.getsize(os.path.join(bdir, f)),
                      'ts': sgx_base.backup_ts(f)} for f in files]
            with get_db() as conn:
                last_row = conn.execute("SELECT value FROM sys_settings WHERE key='auto_backup_last'").fetchone()
            last_backup = last_row['value'] if last_row else None
            self._json(200, {'items': items, 'path': bdir, 'cfg': cfg, 'last_backup': last_backup})

        elif p.startswith('/api/backups/db/download'):
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            name = parse_qs(parsed.query).get('name', [None])[0]
            if not name or not name.startswith('DB_SGCD_BACKUP_') or not name.endswith('.db') or '/' in name or '\\' in name:
                self._json(400, {'error': 'Nome inválido'}); return
            cfg = _get_backup_cfg()
            fp = os.path.join(cfg['path'], name)
            if not os.path.exists(fp): self._json(404, {'error': 'Arquivo não encontrado'}); return
            with open(fp, 'rb') as f: data_bytes = f.read()
            self.send_response(200); self._cors()
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Length', str(len(data_bytes)))
            self.send_header('Content-Disposition', f'attachment; filename="{name}"')
            self.end_headers(); self.wfile.write(data_bytes)

        else:
            self._json(404, {'error': 'Rota não encontrada'})

    def _route_post(self, p, body, s):
        data = self._parse_json(body)

        if p == '/api/auth/logout':
            delete_session(self._token())
            self._json(200, {'ok': True})
            threading.Thread(target=_check_shutdown, daemon=True).start()

        elif p == '/api/processes':
            self._create_process(data, s)

        elif re.fullmatch(r'/api/processes/[^/]+/files', p):
            self._upload_file(p.split('/')[3], s)

        elif p == '/api/fornecedores':
            self._create_fornecedor(data)

        elif p == '/api/fornecedores/import':
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            self._import_fornecedores(data)

        elif p == '/api/audit':
            self._add_audit(data, s)

        elif p == '/api/audit/bulk':
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            self._add_audit_bulk(data)

        elif p in ('/api/settings', '/api/settings/'):
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            self._save_settings(data)

        elif p == '/api/usuarios':
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            self._create_user(data)

        elif p == '/api/backups/db/now':
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            name = _do_db_backup()
            self._json(200, {'ok': bool(name), 'name': name})

        elif p == '/api/backup/restore':
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            self._restore_backup(data, s)

        elif p == '/api/backups/db/restore':
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            self._restore_db_backup(body, s)

        elif p == '/api/files':
            self._upload_file_direct(s)

        else:
            self._json(404, {'error': 'Rota não encontrada'})

    def _route_put(self, p, body, s):
        data = self._parse_json(body)

        if re.fullmatch(r'/api/processes/[^/]+/restore', p):
            self._restore_process(p.split('/')[-2])
        elif re.fullmatch(r'/api/fornecedores/[^/]+/restore', p):
            self._restore_fornecedor(p.split('/')[-2])
        elif re.fullmatch(r'/api/processes/[^/]+', p):
            self._update_process(p.split('/')[-1], data, s)
        elif re.fullmatch(r'/api/fornecedores/[^/]+', p):
            self._update_fornecedor(p.split('/')[-1], data)
        elif p in ('/api/settings', '/api/settings/'):
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            self._save_settings(data)
        elif p in ('/api/settings/org', '/api/settings/org/'):
            # Dados de Organização: qualquer usuário autenticado pode salvar (não é config administrativa)
            allowed = {'orgao', 'municipio', 'aut_nome', 'aut_cargo', 'site_oficial',
                       'diario_url', 'cnpj_orgao', 'codigo_ibge', 'uf', 'decreto_limites'}
            print(f"  [SETTINGS] PUT /api/settings/org recebido de {s.get('nome') or s.get('user_id')} (admin={s['admin']})", flush=True)
            self._save_settings({k: v for k, v in data.items() if k in allowed})
        elif p in ('/api/settings/brasao', '/api/settings/brasao/'):
            # Brasão customizado (data URL base64): qualquer usuário autenticado pode salvar.
            # Bypassa o "vazio nunca sobrescreve" de _save_settings() — aqui vazio É o
            # sinal explícito de "remover o brasão customizado", não um formulário em branco.
            dataurl = data.get('brasao_dataurl', '')
            with get_db() as conn:
                if dataurl:
                    conn.execute('INSERT OR REPLACE INTO sys_settings (key,value) VALUES (?,?)', ('brasao_dataurl', dataurl))
                else:
                    conn.execute("DELETE FROM sys_settings WHERE key='brasao_dataurl'")
            print(f"  [SETTINGS] PUT /api/settings/brasao de {s.get('nome') or s.get('user_id')} — {'removido' if not dataurl else f'{len(dataurl)} bytes'}", flush=True)
            self._json(200, {'ok': True})
        elif p in ('/api/settings/smtp', '/api/settings/smtp/'):
            # Config SMTP: sensível (inclui senha), restrita a admin
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            allowed = {'smtp_host', 'smtp_port', 'smtp_secure', 'smtp_require_tls',
                       'smtp_ignore_ssl', 'smtp_user', 'smtp_pass', 'smtp_from_name', 'smtp_to'}
            # _save_settings() já ignora valores vazios, então smtp_pass em branco preserva a senha salva
            self._save_settings({k: v for k, v in data.items() if k in allowed})
        elif re.fullmatch(r'/api/usuarios/[^/]+', p):
            uid = int(p.split('/')[-1])
            if not s['admin']:
                if uid != s['user_id']:
                    self._json(403, {'error': 'Acesso restrito'}); return
                # não-admin: só a própria senha e a própria config SMTP
                data = {k: data[k] for k in ('password', 'old_password', *_USER_SMTP_COLS) if k in data}
            self._update_user(uid, data, s)
        else:
            self._json(404, {'error': 'Rota não encontrada'})

    def _route_delete(self, p, qs, s):
        purge = qs.get('purge', [None])[0] == '1'

        if re.fullmatch(r'/api/processes/[^/]+', p):
            pid = p.split('/')[-1]
            if purge:
                if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
                self._purge_process(pid)
            else:
                with get_db() as conn:
                    conn.execute('UPDATE processes SET deleted_at=? WHERE id=?', (_now(), pid))
            self._json(200, {'ok': True})

        elif re.fullmatch(r'/api/fornecedores/[^/]+', p):
            fid = p.split('/')[-1]
            if purge:
                if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
                with get_db() as conn:
                    conn.execute('DELETE FROM fornecedores WHERE id=?', (fid,))
            else:
                with get_db() as conn:
                    conn.execute('UPDATE fornecedores SET deleted_at=? WHERE id=?', (_now(), fid))
            self._json(200, {'ok': True})

        elif p == '/api/files' and parse_qs(urlparse(self.path).query).get('process_id'):
            pid_prefix = parse_qs(urlparse(self.path).query)['process_id'][0]
            with get_db() as conn:
                rows = conn.execute(
                    "SELECT nome_disco FROM files WHERE process_id LIKE ?",
                    (pid_prefix + '%',)
                ).fetchall()
                for row in rows:
                    fp = os.path.join(UPLOADS_DIR, row['nome_disco'])
                    if os.path.exists(fp): os.remove(fp)
                conn.execute("DELETE FROM files WHERE process_id LIKE ?", (pid_prefix + '%',))
            self._json(200, {'ok': True})

        elif re.fullmatch(r'/api/files/[^/]+', p):
            fid = p.split('/')[-1]
            with get_db() as conn:
                row = conn.execute('SELECT nome_disco FROM files WHERE id=?', (fid,)).fetchone()
                if row:
                    fp = os.path.join(UPLOADS_DIR, row['nome_disco'])
                    if os.path.exists(fp): os.remove(fp)
                    conn.execute('DELETE FROM files WHERE id=?', (fid,))
            self._json(200, {'ok': True})

        elif re.fullmatch(r'/api/usuarios/[^/]+', p):
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            uid = int(p.split('/')[-1])
            if uid == s['user_id']:
                self._json(400, {'error': 'Não é possível excluir o próprio usuário'}); return
            with get_db() as conn:
                conn.execute('DELETE FROM usuarios WHERE id=?', (uid,))
            self._json(200, {'ok': True})

        elif p == '/api/processes/all':
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            with get_db() as conn:
                conn.execute('DELETE FROM processes')
            self._json(200, {'ok': True})

        elif p == '/api/fornecedores/all':
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            with get_db() as conn:
                conn.execute('DELETE FROM fornecedores')
            self._json(200, {'ok': True})

        elif p == '/api/files/all':
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            import shutil
            with get_db() as conn:
                conn.execute('DELETE FROM files')
            if os.path.exists(UPLOADS_DIR):
                shutil.rmtree(UPLOADS_DIR)
            os.makedirs(UPLOADS_DIR, exist_ok=True)
            self._json(200, {'ok': True})

        elif p == '/api/audit/all':
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            with get_db() as conn:
                conn.execute('DELETE FROM audit_global')
            self._json(200, {'ok': True})

        elif p == '/api/wipe':
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            import shutil
            with get_db() as conn:
                conn.execute('DELETE FROM processes')
                conn.execute('DELETE FROM fornecedores')
                conn.execute('DELETE FROM files')
                conn.execute('DELETE FROM audit_global')
                _insert_audit_raw(conn, {'type': 'FACTORY_RESET', 'ts': _now(),
                                          'user_id': s['user_id'], 'user_nome': s['nome'],
                                          'label': 'Todos os dados apagados', 'detail': 'Reset de fábrica'})
            if os.path.exists(UPLOADS_DIR):
                shutil.rmtree(UPLOADS_DIR)
            os.makedirs(UPLOADS_DIR, exist_ok=True)
            self._json(200, {'ok': True})

        else:
            self._json(404, {'error': 'Rota não encontrada'})

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _token(self):
        auth = self.headers.get('Authorization', '')
        if auth.startswith('Bearer '): return auth[7:]
        qs_tok = parse_qs(urlparse(self.path).query).get('token', [None])[0]
        return qs_tok

    def _auth(self):
        s = get_session(self._token())
        if not s:
            self._json(401, {'error': 'Não autenticado'})
        return s

    def _user_dict(self, s):
        return {
            'id': s['user_id'], 'username': s['username'], 'nome': s['nome'],
            'cpf': s.get('cpf'), 'email': s.get('email'),
            'cargo': s.get('cargo'), 'matricula': s.get('matricula'),
            'admin': bool(s['admin'])
        }

    def _login(self, body):
        try:
            data = json.loads(body)
            username = data.get('username', '').strip()
            password = data.get('password', '')
        except Exception:
            self._json(400, {'error': 'JSON inválido'}); return

        if _login_rate_limited(username):
            self._json(429, {'error': 'Muitas tentativas de login. Aguarde alguns minutos e tente novamente.'}); return

        with get_db() as conn:
            row = conn.execute(
                'SELECT * FROM usuarios WHERE username=? COLLATE NOCASE AND ativo=1', (username,)
            ).fetchone()

        if not row or not _verify_password(password, row['senha_hash']):
            _record_login_failure(username)
            self._json(401, {'error': 'Usuário ou senha incorretos'}); return

        _clear_login_failures(username)
        global _had_session, _backup_pos_sess
        _had_session = True
        _backup_pos_sess = False  # nova sessão — permite backup ao próximo logout
        token = create_session(row['id'])
        self._json(200, {
            'token': token,
            'user': {
                'id': row['id'], 'username': row['username'], 'nome': row['nome'],
                'cpf': row['cpf'], 'email': row['email'],
                'cargo': row['cargo'], 'matricula': row['matricula'], 'admin': bool(row['admin']),
                'mustChangePassword': bool(row['must_change_password'])
            }
        })

    # ── Processos ─────────────────────────────────────────────────────────────

    def _list_processes(self, qs, s):
        def qp(k, d=None): v = qs.get(k); return v[0] if v else d
        q       = qp('q', '')
        status  = qp('status', '')
        unidade = qp('unidade', '')
        tag     = qp('tag', '')
        page    = int(qp('page', 1))
        per     = min(int(qp('per', 500)), 2000)
        trash   = qp('trash') == '1'

        where, params = [], []
        where.append('deleted_at IS NOT NULL' if trash else 'deleted_at IS NULL')
        if q:
            where.append('(objeto LIKE ? OR num_proc LIKE ? OR num_dl LIKE ?)')
            params += [f'%{q}%', f'%{q}%', f'%{q}%']
        if status:
            where.append('status=?'); params.append(status)
        if unidade:
            where.append('unidade=?'); params.append(unidade)
        if tag:
            where.append('id IN (SELECT pt.process_id FROM process_tags pt JOIN tags t ON pt.tag_id=t.id WHERE t.nome=? COLLATE NOCASE)')
            params.append(tag)

        wc = ('WHERE ' + ' AND '.join(where)) if where else ''
        order = 'deleted_at DESC' if trash else 'updated_at DESC'
        with get_db() as conn:
            total = conn.execute(f'SELECT COUNT(*) FROM processes {wc}', params).fetchone()[0]
            rows  = conn.execute(
                f'SELECT id,data,deleted_at FROM processes {wc} ORDER BY {order} LIMIT ? OFFSET ?',
                params + [per, (page-1)*per]
            ).fetchall()
            tags_map = _tags_map(conn, 'process_tags', 'process_id', [r['id'] for r in rows])
        items = []
        for r in rows:
            item = json.loads(r['data'])
            item['deletedAt'] = r['deleted_at']
            item['tags'] = tags_map.get(r['id'], [])
            items.append(item)
        self._json(200, {'total': total, 'items': items})

    def _get_process(self, pid):
        with get_db() as conn:
            row = conn.execute('SELECT data FROM processes WHERE id=?', (pid,)).fetchone()
            if not row: self._json(404, {'error': 'Processo não encontrado'}); return
            tags = _tags_map(conn, 'process_tags', 'process_id', [pid]).get(pid, [])
        item = json.loads(row['data']); item['tags'] = tags
        self._json(200, item)

    def _list_tags(self):
        with get_db() as conn:
            rows = conn.execute('SELECT nome FROM tags ORDER BY nome').fetchall()
        self._json(200, {'items': [r['nome'] for r in rows]})

    def _create_process(self, data, s):
        pid = data.get('id') or str(uuid.uuid4())
        data['id'] = pid
        data.setdefault('createdAt', _now())
        data['updatedAt'] = _now_precise()
        with get_db() as conn:
            conn.execute(
                '''INSERT OR REPLACE INTO processes
                   (id,data,objeto,status,unidade,valor,num_proc,num_dl,created_at,updated_at,created_by)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (pid, json.dumps(data, ensure_ascii=False),
                 data.get('objeto'), data.get('status', 'em_andamento'),
                 data.get('unidade'), _float(data.get('valor')),
                 data.get('num_proc'), data.get('num_dl'),
                 data.get('createdAt'), data['updatedAt'], s['user_id'])
            )
            if 'tags' in data: _sync_tags(conn, 'process_tags', 'process_id', pid, data['tags'])
        self._json(200, data)

    def _update_process(self, pid, data, s):
        with get_db() as conn:
            row = conn.execute('SELECT data FROM processes WHERE id=?', (pid,)).fetchone()
            if not row:
                # Cria se não existir (upsert)
                self._create_process({**data, 'id': pid}, s); return
            existing = json.loads(row['data'])
            # Detecção de conflito: o cliente manda de volta o updatedAt de quando
            # carregou o processo. Se não bater com o que está salvo agora, outro
            # usuário editou nesse meio-tempo — recusa em vez de sobrescrever
            # silenciosamente o que essa outra pessoa salvou (last-write-wins cego).
            base_updated_at = data.pop('_baseUpdatedAt', None)
            if base_updated_at is not None and base_updated_at != existing.get('updatedAt'):
                self._json(409, {
                    'error': 'Este processo foi alterado por outro usuário. Recarregue antes de salvar.',
                    'current': existing,
                })
                return
            existing.update(data)
            existing['updatedAt'] = _now_precise()
            if 'tags' in data: _sync_tags(conn, 'process_tags', 'process_id', pid, data['tags'])
            conn.execute(
                '''UPDATE processes SET data=?,objeto=?,status=?,unidade=?,valor=?,
                   num_proc=?,num_dl=?,updated_at=? WHERE id=?''',
                (json.dumps(existing, ensure_ascii=False),
                 existing.get('objeto'), existing.get('status'), existing.get('unidade'),
                 _float(existing.get('valor')), existing.get('num_proc'), existing.get('num_dl'),
                 existing['updatedAt'], pid)
            )
        self._json(200, existing)

    def _restore_process(self, pid):
        with get_db() as conn:
            conn.execute('UPDATE processes SET deleted_at=NULL WHERE id=?', (pid,))
        self._json(200, {'ok': True})

    def _purge_process(self, pid):
        with get_db() as conn:
            rows = conn.execute('SELECT nome_disco FROM files WHERE process_id LIKE ?', (pid + '%',)).fetchall()
            for row in rows:
                fp = os.path.join(UPLOADS_DIR, row['nome_disco'])
                if os.path.exists(fp): os.remove(fp)
            conn.execute('DELETE FROM files WHERE process_id LIKE ?', (pid + '%',))
            conn.execute('DELETE FROM processes WHERE id=?', (pid,))

    # ── Fornecedores ──────────────────────────────────────────────────────────

    def _list_fornecedores(self, qs):
        def qp(k, d=None): v = qs.get(k); return v[0] if v else d
        q    = qp('q', '')
        page = int(qp('page', 1))
        per     = min(int(qp('per', 500)), 2000)
        trash   = qp('trash') == '1'

        where, params = [], []
        where.append('deleted_at IS NOT NULL' if trash else 'deleted_at IS NULL')
        if q:
            where.append('(razao_social LIKE ? OR cnpj LIKE ?)')
            params += [f'%{q}%', f'%{q}%']

        wc = ('WHERE ' + ' AND '.join(where)) if where else ''
        order = 'deleted_at DESC' if trash else 'razao_social ASC'
        with get_db() as conn:
            total = conn.execute(f'SELECT COUNT(*) FROM fornecedores {wc}', params).fetchone()[0]
            rows  = conn.execute(
                f'SELECT data,deleted_at FROM fornecedores {wc} ORDER BY {order} LIMIT ? OFFSET ?',
                params + [per, (page-1)*per]
            ).fetchall()
        items = []
        for r in rows:
            item = json.loads(r['data'])
            item['deletedAt'] = r['deleted_at']
            items.append(item)
        self._json(200, {'total': total, 'items': items})

    def _get_fornecedor(self, fid):
        with get_db() as conn:
            row = conn.execute('SELECT data FROM fornecedores WHERE id=?', (fid,)).fetchone()
        if not row: self._json(404, {'error': 'Fornecedor não encontrado'}); return
        self._json(200, json.loads(row['data']))

    def _create_fornecedor(self, data):
        fid = data.get('id') or str(uuid.uuid4())
        data['id'] = fid
        data.setdefault('updatedAt', _now_precise())
        with get_db() as conn:
            conn.execute(
                'INSERT OR REPLACE INTO fornecedores (id,data,cnpj,razao_social,updated_at) VALUES (?,?,?,?,?)',
                (fid, json.dumps(data, ensure_ascii=False),
                 data.get('cnpj'), data.get('razao') or data.get('razao_social'), data['updatedAt'])
            )
        self._json(200, data)

    def _import_fornecedores(self, data):
        # Importa fornecedores de um backup do SGCA (mesma forma de dado nos 2 sistemas):
        # upsert por CNPJ. Ao atualizar um existente, preserva os vínculos LOCAIS do SGCD
        # (processos, certidões) e sobrepõe o resto com os dados do arquivo.
        incoming = data.get('fornecedores') if isinstance(data, dict) else None
        if not isinstance(incoming, list):
            self._json(400, {'error': 'Formato inválido: esperado {"fornecedores": [...]} (backup do SGCA)'}); return
        novos = atualizados = ignorados = 0
        with get_db() as conn:
            existentes = {}
            for r in conn.execute("SELECT id,cnpj FROM fornecedores WHERE deleted_at IS NULL").fetchall():
                dig = re.sub(r'\D', '', r['cnpj'] or '')
                if dig: existentes[dig] = r['id']
            for f in incoming:
                if not isinstance(f, dict):
                    ignorados += 1; continue
                cnpj_d = re.sub(r'\D', '', f.get('cnpj') or '')
                if len(cnpj_d) != 14:
                    ignorados += 1; continue
                if cnpj_d in existentes:
                    fid = existentes[cnpj_d]
                    row = conn.execute('SELECT data FROM fornecedores WHERE id=?', (fid,)).fetchone()
                    existing = json.loads(row['data']) if row else {}
                    f = {**existing, **f, 'id': fid,
                         'processos': existing.get('processos', []),
                         'certidoes': existing.get('certidoes', [])}
                    atualizados += 1
                else:
                    fid = f.get('id') or str(uuid.uuid4())
                    existentes[cnpj_d] = fid
                    f['id'] = fid
                    novos += 1
                f['cnpj_digits'] = cnpj_d  # garante o campo (dados de CSV/parciais podem não trazer)
                f['updatedAt'] = _now_precise()
                conn.execute(
                    'INSERT OR REPLACE INTO fornecedores (id,data,cnpj,razao_social,updated_at) VALUES (?,?,?,?,?)',
                    (fid, json.dumps(f, ensure_ascii=False),
                     f.get('cnpj'), f.get('razao') or f.get('razao_social'), f['updatedAt'])
                )
            conn.commit()
        self._json(200, {'ok': True, 'novos': novos, 'atualizados': atualizados, 'ignorados': ignorados})

    def _update_fornecedor(self, fid, data):
        with get_db() as conn:
            row = conn.execute('SELECT data FROM fornecedores WHERE id=?', (fid,)).fetchone()
            if not row:
                self._create_fornecedor({**data, 'id': fid}); return
            existing = json.loads(row['data'])
            base_updated_at = data.pop('_baseUpdatedAt', None)
            if base_updated_at is not None and base_updated_at != existing.get('updatedAt'):
                self._json(409, {
                    'error': 'Este fornecedor foi alterado por outro usuário. Recarregue antes de salvar.',
                    'current': existing,
                })
                return
            existing.update(data)
            existing['updatedAt'] = _now_precise()
            conn.execute(
                'UPDATE fornecedores SET data=?,cnpj=?,razao_social=?,updated_at=? WHERE id=?',
                (json.dumps(existing, ensure_ascii=False),
                 existing.get('cnpj'), existing.get('razao') or existing.get('razao_social'),
                 existing['updatedAt'], fid)
            )
        self._json(200, existing)

    def _restore_fornecedor(self, fid):
        with get_db() as conn:
            conn.execute('UPDATE fornecedores SET deleted_at=NULL WHERE id=?', (fid,))
        self._json(200, {'ok': True})

    # ── Arquivos ──────────────────────────────────────────────────────────────

    def _upload_file(self, process_id, s):
        ct = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in ct:
            self._json(400, {'error': 'Esperado multipart/form-data'}); return

        boundary = ct.split('boundary=')[-1].strip().encode()
        length   = int(self.headers.get('Content-Length', 0))
        if length > MAX_UPLOAD:
            self._json(413, {'error': f'Arquivo muito grande (máximo {MAX_UPLOAD//1024//1024} MB)'}); return
        body     = self.rfile.read(length)

        filename, file_bytes, step_index = _parse_multipart(body, boundary)
        if not filename or file_bytes is None:
            self._json(400, {'error': 'Arquivo não encontrado no upload'}); return

        ext       = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTS:
            self._json(400, {'error': f'Extensão não permitida: {ext}'}); return
        safe_name = secrets.token_hex(16) + ext
        with open(os.path.join(UPLOADS_DIR, safe_name), 'wb') as f:
            f.write(file_bytes)

        fid  = str(uuid.uuid4())
        mime = _mime(ext)
        with get_db() as conn:
            conn.execute(
                '''INSERT INTO files (id,process_id,step_index,nome_original,nome_disco,tamanho,mime,uploaded_by)
                   VALUES (?,?,?,?,?,?,?,?)''',
                (fid, process_id, step_index, filename, safe_name, len(file_bytes), mime, s['user_id'])
            )
        self._json(200, {
            'id': fid, 'process_id': process_id, 'step_index': step_index,
            'nome_original': filename, 'tamanho': len(file_bytes), 'mime': mime
        })

    def _upload_file_direct(self, s):
        """Upload direto sem precisar de process_id no path — extrai do form."""
        ct = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in ct:
            self._json(400, {'error': 'Esperado multipart/form-data'}); return

        boundary = ct.split('boundary=')[-1].strip().encode()
        length   = int(self.headers.get('Content-Length', 0))
        if length > MAX_UPLOAD:
            self._json(413, {'error': f'Arquivo muito grande (máximo {MAX_UPLOAD//1024//1024} MB)'}); return
        body     = self.rfile.read(length)

        parts = _parse_multipart_all(body, boundary)
        file_bytes = parts.get('file', {}).get('data')
        filename   = parts.get('file', {}).get('filename') or parts.get('nome_original', {}).get('text', 'arquivo')
        process_id = parts.get('process_id', {}).get('text', '')
        step_index = parts.get('step_index', {}).get('text', '')
        mime_type  = parts.get('mime', {}).get('text') or ''

        if not file_bytes:
            self._json(400, {'error': 'Arquivo não encontrado no upload'}); return

        ext       = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTS:
            self._json(400, {'error': f'Extensão não permitida: {ext}'}); return
        safe_name = secrets.token_hex(16) + ext
        with open(os.path.join(UPLOADS_DIR, safe_name), 'wb') as f:
            f.write(file_bytes)

        fid  = str(uuid.uuid4())
        mime = mime_type or _mime(ext)
        with get_db() as conn:
            conn.execute(
                '''INSERT INTO files (id,process_id,step_index,nome_original,nome_disco,tamanho,mime,uploaded_by)
                   VALUES (?,?,?,?,?,?,?,?)''',
                (fid, process_id, step_index, filename, safe_name, len(file_bytes), mime, s['user_id'])
            )
        self._json(200, {'id': fid, 'process_id': process_id, 'step_index': step_index,
                         'nome_original': filename, 'tamanho': len(file_bytes), 'mime': mime})

    def _serve_file(self, fid):
        with get_db() as conn:
            row = conn.execute('SELECT * FROM files WHERE id=?', (fid,)).fetchone()
        if not row: self._json(404, {'error': 'Arquivo não encontrado'}); return

        fp = os.path.join(UPLOADS_DIR, row['nome_disco'])
        if not os.path.exists(fp): self._json(404, {'error': 'Arquivo não encontrado no disco'}); return

        with open(fp, 'rb') as f:
            data = f.read()

        self.send_response(200)
        self._cors()
        self.send_header('Content-Type', row['mime'] or 'application/octet-stream')
        self.send_header('Content-Length', str(len(data)))
        safe_fn = row['nome_original'].replace('"', '_').replace('\n', '_').replace('\r', '_')
        self.send_header('Content-Disposition', f'inline; filename="{safe_fn}"')
        self.end_headers()
        self.wfile.write(data)

    # ── Auditoria ─────────────────────────────────────────────────────────────

    def _add_audit(self, data, s=None):
        aid = data.get('id') or str(uuid.uuid4())
        # Compatibilidade com campos antigos do JS (at/ms, evento, usuario, detalhe)
        ts_raw = data.get('ts') or data.get('at')
        if isinstance(ts_raw, (int, float)):
            ts = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(ts_raw / 1000))
        else:
            ts = ts_raw or _now()
        tipo   = data.get('type')   or data.get('evento')
        detail = data.get('detail') or data.get('detalhe')
        label  = data.get('label')  or data.get('evento')
        # Sempre usa dados da sessão autenticada — ignora user_id/user_nome do body
        user_nome = s['nome']    if s else (data.get('userName') or data.get('user_nome') or data.get('usuario'))
        user_id   = s['user_id'] if s else (data.get('userId')   or data.get('user_id'))
        with get_db() as conn:
            conn.execute(
                '''INSERT OR REPLACE INTO audit_global
                   (id,ts,user_id,user_nome,type,label,detail,process_id,process_obj)
                   VALUES (?,?,?,?,?,?,?,?,?)''',
                (aid, ts, user_id, user_nome, tipo, label, detail,
                 data.get('processId') or data.get('process_id'),
                 json.dumps(data['processObj']) if data.get('processObj') else data.get('process_obj'))
            )
        self._json(200, {'ok': True})

    def _add_audit_bulk(self, data):
        """Importa uma lista de eventos de auditoria preservando o autor original
        (usado pela sincronização de backup entre agentes — ver _insert_audit_raw)."""
        eventos = data.get('items') if isinstance(data, dict) else data
        if not isinstance(eventos, list):
            self._json(400, {'error': 'Campo "items" deve ser uma lista'}); return
        with get_db() as conn:
            for a in eventos:
                if isinstance(a, dict):
                    _insert_audit_raw(conn, a)
        self._json(200, {'ok': True, 'inseridos': len(eventos)})

    # ── Configurações ─────────────────────────────────────────────────────────

    def _save_settings(self, data):
        # ponytail: string vazia nunca sobrescreve um valor já salvo — evita que um
        # formulário em branco (navegador que nunca carregou os dados) apague a
        # configuração real ao salvar. Para limpar um campo, edite o banco diretamente.
        gravadas, ignoradas = [], []
        with get_db() as conn:
            for key, value in data.items():
                v = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                if v == '':
                    ignoradas.append(key)
                    continue
                conn.execute('INSERT OR REPLACE INTO sys_settings (key,value) VALUES (?,?)', (key, v))
                gravadas.append(key)
        print(f'  [SETTINGS] gravadas={gravadas} ignoradas(vazias)={ignoradas}', flush=True)
        if 'auto_backup_keep' in data or 'backup_path' in data:
            _rotate_backups()
        self._json(200, {'ok': True})

    # ── Usuários ──────────────────────────────────────────────────────────────

    def _create_user(self, data):
        nome     = (data.get('nome') or '').strip()
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        if not nome or not username or not password:
            self._json(400, {'error': 'Nome, usuário e senha são obrigatórios'}); return
        if len(password) < 6:
            self._json(400, {'error': 'Senha mínima: 6 caracteres'}); return
        try:
            with get_db() as conn:
                conn.execute(
                    'INSERT INTO usuarios (username,nome,cpf,email,cargo,matricula,senha_hash,admin) VALUES (?,?,?,?,?,?,?,?)',
                    (username, nome, data.get('cpf'), data.get('email'), data.get('cargo'), data.get('matricula'),
                     _hash_password(password), int(bool(data.get('admin'))))
                )
                uid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            self._json(200, {'id': uid, 'username': username, 'nome': nome})
        except sqlite3.IntegrityError:
            self._json(409, {'error': f'Usuário "{username}" já existe'})

    def _update_user(self, uid, data, s):
        with get_db() as conn:
            if not conn.execute('SELECT 1 FROM usuarios WHERE id=?', (uid,)).fetchone():
                self._json(404, {'error': 'Usuário não encontrado'}); return
            fields, params = [], []
            for col in ('nome', 'cpf', 'email', 'cargo', 'matricula'):
                if col in data: fields.append(f'{col}=?'); params.append(data[col])
            # Config SMTP do usuário — smtp_pass em branco preserva a senha salva
            for col in _USER_SMTP_COLS:
                if col == 'smtp_pass':
                    if data.get('smtp_pass'): fields.append('smtp_pass=?'); params.append(data['smtp_pass'])
                elif col in data:
                    fields.append(f'{col}=?'); params.append(str(data[col] or '').strip())
            if 'admin' in data: fields.append('admin=?'); params.append(int(bool(data['admin'])))
            if 'ativo' in data: fields.append('ativo=?'); params.append(int(bool(data['ativo'])))
            if data.get('password'):
                if len(data['password']) < 6:
                    self._json(400, {'error': 'Senha mínima: 6 caracteres'}); return
                if 'old_password' in data:
                    row = conn.execute('SELECT senha_hash FROM usuarios WHERE id=?', (uid,)).fetchone()
                    if not row or not _verify_password(data['old_password'], row['senha_hash']):
                        self._json(403, {'error': 'Senha atual incorreta'}); return
                fields.append('senha_hash=?'); params.append(_hash_password(data['password']))
                fields.append('must_change_password=0')
            if fields:
                conn.execute(f'UPDATE usuarios SET {",".join(fields)} WHERE id=?', params + [uid])
        self._json(200, {'ok': True})

    # ── Backup ────────────────────────────────────────────────────────────────

    def _export_backup(self):
        backup = _build_backup_payload()
        payload = json.dumps(backup, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self._cors()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Content-Disposition',
                         f'attachment; filename="SIS_SGCD_BACKUP_{time.strftime("%Y-%m-%d_%H-%M-%S")}.json"')
        self.end_headers()
        self.wfile.write(payload)

    def _restore_backup(self, data, s):
        if not data.get('_sgcd'):
            self._json(400, {'error': 'Arquivo não é um backup SGCD válido'}); return
        _do_db_backup()  # backup do atual antes de substituir tudo — ponto de recuperação se o restore abaixo falhar
        try:
            self._restore_backup_tx(data)
        except Exception as e:
            _log.error('Falha ao restaurar backup: %s', e)
            self._json(500, {'error': f'Falha ao restaurar backup — nenhuma alteração foi aplicada (banco preservado): {e}'})
            return
        # Registrado depois da transação: _restore_backup_tx apaga e reimporta audit_global
        # a partir do payload, então logar antes seria perdido no DELETE FROM audit_global.
        with get_db() as conn:
            _insert_audit_raw(conn, {'type': 'RESTAURAR_BACKUP', 'ts': _now(),
                                      'user_id': s['user_id'], 'user_nome': s['nome'],
                                      'label': 'Backup do sistema restaurado', 'detail': 'Restauração via arquivo JSON'})
        self._json(200, {'ok': True})

    def _restore_backup_tx(self, data):
        # Sem commit() explícito no meio: tudo isto é UMA transação. Se qualquer
        # INSERT falhar (ex.: item malformado no JSON), o `with get_db()` faz
        # ROLLBACK de tudo — inclusive dos DELETEs acima — em vez de deixar o
        # banco vazio sem nada restaurado (bug corrigido: commit() prematuro
        # aqui confirmava os DELETEs antes das inserções serem validadas).
        with get_db() as conn:
            conn.execute('DELETE FROM audit_global')
            conn.execute('DELETE FROM files')
            conn.execute('DELETE FROM processes')
            conn.execute('DELETE FROM fornecedores')

            for p in data.get('processes', []):
                pid = p.get('id') or str(uuid.uuid4())
                p['id'] = pid
                conn.execute(
                    '''INSERT OR REPLACE INTO processes
                       (id,data,objeto,status,unidade,valor,num_proc,num_dl,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?)''',
                    (pid, json.dumps(p, ensure_ascii=False),
                     p.get('objeto'), p.get('status'), p.get('unidade'), _float(p.get('valor')),
                     p.get('num_proc'), p.get('num_dl'), p.get('createdAt'), p.get('updatedAt'))
                )

            for f in data.get('fornecedores', []):
                fid = f.get('id') or str(uuid.uuid4())
                f['id'] = fid
                conn.execute(
                    'INSERT OR REPLACE INTO fornecedores (id,data,cnpj,razao_social,updated_at) VALUES (?,?,?,?,?)',
                    (fid, json.dumps(f, ensure_ascii=False),
                     f.get('cnpj'), f.get('razao') or f.get('razao_social'), f.get('updatedAt'))
                )

            for a in data.get('auditGlobal', []):
                _insert_audit_raw(conn, a)

            for key, value in (data.get('settings') or {}).items():
                v = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                conn.execute('INSERT OR REPLACE INTO sys_settings (key,value) VALUES (?,?)', (key, v))

            for fd in data.get('files', []):
                b64 = fd.get('data_b64') or fd.get('data', '')
                if not b64: continue
                try:
                    binary    = base64.b64decode(b64)
                    safe_name = secrets.token_hex(16) + '.bin'
                    with open(os.path.join(UPLOADS_DIR, safe_name), 'wb') as fh:
                        fh.write(binary)
                    conn.execute(
                        '''INSERT OR REPLACE INTO files
                           (id,process_id,step_index,nome_original,nome_disco,tamanho,mime)
                           VALUES (?,?,?,?,?,?,?)''',
                        (fd.get('id') or str(uuid.uuid4()), fd.get('process_id'),
                         fd.get('step_index'), fd.get('nome_original', 'arquivo'),
                         safe_name, len(binary), fd.get('mime', 'application/octet-stream'))
                    )
                except Exception:
                    pass

            # Backups antigos podem trazer 'signatures' — ignorado (assinatura digital removida).

    def _restore_db_backup(self, raw_bytes, s):
        # raw_bytes é o conteúdo bruto do arquivo .db enviado via multipart ou binário
        if len(raw_bytes) < 16 or raw_bytes[:16] != b'SQLite format 3\x00':
            self._json(400, {'error': 'Arquivo não é um banco SQLite válido'}); return
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        try:
            tmp.write(raw_bytes); tmp.close()
            # Valida que o arquivo tem as tabelas esperadas
            with sqlite3.connect(tmp.name, factory=_ConnAutoClose) as test_conn:
                tables = {r[0] for r in test_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            required = {'processes', 'fornecedores', 'sys_settings'}
            if not required.issubset(tables):
                self._json(400, {'error': 'Banco inválido: tabelas obrigatórias ausentes'}); return
            # Backup do atual antes de restaurar
            _do_db_backup()
            # Substitui o banco atual com o backup via API de backup SQLite (seguro)
            with sqlite3.connect(tmp.name, factory=_ConnAutoClose) as src, get_db() as dst:
                src.backup(dst)
                # Registrado na conexão já restaurada — o backup() acima substitui todo o
                # banco, então logar antes seria sobrescrito pelo conteúdo do arquivo restaurado.
                _insert_audit_raw(dst, {'type': 'RESTAURAR_DB', 'ts': _now(),
                                         'user_id': s['user_id'], 'user_nome': s['nome'],
                                         'label': 'Banco de dados restaurado', 'detail': 'Restauração via arquivo .db'})
            self._json(200, {'ok': True})
        except Exception as e:
            _log.error('Erro ao restaurar banco: %s', e)
            self._json(500, {'error': str(e)})
        finally:
            try: os.remove(tmp.name)
            except: pass

    def _relatorio_integridade(self):
        def _dir_size(path):
            total = 0
            if os.path.isdir(path):
                for f in os.listdir(path):
                    fp = os.path.join(path, f)
                    if os.path.isfile(fp): total += os.path.getsize(fp)
            return total

        cfg = _get_backup_cfg()
        bdir = cfg['path']
        backups_db = sorted(
            (f for f in os.listdir(bdir) if f.startswith('DB_SGCD_BACKUP_') and f.endswith('.db')),
            reverse=True
        ) if os.path.isdir(bdir) else []
        backups_json = sorted(
            (f for f in os.listdir(bdir) if f.startswith('SIS_SGCD_BACKUP_') and f.endswith('.json')),
            reverse=True
        ) if os.path.isdir(bdir) else []

        with get_db() as conn:
            contagens = {
                'processos_ativos': conn.execute('SELECT COUNT(*) FROM processes WHERE deleted_at IS NULL').fetchone()[0],
                'na_lixeira': conn.execute('SELECT COUNT(*) FROM processes WHERE deleted_at IS NOT NULL').fetchone()[0],
                'fornecedores': conn.execute('SELECT COUNT(*) FROM fornecedores WHERE deleted_at IS NULL').fetchone()[0],
                'arquivos': conn.execute('SELECT COUNT(*) FROM files').fetchone()[0],
                'usuarios_ativos': conn.execute('SELECT COUNT(*) FROM usuarios WHERE ativo=1').fetchone()[0],
                'etiquetas': conn.execute('SELECT COUNT(*) FROM tags').fetchone()[0],
            }
            eventos = [dict(r) for r in conn.execute(
                '''SELECT * FROM audit_global WHERE type IN
                   ('SYNC_BACKUP','RESTAURAR_BACKUP','RESTAURAR_DB','FACTORY_RESET')
                   ORDER BY ts DESC LIMIT 15''').fetchall()]
            last_row = conn.execute("SELECT value FROM sys_settings WHERE key='auto_backup_last'").fetchone()

        self._json(200, {
            'auto_backup_enabled': cfg['enabled'], 'auto_backup_keep': cfg['keep'], 'backup_path': bdir,
            'last_backup': last_row['value'] if last_row else None,
            'db_size_bytes': os.path.getsize(DB_PATH) if os.path.isfile(DB_PATH) else 0,
            'uploads_size_bytes': _dir_size(UPLOADS_DIR),
            'uploads_count': len([f for f in os.listdir(UPLOADS_DIR)]) if os.path.isdir(UPLOADS_DIR) else 0,
            'backups_db_count': len(backups_db), 'backups_json_count': len(backups_json),
            'backups_db_size_bytes': sum(os.path.getsize(os.path.join(bdir, f)) for f in backups_db),
            'contagens': contagens, 'eventos_recentes': eventos,
        })

    # ── CNPJ Proxy ────────────────────────────────────────────────────────────

    def _proxy_cnpj(self, digits):
        if not digits.isdigit() or len(digits) != 14:
            self._json(400, {'status': 'ERROR', 'message': 'CNPJ inválido'}); return
        url = f'https://receitaws.com.br/v1/cnpj/{digits}'
        req = urllib.request.Request(url, headers={'User-Agent': 'SGCD/2.0'})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read()
                self.send_response(resp.status)
                self._cors()
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        except urllib.error.HTTPError as e:
            body = e.read()
            self.send_response(e.code); self._cors()
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)
        except Exception as e:
            self._json(502, {'status': 'ERROR', 'message': str(e)})

    # ── CEIS/CNEP (Portal da Transparência/CGU) ────────────────────────────────
    # Consulta automatizada de sanções federais por CNPJ, complementando os links
    # manuais no cadastro de Fornecedores. Exige chave de API gratuita (cadastro em
    # api.portaldatransparencia.gov.br), salva em Configurações e lida via sys_settings.
    def _proxy_ceis_cnep(self, qs):
        def qp(k): v = qs.get(k); return (v[0] if v else '').strip()
        cnpj = re.sub(r'\D', '', qp('cnpj'))
        if len(cnpj) != 14:
            self._json(400, {'error': 'CNPJ inválido'}); return
        with get_db() as conn:
            row = conn.execute(
                "SELECT value FROM sys_settings WHERE key='portal_transparencia_key'"
            ).fetchone()
        api_key = row['value'] if row else ''
        if not api_key:
            self._json(400, {'error': 'Chave de API do Portal da Transparência não configurada (Configurações → Organização)'}); return

        resultado = {'ceis': [], 'cnep': [], 'erro': None}
        for tipo in ('ceis', 'cnep'):
            url = f'https://api.portaldatransparencia.gov.br/api-de-dados/{tipo}?cnpjSancionado={cnpj}&pagina=1'
            req = urllib.request.Request(url, headers={'chave-api-dados': api_key, 'User-Agent': 'SGCD/2.0'})
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resultado[tipo] = json.loads(resp.read())
            except urllib.error.HTTPError as e:
                resultado['erro'] = f'{tipo.upper()}: HTTP {e.code} (verifique a chave de API)'
            except Exception as e:
                resultado['erro'] = f'{tipo.upper()}: {e}'
        self._json(200, resultado)

    # ── Verificar documento ───────────────────────────────────────────────────

    # ── E-mail ────────────────────────────────────────────────────────────────

    def _send_email(self, data, sess):
        if 'smtp' in data:
            # Modo teste ("Testar conexão"): usa a config explícita digitada na tela,
            # sem salvar — único caminho em que o cliente ainda manda config.
            _send_email_raw(data['smtp'], data['from'], data['to'], data['subject'], data['html'], data.get('text', ''))
            return
        # Envio normal: config resolvida no servidor — a do usuário logado,
        # com fallback para a do sistema. A senha nunca passa pelo navegador.
        cfg = get_user_smtp(sess['user_id'])
        if not (cfg.get('smtp_host') and cfg.get('smtp_user')):
            raise ValueError('SMTP não configurado. Configure em Configurações → E-mail (ou no seu perfil).')
        smtp_cfg, frm = _smtp_cfg_build(cfg)
        _send_email_raw(smtp_cfg, frm, data['to'], data['subject'], data['html'], data.get('text', ''))

    # ── Helpers HTTP ──────────────────────────────────────────────────────────

    def _body(self):
        n = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(n) if n else b''

    def _parse_json(self, body):
        try: return json.loads(body) if body else {}
        except Exception: return {}

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type,Authorization')

    def _json(self, status, obj):
        payload = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self._cors()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args): pass

# ── Utilitários ───────────────────────────────────────────────────────────────

def _now():
    return time.strftime('%Y-%m-%dT%H:%M:%S')

def _now_precise():
    # Com precisão de milissegundo — usado especificamente em updatedAt para
    # a checagem de conflito de edição concorrente (_baseUpdatedAt). _now(),
    # com precisão de segundo, colide facilmente entre duas edições rápidas em
    # sequência (ex.: salvar duas vezes em menos de 1s), fazendo o servidor
    # não detectar um conflito real. Formato ainda parseável por new Date() no cliente.
    t = time.time()
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(t)) + f'.{int((t % 1) * 1000):03d}'

def _sync_tags(conn, join_table, id_col, item_id, tag_names):
    """Substitui as tags do registro pela lista informada (cria as que não existem)."""
    nomes = sorted({t.strip() for t in (tag_names or []) if t.strip()})
    conn.execute(f'DELETE FROM {join_table} WHERE {id_col}=?', (item_id,))
    for nome in nomes:
        conn.execute('INSERT OR IGNORE INTO tags (nome) VALUES (?)', (nome,))
        tag_id = conn.execute('SELECT id FROM tags WHERE nome=? COLLATE NOCASE', (nome,)).fetchone()['id']
        conn.execute(f'INSERT OR IGNORE INTO {join_table} ({id_col},tag_id) VALUES (?,?)', (item_id, tag_id))

def _tags_map(conn, join_table, id_col, item_ids):
    """Retorna {item_id: [nomes de tag]} para os ids informados."""
    if not item_ids: return {}
    qs = ','.join('?' * len(item_ids))
    rows = conn.execute(
        f'''SELECT j.{id_col} AS iid, t.nome FROM {join_table} j
            JOIN tags t ON j.tag_id=t.id WHERE j.{id_col} IN ({qs})
            ORDER BY t.nome''', item_ids
    ).fetchall()
    out = {}
    for r in rows:
        out.setdefault(r['iid'], []).append(r['nome'])
    return out

def _insert_audit_raw(conn, a):
    """Insere um evento de auditoria preservando autor/id/data originais do payload
    (ao contrário de _add_audit, que sempre carimba o usuário da sessão atual —
    correto para lançar eventos ao vivo, errado para importar histórico de outra
    máquina via restauração/sincronização de backup)."""
    conn.execute(
        '''INSERT OR REPLACE INTO audit_global
           (id,ts,user_id,user_nome,type,label,detail,process_id,process_obj)
           VALUES (?,?,?,?,?,?,?,?,?)''',
        (a.get('id') or str(uuid.uuid4()), a.get('ts'),
         a.get('userId') or a.get('user_id'),
         a.get('userName') or a.get('user_nome'),
         a.get('type'), a.get('label'), a.get('detail'),
         a.get('processId') or a.get('process_id'),
         json.dumps(a['processObj']) if a.get('processObj') else a.get('process_obj'))
    )

def _float(v):
    if v is None or v == '':
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace('R$', '').strip()
    if not s:
        return None
    # Formato BR: ponto = milhar, vírgula = decimal. Com os dois presentes,
    # remove os pontos e troca a vírgula por ponto (1.234,56 -> 1234.56).
    # Só vírgula -> decimal (1234,56 -> 1234.56). Só ponto -> já é decimal.
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except (ValueError, TypeError):
        return None

def _mime(ext):
    return {'.pdf': 'application/pdf', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}.get(ext, 'application/octet-stream')

def _parse_multipart(body, boundary):
    filename, file_bytes, step_index = None, None, None
    for part in body.split(b'--' + boundary):
        if b'Content-Disposition' not in part: continue
        sep = part.find(b'\r\n\r\n')
        if sep < 0: continue
        header  = part[:sep].decode('utf-8', errors='replace')
        content = part[sep+4:]
        if content.endswith(b'\r\n'): content = content[:-2]
        if 'filename=' in header:
            m = re.search(r'filename="([^"]*)"', header)
            if m: filename = m.group(1)
            file_bytes = content
        elif 'name="step_index"' in header:
            try: step_index = int(content.strip())
            except: pass
    return filename, file_bytes, step_index

def _parse_multipart_all(body, boundary):
    """Extrai todos os campos do multipart/form-data em um dict.
    Retorna: {field_name: {'text': str, 'data': bytes, 'filename': str}}
    """
    parts = {}
    for part in body.split(b'--' + boundary):
        if b'Content-Disposition' not in part: continue
        sep = part.find(b'\r\n\r\n')
        if sep < 0: continue
        header  = part[:sep].decode('utf-8', errors='replace')
        content = part[sep+4:]
        if content.endswith(b'\r\n'): content = content[:-2]
        m_name = re.search(r'name="([^"]*)"', header)
        if not m_name: continue
        name = m_name.group(1)
        m_file = re.search(r'filename="([^"]*)"', header)
        if m_file:
            parts[name] = {'data': content, 'filename': m_file.group(1), 'text': None}
        else:
            parts[name] = {'data': content, 'filename': None, 'text': content.decode('utf-8', errors='replace').strip()}
    return parts

def _find_browser():
    for c in [
        os.path.expandvars(r'%ProgramFiles%\Google\Chrome\Application\chrome.exe'),
        os.path.expandvars(r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe'),
        os.path.expandvars(r'%LocalAppData%\Google\Chrome\Application\chrome.exe'),
        os.path.expandvars(r'%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe'),
    ]:
        if os.path.isfile(c): return c
    return None

# _send_email_raw vem do sgx_base (esqueleto compartilhado da família)
_send_email_raw = sgx_base.send_email_raw

def _send_daily_alerts():
    """Resumo diário por e-mail de prazos vencendo e processos parados.
    Só envia se SMTP estiver configurado no servidor e ainda não tiver enviado hoje."""
    with get_db() as conn:
        cfg = {r['key']: r['value'] for r in conn.execute(
            "SELECT key,value FROM sys_settings WHERE key LIKE 'smtp_%' OR key='alert_email_last_sent'"
        ).fetchall()}
    if not (cfg.get('smtp_host') and cfg.get('smtp_user') and cfg.get('smtp_pass') and cfg.get('smtp_to')):
        return
    hoje = time.strftime('%Y-%m-%d')
    if cfg.get('alert_email_last_sent') == hoje:
        return

    with get_db() as conn:
        rows = conn.execute("SELECT data FROM processes WHERE deleted_at IS NULL").fetchall()

    agora = time.time()
    parados, prazos = [], []
    for row in rows:
        try:
            p = json.loads(row['data'])
        except Exception:
            continue
        steps = p.get('steps') or []
        done = sum(1 for st in steps if st.get('status') == 'done')
        if steps and done == len(steps):
            continue  # processo concluído — fora dos alertas

        objeto = p.get('objeto') or p.get('num') or p.get('id')
        updated = p.get('updatedAt')
        if updated:
            try:
                ts = time.mktime(time.strptime(updated[:19], '%Y-%m-%dT%H:%M:%S'))
                dias_parado = int((agora - ts) / 86400)
                if dias_parado >= 15:
                    parados.append((objeto, dias_parado))
            except Exception:
                pass

        prazo = p.get('prazo')
        if prazo:
            try:
                ts = time.mktime(time.strptime(prazo[:10], '%Y-%m-%d'))
                dias = int((ts - agora) / 86400)
                if dias <= 7:
                    prazos.append((objeto, dias))
            except Exception:
                pass

    if not parados and not prazos:
        # Nada para reportar hoje — ainda assim marca como "enviado" para não reprocessar
        with get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO sys_settings (key,value) VALUES ('alert_email_last_sent',?)", (hoje,))
        return

    linhas = []
    if prazos:
        linhas.append('<h3>Prazos</h3><ul>')
        for objeto, dias in sorted(prazos, key=lambda x: x[1]):
            txt = f'vencido há {-dias} dia(s)' if dias < 0 else (f'vence hoje' if dias == 0 else f'vence em {dias} dia(s)')
            linhas.append(f'<li><strong>{html_mod.escape(str(objeto))}</strong> — {txt}</li>')
        linhas.append('</ul>')
    if parados:
        linhas.append('<h3>Processos parados (15+ dias sem atualização)</h3><ul>')
        for objeto, dias in sorted(parados, key=lambda x: -x[1]):
            linhas.append(f'<li><strong>{html_mod.escape(str(objeto))}</strong> — {dias} dias sem atualização</li>')
        linhas.append('</ul>')

    corpo = f"<p>Resumo automático do SGCD — {hoje}</p>" + ''.join(linhas)
    smtp_cfg, frm = _smtp_cfg_build(cfg)
    try:
        _send_email_raw(smtp_cfg, frm, cfg['smtp_to'], f'SGCD — Resumo de pendências ({hoje})', corpo)
        print(f'  [ALERTAS] E-mail de resumo enviado ({len(prazos)} prazo(s), {len(parados)} parado(s))', flush=True)
    except Exception as e:
        _log.error('Falha ao enviar e-mail de alertas: %s', e)
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO sys_settings (key,value) VALUES ('alert_email_last_sent',?)", (hoje,))

_last_trash_purge = 0

def _purge_old_trash():
    """Esvazia a lixeira: processos/fornecedores excluídos há mais de 30 dias."""
    global _last_trash_purge
    _last_trash_purge = time.time()
    limite_iso = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(time.time() - 30 * 86400))
    with get_db() as conn:
        old_procs = conn.execute(
            "SELECT id FROM processes WHERE deleted_at IS NOT NULL AND deleted_at < ?", (limite_iso,)
        ).fetchall()
        for row in old_procs:
            pid = row['id']
            files = conn.execute('SELECT nome_disco FROM files WHERE process_id LIKE ?', (pid + '%',)).fetchall()
            for f in files:
                fp = os.path.join(UPLOADS_DIR, f['nome_disco'])
                if os.path.exists(fp): os.remove(fp)
            conn.execute('DELETE FROM files WHERE process_id LIKE ?', (pid + '%',))
            conn.execute('DELETE FROM processes WHERE id=?', (pid,))
        conn.execute("DELETE FROM fornecedores WHERE deleted_at IS NOT NULL AND deleted_at < ?", (limite_iso,))

def _watchdog():
    # Limpa sessões expiradas a cada 5s e dispara o backup pós-sessão
    # (_check_shutdown — não encerra mais o servidor, só faz backup).
    # SESSION_TTL=60s dá folga de sobra sobre o ping a cada 5s: um TTL curto
    # (era 15s) expirava sessões à toa quando o ping atrasava por qualquer
    # motivo comum — carregamento inicial da página disputando conexão HTTP
    # com várias outras chamadas simultâneas (settings, dashboard, processo),
    # ou a aba principal perdendo foco ao abrir um popup de documento.
    while True:
        time.sleep(5)
        if _watchdog_paused:
            continue
        sgx_base.purge_expired_sessions(get_db)
        try: _check_shutdown()
        except Exception as e: _log.error('Erro em _check_shutdown: %s', e)
        if time.time() - _last_trash_purge > 3600:
            try: _purge_old_trash()
            except Exception as e: _log.error('Erro ao esvaziar lixeira: %s', e)
        try: _send_daily_alerts()
        except Exception as e: _log.error('Erro ao enviar alertas por e-mail: %s', e)

# ── Backup automático do banco ─────────────────────────────────────────────────

def _build_backup_payload():
    with get_db() as conn:
        processes    = [json.loads(r['data']) for r in conn.execute('SELECT data FROM processes').fetchall()]
        fornecedores = [json.loads(r['data']) for r in conn.execute('SELECT data FROM fornecedores').fetchall()]
        audit        = [dict(r) for r in conn.execute('SELECT * FROM audit_global').fetchall()]
        settings     = {r['key']: r['value'] for r in conn.execute('SELECT key,value FROM sys_settings').fetchall()}
        file_rows    = conn.execute('SELECT * FROM files').fetchall()
    files_out = []
    for fr in file_rows:
        fp = os.path.join(UPLOADS_DIR, fr['nome_disco'])
        b64 = ''
        if os.path.exists(fp):
            with open(fp, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode()
        files_out.append({**dict(fr), 'data_b64': b64})
    return {
        '_sgcd': True, 'version': 5, 'exportedAt': _now(),
        'processes': processes, 'fornecedores': fornecedores,
        'auditGlobal': audit, 'settings': settings, 'files': files_out,
    }

def _do_json_backup(cfg=None):
    if cfg is None: cfg = _get_backup_cfg()
    bdir = cfg['path']
    keep = cfg['keep']
    os.makedirs(bdir, exist_ok=True)
    name = time.strftime('SIS_SGCD_BACKUP_%Y-%m-%d_%H-%M-%S.json')
    dst  = os.path.join(bdir, name)
    try:
        backup = _build_backup_payload()
        with open(dst, 'w', encoding='utf-8') as f:
            json.dump(backup, f, ensure_ascii=False)
        print(f'Backup JSON automático: {name}')
        return name
    except Exception as e:
        _log.error('Falha no backup JSON automático: %s', e)
        return None

def _rotate_backups(cfg=None):
    if cfg is None: cfg = _get_backup_cfg()
    bdir = cfg['path']
    keep = cfg['keep']
    if not os.path.isdir(bdir): return
    for prefix, ext in [('DB_SGCD_BACKUP_', '.db'), ('SIS_SGCD_BACKUP_', '.json')]:
        files = sorted(f for f in os.listdir(bdir) if f.startswith(prefix) and f.endswith(ext))
        to_delete = files[:-keep] if keep else files
        for old in to_delete:
            fp = os.path.join(bdir, old)
            for attempt in range(6):  # tenta por até ~10s (OneDrive pode manter o arquivo aberto)
                try:
                    os.remove(fp)
                    print(f'Rotação: removido {old}')
                    break
                except PermissionError:
                    if attempt < 5:
                        time.sleep(2)
                    else:
                        _log.error('Falha ao remover backup %s: arquivo bloqueado (OneDrive/antivírus). Remova manualmente.', old)
                except Exception as e:
                    _log.error('Falha ao remover backup %s: %s', old, e)
                    break

def _get_backup_cfg():
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT key,value FROM sys_settings WHERE key IN ('backup_path','auto_backup_enabled','auto_backup_keep')"
            ).fetchall()
        cfg = {r['key']: r['value'] for r in rows}
    except Exception:
        cfg = {}
    try:
        keep = max(1, int(cfg.get('auto_backup_keep') or BACKUP_KEEP))
    except (TypeError, ValueError):
        keep = BACKUP_KEEP  # valor não-numérico salvo por engano (ex.: via chamada direta à API) — ignora em vez de derrubar o watchdog
    return {
        'path':    cfg.get('backup_path') or BACKUP_DIR,
        'enabled': cfg.get('auto_backup_enabled', '1') != '0',
        'keep':    keep,
    }

def _do_db_backup(cfg=None):
    if cfg is None: cfg = _get_backup_cfg()
    bdir = cfg['path']
    keep = cfg['keep']
    os.makedirs(bdir, exist_ok=True)
    name = time.strftime('DB_SGCD_BACKUP_%Y-%m-%d_%H-%M-%S.db')
    dst  = os.path.join(bdir, name)
    try:
        with sqlite3.connect(DB_PATH, factory=_ConnAutoClose) as src, sqlite3.connect(dst, factory=_ConnAutoClose) as bk:
            src.backup(bk)
        # Registra timestamp do último backup
        with get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO sys_settings (key,value) VALUES ('auto_backup_last',?)", (_now(),))
        print(f'Backup automático: {name}')
        return name
    except Exception as e:
        _log.error('Falha no backup automático: %s', e)
        return None

# ── Inicialização ─────────────────────────────────────────────────────────────

init_db()

# Verifica integridade do banco na inicialização
def _check_db_integrity():
    try:
        with get_db() as conn:
            result = conn.execute('PRAGMA integrity_check').fetchone()[0]
            if result != 'ok':
                _log.error('INTEGRITY CHECK FALHOU: %s', result)
                print(f'[AVISO] Banco de dados com problema de integridade: {result}')
            else:
                print('[DB] Integridade verificada: ok')
    except Exception as e:
        _log.error('Erro ao verificar integridade do banco: %s', e)

# ── Menu inicial ──────────────────────────────────────────────────────────────

def _selecionar_modo():
    print()
    print('  ╔══════════════════════════════════════════════════╗')
    print('  ║   SGCD — Sistema de Gestão de Contratação Direta ║')
    print('  ╚══════════════════════════════════════════════════╝')
    print()
    print('  [1] Diagnóstico     — Verifica rede, porta e firewall')
    print('  [2] Iniciar Servidor')
    print()
    if not sys.stdin.isatty():
        op = '2'
    else:
        while True:
            try:
                op = input('  Opção [1/2]: ').strip()
            except (EOFError, KeyboardInterrupt):
                op = '2'
            if op in ('1', '2'):
                break
            print('  Digite 1 ou 2.')
    if op == '1':
        import subprocess as _sp
        diag = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'diagnostico.py')
        _sp.run([sys.executable, diag])
        sys.exit(0)
    print()
    print('  ─────────────────────────────────────────────────')

if __name__ == '__main__':
    _selecionar_modo()
    _check_db_integrity()
    _rotate_backups(_get_backup_cfg())  # limpa excedentes dos backups da sessão anterior
    threading.Thread(target=_watchdog, daemon=True).start()

    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(('', PORT), SGCDHandler) as httpd:
        print(f'  Servidor: http://localhost:{PORT}')
        import socket as _socket
        try:
            ip_local = _socket.gethostbyname(_socket.gethostname())
        except Exception:
            ip_local = 'desconhecido'
        print(f'  Rede:     http://{ip_local}:{PORT}/SGCD.html')
        print()

        browser = _find_browser()
        if browser:
            profile_dir = os.path.join(os.environ.get('TEMP', os.path.expanduser('~')), 'SGCD-Profile')
            subprocess.Popen([
                browser,
                f'--app=http://localhost:{PORT}/SGCD.html',
                '--start-maximized',
                '--disable-background-mode',
                f'--user-data-dir={profile_dir}',
            ])
            print('  App aberto no navegador.')
        else:
            print(f'  Chrome/Edge não encontrado. Abra manualmente: http://localhost:{PORT}/SGCD.html')

        print('  Aguardando conexões... (Ctrl+C para encerrar)')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\n  Encerrando servidor...')
