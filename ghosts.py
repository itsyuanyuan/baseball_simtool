"""League placeholder curve on the engine scale (source 20–80 shown in UI)."""
KEYS=('stamina','contact','power','eye','velocity','movement','control','range','error','arm','sequencing','speed')
MATURITY_AGE=26

def ratings(age):
    skill=max(0,min(50,(age-16)*5))
    return {key:100-skill if key=='error' else skill for key in KEYS}

def initialize(p):
    p.update(ratings(p['age']))
    p['potential']=ratings(MATURITY_AGE)
    p['history']={str(age):ratings(age) for age in range(16,32)}
    p['is_ghost']=True;p['ghost_curve']=1
    return p
