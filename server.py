"""Local-only, dependency-free HTTP service."""
import json
import socket
import argparse
import sqlite3
import traceback
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from engine import simulate, demo_team
import rosters
import league
import lan
import transactions
from urllib.parse import urlparse, parse_qs

PUBLIC = Path(__file__).parent / 'public'
class LocalServer(ThreadingHTTPServer):
    allow_reuse_address = False
    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

class Handler(SimpleHTTPRequestHandler):
    def token(self):
        return self.headers.get('Authorization','').removeprefix('Bearer ')
    def require_commissioner(self):
        if not lan.commissioner(self.token()): raise PermissionError('Only the commissioner can create leagues, invite managers or simulate games.')
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
            if url.path == '/api/health': return self.reply(200, {'service':'diamond-lab','league_api':1,'lan':getattr(self.server,'lan_mode',False)})
            if url.path == '/api/lan/me': return self.reply(200,lan.identity(self.token()))
            if url.path == '/api/lan/network':
                self.require_commissioner()
                addresses=sorted({r[4][0] for r in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET) if not r[4][0].startswith('127.')})
                return self.reply(200,{'addresses':addresses,'port':self.server.server_port})
            if url.path == '/api/leagues': return self.reply(200, league.list_leagues())
            if url.path == '/api/league': return self.reply(200, league.get(params['id'][0]))
            if url.path == '/api/league/archive': return self.reply(200, league.archive(params['id'][0],params['season'][0]))
            if url.path == '/api/league/game': return self.reply(200, league.game(params['id'][0],params['game'][0]))
            if url.path == '/api/league/demo': return self.reply(200, [rosters.full_team(demo_team(name,i+10),i) for i,name in enumerate(('Harbor','Forest','Summit','Comets','Tigers','Falcons','Wolves','Stars','Bears','Foxes','Sharks','Storm','Owls','Kings','Rockets','Dragons'))])
        except PermissionError as exc: return self.reply(403,{'error':str(exc)})
        except (ValueError,KeyError) as exc: return self.reply(400,{'error':str(exc)})
        if self.path == '/api/demo':
            return self.reply(200, {'away': demo_team('Harbor', 1), 'home': demo_team('Forest', 2)})
        if url.path.startswith('/api/'):
            return self.reply(404, {'error':'Unknown API endpoint. Restart the current server.py if the page and server versions differ.'})
        super().do_GET()
    def do_POST(self):
        routes={'/api/simulate':simulate,'/api/league/create':league.create,'/api/league/advance':league.advance,'/api/league/next-season':league.next_season,'/api/lan/invite':lan.invite,'/api/lan/submit':None,'/api/team/save':None}
        for action in ('import','assign','propose','accept','reject','cancel'):routes['/api/transactions/'+action]=None
        if self.path not in routes: return self.reply(404, {'error': 'Unknown endpoint'})
        try:
            origin=self.headers.get('Origin')
            if origin and urlparse(origin).netloc != self.headers.get('Host'):
                raise PermissionError('Cross-origin changes are not allowed.')
            if self.path=='/api/lan/invite' or (getattr(self.server,'lan_mode',False) and self.path in ('/api/league/create','/api/league/advance','/api/league/next-season')):
                self.require_commissioner()
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 1_000_000: raise ValueError('Request must be 1 byte–1 MB')
            request = json.loads(self.rfile.read(length))
            if not isinstance(request,dict): raise ValueError('Request must be an object')
            if self.path=='/api/league/advance' and not getattr(self.server,'lan_mode',False):
                request['override_ready']=True
            if self.path.startswith('/api/transactions/'):
                who=lan.identity(self.token()) if getattr(self.server,'lan_mode',False) else {'role':'commissioner'}
                return self.reply(200,transactions.transact(request,who,self.path.rsplit('/',1)[1]))
            if self.path=='/api/lan/submit':
                return self.reply(200,lan.submit(request,lan.identity(self.token())))
            if self.path=='/api/team/save':
                who=lan.identity(self.token()) if getattr(self.server,'lan_mode',False) else {'role':'commissioner'}
                return self.reply(200,lan.submit(request,who))
            self.reply(200, routes[self.path](request))
        except PermissionError as exc:
            self.reply(403,{'error':str(exc)})
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            self.reply(400, {'error': str(exc)})
        except sqlite3.Error:
            traceback.print_exc()
            self.reply(500,{'error':'Database operation failed; this batch was rolled back. Reload the league before retrying.'})
        except Exception:
            traceback.print_exc()
            self.reply(500,{'error':'The server could not complete this operation. Reload the saved league and check the server log.'})

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--lan',action='store_true',help='Allow local-network access; commissioner key required for league administration')
    parser.add_argument('--port',type=int,default=8000)
    args=parser.parse_args()
    try:
        server = LocalServer(('0.0.0.0' if args.lan else '127.0.0.1', args.port), Handler)
    except OSError as exc:
        raise SystemExit(f'Cannot start Diamond Lab: port 8000 is unavailable. Stop the existing server before restarting. ({exc})')
    server.lan_mode=args.lan
    print(f'Diamond Lab: http://127.0.0.1:{args.port}', flush=True)
    if args.lan:
        lan.host_key()
        print(f'LAN lobby: http://<this-PC-LAN-IP>:{args.port}/lan.html\nCommissioner login key is stored in {lan.KEY_FILE}. Keep it private.',flush=True)
    server.serve_forever()
