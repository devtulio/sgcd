# SGCD v2.0.0 — Servidor local: SQLite, autenticação, REST API, proxy CNPJ, e-mail SMTP
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
import urllib.error
import uuid
import re
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlparse, parse_qs

PORT          = 3000
DB_PATH       = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sgcd.db')
UPLOADS_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
HEARTBEAT_TIMEOUT = 30
SESSION_TTL   = 8 * 3600  # 8 horas

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(UPLOADS_DIR, exist_ok=True)

_last_heartbeat = time.time()

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

# ── HTTP Handler ──────────────────────────────────────────────────────────────

class SGCDHandler(http.server.SimpleHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        global _last_heartbeat
        parsed = urlparse(self.path)
        p  = parsed.path.rstrip('/')
        qs = parse_qs(parsed.query)

        if p in ('/health', '/heartbeat'):
            _last_heartbeat = time.time()
            self._json(200, {'ok': True})
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

        if p == '/shutdown':
            try: self.send_response(200); self.end_headers()
            except: pass
            os._exit(0)

        if p == '/api/auth/login':
            self._login(self._body())
            return

        if p == '/send-email':
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
        p = urlparse(self.path).path.rstrip('/')
        s = self._auth()
        if not s: return
        self._route_delete(p, s)

    # ── Roteamento ────────────────────────────────────────────────────────────

    def _route_get(self, p, qs, s):
        def qp(k, d=None): v = qs.get(k); return v[0] if v else d

        # Auth
        if p == '/api/auth/me':
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
            pid = qp('process_id')
            per = int(qp('per', 200))
            with get_db() as conn:
                if pid:
                    total = conn.execute('SELECT COUNT(*) FROM files WHERE process_id=?', (pid,)).fetchone()[0]
                    rows  = conn.execute('SELECT id,process_id,step_index,nome_original,mime,tamanho,criado_em FROM files WHERE process_id=? LIMIT ?', (pid, per)).fetchall()
                else:
                    total = conn.execute('SELECT COUNT(*) FROM files').fetchone()[0]
                    rows  = conn.execute('SELECT id,process_id,step_index,nome_original,mime,tamanho,criado_em FROM files LIMIT ?', (per,)).fetchall()
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
            page = int(qp('page', 1)); per = int(qp('per', 200))
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
            self._json(200, {r['key']: r['value'] for r in rows})

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

        else:
            self._json(404, {'error': 'Rota não encontrada'})

    def _route_post(self, p, body, s):
        data = self._parse_json(body)

        if p == '/api/auth/logout':
            delete_session(self._token())
            self._json(200, {'ok': True})

        elif p == '/api/processes':
            self._create_process(data, s)

        elif re.fullmatch(r'/api/processes/[^/]+/files', p):
            self._upload_file(p.split('/')[3], s)

        elif p == '/api/fornecedores':
            self._create_fornecedor(data)

        elif p == '/api/audit':
            self._add_audit(data)

        elif p in ('/api/settings', '/api/settings/'):
            self._save_settings(data)

        elif p == '/api/users':
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
            self._create_user(data)

        elif p == '/api/backup/restore':
            if not s['admin']: self._json(403, {'error': 'Acesso negado'}); return
            self._restore_backup(data)

        elif p == '/api/files':
            self._upload_file_direct(s)

        else:
            self._json(404, {'error': 'Rota não encontrada'})

    def _route_put(self, p, body, s):
        data = self._parse_json(body)

        if re.fullmatch(r'/api/processes/[^/]+', p):
            self._update_process(p.split('/')[-1], data, s)
        elif re.fullmatch(r'/api/fornecedores/[^/]+', p):
            self._update_fornecedor(p.split('/')[-1], data)
        elif p in ('/api/settings', '/api/settings/'):
            self._save_settings(data)
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

    def _route_delete(self, p, s):
        if re.fullmatch(r'/api/processes/[^/]+', p):
            with get_db() as conn:
                conn.execute('DELETE FROM processes WHERE id=?', (p.split('/')[-1],))
            self._json(200, {'ok': True})

        elif re.fullmatch(r'/api/fornecedores/[^/]+', p):
            with get_db() as conn:
                conn.execute('DELETE FROM fornecedores WHERE id=?', (p.split('/')[-1],))
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
        return auth[7:] if auth.startswith('Bearer ') else None

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
        per     = int(qp('per', 500))

        where, params = [], []
        if q:
            where.append('(objeto LIKE ? OR num_proc LIKE ? OR num_dl LIKE ?)')
            params += [f'%{q}%', f'%{q}%', f'%{q}%']
        if status:
            where.append('status=?'); params.append(status)
        if unidade:
            where.append('unidade=?'); params.append(unidade)

        wc = ('WHERE ' + ' AND '.join(where)) if where else ''
        with get_db() as conn:
            total = conn.execute(f'SELECT COUNT(*) FROM processes {wc}', params).fetchone()[0]
            rows  = conn.execute(
                f'SELECT data FROM processes {wc} ORDER BY updated_at DESC LIMIT ? OFFSET ?',
                params + [per, (page-1)*per]
            ).fetchall()
        self._json(200, {'total': total, 'items': [json.loads(r['data']) for r in rows]})

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

    # ── Fornecedores ──────────────────────────────────────────────────────────

    def _list_fornecedores(self, qs):
        def qp(k, d=None): v = qs.get(k); return v[0] if v else d
        q    = qp('q', '')
        page = int(qp('page', 1))
        per  = int(qp('per', 500))

        where, params = [], []
        if q:
            where.append('(razao_social LIKE ? OR cnpj LIKE ?)')
            params += [f'%{q}%', f'%{q}%']

        wc = ('WHERE ' + ' AND '.join(where)) if where else ''
        with get_db() as conn:
            total = conn.execute(f'SELECT COUNT(*) FROM fornecedores {wc}', params).fetchone()[0]
            rows  = conn.execute(
                f'SELECT data FROM fornecedores {wc} ORDER BY razao_social ASC LIMIT ? OFFSET ?',
                params + [per, (page-1)*per]
            ).fetchall()
        self._json(200, {'total': total, 'items': [json.loads(r['data']) for r in rows]})

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

    # ── Arquivos ──────────────────────────────────────────────────────────────

    def _upload_file(self, process_id, s):
        ct = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in ct:
            self._json(400, {'error': 'Esperado multipart/form-data'}); return

        boundary = ct.split('boundary=')[-1].strip().encode()
        length   = int(self.headers.get('Content-Length', 0))
        body     = self.rfile.read(length)

        filename, file_bytes, step_index = _parse_multipart(body, boundary)
        if not filename or file_bytes is None:
            self._json(400, {'error': 'Arquivo não encontrado no upload'}); return

        ext       = os.path.splitext(filename)[1].lower()
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
        self.send_header('Content-Disposition', f'inline; filename="{row["nome_original"]}"')
        self.end_headers()
        self.wfile.write(data)

    # ── Auditoria ─────────────────────────────────────────────────────────────

    def _add_audit(self, data):
        aid = data.get('id') or str(uuid.uuid4())
        with get_db() as conn:
            conn.execute(
                '''INSERT OR REPLACE INTO audit_global
                   (id,ts,user_id,user_nome,type,label,detail,process_id,process_obj)
                   VALUES (?,?,?,?,?,?,?,?,?)''',
                (aid, data.get('ts') or _now(),
                 data.get('userId') or data.get('user_id'),
                 data.get('userName') or data.get('user_nome'),
                 data.get('type'), data.get('label'), data.get('detail'),
                 data.get('processId') or data.get('process_id'),
                 json.dumps(data['processObj']) if data.get('processObj') else data.get('process_obj'))
            )
        self._json(200, {'ok': True})

    # ── Configurações ─────────────────────────────────────────────────────────

    def _save_settings(self, data):
        with get_db() as conn:
            for key, value in data.items():
                v = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                conn.execute('INSERT OR REPLACE INTO sys_settings (key,value) VALUES (?,?)', (key, v))
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
                         f'attachment; filename="SGCD_backup_{time.strftime("%Y-%m-%d")}.json"')
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
                    safe_name = fd.get('nome_disco') or (secrets.token_hex(16) + '.bin')
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
  <div class="cod">{cod}</div>
  <div id="status" style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;padding:16px 20px;margin-bottom:20px">
    <p style="font-size:13px;color:#6b7280">Consultando base de dados local…</p>
  </div>
  <div class="footer">SGCD v2.0 · Lei Federal nº 14.133/2021 · Verificação local</div>
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
      const cod='{cod}';
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

    def handle_error(self, request, client_address): pass
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

def _watchdog():
    while True:
        time.sleep(5)
        idle = time.time() - _last_heartbeat
        if idle > HEARTBEAT_TIMEOUT:
            print(f'\nSem heartbeat há {idle:.0f}s. Encerrando servidor...')
            os._exit(0)

# ── Inicialização ─────────────────────────────────────────────────────────────

init_db()
threading.Thread(target=_watchdog, daemon=True).start()

socketserver.ThreadingTCPServer.allow_reuse_address = True
with socketserver.ThreadingTCPServer(('', PORT), SGCDHandler) as httpd:
    print(f'SGCD v2.0 Server — http://localhost:{PORT}')

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
        print('App aberto. Feche a janela do SGCD para encerrar.')
        proc.wait()
        print('Encerrando servidor...')
        _last_heartbeat = time.time() - (HEARTBEAT_TIMEOUT - 6)
        while True: time.sleep(1)
    else:
        print('Chrome/Edge não encontrado. Abra: http://localhost:3000/SGCD.html')
        httpd.serve_forever()
