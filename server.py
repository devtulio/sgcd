import http.server, socketserver, os

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.path = '/SGCD.html'
        return super().do_GET()
    def log_message(self, *a): pass

os.chdir(os.path.dirname(os.path.abspath(__file__)))
with socketserver.TCPServer(('', 3000), Handler) as httpd:
    httpd.serve_forever()
