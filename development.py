"""Seeded offseason growth/decline. Historical peaks are ceilings, not promises."""
import random
from engine import RATINGS

def develop(p,seed):
    rng=random.Random(seed)
    before={k:float(p.get(k,50)) for k in (*RATINGS,'speed')}
    potential=p.setdefault('potential',dict(before))
    old_age=p['age']
    p['age']=min(100,old_age+1)
    changes={}
    for key,current in before.items():
        ceiling=float(potential.get(key,current))
        ability=100-current if key=='error' else current
        maximum=100-ceiling if key=='error' else ceiling
        maximum=max(ability,maximum)
        if old_age<27:
            delta=(maximum-ability)*rng.uniform(.10,.22)
        elif old_age<32:
            delta=rng.uniform(-1,.5)
        else:
            delta=-rng.uniform(.5,2.5)*(1.5 if key in ('speed','range','velocity','stamina') else 1)
        next_ability=max(0,min(maximum,ability+delta))
        value=round(100-next_ability if key=='error' else next_ability,2)
        p[key]=value
        if value!=current: changes[key]=round(value-current,2)
    p.pop('current',None)
    return {'name':p['name'],'age_before':old_age,'age_after':p['age'],'changes':changes}
