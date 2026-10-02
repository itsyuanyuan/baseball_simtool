"""Local SQLite leagues: immutable rosters, balanced schedules and seeded playoffs."""
from copy import deepcopy
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import uuid
from development import develop
from datetime import date
import rosters
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
                playing_day=cycle*(n-1)+day+1
                calendar_day=playing_day+(playing_day-1)//6
                games.append(dict(id=f'r{len(games)+1}', day=calendar_day, away=a, home=b, phase='regular', score=None))
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

def ensure_player_ids(state):
    """Deterministic legacy IDs allow old saved lineups to be reordered safely."""
    for team_id,t in enumerate(state['teams']):
        for group in rosters.GROUPS:
            for slot,p in enumerate(t[group]):
                if 'player_id' not in p:
                    p['player_id']=f'legacy-{team_id}-{group}-{slot}'
                    if group=='lineup':
                        for totals in state['stats'].values():
                            old=f'{team_id}:{slot}'
                            if old in totals:totals[f"{team_id}:{p['player_id']}"]=totals.pop(old)

def save(conn,state):
    conn.execute('INSERT OR REPLACE INTO leagues VALUES (?,?)',(state['id'],json.dumps(state)))

def create(request):
    teams = [rosters.validate_full(rosters.full_team(t,i)) for i,t in enumerate(request['teams'])]
    for t in teams:
        for group in rosters.GROUPS:
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
    start_date=date.fromisoformat(request.get('start_date','2026-04-01')).isoformat()
    state = dict(id=uuid.uuid4().hex, name=str(request.get('name','My league'))[:80], seed=str(request.get('seed','season-1'))[:100],
                 version=0, model_version=MODEL_VERSION, teams=teams, phase='regular', games_per_opponent=repeats,
                 playoff_teams=playoff,best_of=best, schedule=schedule(n,repeats), rounds=[], champion=None,
                 stats={'regular':{},'playoffs':{}},start_date=start_date,calendar_day=0,roster_version=1)
    rosters.prepare(state)
    with connect() as conn: save(conn,state)
    return view(state)

def get(league_id):
    with connect() as conn:
        row=conn.execute('SELECT state FROM leagues WHERE id=?',(league_id,)).fetchone()
    if not row: raise ValueError('League not found')
    state=json.loads(row[0]);rosters.prepare(state);ensure_player_ids(state)
    return view(state)

def list_leagues():
    with connect() as conn: rows=conn.execute('SELECT state FROM leagues ORDER BY rowid DESC').fetchall()
    return [dict(id=s['id'],name=s['name'],phase=s['phase'],teams=len(s['teams'])) for s in (json.loads(r[0]) for r in rows)]

