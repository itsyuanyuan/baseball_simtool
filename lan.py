"""Capability-based LAN access. Invitation keys are stored hashed in SQLite."""
import hashlib
import json
import secrets
from pathlib import Path
import league
from engine import validate_team

KEY_FILE = Path(__file__).parent / 'data' / 'commissioner.key'

def host_key():
    KEY_FILE.parent.mkdir(exist_ok=True)
    if not KEY_FILE.exists(): KEY_FILE.write_text(secrets.token_urlsafe(32),encoding='utf-8')
    return KEY_FILE.read_text(encoding='utf-8').strip()

def commissioner(token):
    return bool(token) and secrets.compare_digest(token,host_key())

def table(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS managers (league_id TEXT, team INTEGER, token_hash TEXT UNIQUE, PRIMARY KEY(league_id,team))')

def identity(token):
    if commissioner(token): return {'role':'commissioner'}
    if not token: raise PermissionError('Sign in with your commissioner key or team invitation.')
    with league.connect() as conn:
        table(conn)
        row=conn.execute('SELECT league_id,team FROM managers WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    if not row: raise PermissionError('Invalid or revoked invitation.')
    return {'role':'manager','league_id':row[0],'team':row[1],'token_hash':hashlib.sha256(token.encode()).hexdigest()}

def invite(request):
    key=secrets.token_urlsafe(32)
    with league.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        table(conn)
        s=load(conn,request['id'])
        for team_id,t in enumerate(s['teams']):
            for group in ('lineup','pitchers'):
                for slot,p in enumerate(t[group]):
                    if 'player_id' not in p:
                        p['player_id']=secrets.token_hex(12)
                        if group=='lineup':
                            for totals in s['stats'].values():
                                old=f'{team_id}:{slot}'
                                if old in totals: totals[f"{team_id}:{p['player_id']}"]=totals.pop(old)
        i=int(request['team'])
        if not 0<=i<len(s['teams']): raise ValueError('Unknown team')
        conn.execute('INSERT OR REPLACE INTO managers VALUES (?,?,?)',(s['id'],i,hashlib.sha256(key.encode()).hexdigest()))
        s.setdefault('managed',{})[str(i)]=True
        s.setdefault('ready',{})[str(i)]=False
        s['version']+=1
        league.save(conn,s)
    return {'key':key,'team':i,'league_id':s['id']}

def load(conn,id):
    row=conn.execute('SELECT state FROM leagues WHERE id=?',(id,)).fetchone()
    if not row: raise ValueError('League not found')
    return json.loads(row[0])

def submit(request,who):
    admin=who['role']=='commissioner'
    if who['role'] not in ('manager','commissioner'): raise PermissionError('Sign in to manage a team.')
    if not admin and (request.get('id')!=who['league_id'] or request.get('team')!=who['team']):
        raise PermissionError('You can only manage your assigned team.')
    with league.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        table(conn)
        if not admin:
            active=conn.execute('SELECT token_hash FROM managers WHERE league_id=? AND team=?',(who['league_id'],who['team'])).fetchone()
            if not active or active[0]!=who.get('token_hash'): raise PermissionError('This invitation was revoked.')
        s=load(conn,request['id']);league.ensure_player_ids(s);i=request['team'];key=str(i)
        if type(i) is not int or not 0<=i<len(s['teams']): raise ValueError('Unknown team')
        if s['phase']=='complete': raise ValueError('This league is complete.')
        revisions=s.setdefault('team_versions',{})
        if request.get('version')!=revisions.get(key,0): raise ValueError('Your team changed in another tab. Reload before saving.')
        if request.get('lineup_epoch')!=s.get('lineup_epoch',0): raise ValueError('League advanced. Reload to review the current day before saving.')
        if 'roster' in request:
            raw=request['roster'];new=validate_team(raw)
            old=s['teams'][i]
            started=any(g['score'] is not None for g in s['schedule'])
            if started:
                # Season player identities and abilities are immutable; order may change.
                new['name']=old['name']
                for group in ('lineup','pitchers'):
                    existing={p['player_id']:p for p in old[group]}
                    ids=[p.get('player_id') for p in raw[group]]
                    if len(ids)!=len(existing) or set(ids)!=set(existing): raise ValueError('After opening day you may reorder existing players only.')
                    new[group]=[existing[id] for id in ids]
            else:
                if any(t['name']==new['name'] for j,t in enumerate(s['teams']) if j!=i): raise ValueError('Team names must be unique.')
                for group in ('lineup','pitchers'):
                    for p in new[group]: p['player_id']=secrets.token_hex(12)
            s['teams'][i]=new
        s.setdefault('ready',{})[key]=request.get('ready') is True
        revisions[key]=revisions.get(key,0)+1
        s['version']+=1
        league.save(conn,s)
    return league.view(s)
