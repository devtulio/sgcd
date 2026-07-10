# SGCD v2.25.0 — Servidor local: SQLite, autenticação, REST API, proxy CNPJ, e-mail SMTP, backup automático
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
SESSION_TTL   = 15   # 15s — renovado pelo ping a cada 5s; expira rápido se browser fechar
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
_had_session      = False   # True após primeiro login; evita encerramento antes de qualquer usuário logar
_modo_servidor    = False   # True = modo servidor contínuo (sem encerramento automático)
_backup_pos_sess  = False   # True = backup pós-sessão já executado; aguarda nova sessão para resetar

# ── Banco de dados ────────────────────────────────────────────────────────────

class _ConnAutoClose(sqlite3.Connection):
    """sqlite3.Connection.__exit__ só faz commit/rollback da transação — não fecha
    a conexão. Sem isso, todo `with get_db() as conn:` (63 pontos no arquivo) vaza
    uma conexão aberta por chamada. Fecha a conexão junto, sem precisar alterar
    nenhum call site."""
    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()

def get_db():
    conn = sqlite3.connect(DB_PATH, factory=_ConnAutoClose)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn

def init_db():
    with get_db() as conn:
        # Migração: tabela 'users' (nome antigo) → 'usuarios' (padrão SGDP).
        # SQLite atualiza sozinho as FKs de sessions/processes/files/signatures
        # que apontavam para users(id); preserva cargo/matricula e demais dados.
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'users' in tables and 'usuarios' not in tables:
            conn.execute('ALTER TABLE users RENAME TO usuarios')
            conn.commit()
        # Migração: remove a FK indevida em files.process_id → processes(id).
        # A coluna é usada tanto com o id real do processo quanto com uma chave
        # sintética por etapa ("<processId>_<stepIndex>", usada pelos anexos de
        # etapa e pelas certidões da Habilitação — ver /api/files?prefix=1), que
        # nunca bate com processes.id e sempre violava a FK (crash ao anexar
        # qualquer arquivo numa etapa). Como a FK sempre bloqueou essas
        # inserções, não existe linha desse tipo para preservar — só recria a
        # tabela sem a FK.
        if 'files' in tables:
            fks = conn.execute("PRAGMA foreign_key_list(files)").fetchall()
            if any(fk[2] == 'processes' for fk in fks):
                # Cria a tabela nova primeiro e só troca o nome no fim — renomear a
                # tabela ANTIGA direto faz o SQLite reescrever a REFERENCES de
                # signatures.file_id para o nome temporário, deixando-a apontando
                # para uma tabela inexistente assim que a antiga é descartada.
                conn.execute('''
                    CREATE TABLE files_new (
                        id            TEXT PRIMARY KEY,
                        process_id    TEXT,
                        step_index    INTEGER,
                        nome_original TEXT NOT NULL,
                        nome_disco    TEXT NOT NULL,
                        tamanho       INTEGER,
                        mime          TEXT,
                        uploaded_by   INTEGER REFERENCES usuarios(id),
                        uploaded_em   TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
                    )
                ''')
                conn.execute('INSERT INTO files_new SELECT * FROM files')
                conn.execute('DROP TABLE files')
                conn.execute('ALTER TABLE files_new RENAME TO files')
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
                process_id    TEXT,
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
            CREATE TABLE IF NOT EXISTS signatures (
                id             TEXT PRIMARY KEY,
                cod            TEXT UNIQUE,
                process_id     TEXT REFERENCES processes(id) ON DELETE CASCADE,
                doc_type       TEXT NOT NULL,
                doc_filename   TEXT,
                signer_user_id INTEGER REFERENCES usuarios(id),
                signer_name    TEXT,
                method         TEXT NOT NULL,
                status         TEXT DEFAULT 'signed',
                hash_sha256    TEXT,
                file_id        TEXT REFERENCES files(id),
                signed_at      TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
                extra_json     TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_proc_status   ON processes(status);
            CREATE INDEX IF NOT EXISTS idx_proc_unidade  ON processes(unidade);
            CREATE INDEX IF NOT EXISTS idx_proc_updated  ON processes(updated_at);
            CREATE INDEX IF NOT EXISTS idx_files_proc    ON files(process_id);
            CREATE INDEX IF NOT EXISTS idx_forn_cnpj     ON fornecedores(cnpj);
            CREATE INDEX IF NOT EXISTS idx_audit_ts      ON audit_global(ts);
            CREATE INDEX IF NOT EXISTS idx_sig_proc      ON signatures(process_id);
            CREATE INDEX IF NOT EXISTS idx_sig_cod       ON signatures(cod);
            CREATE INDEX IF NOT EXISTS idx_proc_tags_tag ON process_tags(tag_id);
        ''')
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
        for col in ('cpf', 'email'):
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

def _hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100_000)
    return f'{salt}:{dk.hex()}'

def _verify_password(password, stored):
    try:
        salt, _ = stored.split(':', 1)
        return secrets.compare_digest(_hash_password(password, salt), stored)
    except Exception:
        return False

# ── Rate limit de login ─────────────────────────────────────────────────────
# ponytail: dict em memória, sem lock — pior caso é uma contagem levemente
# imprecisa sob concorrência, não uma falha; zera a cada reinício do servidor.
LOGIN_MAX_ATTEMPTS   = 5
LOGIN_LOCKOUT_WINDOW = 300   # 5 min — janela deslizante de tentativas falhas
_login_failures = {}   # username (lower) -> [timestamps de tentativas falhas]

def _login_rate_limited(username):
    key = (username or '').strip().lower()
    now = time.time()
    attempts = [t for t in _login_failures.get(key, []) if now - t < LOGIN_LOCKOUT_WINDOW]
    _login_failures[key] = attempts
    return len(attempts) >= LOGIN_MAX_ATTEMPTS

def _record_login_failure(username):
    key = (username or '').strip().lower()
    _login_failures.setdefault(key, []).append(time.time())

def _clear_login_failures(username):
    _login_failures.pop((username or '').strip().lower(), None)

def create_session(user_id):
    token = secrets.token_urlsafe(32)
    expires = time.time() + SESSION_TTL
    with get_db() as conn:
        conn.execute('DELETE FROM sessions WHERE expires < ?', (time.time(),))
        conn.execute('INSERT INTO sessions (token,user_id,expires) VALUES (?,?,?)',
                     (token, user_id, expires))
    return token

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

def delete_session(token):
    with get_db() as conn:
        conn.execute('DELETE FROM sessions WHERE token=?', (token,))

def renew_session(token):
    with get_db() as conn:
        conn.execute('UPDATE sessions SET expires=? WHERE token=?',
                     (time.time() + SESSION_TTL, token))

def active_sessions():
    with get_db() as conn:
        return conn.execute('SELECT COUNT(*) FROM sessions WHERE expires>?', (time.time(),)).fetchone()[0]

def _check_shutdown():
    """Encerra o servidor quando não há mais sessões ativas (último logout).
    No modo servidor contínuo (_modo_servidor=True), apenas faz backup sem encerrar."""
    global _backup_pos_sess
    if _modo_servidor:
        # Modo servidor: backup uma única vez após última sessão encerrada
        if _had_session and active_sessions() == 0 and not _backup_pos_sess:
            _backup_pos_sess = True
            cfg = _get_backup_cfg()
            if cfg['enabled']:
                print('\nÚltima sessão encerrada. Executando backup automático...')
                _do_json_backup(cfg)
                _do_db_backup(cfg)
        return
    if not _had_session:
        return
    if active_sessions() > 0:
        return
    print('\nÚltima sessão encerrada. Executando backup e encerrando servidor...')
    cfg = _get_backup_cfg()
    if cfg['enabled']:
        _do_json_backup(cfg)
        _do_db_backup(cfg)
    os._exit(0)

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

    def do_GET(self):
        parsed = urlparse(self.path)
        p  = parsed.path.rstrip('/')
        qs = parse_qs(parsed.query)

        if p == '/health':
            self._json(200, {'ok': True, 'modo_servidor': _modo_servidor})
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
        elif p.startswith('/verificar/'):
            self._serve_verificar(p[11:].strip('/').upper())
        elif p.startswith('/api/'):
            s = self._auth()
            if s: self._route_get(p, qs, s)
        else:
            super().do_GET()

    def do_POST(self):
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
            if not get_session(self._token()):
                self._json(401, {'error': 'Não autenticado'}); return
            try:
                self._send_email(json.loads(self._body()))
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
        p = urlparse(self.path).path.rstrip('/')
        s = self._auth()
        if not s: return
        self._route_put(p, self._body(), s)

    def do_DELETE(self):
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

        # Assinaturas
        elif p == '/api/signatures':
            pid = qp('process_id')
            with get_db() as conn:
                if pid:
                    rows = conn.execute(
                        'SELECT * FROM signatures WHERE process_id=? ORDER BY signed_at DESC', (pid,)
                    ).fetchall()
                else:
                    rows = conn.execute('SELECT * FROM signatures ORDER BY signed_at DESC LIMIT 500').fetchall()
            self._json(200, {'items': [dict(r) for r in rows]})

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
                with sqlite3.connect(DB_PATH) as src, sqlite3.connect(tmp.name) as bk:
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
                import subprocess as _sp
                ps_cmd = (
                    'Add-Type -AssemblyName System.Windows.Forms;'
                    '$d=New-Object System.Windows.Forms.FolderBrowserDialog;'
                    '$d.Description="Selecione a pasta de backup do SGCD";'
                    '$d.ShowNewFolderButton=$true;'
                    'if($d.ShowDialog()-eq"OK"){Write-Output $d.SelectedPath}'
                )
                r = _sp.run(['powershell', '-Sta', '-WindowStyle', 'Hidden', '-Command', ps_cmd],
                            capture_output=True, text=True, timeout=120)
                path = r.stdout.strip()
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
            def _parse_ts(f):
                # DB_SGCD_BACKUP_2026-06-27_20-35-41.db → 2026-06-27T20:35:41
                d = f[15:25]; t = f[26:34].replace('-', ':')
                return f'{d}T{t}'
            items = [{'name': f, 'size': os.path.getsize(os.path.join(bdir, f)),
                      'ts': _parse_ts(f)} for f in files]
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
            self._restore_backup(data)

        elif p == '/api/backups/db/restore':
            if not s['admin']: self._json(403, {'error': 'Acesso restrito'}); return
            self._restore_db_backup(body)

        elif p == '/api/files':
            self._upload_file_direct(s)

        elif p == '/api/signatures':
            self._create_signature_simple(data, s)

        elif p == '/api/signatures/upload':
            self._create_signature_upload(s)

        elif re.fullmatch(r'/api/processes/[^/]+/pdf-consolidado', p):
            self._gerar_pdf_consolidado(p.split('/')[3], data)

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
                # ponytail: não-admin só pode trocar a própria senha
                data = {k: data[k] for k in ('password', 'old_password') if k in data}
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
        now = _now()
        data.setdefault('createdAt', now)
        data['updatedAt'] = now
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
            existing.update(data)
            existing['updatedAt'] = _now()
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
        data.setdefault('updatedAt', _now())
        with get_db() as conn:
            conn.execute(
                'INSERT OR REPLACE INTO fornecedores (id,data,cnpj,razao_social,updated_at) VALUES (?,?,?,?,?)',
                (fid, json.dumps(data, ensure_ascii=False),
                 data.get('cnpj'), data.get('razao') or data.get('razao_social'), data['updatedAt'])
            )
        self._json(200, data)

    def _update_fornecedor(self, fid, data):
        with get_db() as conn:
            row = conn.execute('SELECT data FROM fornecedores WHERE id=?', (fid,)).fetchone()
            if not row:
                self._create_fornecedor({**data, 'id': fid}); return
            existing = json.loads(row['data'])
            existing.update(data)
            existing['updatedAt'] = _now()
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

    # ── Assinaturas ───────────────────────────────────────────────────────────

    def _create_signature_simple(self, data, s):
        """Módulo 1 — Assinatura Simples: hash do documento + identidade do usuário logado."""
        process_id = data.get('process_id') or ''
        doc_type   = data.get('doc_type') or ''
        filename   = data.get('doc_filename') or ''
        hash_sha256 = data.get('hash_sha256') or ''
        if not doc_type or not hash_sha256:
            self._json(400, {'error': 'doc_type e hash_sha256 são obrigatórios'}); return

        sig_id = str(uuid.uuid4())
        cod = _gerar_cod_assinatura()
        with get_db() as conn:
            conn.execute(
                '''INSERT INTO signatures (id,cod,process_id,doc_type,doc_filename,signer_user_id,
                   signer_name,method,status,hash_sha256)
                   VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (sig_id, cod, process_id, doc_type, filename, s['user_id'], s.get('nome'),
                 'internal', 'signed', hash_sha256)
            )
        self._json(200, {'id': sig_id, 'cod': cod})

    def _create_signature_upload(self, s):
        """Módulos 2 (gov.br), 3 (ICP-Brasil) e 4 (física digitalizada) — recebe PDF
        já assinado (gov.br e física) ou a assinar + certificado .pfx + senha (ICP-Brasil)."""
        ct = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in ct:
            self._json(400, {'error': 'Esperado multipart/form-data'}); return
        boundary = ct.split('boundary=')[-1].strip().encode()
        length = int(self.headers.get('Content-Length', 0))
        if length > MAX_UPLOAD:
            self._json(413, {'error': f'Arquivo muito grande (máximo {MAX_UPLOAD//1024//1024} MB)'}); return
        body = self.rfile.read(length)
        parts = _parse_multipart_all(body, boundary)

        method     = parts.get('method', {}).get('text', '')
        process_id = parts.get('process_id', {}).get('text', '')
        doc_type   = parts.get('doc_type', {}).get('text', '')
        pdf_bytes  = parts.get('pdf', {}).get('data')
        pdf_name   = parts.get('pdf', {}).get('filename') or 'documento.pdf'

        if method not in ('govbr', 'icp-brasil', 'fisica'):
            self._json(400, {'error': 'method deve ser "govbr", "icp-brasil" ou "fisica"'}); return
        if not pdf_bytes:
            self._json(400, {'error': 'PDF não encontrado no upload'}); return

        extra = {}
        if method == 'icp-brasil':
            cert_bytes = parts.get('cert', {}).get('data')
            senha = parts.get('senha', {}).get('text', '')
            if not cert_bytes or not senha:
                self._json(400, {'error': 'Certificado (.pfx) e senha são obrigatórios para ICP-Brasil'}); return
            try:
                pdf_bytes, cert_info = _assinar_pdf_icp(pdf_bytes, cert_bytes, senha)
                extra['cert_subject'] = cert_info
            except Exception as e:
                self._json(400, {'error': f'Falha ao assinar com o certificado: {e}'}); return
            finally:
                cert_bytes = None; senha = None  # descarta referências assim que possível

        # Salva o PDF (assinado) como um arquivo do processo, reaproveitando a tabela files
        safe_name = secrets.token_hex(16) + '.pdf'
        with open(os.path.join(UPLOADS_DIR, safe_name), 'wb') as f:
            f.write(pdf_bytes)
        fid = str(uuid.uuid4())
        with get_db() as conn:
            conn.execute(
                '''INSERT INTO files (id,process_id,step_index,nome_original,nome_disco,tamanho,mime,uploaded_by)
                   VALUES (?,?,?,?,?,?,?,?)''',
                (fid, process_id, '', pdf_name, safe_name, len(pdf_bytes), 'application/pdf', s['user_id'])
            )

        sig_id = str(uuid.uuid4())
        cod = _gerar_cod_assinatura()
        with get_db() as conn:
            conn.execute(
                '''INSERT INTO signatures (id,cod,process_id,doc_type,doc_filename,signer_user_id,
                   signer_name,method,status,file_id,extra_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (sig_id, cod, process_id, doc_type, pdf_name, s['user_id'], s.get('nome'),
                 method, 'signed', fid, json.dumps(extra, ensure_ascii=False) if extra else None)
            )
        self._json(200, {'id': sig_id, 'cod': cod, 'file_id': fid})

    def _gerar_pdf_consolidado(self, process_id, data):
        """Monta o dossiê consolidado do processo (todas as peças em sequência,
        páginas numeradas) — ver _montar_pdf_consolidado. Import de pyHanko é
        tardio (dentro dela), então sem a lib instalada só esta rota falha,
        com mensagem clara — o resto do servidor segue normal."""
        slots = data.get('slots') or []
        try:
            pdf_bytes = _montar_pdf_consolidado(slots)
        except ImportError:
            self._json(400, {'error': 'Módulo de PDF consolidado indisponível — instale o pyHanko rodando "Instalar Assinatura ICP-Brasil.bat".'}); return
        except ValueError as e:
            self._json(400, {'error': str(e)}); return
        except Exception as e:
            _log.error('Erro ao gerar PDF consolidado: %s', e)
            self._json(500, {'error': f'Erro ao gerar PDF consolidado: {e}'}); return

        self.send_response(200)
        self._cors()
        self.send_header('Content-Type', 'application/pdf')
        self.send_header('Content-Length', str(len(pdf_bytes)))
        self.send_header('Content-Disposition', f'attachment; filename="processo-{process_id}-consolidado.pdf"')
        self.end_headers()
        self.wfile.write(pdf_bytes)

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

    def _restore_backup(self, data):
        if not data.get('_sgcd'):
            self._json(400, {'error': 'Arquivo não é um backup SGCD válido'}); return
        _do_db_backup()  # backup do atual antes de substituir tudo
        with get_db() as conn:
            conn.execute('DELETE FROM audit_global')
            conn.execute('DELETE FROM signatures')
            conn.execute('DELETE FROM files')
            conn.execute('DELETE FROM processes')
            conn.execute('DELETE FROM fornecedores')
            conn.commit()

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

            for sg in data.get('signatures', []):
                conn.execute(
                    '''INSERT OR REPLACE INTO signatures
                       (id,cod,process_id,doc_type,doc_filename,signer_user_id,signer_name,
                        method,status,hash_sha256,file_id,signed_at,extra_json)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (sg.get('id'), sg.get('cod'), sg.get('process_id'), sg.get('doc_type'),
                     sg.get('doc_filename'), sg.get('signer_user_id'), sg.get('signer_name'),
                     sg.get('method'), sg.get('status'), sg.get('hash_sha256'),
                     sg.get('file_id'), sg.get('signed_at'), sg.get('extra_json'))
                )

        self._json(200, {'ok': True})

    def _restore_db_backup(self, raw_bytes):
        # raw_bytes é o conteúdo bruto do arquivo .db enviado via multipart ou binário
        if len(raw_bytes) < 16 or raw_bytes[:16] != b'SQLite format 3\x00':
            self._json(400, {'error': 'Arquivo não é um banco SQLite válido'}); return
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        try:
            tmp.write(raw_bytes); tmp.close()
            # Valida que o arquivo tem as tabelas esperadas
            with sqlite3.connect(tmp.name) as test_conn:
                tables = {r[0] for r in test_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            required = {'processes', 'fornecedores', 'sys_settings'}
            if not required.issubset(tables):
                self._json(400, {'error': 'Banco inválido: tabelas obrigatórias ausentes'}); return
            # Backup do atual antes de restaurar
            _do_db_backup()
            # Substitui o banco atual com o backup via API de backup SQLite (seguro)
            with sqlite3.connect(tmp.name) as src, get_db() as dst:
                src.backup(dst)
            self._json(200, {'ok': True})
        except Exception as e:
            _log.error('Erro ao restaurar banco: %s', e)
            self._json(500, {'error': str(e)})
        finally:
            try: os.remove(tmp.name)
            except: pass

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

    # ── Verificar documento ───────────────────────────────────────────────────

    def _serve_verificar(self, cod):
        cod_safe = html_mod.escape(cod)
        # Consulta real no servidor — antes disso era um hash fraco recalculado no
        # navegador com URL fixa para localhost, o que nem funcionava fora da máquina
        # do servidor. Agora consulta a tabela signatures diretamente.
        with get_db() as conn:
            row = conn.execute(
                '''SELECT sig.*, p.objeto AS proc_objeto, p.num_proc, p.num_dl, p.unidade
                   FROM signatures sig LEFT JOIN processes p ON p.id = sig.process_id
                   WHERE sig.cod = ?''', (cod,)
            ).fetchone()

        metodo_label = {'internal': 'Assinatura Simples (nível básico — controle interno)',
                         'govbr': 'gov.br (nível avançado)',
                         'icp-brasil': 'Certificado ICP-Brasil (nível qualificado)'}
        extra_note = ''
        if row:
            nums = ' · '.join(x for x in [f"PA {row['num_proc']}" if row['num_proc'] else '', f"DL {row['num_dl']}" if row['num_dl'] else ''] if x)
            status_html = f'''<h2>✓ Assinatura Encontrada</h2>
    <div class="field"><strong>Documento:</strong> {html_mod.escape(row['doc_type'] or '')}</div>
    <div class="field"><strong>Processo:</strong> {html_mod.escape(nums or '—')} — {html_mod.escape(row['proc_objeto'] or '—')}</div>
    <div class="field"><strong>Assinado por:</strong> {html_mod.escape(row['signer_name'] or '—')}</div>
    <div class="field"><strong>Método:</strong> {html_mod.escape(metodo_label.get(row['method'], row['method']))}</div>
    <div class="field"><strong>Data:</strong> {html_mod.escape(row['signed_at'] or '—')}</div>'''
            status_class = 'ok'
            if row['method'] == 'icp-brasil':
                extra_note = '<p style="font-size:12px;color:#6b7280;margin-top:10px">Para validar a cadeia de certificação, confira também o <a href="https://verificador.iti.gov.br/" target="_blank">verificador oficial do ITI</a>.</p>'
        else:
            status_html = '<h2>✗ Não encontrado</h2><p style="font-size:13px;margin-top:6px">O código não corresponde a nenhuma assinatura registrada nesta instalação.</p>'
            status_class = 'err'

        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Verificação de Autenticidade — SGCD</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:system-ui,sans-serif;background:#f3f4f6;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}}
  .card{{background:#fff;border-radius:12px;box-shadow:0 4px 24px rgba(0,0,0,.10);max-width:520px;width:100%;padding:32px 36px}}
  .logo{{font-size:13px;font-weight:700;letter-spacing:.5px;color:#6b7280;text-transform:uppercase;margin-bottom:20px}}
  h1{{font-size:18px;font-weight:700;margin-bottom:6px}}
  .cod{{font-family:monospace;font-size:15px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;padding:8px 14px;display:inline-block;margin-bottom:20px;letter-spacing:2px}}
  #status{{border-radius:8px;padding:16px 20px;margin-bottom:20px}}
  #status.ok{{background:#f0fdf4;border:1px solid #86efac}}
  #status.err{{background:#fef2f2;border:1px solid #fca5a5}}
  #status h2{{font-size:15px;font-weight:700;margin-bottom:4px}}
  #status.ok h2{{color:#166534}} #status.err h2{{color:#b91c1c}}
  .field{{margin-bottom:8px;font-size:13px}} .field strong{{color:#374151}}
  .footer{{font-size:11px;color:#9ca3af;margin-top:20px;text-align:center}}
</style>
</head>
<body>
<div class="card">
  <div class="logo">SGCD — Sistema de Gestão de Contratação Direta</div>
  <h1>Verificação de Autenticidade</h1>
  <p style="font-size:13px;color:#6b7280;margin-bottom:14px">Código informado:</p>
  <div class="cod">{cod_safe}</div>
  <div id="status" class="{status_class}">{status_html}</div>
  {extra_note}
  <div class="footer">SGCD · Lei Federal nº 14.133/2021 · Verificação local</div>
</div>
</body></html>"""
        payload = html.encode('utf-8')
        self.send_response(200)
        self._cors()
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # ── E-mail ────────────────────────────────────────────────────────────────

    def _send_email(self, data):
        _send_email_raw(data['smtp'], data['from'], data['to'], data['subject'], data['html'], data.get('text', ''))

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

    def handle_error(self, request, client_address):
        import traceback
        _log.error('Erro na requisição de %s:\n%s', client_address, traceback.format_exc())

    def log_message(self, fmt, *args): pass

# ── Utilitários ───────────────────────────────────────────────────────────────

def _now():
    return time.strftime('%Y-%m-%dT%H:%M:%S')

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

def _gerar_cod_assinatura():
    """Código curto de verificação (ex: A1B2-C3D4), único na tabela signatures."""
    with get_db() as conn:
        for _ in range(10):
            raw = secrets.token_hex(4).upper()
            cod = raw[:4] + '-' + raw[4:]
            if not conn.execute('SELECT 1 FROM signatures WHERE cod=?', (cod,)).fetchone():
                return cod
    raise RuntimeError('Não foi possível gerar código de verificação único')

def _float(v):
    if v is None: return None
    try: return float(str(v).replace(',', '.').replace('R$', '').strip())
    except: return None

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

def _assinar_pdf_icp(pdf_bytes, cert_bytes, senha):
    """Assina um PDF com certificado ICP-Brasil A1 (.pfx), nível qualificado.
    Import tardio de pyHanko: o servidor sobe normalmente mesmo sem a lib
    instalada — só o módulo ICP-Brasil fica indisponível, com erro claro.
    Retorna (pdf_assinado_bytes, subject_do_certificado)."""
    import tempfile, io
    from pyhanko.sign import signers
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

    with tempfile.NamedTemporaryFile(suffix='.pfx', delete=False) as tf:
        tf.write(cert_bytes)
        pfx_path = tf.name
    try:
        signer = signers.SimpleSigner.load_pkcs12(pfx_path, passphrase=senha.encode('utf-8'))
        if signer is None:
            raise ValueError('Senha do certificado incorreta ou arquivo .pfx inválido/corrompido')
        cert_subject = str(signer.signing_cert.subject.human_friendly)
        writer = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))
        out = io.BytesIO()
        signers.sign_pdf(writer, signers.PdfSignatureMetadata(field_name='Signature1'), signer=signer, output=out)
        return out.getvalue(), cert_subject
    finally:
        os.remove(pfx_path)

def _render_html_to_pdf(html_str):
    """Imprime um HTML em PDF via Chrome/Edge headless — mesmo navegador que o
    sistema já exige para o Modo Pessoal (_find_browser), sem depender de
    nenhuma lib nova. Usado pelo PDF Consolidado para os documentos que não
    têm um PDF já assinado salvo (rascunho ou Assinatura Simples)."""
    import tempfile, pathlib
    browser = _find_browser()
    if not browser:
        raise RuntimeError('Navegador (Chrome ou Edge) não encontrado para gerar o PDF consolidado.')

    tmp_dir   = tempfile.gettempdir()
    html_path = os.path.join(tmp_dir, f'sgcd_doc_{secrets.token_hex(8)}.html')
    pdf_path  = os.path.join(tmp_dir, f'sgcd_doc_{secrets.token_hex(8)}.pdf')
    try:
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_str)
        uri = pathlib.Path(html_path).as_uri()
        result = subprocess.run(
            [browser, '--headless', '--disable-gpu', '--no-pdf-header-footer',
             f'--print-to-pdf={pdf_path}', uri],
            capture_output=True, timeout=30
        )
        if not os.path.isfile(pdf_path):
            err = result.stderr.decode('utf-8', 'replace')[:300] if result.stderr else 'motivo desconhecido'
            raise RuntimeError(f'Falha ao converter documento em PDF: {err}')
        with open(pdf_path, 'rb') as f:
            return f.read()
    finally:
        for p in (html_path, pdf_path):
            try: os.remove(p)
            except OSError: pass


def _pdf_pages(pdf_handler):
    """Lista, em ordem, os objetos /Page de um PdfFileReader ou PdfFileWriter
    (ambos expõem .root — a árvore /Pages pode ter Kids aninhados)."""
    out = []
    def walk(node):
        if node.get('/Type') == '/Pages':
            for kid in node['/Kids']:
                walk(kid.get_object())
        elif node.get('/Type') == '/Page':
            out.append(node)
    walk(pdf_handler.root['/Pages'])
    return out


def _montar_pdf_consolidado(slots):
    """Monta o dossiê consolidado do processo: mescla em sequência os PDFs de
    cada slot (renderizado na hora ou já assinado/anexado) e numera todas as
    páginas do resultado. Import tardio de pyHanko — mesmo padrão de
    _assinar_pdf_icp: sem a lib instalada, só este endpoint fica indisponível.
    `slots`: lista de dicts {tipo:'html', html:str} ou {tipo:'file', file_id:str}.
    """
    import io
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.pdf_utils.writer import PdfFileWriter
    from pyhanko.stamp import TextStamp, TextStampStyle

    pdf_blobs = []
    for slot in slots:
        tipo = slot.get('tipo')
        if tipo == 'html':
            html_str = (slot.get('html') or '').strip()
            if html_str:
                pdf_blobs.append(_render_html_to_pdf(html_str))
        elif tipo == 'file':
            with get_db() as conn:
                row = conn.execute('SELECT nome_disco FROM files WHERE id=?', (slot.get('file_id'),)).fetchone()
            if row:
                fp = os.path.join(UPLOADS_DIR, row['nome_disco'])
                if os.path.isfile(fp):
                    with open(fp, 'rb') as f:
                        pdf_blobs.append(f.read())

    if not pdf_blobs:
        raise ValueError('Nenhum documento disponível para consolidar — preencha ao menos uma etapa do processo.')

    writer = PdfFileWriter()
    for blob in pdf_blobs:
        reader = PdfFileReader(io.BytesIO(blob))
        for page in _pdf_pages(reader):
            imported = writer.import_object(page)
            if '/Parent' in imported:
                del imported['/Parent']
            writer.insert_page(imported)

    paginas = _pdf_pages(writer)
    total = len(paginas)
    for i, pg in enumerate(paginas):
        mb = pg.get('/MediaBox')
        largura = float(mb[2]) - float(mb[0]) if mb else 612.0
        style = TextStampStyle(stamp_text='Página %(page)d de %(total)d', border_width=0)
        stamp = TextStamp(writer, style, text_params={'page': i + 1, 'total': total})
        stamp.apply(i, largura - 140, 20)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _send_email_raw(smtp, frm, to, subj, html, plain=''):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subj
    msg['From']    = f"{frm['name']} <{frm['email']}>"
    msg['To']      = to if isinstance(to, str) else ', '.join(to)
    if plain: msg.attach(MIMEText(plain, 'plain', 'utf-8'))
    msg.attach(MIMEText(html, 'html', 'utf-8'))

    port = int(smtp.get('port', 587))
    host = smtp['host']
    user = smtp['auth']['user']
    pw   = smtp['auth']['pass']

    ctx = ssl.create_default_context()
    if smtp.get('ignoreSSL'):
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE

    if smtp.get('secure'):
        with smtplib.SMTP_SSL(host, port, context=ctx) as s:
            s.login(user, pw); s.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as s:
            s.ehlo()
            if smtp.get('requireTLS', True): s.starttls(context=ctx)
            s.login(user, pw); s.send_message(msg)

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
    smtp_cfg = {
        'host': cfg['smtp_host'], 'port': cfg.get('smtp_port', 587),
        'secure': cfg.get('smtp_secure') == '1', 'requireTLS': cfg.get('smtp_require_tls') != '0',
        'ignoreSSL': cfg.get('smtp_ignore_ssl') == '1',
        'auth': {'user': cfg['smtp_user'], 'pass': cfg['smtp_pass']},
    }
    frm = {'name': cfg.get('smtp_from_name') or 'SGCD', 'email': cfg['smtp_user']}
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
    # Limpa sessões expiradas a cada 5s e verifica encerramento.
    # Com SESSION_TTL=15s e ping a cada 5s, um browser fechado sem logout
    # causa encerramento do servidor em no máximo ~20 segundos.
    while True:
        time.sleep(5)
        if _watchdog_paused:
            continue
        with get_db() as conn:
            conn.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
        _check_shutdown()
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
        signatures   = [dict(r) for r in conn.execute('SELECT * FROM signatures').fetchall()]
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
        'signatures': signatures,
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
    return {
        'path':    cfg.get('backup_path') or BACKUP_DIR,
        'enabled': cfg.get('auto_backup_enabled', '1') != '0',
        'keep':    max(1, int(cfg.get('auto_backup_keep') or BACKUP_KEEP)),
    }

def _do_db_backup(cfg=None):
    if cfg is None: cfg = _get_backup_cfg()
    bdir = cfg['path']
    keep = cfg['keep']
    os.makedirs(bdir, exist_ok=True)
    name = time.strftime('DB_SGCD_BACKUP_%Y-%m-%d_%H-%M-%S.db')
    dst  = os.path.join(bdir, name)
    try:
        with sqlite3.connect(DB_PATH) as src, sqlite3.connect(dst) as bk:
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

# ── Seleção de modo ───────────────────────────────────────────────────────────

def _selecionar_modo():
    global _modo_servidor
    print()
    print('  ╔══════════════════════════════════════════════════╗')
    print('  ║   SGCD — Sistema de Gestão de Contratação Direta ║')
    print('  ╚══════════════════════════════════════════════════╝')
    print()
    print('  Selecione o modo de operação:')
    print()
    print('  [1] Pessoal   — Uso individual no próprio computador')
    print('                  Abre o app automaticamente no navegador')
    print('                  Encerra quando o último usuário sair')
    print()
    print('  [2] Servidor  — Máquina central / acesso pela rede')
    print('                  Não abre navegador automaticamente')
    print('                  Fica rodando continuamente (Ctrl+C para parar)')
    print()
    print('  [3] Diagnóstico — Verifica rede, porta e firewall')
    print()
    if not sys.stdin.isatty():
        op = '2'
    else:
        while True:
            try:
                op = input('  Opção [1/2/3]: ').strip()
            except (EOFError, KeyboardInterrupt):
                op = '1'
            if op in ('1', '2', '3'):
                break
            print('  Digite 1, 2 ou 3.')
    if op == '3':
        import subprocess as _sp
        diag = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'diagnostico.py')
        _sp.run([sys.executable, diag])
        sys.exit(0)
    _modo_servidor = (op == '2')
    modo_label = 'SERVIDOR CONTÍNUO' if _modo_servidor else 'PESSOAL'
    print()
    print(f'  Modo: {modo_label}')
    print('  ─────────────────────────────────────────────────')

if __name__ == '__main__':
    _selecionar_modo()
    _check_db_integrity()
    _rotate_backups(_get_backup_cfg())  # limpa excedentes dos backups da sessão anterior
    threading.Thread(target=_watchdog, daemon=True).start()

    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(('', PORT), SGCDHandler) as httpd:
        print(f'  Servidor: http://localhost:{PORT}')

        if _modo_servidor:
            # Modo servidor: exibe IP da rede e fica rodando sem abrir browser
            import socket as _socket
            try:
                ip_local = _socket.gethostbyname(_socket.gethostname())
            except Exception:
                ip_local = 'desconhecido'
            print(f'  Rede:     http://{ip_local}:{PORT}/SGCD.html')
            print()
            print('  Aguardando conexões... (Ctrl+C para encerrar)')
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print('\n  Encerrando servidor...')
        else:
            # Modo pessoal: abre o app no navegador
            browser = _find_browser()
            if browser:
                threading.Thread(target=httpd.serve_forever, daemon=True).start()
                time.sleep(1)
                profile_dir = os.path.join(os.environ.get('TEMP', os.path.expanduser('~')), 'SGCD-Profile')
                proc = subprocess.Popen([
                    browser,
                    f'--app=http://localhost:{PORT}/SGCD.html',
                    '--start-maximized',
                    '--disable-background-mode',
                    f'--user-data-dir={profile_dir}',
                ])
                print('  App aberto. Feche a janela do SGCD para encerrar.')
                proc.wait()
                print('  Encerrando servidor...')
                while True: time.sleep(1)
            else:
                print(f'  Chrome/Edge não encontrado. Abra manualmente: http://localhost:{PORT}/SGCD.html')
                httpd.serve_forever()