def new_round(state, seeds):
    seeds=sorted(seeds)
    number=len(state['rounds'])+1
    prefix=f"y{state['season']}" if state.get('season',1)>1 else ''
    series=[dict(id=f'{prefix}p{number}s{i+1}',high=seeds[i],low=seeds[-i-1],wins=[0,0],winner=None,games=[]) for i in range(len(seeds)//2)]
    state['rounds'].append(dict(number=number,series=series,start_day=state.get('calendar_day',0)+2))

def roster(state, team_id, played):
    return rosters.game_team(state,team_id,played)

def play(conn,state,g):
    rosters.recover_to(state,g['day'])
    g['date']=rosters.day_date(state,g['day'])
    played={i:sum(1 for old in state['schedule'] if old['score'] is not None and i in (old['away'],old['home'])) for i in (g['away'],g['home'])}
    for round_ in state['rounds']:
        for series in round_['series']:
            for old in series['games']:
                for i in played:
                    if old['score'] is not None and i in (old['away'],old['home']): played[i]+=1
    selected=[roster(state,g[side],played[g[side]]) for side in ('away','home')]
    result=simulate(dict(away=selected[0],home=selected[1],seed=f"{state['seed']}:{g['id']}"),max_innings=100)
    if result['tie']: raise ValueError('Game reached the 100-inning safety limit; no progress was saved')
    g['score']=result['score']
    result['date']=g['date']
    result['selection_notes']=[t['selection_notes'] for t in selected]
    conn.execute('INSERT INTO games VALUES (?,?,?)',(state['id'],g['id'],json.dumps(result)))
    for side, team_id in enumerate((g['away'],g['home'])):
        rosters.charge(state,team_id,selected[side],result,side)
        for slot,p in enumerate(result['batting'][side]):
            key=f"{team_id}:{selected[side]['lineup'][slot]['player_id']}"
            totals=state['stats'][g['phase']].setdefault(key,dict(team=team_id,name=p['name'],G=0,AB=0,H=0,HR=0,BB=0,HBP=0,SF=0,SO=0,RBI=0,SB=0,CS=0))
            totals['G']+=1
            for stat in ('AB','H','HR','BB','HBP','SF','SO','RBI'): totals[stat]+=p[stat]
            for stat in ('SB','CS'): totals[stat]=totals.get(stat,0)+p.get(stat,0)

def advance(request):
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT state FROM leagues WHERE id=?',(request['id'],)).fetchone()
        if not row: raise ValueError('League not found')
        state=json.loads(row[0])
        if request.get('version') != state['version']: raise ValueError('League changed in another tab. Reload it before continuing.')
        rosters.prepare(state);ensure_player_ids(state)
        if state['model_version']!=MODEL_VERSION:
            if state['model_version'] not in ('0.2-calibrated','0.3-speed-development'): raise ValueError('This league uses an unsupported engine version.')
            state.setdefault('model_history',[]).append(state['model_version'])
            state['model_version']=MODEL_VERSION
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
            target=pending[0]['day'] if pending[0]['day']<=state['calendar_day'] else state['calendar_day']+1
            selected=pending[:1] if action=='next' else ([g for g in pending if g['day']==target] if action=='day' else pending[:20])
            if action=='day' and not selected:rosters.recover_to(state,target)
            if state.get('managed') and action=='batch' and request.get('override_ready') is not True:
                selected=[g for g in pending if g['day']==pending[0]['day']]
            check_ready({i for g in selected for i in (g['away'],g['home'])})
            for g in selected: played(g)
            if all(g['score'] is not None for g in state['schedule']): state['phase']='ready'
        elif state['phase']=='playoffs':
            series=[s for s in state['rounds'][-1]['series'] if s['winner'] is None]
            def next_day(s):
                game_index=len(s['games'])
                travel=sum(game_index>=boundary for boundary in ((2,5) if state['best_of']==7 else (2,)))
                return state['rounds'][-1]['start_day']+game_index+travel
            earliest=min(next_day(s) for s in series)
            target=min(earliest,state['calendar_day']+1) if action=='day' else earliest
            today=[s for s in series if next_day(s)==target]
            if action=='next':today=today[:1]
            if not today:rosters.recover_to(state,target)
            check_ready({state['seeds'][seed] for s in today for seed in (s['high'],s['low'])})
            for s in today:
                game_number=len(s['games'])
                # Higher seed hosts games 1,2,5,7 (best-of-seven), or odd games otherwise.
                high_home=game_number in (0,1,4,6) if state['best_of']==7 else game_number%2==0
                high,low=state['seeds'][s['high']],state['seeds'][s['low']]
                g=dict(id=f"{s['id']}g{game_number+1}",day=next_day(s),away=low if high_home else high,home=high if high_home else low,phase='playoffs',score=None)
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

def next_season(request):
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT state FROM leagues WHERE id=?',(request['id'],)).fetchone()
        if not row: raise ValueError('League not found')
        s=json.loads(row[0])
        if request.get('version')!=s['version']: raise ValueError('League changed. Reload before advancing the season.')
        if s['phase']!='complete': raise ValueError('Finish the championship before advancing to next season.')
        rosters.prepare(s);ensure_player_ids(s)
        year=s.get('season',1)
        conn.execute('CREATE TABLE IF NOT EXISTS seasons (league_id TEXT, season INTEGER, state TEXT, PRIMARY KEY(league_id,season))')
        conn.execute('INSERT INTO seasons VALUES (?,?,?)',(s['id'],year,json.dumps(s)))
        reports=[]
        for team_id,t in enumerate(s['teams']):
            for group in rosters.GROUPS:
                for slot,p in enumerate(t[group]):
                    p.setdefault('player_id',uuid.uuid4().hex)
                    report=develop(p,f"{s['seed']}:development:{year+1}:{p['player_id']}")
                    p['energy']=100
                    reports.append({'team':team_id,**report})
        s['development_report']=reports
        s['season']=year+1
        previous_start=date.fromisoformat(s['start_date'])
        s['start_date']=date(previous_start.year+1,4,1).isoformat()
        s['calendar_day']=0
        s.setdefault('past_seasons',[]).append({'season':year,'champion':s['teams'][s['champion']]['name']})
        s['schedule']=schedule(len(s['teams']),s['games_per_opponent'])
        for g in s['schedule']:g['id']=f"y{year+1}{g['id']}"
        s.update(phase='regular',rounds=[],champion=None,stats={'regular':{},'playoffs':{}},ready={},model_version=MODEL_VERSION)
        s.pop('seeds',None)
        rosters.prepare(s)
        s['version']+=1;s['lineup_epoch']=s.get('lineup_epoch',0)+1
        save(conn,s)
    return view(s)

def archive(league_id,season):
    with connect() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS seasons (league_id TEXT, season INTEGER, state TEXT, PRIMARY KEY(league_id,season))')
        row=conn.execute('SELECT state FROM seasons WHERE league_id=? AND season=?',(league_id,int(season))).fetchone()
    if not row:raise ValueError('Archived season not found')
    return view(json.loads(row[0]))
