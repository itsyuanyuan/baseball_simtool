"""26-player roster migration and persistent daily condition."""
from copy import deepcopy
from datetime import date,timedelta
from engine import demo_team,player,validate_team

GROUPS=('lineup','bench','pitchers')

def full_team(team,index=0):
    t=deepcopy(team)
    t.setdefault('bench',[])
    for slot,pos in enumerate(('C','2B','CF','DH')):
        if len(t['bench'])<=slot:
            p=demo_team(t['name']+' Reserve',1000+index*100+slot)['lineup'][slot]
            p['name']=f"{t['name']} Reserve {slot+1}";p['position']=pos
            p['player_id']=f'roster-{index}-bench-{slot}'
            t['bench'].append(p)
    while len(t['pitchers'])<13:
        slot=len(t['pitchers'])
        p=demo_team(t['name']+' Staff',2000+index*100+slot)['pitchers'][0]
        p['name']=f"{t['name']} Pitcher {slot+1}";p['position']='P'
        p['player_id']=f'roster-{index}-pitchers-{slot}'
        t['pitchers'].append(p)
    t.setdefault('rotation_size',5)
    t.setdefault('auto_rest',True)
    for group in GROUPS:
        for p in t[group]:p.setdefault('energy',100)
    return t

def validate_full(team):
    t=validate_team(team)
    t['bench']=[player(p) for p in team.get('bench',[])]
    if len(t['bench'])!=4 or len(t['pitchers'])!=13:raise ValueError('League rosters require 9 batters, 4 bench players and 13 pitchers (26 total).')
    if not 1<=t['rotation_size']<=12:raise ValueError('Keep at least one pitcher in the bullpen.')
    t['auto_rest']=team.get('auto_rest',True) is True
    return t

def prepare(s):
    legacy=s.get('roster_version')!=1
    if s.get('roster_version')!=1:
        s['teams']=[full_team(t,i) for i,t in enumerate(s['teams'])]
        s['roster_version']=1
    s.setdefault('start_date','2026-04-01')
    # Legacy day numbers stay in place; future seasons include scheduled off days.
    s.setdefault('calendar_day',max((g['day'] for g in s['schedule'] if g['score'] is not None),default=0))
    s['calendar_date']=day_date(s,max(1,s['calendar_day']))
    for g in s['schedule']:g.setdefault('date',day_date(s,g['day']))
    last=max((g['day'] for g in s['schedule'] if g['score'] is not None),default=0)
    for r in s['rounds']:
        r.setdefault('start_day',last+2)
        for series in r['series']:
            if s.get('season',1)>1 and not series['id'].startswith(f"y{s['season']}"):
                series['id']=f"y{s['season']}"+series['id']
            for i,g in enumerate(series['games']):
                g.setdefault('day',r['start_day']+i+sum(i>=b for b in ((2,5) if s['best_of']==7 else (2,))))
                g.setdefault('date',day_date(s,g['day']))
                if g['score'] is not None:last=max(last,g['day'])
    if legacy:
        s['calendar_day']=max(s['calendar_day'],last)
        s['calendar_date']=day_date(s,max(1,s['calendar_day']))
    for t in s['teams']:
        for group in GROUPS:
            for p in t[group]:p.setdefault('is_ghost',not bool(p.get('history') or p.get('career_id')))

def day_date(s,day):
    return (date.fromisoformat(s['start_date'])+timedelta(days=day-1)).isoformat()

def recover_to(s,day):
    if day<s['calendar_day']:raise ValueError('Cannot simulate a game before the current calendar date.')
    elapsed=day-s['calendar_day']
    if elapsed:
        for t in s['teams']:
            for group in GROUPS:
                for p in t[group]:
                    recovery=(14+p['stamina']*.12) if group=='pitchers' else (8+p['stamina']*.08)
                    p['energy']=round(min(100,p.get('energy',100)+elapsed*recovery),2)
        s['calendar_day']=day;s['calendar_date']=day_date(s,day)
        for p in s.get('released',{}).values():
            recovery=14+p['stamina']*.12 if p['position']=='P' else 8+p['stamina']*.08
            p['energy']=round(min(100,p.get('energy',100)+elapsed*recovery),2)

def game_team(s,team_id,played):
    t=deepcopy(s['teams'][team_id])
    substitutions=[]
    used=set()
    if t.get('auto_rest',True):
        for slot,p in enumerate(t['lineup']):
            if p['energy']>=65:continue
            available=[(j,b) for j,b in enumerate(t['bench']) if j not in used and b['energy']>p['energy']+10]
            if not available:continue
            j,b=max(available,key=lambda jb:(jb[1]['position']==p['position'],jb[1]['energy']))
            replacement=deepcopy(b);replacement['position']=p['position'];t['lineup'][slot]=replacement;used.add(j)
            substitutions.append(f"{b['name']} starts for tired {p['name']}")
    rotation=t['rotation_size'];scheduled=played%rotation
    candidates=t['pitchers'][:rotation]
    starter=scheduled
    if candidates[scheduled]['energy']<70:
        starter=max(range(rotation),key=lambda i:candidates[i]['energy'])
    bullpen=t['pitchers'][rotation:]
    # Preserve priority among rested relievers; exhausted relievers are emergency options.
    bullpen=sorted(enumerate(bullpen),key=lambda pair:(pair[1]['energy']<45,pair[0]))
    t['pitchers']=[candidates[starter]]+[p for _,p in bullpen]
    t['rotation_size']=1
    t['selection_notes']=substitutions
    for p in t['lineup']:
        penalty=max(0,100-p['energy'])*.12
        for key in ('contact','power','speed','range','arm'):p[key]=max(0,p.get(key,50)-penalty)
    return t

def charge(s,team_id,selected,result,side):
    players={p['player_id']:p for group in GROUPS for p in s['teams'][team_id][group]}
    for p in selected['lineup']:
        original=players[p['player_id']]
        cost=20-original['stamina']*.10+(4 if p['position']=='C' else 0)
        original['energy']=round(max(0,original['energy']-cost),2)
    for i,stats in enumerate(result['pitching'][side]):
        if not stats['pitches']:continue
        original=players[selected['pitchers'][i]['player_id']]
        cost=stats['pitches']*(1.05-original['stamina']*.004)+5
        original['energy']=round(max(0,original['energy']-cost),2)
