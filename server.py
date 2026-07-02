# SGCD v2.1.0 — Servidor local: SQLite, autenticação, REST API, proxy CNPJ, e-mail SMTP, backup automático
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

PORT          = 3000
_BASE         = os.path.dirname(os.path.abspath(__file__))
DB_PATH       = os.path.join(_BASE, 'sgcd.db')
UPLOADS_DIR   = os.path.join(_BASE, 'uploads')
BACKUP_DIR    = os.path.join(_BASE, 'backups')
LOG_PATH      = os.path.join(_BASE, 'sgcd_errors.log')
BACKUP_KEEP   = 7        # número de backups automáticos mantidos
SESSION_TTL   = 15   # 15s — renovado pelo ping a cada 5s; expira rápido se browser fechar
MAX_UPLOAD    = 50 * 1024 * 1024   # 50 MB — limite de tamanho por upload
ALLOWED_EXTS  = {'.pdf','.docx','.doc','.xlsx','.xls','.odt','.ods','.png','.jpg','.jpeg','.gif','.webp','.txt','.csv','.zip'}

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

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT NOT NULL UNIQUE COLLATE NOCASE,
                nome       TEXT NOT NULL,
                cargo      TEXT,
                matricula  TEXT,
                senha_hash TEXT NOT NULL,
                admin      INTEGER DEFAULT 0,
                ativo      INTEGER DEFAULT 1,
                criado_em  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token    TEXT PRIMARY KEY,
                user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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
                created_by INTEGER REFERENCES users(id)
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
                uploaded_by   INTEGER REFERENCES users(id),
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
            CREATE INDEX IF NOT EXISTS idx_proc_status   ON processes(status);
            CREATE INDEX IF NOT EXISTS idx_proc_unidade  ON processes(unidade);
            CREATE INDEX IF NOT EXISTS idx_proc_updated  ON processes(updated_at);
            CREATE INDEX IF NOT EXISTS idx_files_proc    ON files(process_id);
            CREATE INDEX IF NOT EXISTS idx_forn_cnpj     ON fornecedores(cnpj);
            CREATE INDEX IF NOT EXISTS idx_audit_ts      ON audit_global(ts);
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
        # Sessões são descartadas a cada início do servidor (logout automático ao fechar janela)
        conn.execute('DELETE FROM sessions')
        # Cria admin padrão se não houver usuários
        if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
            conn.execute(
                'INSERT INTO users (username,nome,cargo,senha_hash,admin) VALUES (?,?,?,?,1)',
                ('admin', 'Administrador', 'Agente de Contratação', _hash_password('admin123'))
            )
            conn.commit()
            print('Usuário padrão criado: admin / admin123 — troque a senha nas Configurações.')

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
                      u.nome, u.username, u.cargo, u.matricula, u.admin, u.ativo
               FROM sessions s JOIN users u ON u.id=s.user_id
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
        self._route_post(p, self._body(), s)

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
        elif p == '/api/audit':
            page = int(qp('page', 1)); per    = min(int(qp('per', 200)), 1000)
            with get_db() as conn:
                total = conn.execute('SELECT COUNT(*) FROM audit_global').fetchone()[0]
                rows  = conn.execute(
                    'SELECT * FROM audit_global ORDER BY ts DESC LIMIT ? OFFSET ?',
                    (per, (page-1)*per)
                ).fetchall()
            self._json(200, {'total': total, 'items': [dict(r) for r in rows]})

        # Configurações do sistema
        elif p == '/api/settings':
            with get_db() as conn:
                rows = conn.execute('SELECT key,value FROM sys_settings').fetchall()
            result = {r['key']: r['value'] for r in rows}
            print(f"  [SETTINGS] GET /api/settings de {s.get('nome') or s.get('user_id')} — chaves retornadas: {sorted(result.keys())}", flush=True)
            self._json(200, result)

        # Usuários (admin)
        elif p == '/api/users':
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
            with get_db() as conn:
                rows = conn.execute(
                    'SELECT id,username,nome,cargo,matricula,admin,ativo,criado_em FROM users'
                ).fetchall()
            self._json(200, [dict(r) for r in rows])

        # Backup
        elif p == '/api/backup':
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
            self._export_backup()

        elif p == '/api/backup/db':
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
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
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
            self._json(200, _get_backup_cfg())

        elif p == '/api/dialog/folder':
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
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
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
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
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
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

        elif p in ('/api/settings', '/api/settings/'):
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
            self._save_settings(data)

        elif p == '/api/users':
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
            self._create_user(data)

        elif p == '/api/backups/db/now':
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
            name = _do_db_backup()
            self._json(200, {'ok': bool(name), 'name': name})

        elif p == '/api/backup/restore':
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
            self._restore_backup(data)

        elif p == '/api/backups/db/restore':
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
            self._restore_db_backup(body)

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
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
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
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
            allowed = {'smtp_host', 'smtp_port', 'smtp_secure', 'smtp_require_tls',
                       'smtp_ignore_ssl', 'smtp_user', 'smtp_pass', 'smtp_from_name', 'smtp_to'}
            # _save_settings() já ignora valores vazios, então smtp_pass em branco preserva a senha salva
            self._save_settings({k: v for k, v in data.items() if k in allowed})
        elif re.fullmatch(r'/api/users/[^/]+', p):
            uid = int(p.split('/')[-1])
            if not s['admin']:
                if uid != s['user_id']:
                    self._json(403, {'error': 'Acesso negado'}); return
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
                if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
                self._purge_process(pid)
            else:
                with get_db() as conn:
                    conn.execute('UPDATE processes SET deleted_at=? WHERE id=?', (_now(), pid))
            self._json(200, {'ok': True})

        elif re.fullmatch(r'/api/fornecedores/[^/]+', p):
            fid = p.split('/')[-1]
            if purge:
                if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
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

        elif re.fullmatch(r'/api/users/[^/]+', p):
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
            uid = int(p.split('/')[-1])
            if uid == s['user_id']:
                self._json(400, {'error': 'Não é possível excluir o próprio usuário'}); return
            with get_db() as conn:
                conn.execute('DELETE FROM users WHERE id=?', (uid,))
            self._json(200, {'ok': True})

        elif p == '/api/processes/all':
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
            with get_db() as conn:
                conn.execute('DELETE FROM processes')
            self._json(200, {'ok': True})

        elif p == '/api/fornecedores/all':
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
            with get_db() as conn:
                conn.execute('DELETE FROM fornecedores')
            self._json(200, {'ok': True})

        elif p == '/api/files/all':
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
            import shutil
            with get_db() as conn:
                conn.execute('DELETE FROM files')
            if os.path.exists(UPLOADS_DIR):
                shutil.rmtree(UPLOADS_DIR)
            os.makedirs(UPLOADS_DIR, exist_ok=True)
            self._json(200, {'ok': True})

        elif p == '/api/audit/all':
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
            with get_db() as conn:
                conn.execute('DELETE FROM audit_global')
            self._json(200, {'ok': True})

        elif p == '/api/wipe':
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
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

        with get_db() as conn:
            row = conn.execute(
                'SELECT * FROM users WHERE username=? COLLATE NOCASE AND ativo=1', (username,)
            ).fetchone()

        if not row or not _verify_password(password, row['senha_hash']):
            self._json(401, {'error': 'Usuário ou senha incorretos'}); return

        global _had_session, _backup_pos_sess
        _had_session = True
        _backup_pos_sess = False  # nova sessão — permite backup ao próximo logout
        token = create_session(row['id'])
        self._json(200, {
            'token': token,
            'user': {
                'id': row['id'], 'username': row['username'], 'nome': row['nome'],
                'cargo': row['cargo'], 'matricula': row['matricula'], 'admin': bool(row['admin'])
            }
        })

    # ── Processos ─────────────────────────────────────────────────────────────

    def _list_processes(self, qs, s):
        def qp(k, d=None): v = qs.get(k); return v[0] if v else d
        q       = qp('q', '')
        status  = qp('status', '')
        unidade = qp('unidade', '')
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

        wc = ('WHERE ' + ' AND '.join(where)) if where else ''
        order = 'deleted_at DESC' if trash else 'updated_at DESC'
        with get_db() as conn:
            total = conn.execute(f'SELECT COUNT(*) FROM processes {wc}', params).fetchone()[0]
            rows  = conn.execute(
                f'SELECT data,deleted_at FROM processes {wc} ORDER BY {order} LIMIT ? OFFSET ?',
                params + [per, (page-1)*per]
            ).fetchall()
        items = []
        for r in rows:
            item = json.loads(r['data'])
            item['deletedAt'] = r['deleted_at']
            items.append(item)
        self._json(200, {'total': total, 'items': items})

    def _get_process(self, pid):
        with get_db() as conn:
            row = conn.execute('SELECT data FROM processes WHERE id=?', (pid,)).fetchone()
        if not row: self._json(404, {'error': 'Processo não encontrado'}); return
        self._json(200, json.loads(row['data']))

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
                    'INSERT INTO users (username,nome,cargo,matricula,senha_hash,admin) VALUES (?,?,?,?,?,?)',
                    (username, nome, data.get('cargo'), data.get('matricula'),
                     _hash_password(password), int(bool(data.get('admin'))))
                )
                uid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            self._json(200, {'id': uid, 'username': username, 'nome': nome})
        except sqlite3.IntegrityError:
            self._json(409, {'error': f'Usuário "{username}" já existe'})

    def _update_user(self, uid, data, s):
        with get_db() as conn:
            if not conn.execute('SELECT 1 FROM users WHERE id=?', (uid,)).fetchone():
                self._json(404, {'error': 'Usuário não encontrado'}); return
            fields, params = [], []
            for col in ('nome', 'cargo', 'matricula'):
                if col in data: fields.append(f'{col}=?'); params.append(data[col])
            if 'admin' in data: fields.append('admin=?'); params.append(int(bool(data['admin'])))
            if 'ativo' in data: fields.append('ativo=?'); params.append(int(bool(data['ativo'])))
            if data.get('password'):
                if len(data['password']) < 6:
                    self._json(400, {'error': 'Senha mínima: 6 caracteres'}); return
                if 'old_password' in data:
                    row = conn.execute('SELECT senha_hash FROM users WHERE id=?', (uid,)).fetchone()
                    if not row or not _verify_password(data['old_password'], row['senha_hash']):
                        self._json(403, {'error': 'Senha atual incorreta'}); return
                fields.append('senha_hash=?'); params.append(_hash_password(data['password']))
            if fields:
                conn.execute(f'UPDATE users SET {",".join(fields)} WHERE id=?', params + [uid])
        self._json(200, {'ok': True})

    # ── Backup ────────────────────────────────────────────────────────────────

    def _export_backup(self):
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

        backup  = {
            '_sgcd': True, 'version': 4,
            'exportedAt': _now(),
            'processes': processes,
            'fornecedores': fornecedores,
            'auditGlobal': audit,
            'settings': settings,
            'files': files_out
        }
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
        with get_db() as conn:
            conn.execute('DELETE FROM audit_global')
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
  <div id="status" style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;padding:16px 20px;margin-bottom:20px">
    <p style="font-size:13px;color:#6b7280">Consultando base de dados local…</p>
  </div>
  <div class="footer">SGCD v2.1 · Lei Federal nº 14.133/2021 · Verificação local</div>
