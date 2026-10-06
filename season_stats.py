"""Season pitching totals and derived rates. Outs, not decimal innings, are stored."""

def add_pitching(s,g,result,selected=None):
    bucket=s.setdefault('pitching_stats',{'regular':{},'playoffs':{}})[g['phase']]
    for side,team in enumerate((g['away'],g['home'])):
        for index,p in enumerate(result['pitching'][side]):
            if not p['pitches']:continue
            identity=p.get('player_id')
            if selected:identity=selected[side]['pitchers'][index]['player_id']
            if not identity:
                matches=[q for q in s['teams'][team]['pitchers'] if q['name']==p['name']]
                identity=matches[0]['player_id'] if len(matches)==1 else 'legacy:'+p['name']
            p=dict(p)
            if 'BF' not in p:
                names=[q['name'] for q in result['pitching'][side]]
                if names.count(p['name'])==1:
                    events=[e for e in result['log'] if e['half']==('Bottom' if side==0 else 'Top') and e['pitcher']==p['name'] and e.get('plate_appearance',True)]
                    p.update(BF=len(events),HR=sum(e['outcome']=='Home run' for e in events),HBP=sum(e['outcome']=='Hit by pitch' for e in events))
            key=f'{team}:{identity}'
            row=bucket.setdefault(key,dict(team=team,player_id=identity,name=p['name'],G=0,GS=0,outs=0,pitches=0,H=0,R=0,BB=0,SO=0,BF=0,HR=0,HBP=0,complete=True))
            row['G']+=1;row['GS']+=int(index==0)
            row['complete']=row['complete'] and 'BF' in p
            for k in ('outs','pitches','H','R','BB','SO','BF','HR','HBP'):row[k]+=p.get(k,0)

def migrate(conn,s):
    if s.get('pitching_stats') is not None:return
    s['pitching_stats']={'regular':{},'playoffs':{}}
    import json
    games=list(s['schedule'])+[g for r in s['rounds'] for series in r['series'] for g in series['games']]
    for g in games:
        if g['score'] is None:continue
        row=conn.execute('SELECT result FROM games WHERE league_id=? AND game_id=?',(s['id'],g['id'])).fetchone()
        if row:add_pitching(s,g,json.loads(row[0]))

def player_totals(s,p,kind='batting'):
    buckets=s['stats'] if kind=='batting' else s.get('pitching_stats',{})
    total={}
    for key,row in buckets.get('regular',{}).items():
        if row.get('player_id')==p['player_id'] or key.endswith(':'+p['player_id']):
            for k,v in row.items():
                if k not in ('team','complete') and isinstance(v,(int,float)):total[k]=total.get(k,0)+v
    return total
