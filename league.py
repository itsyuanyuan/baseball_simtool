"""Local SQLite leagues: immutable rosters, balanced schedules and seeded playoffs."""
from copy import deepcopy
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import uuid
from engine import simulate, validate_team, MODEL_VERSION

DB = Path(__file__).parent / 'data' / 'leagues.sqlite3'

@contextmanager
def connect():
    DB.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB, timeout=30)
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS leagues (id TEXT PRIMARY KEY, state TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS games (league_id TEXT, game_id TEXT, result TEXT NOT NULL, PRIMARY KEY(league_id,game_id))')
        with conn:
            yield conn
    finally:
        conn.close()

def schedule(n, repeats):
    ring = list(range(n))
    rounds = []
    for turn in range(n-1):
        pairs = []
        for i in range(n//2):
            a, b = ring[i], ring[-1-i]
            pairs.append((a,b) if (turn+i)%2 else (b,a))
        rounds.append(pairs)
        ring = [ring[0], ring[-1], *ring[1:-1]]
    games = []
    for cycle in range(repeats):
        for day, pairs in enumerate(rounds):
            for a,b in pairs:
                if cycle%2: a,b=b,a
                games.append(dict(id=f'r{len(games)+1}', day=cycle*(n-1)+day+1, away=a, home=b, phase='regular', score=None))
    return games

def standings(state):
    rows = [dict(team=i, name=t['name'], W=0,L=0,RF=0,RA=0) for i,t in enumerate(state['teams'])]
    for g in state['schedule']:
        if g['score'] is None: continue
        a,h = g['away'],g['home']
        ar,hr = g['score']
        rows[a]['RF']+=ar; rows[a]['RA']+=hr
        rows[h]['RF']+=hr; rows[h]['RA']+=ar
        rows[a if ar>hr else h]['W']+=1
        rows[h if ar>hr else a]['L']+=1
    for r in rows:
        r['GP']=r['W']+r['L']; r['PCT']=r['W']/r['GP'] if r['GP'] else 0
        r['DIFF']=r['RF']-r['RA']
    return sorted(rows,key=lambda r:(-r['PCT'],-r['DIFF'],-r['RF'],r['team']))

def view(state):
    return {**state,'standings':standings(state)}

def save(conn,state):
    conn.execute('INSERT OR REPLACE INTO leagues VALUES (?,?)',(state['id'],json.dumps(state)))

def create(request):
    teams = [validate_team(t) for t in request['teams']]
    for t in teams:
        for group in ('lineup','pitchers'):
            for p in t[group]: p['player_id']=uuid.uuid4().hex
    n = len(teams)
    repeats = int(request.get('games_per_opponent', 4))
    playoff = int(request.get('playoff_teams',4))
    best = int(request.get('best_of',5))
    if n not in range(2,17,2): raise ValueError('Choose an even number of teams from 2 to 16')
    if repeats not in range(2,21,2): raise ValueError('Games per opponent must be even, from 2 to 20')
    if playoff not in (2,4,8,16) or playoff>n: raise ValueError('Playoff field must be 2, 4, 8 or 16 and no larger than the league')
    if best not in (1,3,5,7): raise ValueError('Series must be best of 1, 3, 5 or 7')
    names = [t['name'].strip() for t in teams]
    if any(not name for name in names) or len(set(names))!=n: raise ValueError('Team names must be nonempty and unique')
    state = dict(id=uuid.uuid4().hex, name=str(request.get('name','My league'))[:80], seed=str(request.get('seed','season-1'))[:100],
                 version=0, model_version=MODEL_VERSION, teams=teams, phase='regular', games_per_opponent=repeats,
                 playoff_teams=playoff,best_of=best, schedule=schedule(n,repeats), rounds=[], champion=None,
                 stats={'regular':{},'playoffs':{}})
    with connect() as conn: save(conn,state)
    return view(state)

def get(league_id):
    with connect() as conn:
        row=conn.execute('SELECT state FROM leagues WHERE id=?',(league_id,)).fetchone()
    if not row: raise ValueError('League not found')
    return view(json.loads(row[0]))

def list_leagues():
    with connect() as conn: rows=conn.execute('SELECT state FROM leagues ORDER BY rowid DESC').fetchall()
    return [dict(id=s['id'],name=s['name'],phase=s['phase'],teams=len(s['teams'])) for s in (json.loads(r[0]) for r in rows)]

def new_round(state, seeds):
    seeds=sorted(seeds)
    number=len(state['rounds'])+1
    series=[dict(id=f'p{number}s{i+1}',high=seeds[i],low=seeds[-i-1],wins=[0,0],winner=None,games=[]) for i in range(len(seeds)//2)]
    state['rounds'].append(dict(number=number,series=series))

def roster(state, team_id, played):
    t=deepcopy(state['teams'][team_id])
    # First up to three pitchers form a rotation; remaining pitchers relieve.
    rotation=min(3,max(1,len(t['pitchers'])-1))
    starter=played%rotation
    order=[starter]+list(range(rotation,len(t['pitchers'])))
    t['pitchers']=[t['pitchers'][i] for i in order]
    return t

def play(conn,state,g):
    played={i:sum(1 for old in state['schedule'] if old['score'] is not None and i in (old['away'],old['home'])) for i in (g['away'],g['home'])}
    for round_ in state['rounds']:
        for series in round_['series']:
            for old in series['games']:
                for i in played:
                    if old['score'] is not None and i in (old['away'],old['home']): played[i]+=1
    result=simulate(dict(away=roster(state,g['away'],played[g['away']]),home=roster(state,g['home'],played[g['home']]),seed=f"{state['seed']}:{g['id']}"),max_innings=100)
    if result['tie']: raise ValueError('Game reached the 100-inning safety limit; no progress was saved')
    g['score']=result['score']
    conn.execute('INSERT INTO games VALUES (?,?,?)',(state['id'],g['id'],json.dumps(result)))
    for side, team_id in enumerate((g['away'],g['home'])):
        for slot,p in enumerate(result['batting'][side]):
            key=f"{team_id}:{state['teams'][team_id]['lineup'][slot].get('player_id',slot)}"
            totals=state['stats'][g['phase']].setdefault(key,dict(team=team_id,name=p['name'],G=0,AB=0,H=0,HR=0,BB=0,HBP=0,SF=0,SO=0,RBI=0))
            totals['G']+=1
            for stat in ('AB','H','HR','BB','HBP','SF','SO','RBI'): totals[stat]+=p[stat]

def advance(request):
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT state FROM leagues WHERE id=?',(request['id'],)).fetchone()
        if not row: raise ValueError('League not found')
        state=json.loads(row[0])
        if request.get('version') != state['version']: raise ValueError('League changed in another tab. Reload it before continuing.')
        if state['model_version']!=MODEL_VERSION: raise ValueError('This league uses a different engine version; create a new league to use the current engine.')
        action=request.get('action','next')
        if action not in ('next','day','batch','playoffs'): raise ValueError('Unknown league action')
        def check_ready(team_ids):
            missing=[state['teams'][i]['name'] for i in team_ids if state.get('managed',{}).get(str(i)) and not state.get('ready',{}).get(str(i))]
            if missing and request.get('override_ready') is not True:
                raise ValueError('Waiting for ready teams: '+', '.join(missing))
        def played(g):
            play(conn,state,g)
            for i in (g['away'],g['home']): state.setdefault('ready',{})[str(i)]=False
        if action=='playoffs':
            if state['phase']!='ready': raise ValueError('Finish the regular season before starting playoffs')
            state['seeds']=[r['team'] for r in standings(state)[:state['playoff_teams']]]
            state['phase']='playoffs'
            new_round(state,list(range(state['playoff_teams'])))
        elif state['phase']=='regular':
            pending=[g for g in state['schedule'] if g['score'] is None]
            selected=pending[:1] if action=='next' else ([g for g in pending if g['day']==pending[0]['day']] if action=='day' else pending[:20])
            if state.get('managed') and action=='batch' and request.get('override_ready') is not True:
                selected=[g for g in pending if g['day']==pending[0]['day']]
            check_ready({i for g in selected for i in (g['away'],g['home'])})
            for g in selected: played(g)
            if all(g['score'] is not None for g in state['schedule']): state['phase']='ready'
        elif state['phase']=='playoffs':
            series=[s for s in state['rounds'][-1]['series'] if s['winner'] is None]
            check_ready({state['seeds'][seed] for s in (series[:1] if action=='next' else series) for seed in (s['high'],s['low'])})
            for s in (series[:1] if action=='next' else series):
                game_number=len(s['games'])
                # Higher seed hosts games 1,2,5,7 (best-of-seven), or odd games otherwise.
                high_home=game_number in (0,1,4,6) if state['best_of']==7 else game_number%2==0
                high,low=state['seeds'][s['high']],state['seeds'][s['low']]
                g=dict(id=f"{s['id']}g{game_number+1}",day=len(state['rounds']),away=low if high_home else high,home=high if high_home else low,phase='playoffs',score=None)
                played(g)
                s['games'].append(g)
                winner=g['away'] if g['score'][0]>g['score'][1] else g['home']
                index=0 if winner==high else 1
                s['wins'][index]+=1
                if s['wins'][index]>state['best_of']//2: s['winner']=s['high'] if index==0 else s['low']
            current=state['rounds'][-1]['series']
            if all(s['winner'] is not None for s in current):
                winners=[s['winner'] for s in current]
                if len(winners)==1:
                    state['champion']=state['seeds'][winners[0]];state['phase']='complete'
                else: new_round(state,winners)
        else: raise ValueError('No games to advance in this phase')
        state['lineup_epoch']=state.get('lineup_epoch',0)+1
        state['version']+=1
        save(conn,state)
    return view(state)

def game(league_id,game_id):
    with connect() as conn: row=conn.execute('SELECT result FROM games WHERE league_id=? AND game_id=?',(league_id,game_id)).fetchone()
    if not row: raise ValueError('Game not found')
    return json.loads(row[0])
