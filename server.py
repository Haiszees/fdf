import http.server
import socketserver
import os

PORT = int(os.environ.get("PORT", 8080))
DIR  = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def do_GET(self):
        if self.path == '/':
            self.path = '/landing.html'
        return super().do_GET()

    def log_message(self, *args):
        pass

print(f"Server on port {PORT}")
with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
    httpd.serve_forever()
