"""Local-only, dependency-free HTTP service."""
import json
import socket
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from engine import simulate, demo_team
import league
from urllib.parse import urlparse, parse_qs

PUBLIC = Path(__file__).parent / 'public'
class LocalServer(ThreadingHTTPServer):
    allow_reuse_address = False
    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC), **kwargs)
    def reply(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        url=urlparse(self.path)
        params=parse_qs(url.query)
        try:
            if url.path == '/api/health': return self.reply(200, {'service':'diamond-lab','league_api':1})
            if url.path == '/api/leagues': return self.reply(200, league.list_leagues())
            if url.path == '/api/league': return self.reply(200, league.get(params['id'][0]))
            if url.path == '/api/league/game': return self.reply(200, league.game(params['id'][0],params['game'][0]))
            if url.path == '/api/league/demo': return self.reply(200, [demo_team(name,i+10) for i,name in enumerate(('Harbor','Forest','Summit','Comets','Tigers','Falcons','Wolves','Stars','Bears','Foxes','Sharks','Storm','Owls','Kings','Rockets','Dragons'))])
        except (ValueError,KeyError) as exc: return self.reply(400,{'error':str(exc)})
        if self.path == '/api/demo':
            return self.reply(200, {'away': demo_team('Harbor', 1), 'home': demo_team('Forest', 2)})
        if url.path.startswith('/api/'):
            return self.reply(404, {'error':'Unknown API endpoint. Restart the current server.py if the page and server versions differ.'})
        super().do_GET()
    def do_POST(self):
        routes={'/api/simulate':simulate,'/api/league/create':league.create,'/api/league/advance':league.advance}
        if self.path not in routes: return self.reply(404, {'error': 'Unknown endpoint'})
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 1_000_000: raise ValueError('Request must be 1 byte–1 MB')
            request = json.loads(self.rfile.read(length))
            self.reply(200, routes[self.path](request))
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            self.reply(400, {'error': str(exc)})

if __name__ == '__main__':
    try:
        server = LocalServer(('127.0.0.1', 8000), Handler)
    except OSError as exc:
        raise SystemExit(f'Cannot start Diamond Lab: port 8000 is unavailable. Stop the existing server before restarting. ({exc})')
    print('Diamond Lab: http://127.0.0.1:8000', flush=True)
    server.serve_forever()
