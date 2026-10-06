"""Read-only league player histories by stable identity, never by name."""
from copy import deepcopy
import json
import league,rosters
import season_stats
from engine import RATINGS

def states(league_id):
    current=league.get(league_id)
    with league.connect() as conn:
        exists=conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='seasons'").fetchone()
        archived=[json.loads(r[0]) for r in conn.execute('SELECT state FROM seasons WHERE league_id=? ORDER BY season',(league_id,)).fetchall()] if exists else []
        for s in archived:season_stats.migrate(conn,s)
    return archived+[current]

def roster_players(s):
    # Current roster takes precedence over old departure records.
    entries={}
    for p in s.get('departed_players',{}).values():
        if p.get('player_id'):entries[p['player_id']]={'player':p,'team':None,'status':'Departed'}
    for p in s.get('released',{}).values():
        if p.get('player_id'):entries[p['player_id']]={'player':p,'team':None,'status':'Available'}
    for i,t in enumerate(s['teams']):
        for group in rosters.GROUPS:
            for p in t.get(group,[]):
                if p.get('player_id'):entries[p['player_id']]={'player':p,'team':i,'status':'On roster'}
    return entries

def identity(key,row):return str(row.get('player_id') or key.split(':',1)[-1])

def directory(league_id):
    result={}
    for s in states(league_id):
        for bucket in (s['stats'],s.get('pitching_stats',{})):
            for phase in ('regular','playoffs'):
                for key,row in bucket.get(phase,{}).items():
                    pid=identity(key,row)
                    result.setdefault(pid,dict(id=pid,name=row['name'],status='Historical',age=None))
        for pid,item in roster_players(s).items():
            p=item['player'];result[pid]=dict(id=pid,name=p['name'],age=p.get('age'),status=item['status'])
    live=roster_players(s)
    for pid,p in result.items():
        if pid not in live:p['status']='Historical'
    return sorted(result.values(),key=lambda p:(p['name'].casefold(),p['id']))

def context(s,phase):
    bat=list(s['stats'].get(phase,{}).values());pitch=list(s.get('pitching_stats',{}).get(phase,{}).values())
    b={k:sum(p.get(k,0) for p in bat) for k in ('AB','H','HR','BB','HBP','SF','SO','SB','CS')}
    for k in ('D','T'):b[k]=sum(p[k] for p in bat) if all(k in p for p in bat) else None
    q={k:sum(p.get(k,0) for p in pitch) for k in ('outs','H','R','BB','SO','BF','HR','HBP')}
    q['complete']=all(p.get('complete',True) for p in pitch)
    return {'batting':b,'pitching':q}

def profile(league_id,pid):
    all_states=states(league_id);timeline=[];events={};latest=None;source=None;original_history={};found=False
    for s in all_states:
        season=s.get('season',1);entry=roster_players(s).get(pid)
        if entry:
            latest=deepcopy(entry);found=True
            original_history=entry['player'].get('history',original_history)
            career=entry['player'].get('career_id')
            source=s.get('library',{}).get(career,{}).get('source_career',source)
        batting=[];pitching=[]
        for phase in ('regular','playoffs'):
            for bucket,destination in ((s['stats'],batting),(s.get('pitching_stats',{}),pitching)):
                for key,row in bucket.get(phase,{}).items():
                    if identity(key,row)!=pid:continue
                    found=True
                    if latest is None:latest={'player':{'name':row['name'],'player_id':pid},'team':None,'status':'Historical'}
                    destination.append({'phase':phase,'team_name':s['teams'][row['team']]['name'],'stats':row})
        if (entry and entry['status']!='Departed') or batting or pitching:
            p=entry['player'] if entry else None
            timeline.append(dict(season=season,current=s is all_states[-1],age=p.get('age') if p else None,
                team_name=s['teams'][entry['team']]['name'] if entry and entry['team'] is not None else None,
                rating_status='Last recorded' if entry and entry['status']=='Departed' else ('Current' if s is all_states[-1] else 'Season-end'),
                ratings={k:p[k] for k in (*RATINGS,'speed') if k in p} if p else None,
                batting=batting,pitching=pitching,contexts={phase:context(s,phase) for phase in ('regular','playoffs')}))
        for o in s.get('trades',[]):
            if o['status']=='accepted' and pid in (o['give'],o['take']):
                origin=o['from'] if pid==o['give'] else o['to'];target=o['to'] if pid==o['give'] else o['from']
                events['trade:'+o['id']]=dict(season=o['season'],day=o.get('resolved_day',o['day']),text=f"Traded from {s['teams'][origin]['name']} to {s['teams'][target]['name']}")
        for i,e in enumerate(s.get('transactions',[])):
            if pid not in (e.get('out_id'),e.get('incoming_id')):continue
            year=e.get('season',season)
            events[f'replacement:{year}:{i}']=dict(season=year,day=e['day'],text=('Joined ' if pid==e.get('incoming_id') else 'Left ')+s['teams'][e['team']]['name'])
        for report in s.get('development_report',[]):
            if report.get('player_id')==pid:
                events[f'development:{season}']=dict(season=season,day=0,text=f"Offseason: age {report['age_before']} → {report['age_after']}",changes=report['changes'],components=report.get('components',{}))
    if not found:raise ValueError('Player not found in this league history')
    live=roster_players(all_states[-1]).get(pid)
    if not live:latest['status']='Historical';latest['team']=None
    return dict(league_id=league_id,league_name=all_states[-1]['name'],player_id=pid,
        player=latest['player'],status=latest['status'],team_name=all_states[-1]['teams'][latest['team']]['name'] if latest['team'] is not None else None,
        seasons=timeline,events=sorted(events.values(),key=lambda e:(e['season'],e['day'])),history=original_history,source_career=source)
