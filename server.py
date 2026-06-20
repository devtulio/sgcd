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
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

PORT = 3000
# Heartbeat: fallback para crash do navegador (proc.wait() é o mecanismo principal)
HEARTBEAT_TIMEOUT = 60
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
        else:
            super().do_GET()

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

        proc.wait()  # bloqueia ate o navegador fechar

        print("\nApp fechado. Encerrando servidor...")
        os._exit(0)
    else:
        # Fallback: sem navegador compativel, serve normalmente
        print("Navegador Chrome/Edge nao encontrado.")
        print("Abra manualmente: http://localhost:3000/SGCD.html")
        print("Feche esta janela para encerrar o servidor.")
        httpd.serve_forever()
