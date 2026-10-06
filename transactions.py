"""League career library, replacements and consensual one-for-one trades."""
from copy import deepcopy
import hashlib,json,uuid
import league,lan,rosters
from engine import player

def authorize(conn,s,who,team):
    if type(team) is not int or not 0<=team<len(s['teams']):raise ValueError('Unknown team')
    if who['role']=='commissioner':return
    if who.get('league_id')!=s['id'] or who.get('team')!=team:raise PermissionError('You can only manage your assigned team.')
    lan.table(conn)
    row=conn.execute('SELECT token_hash FROM managers WHERE league_id=? AND team=?',(s['id'],team)).fetchone()
    if not row or row[0]!=who.get('token_hash'):raise PermissionError('Invitation revoked.')

def locate(s,team,identity):
    for group in rosters.GROUPS:
        for slot,p in enumerate(s['teams'][team][group]):
            if p['player_id']==identity:return group,slot,p
    raise ValueError('Player is no longer on that team. Reload the roster.')

def invalidate(s,teams):
    for team in teams:
        key=str(team);s.setdefault('team_versions',{})[key]=s.get('team_versions',{}).get(key,0)+1
        s.setdefault('ready',{})[key]=False

def transact(request,who,action):
    with league.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        s=lan.load(conn,request['id']);rosters.prepare(s);league.ensure_player_ids(s)
        if request.get('version')!=s['version']:raise ValueError('League changed. Reload before submitting this transaction.')
        team=request.get('team');authorize(conn,s,who,team)
        if action=='import':
            p=player(request['player'])
            if p.get('is_ghost'):raise ValueError('Generated ghost players cannot be imported as tradeable careers.')
            fingerprint={'name':p['name'],'history':p.get('history')} if p.get('history') else {k:v for k,v in p.items() if k not in ('energy','player_id','career_id')}
            career=hashlib.sha256(json.dumps(fingerprint,sort_keys=True).encode()).hexdigest()[:24]
            p.pop('player_id',None);p['career_id']=career;p['energy']=100;p['is_ghost']=False
            source=request['player'].get('source_career')
            if source is not None:
                if not isinstance(source,dict):raise ValueError('Original career must be an object')
                if len(json.dumps(source,allow_nan=False).encode())>800000:raise ValueError('Original career is too large')
                p['source_career']=deepcopy(source)
            stored=s.setdefault('library',{}).setdefault(career,p)
            if source is not None:stored['source_career']=p['source_career']
        elif action=='assign':
            if s['phase']=='complete':raise ValueError('Start the next season before changing a completed roster.')
            group=request['group'];slot=request['slot']
            if group not in rosters.GROUPS or type(slot) is not int or not 0<=slot<len(s['teams'][team][group]):raise ValueError('Unknown roster slot')
            career=request['career_id'];p=deepcopy(s.get('library',{}).get(career))
            if not p:raise ValueError('Import this career into the league library first.')
            if any(q.get('career_id')==career for t in s['teams'] for g in rosters.GROUPS for q in t[g]):raise ValueError('This career is already on a team. Use a trade to acquire it.')
            released=s.setdefault('released',{})
            p=released.pop(career,p)
            p.pop('source_career',None) # Keep the raw source once, in the shared library.
            old=s['teams'][team][group][slot]
            if s['phase']!='regular' and old.get('career_id'):raise ValueError('During the postseason you can fill ghost slots; replacing an existing career waits until the next regular season.')
            if old.get('career_id'):released[old['career_id']]=old
            s.setdefault('departed_players',{})[old['player_id']]=deepcopy(old)
            p.setdefault('player_id',uuid.uuid4().hex);p['position']=old['position']
            s['teams'][team][group][slot]=p
            s.setdefault('transactions',[]).append(dict(type='replacement',team=team,out=old['name'],out_id=old['player_id'],incoming=p['name'],incoming_id=p['player_id'],season=s.get('season',1),day=s['calendar_day']))
            invalidate(s,[team])
        elif action=='propose':
            if s['phase']!='regular':raise ValueError('Trades are open during the regular season only.')
            other=request['other']
            if type(other) is not int or not 0<=other<len(s['teams']) or other==team:raise ValueError('Choose another team')
            give=locate(s,team,request['give']);take=locate(s,other,request['take'])
            if any(not p.get('career_id') or p.get('is_ghost') for p in (give[2],take[2])):raise ValueError('Ghost players cannot be traded. Only imported league careers are eligible.')
            if (give[0]=='pitchers')!=(take[0]=='pitchers'):raise ValueError('Trade a pitcher for a pitcher or a position player for a position player to keep both rosters at 26.')
            offers=s.setdefault('trades',[])
            if any(o['status']=='pending' and o['from']==team and o['to']==other and o['give']==request['give'] and o['take']==request['take'] for o in offers):raise ValueError('This offer is already pending.')
            offers.append(dict(id=uuid.uuid4().hex,season=s.get('season',1),day=s['calendar_day'],status='pending',**{'from':team,'to':other},give=request['give'],take=request['take'],give_name=give[2]['name'],take_name=take[2]['name']))
        elif action in ('accept','reject','cancel'):
            offer=next((o for o in s.get('trades',[]) if o['id']==request['offer']),None)
            if not offer or offer['status']!='pending':raise ValueError('This offer is no longer pending.')
            responsible=offer['from'] if action=='cancel' else offer['to']
            if team!=responsible:raise PermissionError('Only the receiving team can accept/reject; only the proposing team can cancel.')
            if action=='accept':
                if s['phase']!='regular' or offer['season']!=s.get('season',1):raise ValueError('This trade window is closed.')
                a=locate(s,offer['from'],offer['give']);b=locate(s,offer['to'],offer['take'])
                if any(not p.get('career_id') or p.get('is_ghost') for p in (a[2],b[2])):raise ValueError('Ghost players cannot be traded.')
                if (a[0]=='pitchers')!=(b[0]=='pitchers'):raise ValueError('Player roles changed. Cancel and propose a new trade.')
                for own,incoming,t in ((a,b[2],offer['from']),(b,a[2],offer['to'])):
                    s['teams'][t][own[0]][own[1]]={**incoming,'position':own[2]['position']}
                invalidate(s,[offer['from'],offer['to']])
            offer['status']={'accept':'accepted','reject':'rejected','cancel':'cancelled'}[action]
            offer['resolved_day']=s['calendar_day']
        else:raise ValueError('Unknown transaction')
        s['version']+=1;league.save(conn,s)
    return league.get(s['id'])
