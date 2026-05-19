import http.server
import socketserver
import os
import time
import json
import urllib.parse
from collections import defaultdict

PORT       = int(os.environ.get("PORT", 8080))
DIR        = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.environ.get("DATABASE_URL", "")

RATE_LIMIT  = 60
RATE_WINDOW = 60
_rate_data  = defaultdict(list)
_stats_cache = {"data": None, "ts": 0}
STATS_TTL   = 300  # 5 мин


def get_stats() -> dict:
    """Счётчики из PostgreSQL. Кешируем на 5 минут."""
    now = time.time()
    if _stats_cache["data"] and now - _stats_cache["ts"] < STATS_TTL:
        return _stats_cache["data"]

    if not DATABASE_URL:
        return {"chats": 0, "users": 0}

    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=3)
        cur  = conn.cursor()

        # Проверяем какие таблицы есть
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        tables = [r[0] for r in cur.fetchall()]
        print(f"Tables: {tables}")

        chats = 0
        if 'chats' in tables:
            cur.execute("SELECT COUNT(*) FROM chats")
            chats = cur.fetchone()[0]
            print(f"Chats count: {chats}")

        users = 0
        if 'message_activity' in tables:
            cur.execute("SELECT COUNT(DISTINCT user_id) FROM message_activity")
            users = cur.fetchone()[0]
            print(f"Users count: {users}")

        conn.close()
        data = {"chats": chats, "users": users}
        _stats_cache.update({"data": data, "ts": now})
        return data
    except ImportError:
        print("ERROR: psycopg2 not installed. Add psycopg2-binary to requirements.txt")
        return {"chats": 0, "users": 0}
    except Exception as e:
        print(f"DB error: {type(e).__name__}: {e}")
        return {"chats": 0, "users": 0}


class Handler(http.server.SimpleHTTPRequestHandler):
    server_version = ""
    sys_version    = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def do_GET(self):
        # Rate limiting
        ip  = self.client_address[0]
        now = time.time()
        _rate_data[ip] = [t for t in _rate_data[ip] if now - t < RATE_WINDOW]
        if len(_rate_data[ip]) >= RATE_LIMIT:
            self.send_response(429)
            self.send_header("Retry-After", "60")
            self.end_headers()
            self.wfile.write(b"Too Many Requests")
            return
        _rate_data[ip].append(now)

        # API эндпоинт
        if self.path == "/api/stats":
            stats = get_stats()
            body  = json.dumps(stats).encode()
            self.send_response(200)
            self.send_header("Content-Type",  "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/":
            self.path = "/landing.html"
        return super().do_GET()

    def end_headers(self):
        self.send_header("X-Content-Type-Options",  "nosniff")
        self.send_header("X-Frame-Options",          "DENY")
        self.send_header("X-XSS-Protection",         "1; mode=block")
        self.send_header("Referrer-Policy",          "no-referrer")
        self.send_header("Content-Security-Policy",
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; "
            "script-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self';"   # разрешаем fetch к своему /api/stats
        )
        self.send_header("Permissions-Policy",
            "geolocation=(), camera=(), microphone=()"
        )
        super().end_headers()

    def log_message(self, *args):
        pass


print(f"Glock Helper Brandbook · port {PORT}")
print(f"DATABASE_URL: {'set (' + DATABASE_URL[:20] + '...)' if DATABASE_URL else 'NOT SET — stats will show 0'}")
with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
    httpd.allow_reuse_address = True
    httpd.serve_forever()
