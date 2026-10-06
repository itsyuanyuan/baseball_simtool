"""Historical age slopes, regressed season performance and small seeded variation."""
import random
from engine import RATINGS

def historical_value(history,key,age):
    points=sorted((int(a),float(r[key])) for a,r in history.items() if key in r)
    if not points or age<points[0][0] or age>points[-1][0]:return None
    for a,v in points:
        if a==age:return v
    for (a,v),(b,w) in zip(points,points[1:]):
        if a<age<b:return v+(w-v)*(age-a)/(b-a)

def performance(stats,pitching=False):
    stats=stats or {}
    if pitching:
        bf=stats.get('BF',0)
        if not bf:return 0
        signal=((stats.get('SO',0)-stats.get('BB',0))/bf-.14)*2
        weight=bf/(bf+200)
    else:
        ab=stats.get('AB',0);pa=ab+stats.get('BB',0)+stats.get('HBP',0)+stats.get('SF',0)
        if not pa:return 0
        signal=((stats.get('H',0)+stats.get('BB',0)+stats.get('HBP',0))/pa-.315)*3
        weight=pa/(pa+200)
    return max(-.25,min(.25,signal*weight))

def develop(p,seed,batting=None,pitching=None):
    rng=random.Random(seed);old_age=p['age'];p['age']=min(100,old_age+1)
    before={k:float(p.get(k,50)) for k in (*RATINGS,'speed')}
    p.setdefault('potential',dict(before));history=p.get('history',{})
    changes={};components={}
    for key,current in before.items():
        direction=-1 if key=='error' else 1
        a=historical_value(history,key,old_age);b=historical_value(history,key,p['age'])
        ability=100-current if key=='error' else current
        if a is not None and b is not None:
            base=(b-a)*direction;source='history'
        else:
            peak=p['potential'].get(key,current);peak=100-peak if key=='error' else peak
            base=max(0,peak-ability)*.15 if old_age<27 else (-.25 if old_age<32 else -1.5*(1.5 if key in ('speed','range','velocity','stamina') else 1))
            source='age fallback'
        signal=performance(pitching,True) if key in ('velocity','movement','control') else performance(batting) if key in ('contact','power','eye','speed') else 0
        adjustment=abs(base)*signal # Good seasons amplify growth or soften decline.
        noise=rng.uniform(-.25,.25)
        value=round(max(0,min(100,ability+base+adjustment+noise)),2)
        value=100-value if key=='error' else value
        p[key]=round(value,2)
        changes[key]=round(p[key]-current,2)
        components[key]={'source':source,'base':round(base,3),'performance':round(adjustment,3),'random':round(noise,3)}
    p.pop('current',None)
    return {'name':p['name'],'age_before':old_age,'age_after':p['age'],'changes':changes,'components':components}
