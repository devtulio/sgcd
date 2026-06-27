# SGCD v1.19.0 — Servidor local: proxy CNPJ, e-mail SMTP, verificação de documentos
import http.server
import socketserver
import os
import json
import smtplib
import ssl
import threading
import time
import subprocess
import sys
import urllib.request
import urllib.error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

PORT = 3000
# Heartbeat: fallback para crash do navegador (proc.wait() é o mecanismo principal).
# Timeout de 30s para tolerar recarregamentos de página (o SGCD.html é grande e pode
# levar alguns segundos para inicializar — o heartbeat só começa após o JS estar pronto).
HEARTBEAT_TIMEOUT = 30
os.chdir(os.path.dirname(os.path.abspath(__file__)))

_last_heartbeat = time.time()
_server_ref = None

def _find_browser():
    candidates = [
        os.path.expandvars(r'%ProgramFiles%\Google\Chrome\Application\chrome.exe'),
        os.path.expandvars(r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe'),
        os.path.expandvars(r'%LocalAppData%\Google\Chrome\Application\chrome.exe'),
        os.path.expandvars(r'%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe'),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None

def _watchdog():
    while True:
        time.sleep(5)
        idle = time.time() - _last_heartbeat
        if idle > HEARTBEAT_TIMEOUT:
            print(f"\nSem heartbeat ha {idle:.0f}s. Encerrando servidor...")
            os._exit(0)

class SGCDHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        global _last_heartbeat
        if self.path in ('/health', '/heartbeat'):
            _last_heartbeat = time.time()
            self._json({"ok": True})
        elif self.path.startswith('/cnpj/'):
            digits = self.path[6:].strip('/')
            self._proxy_cnpj(digits)
        elif self.path.startswith('/verificar/'):
            cod = self.path[11:].strip('/').upper()
            self._serve_verificar(cod)
        else:
            super().do_GET()

    def _serve_verificar(self, cod):
        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Verificação de Autenticidade — SGCD</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:system-ui,sans-serif;background:#f3f4f6;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}}
  .card{{background:#fff;border-radius:12px;box-shadow:0 4px 24px rgba(0,0,0,.10);max-width:520px;width:100%;padding:32px 36px}}
  .logo{{font-size:13px;font-weight:700;letter-spacing:.5px;color:#6b7280;text-transform:uppercase;margin-bottom:20px}}
  h1{{font-size:18px;font-weight:700;margin-bottom:6px}}
  .cod{{font-family:monospace;font-size:15px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;padding:8px 14px;display:inline-block;margin-bottom:20px;letter-spacing:2px}}
  #status{{border-radius:8px;padding:16px 20px;margin-bottom:20px;display:none}}
  #status.ok{{background:#f0fdf4;border:1px solid #86efac}}
  #status.err{{background:#fef2f2;border:1px solid #fca5a5}}
  #status h2{{font-size:15px;font-weight:700;margin-bottom:4px}}
  #status.ok h2{{color:#166534}} #status.err h2{{color:#b91c1c}}
  .field{{margin-bottom:8px;font-size:13px}} .field strong{{color:#374151}}
  .spinner{{text-align:center;color:#9ca3af;padding:20px 0;font-size:13px}}
  .footer{{font-size:11px;color:#9ca3af;margin-top:20px;text-align:center}}
</style>
</head>
<body>
<div class="card">
  <div class="logo">SGCD — Sistema de Gestão de Contratação Direta</div>
  <h1>Verificação de Autenticidade</h1>
  <p style="font-size:13px;color:#6b7280;margin-bottom:14px">Código informado:</p>
  <div class="cod">{cod}</div>
  <div id="status"><h2 id="status-title"></h2><div id="status-body"></div></div>
  <div class="spinner" id="spinner">Consultando base de dados local…</div>
  <div class="footer">SGCD · Lei Federal nº 14.133/2021 · Verificação local</div>
</div>
<script>
(function(){{
  const cod = '{cod}';
  function authCode(p) {{
    const str = [p.id, p.objeto, p.valor, p.createdAt].join('|');
    let h = 0;
    for (let i = 0; i < str.length; i++) h = Math.imul(31, h) + str.charCodeAt(i) | 0;
    const hex = (h >>> 0).toString(16).toUpperCase().padStart(8, '0');
    return hex.slice(0,4) + '-' + hex.slice(4);
  }}
  function fmtDate(ts) {{
    if (!ts) return '—';
    return new Date(ts).toLocaleDateString('pt-BR');
  }}
  function fmtMoney(v) {{
    const n = parseFloat(String(v).replace(/[^\d,.-]/g,'').replace(',','.'));
    if (isNaN(n)) return v || '—';
    return n.toLocaleString('pt-BR',{{style:'currency',currency:'BRL'}});
  }}

  const req = indexedDB.open('dispensaDB', 3);
  req.onerror = () => show(false, 'Não foi possível acessar o banco de dados.', null);
  req.onsuccess = function(e) {{
    const db = e.target.result;
    const tx = db.transaction('processes','readonly');
    const store = tx.objectStore('processes');
    const all = store.getAll();
    all.onsuccess = function() {{
      const match = all.result.find(p => authCode(p) === cod);
      document.getElementById('spinner').style.display = 'none';
      if (match) {{
        show(true, '✓ Documento Autêntico', match);
      }} else {{
        show(false, '✗ Documento não encontrado', null);
      }}
    }};
    all.onerror = () => show(false, 'Erro ao ler os processos.', null);
  }};

  function show(ok, title, p) {{
    const el = document.getElementById('status');
    el.className = ok ? 'ok' : 'err';
    el.style.display = '';
    document.getElementById('status-title').textContent = title;
    if (p) {{
      const nums = [p.num_proc && 'PA ' + p.num_proc, p.num_dl && 'DL ' + p.num_dl].filter(Boolean).join(' · ');
      document.getElementById('status-body').innerHTML = `
        <div class="field"><strong>Processo:</strong> ${{nums || '—'}}</div>
        <div class="field"><strong>Objeto:</strong> ${{p.objeto || '—'}}</div>
        <div class="field"><strong>Unidade:</strong> ${{p.unidade || '—'}}</div>
        <div class="field"><strong>Valor estimado:</strong> ${{fmtMoney(p.valor)}}</div>
        <div class="field"><strong>Criado em:</strong> ${{fmtDate(p.createdAt)}}</div>
        <div class="field"><strong>Prazo:</strong> ${{p.prazo || '—'}}</div>
      `;
    }} else if (!ok) {{
      document.getElementById('status-body').innerHTML =
        '<p style="font-size:13px;margin-top:6px">O código informado não corresponde a nenhum processo nesta base de dados. O documento pode ter sido adulterado ou gerado em outra instalação do SGCD.</p>';
    }}
  }}
}})();
</script>
</body></html>"""
        payload = html.encode('utf-8')
        self.send_response(200)
        self._cors_headers()
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _proxy_cnpj(self, digits):
        if not digits.isdigit() or len(digits) != 14:
            self._json({"status": "ERROR", "message": "CNPJ inválido"}, status=400)
            return
        url = f"https://receitaws.com.br/v1/cnpj/{digits}"
        req = urllib.request.Request(url, headers={"User-Agent": "SGCD/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
                self.send_response(resp.status)
                self._cors_headers()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            body = e.read()
            self.send_response(e.code)
            self._cors_headers()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self._json({"status": "ERROR", "message": str(e)}, status=502)

    def do_POST(self):
        if self.path == '/shutdown':
            print("\nRecebido sinal de encerramento. Encerrando servidor...")
            try: self.send_response(200); self.end_headers()
            except: pass
            os._exit(0)
        if self.path == '/send-email':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                self._send_email(data)
                self._json({"ok": True})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, status=500)
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def _cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, obj, status=200):
        payload = json.dumps(obj).encode()
        self.send_response(status)
        self._cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

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
        if plain:
            msg.attach(MIMEText(plain, 'plain', 'utf-8'))
        msg.attach(MIMEText(html, 'html', 'utf-8'))

        port = int(smtp.get('port', 587))
        host = smtp['host']
        user = smtp['auth']['user']
        pw   = smtp['auth']['pass']

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        if smtp.get('secure'):
            with smtplib.SMTP_SSL(host, port, context=ctx) as s:
                s.login(user, pw)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port) as s:
                s.ehlo()
                if smtp.get('requireTLS', True):
                    s.starttls(context=ctx)
                s.login(user, pw)
                s.send_message(msg)

    def handle_error(self, request, client_address):
        pass  # suprime erros de conexão abortada

    def log_message(self, fmt, *args):
        pass  # suprime logs de requisição

threading.Thread(target=_watchdog, daemon=True).start()

with socketserver.TCPServer(("", PORT), SGCDHandler) as httpd:
    _server_ref = httpd
    print(f"SGCD Server em execucao — http://localhost:{PORT}")

    browser = _find_browser()
    if browser:
        # Inicia o servidor em background e monitora o processo do navegador
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()

        time.sleep(1)  # aguarda servidor ficar pronto

        profile_dir = os.path.join(os.environ.get('TEMP', os.path.expanduser('~')), 'SGCD-Profile')
        flags = [
            browser,
            f'--app=http://localhost:{PORT}/SGCD.html',
            '--start-maximized',
            '--disable-background-mode',
            f'--user-data-dir={profile_dir}',
        ]
        proc = subprocess.Popen(flags)
        print(f"App aberto. Feche a janela do SGCD para encerrar.")

        proc.wait()  # bloqueia ate o processo do navegador encerrar

        # Após fechar o app, dá 6s para o caso de F5/reload (heartbeat volta).
        # Se não voltar, o watchdog encerra logo em seguida.
        print("Processo do app encerrado. Encerrando servidor em instantes...")
        _last_heartbeat = time.time() - (HEARTBEAT_TIMEOUT - 6)
        while True:
            time.sleep(1)
    else:
        # Fallback: sem navegador compativel, serve normalmente
        print("Navegador Chrome/Edge nao encontrado.")
        print("Abra manualmente: http://localhost:3000/SGCD.html")
        print("Feche esta janela para encerrar o servidor.")
        httpd.serve_forever()
