import http.server
import socketserver
import os

PORT = int(os.environ.get("PORT", 8080))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(__file__), **kwargs)

    def log_message(self, format, *args):
        pass  # тишина в логах

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Brandbook running on port {PORT}")
    httpd.serve_forever()