</div>
<script>
(function(){{
  function authCode(p){{
    const str=[p.id,p.objeto,p.valor,p.createdAt].join('|');
    let h=0; for(let i=0;i<str.length;i++) h=Math.imul(31,h)+str.charCodeAt(i)|0;
    const hex=(h>>>0).toString(16).toUpperCase().padStart(8,'0');
    return hex.slice(0,4)+'-'+hex.slice(4);
  }}
  const token=localStorage.getItem('sgcd-token')||'';
  fetch('http://localhost:3000/api/processes?per=2000',{{headers:{{'Authorization':'Bearer '+token}}}})
    .then(r=>r.json()).then(d=>{{
      const cod={json.dumps(cod_safe)};
      const match=(d.items||[]).find(p=>authCode(p)===cod);
      const el=document.getElementById('status');
      if(match){{
        el.className='ok';
        const nums=[match.num_proc&&'PA '+match.num_proc,match.num_dl&&'DL '+match.num_dl].filter(Boolean).join(' · ');
        el.innerHTML='<h2>✓ Documento Autêntico</h2>'
          +'<div class="field"><strong>Processo:</strong> '+(nums||'—')+'</div>'
          +'<div class="field"><strong>Objeto:</strong> '+(match.objeto||'—')+'</div>'
          +'<div class="field"><strong>Unidade:</strong> '+(match.unidade||'—')+'</div>'
          +'<div class="field"><strong>Valor estimado:</strong> '+((v=>{{const n=parseFloat(String(v).replace(/[^\\d,.-]/g,'').replace(',','.'));return isNaN(n)?v||'—':n.toLocaleString('pt-BR',{{style:'currency',currency:'BRL'}})}})(match.valor))+'</div>';
      }}else{{
        el.className='err';
        el.innerHTML='<h2>✗ Documento não encontrado</h2><p style="font-size:13px;margin-top:6px">O código não corresponde a nenhum processo nesta instalação.</p>';
      }}
    }}).catch(()=>{{
      const el=document.getElementById('status');
      el.className='err';
      el.innerHTML='<h2>Erro ao consultar</h2><p style="font-size:13px;margin-top:6px">Verifique se o sistema SGCD está em execução.</p>';
    }});
}})();
</script>
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
        smtp  = data['smtp']
        frm   = data['from']
        to    = data['to']
        subj  = data['subject']
        html  = data['html']
        plain = data.get('text', '')

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

        try:
            if smtp.get('secure'):
                with smtplib.SMTP_SSL(host, port, context=ctx) as s:
                    s.login(user, pw); s.send_message(msg)
            else:
                with smtplib.SMTP(host, port) as s:
                    s.ehlo()
                    if smtp.get('requireTLS', True): s.starttls(context=ctx)
                    s.login(user, pw); s.send_message(msg)
        except ssl.SSLCertVerificationError as e:
            raise RuntimeError(
                f'Falha SSL no servidor SMTP ({host}). '
                f'Ative "Ignorar verificação SSL" nas configurações. Detalhe: {e}'
            ) from e

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

# ── Backup automático do banco ─────────────────────────────────────────────────

def _do_json_backup(cfg=None):
    if cfg is None: cfg = _get_backup_cfg()
    bdir = cfg['path']
    keep = cfg['keep']
    os.makedirs(bdir, exist_ok=True)
    name = time.strftime('SIS_SGCD_BACKUP_%Y-%m-%d_%H-%M-%S.json')
    dst  = os.path.join(bdir, name)
    try:
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
        backup = {
            '_sgcd': True, 'version': 4, 'exportedAt': _now(),
            'processes': processes, 'fornecedores': fornecedores,
            'auditGlobal': audit, 'settings': settings, 'files': files_out,
        }
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
