"""Original, seeded baseball model. Ratings are 0–100; velocity is a rating, not mph."""
import random

RATINGS = ('stamina', 'contact', 'power', 'eye', 'velocity', 'movement', 'control', 'range', 'error', 'arm', 'sequencing')
POSITIONS = ('C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH')
MODEL_VERSION = '0.5-careers-trades'
# Neutral, 50-rated baseline. Slopes retain individual player differences.
MODEL = dict(zone=.507, swing_zone=.68, chase=.30, contact=.85, foul=.48,
             homer=.044, hit=.300, double=23.5, triple=1.8,
             hbp=.0028, error=.018, score_second=.67, first_to_third=.28,
             score_first_double=.55, productive_out=.36, double_play=.13)

def player(value):
    if not isinstance(value, dict):
        raise ValueError('Each player must be an object')
    ratings = value.get('current', value.get('ratings', value))
    if not isinstance(ratings, dict):
        raise ValueError('Ratings must be an object')
    missing = [key for key in RATINGS if key not in ratings]
    if missing:
        raise ValueError('Missing ratings: ' + ', '.join(missing))
    out = {'name': str(value.get('name', 'Player'))[:60], 'age': int(value.get('age', 25)), 'position': value.get('position', 'DH')}
    if not 10 <= out['age'] <= 100:
        raise ValueError('Age must be 10–100')
    for key in RATINGS:
        rating = float(ratings[key])
        if not 0 <= rating <= 100:
            raise ValueError(key + ' must be between 0 and 100')
        out[key] = rating
    out['speed']=float(ratings.get('speed',50))
    if not 0<=out['speed']<=100: raise ValueError('speed must be between 0 and 100')
    out['energy']=float(value.get('energy',100))
    if 'is_ghost' in value:out['is_ghost']=value['is_ghost'] is True
    if not 0<=out['energy']<=100: raise ValueError('energy must be between 0 and 100')
    for key in ('player_id','career_id'):
        if key in value:out[key]=str(value[key])[:100]
    if 'history' in value:
        history=value['history']
        if not isinstance(history,dict) or len(history)>91:raise ValueError('Invalid career history')
        out['history']={}
        for age,ratings_at_age in history.items():
            if not str(age).isdigit() or not 10<=int(age)<=100 or not isinstance(ratings_at_age,dict):raise ValueError('Invalid historical age')
            normalized={}
            for key in (*RATINGS,'speed'):
                if key not in ratings_at_age:continue
                number=float(ratings_at_age[key])
                if not 0<=number<=100:raise ValueError('Historical ratings must be 0–100')
                normalized[key]=number
            out['history'][str(age)]=normalized
    if 'potential' in value:
        if not isinstance(value['potential'],dict): raise ValueError('potential must be an object')
        potential={}
        for key in (*RATINGS,'speed'):
            p=float(value['potential'].get(key,out[key]))
            if not 0<=p<=100: raise ValueError('Potential must be between 0 and 100')
            potential[key]=p
        out['potential']=potential
    return out

def demo_team(name, offset=0):
    rng = random.Random(120 + offset)
    def make(i, pos):
        p = {'name': f'{name} {i+1:02}', 'age': 22 + i % 12, 'position': pos, 'is_ghost':True}
        p.update({key: rng.randint(38, 78) for key in RATINGS})
        p['error'] = rng.randint(8, 28)
        return p
    return {'name': name, 'lineup': [make(i, pos) for i, pos in enumerate(POSITIONS)], 'pitchers': [make(i + 9, 'P') for i in range(4)]}

def validate_team(team):
    if not isinstance(team, dict):
        raise ValueError('Each team must be an object')
    lineup = [player(p) for p in team['lineup']]
    pitchers = [player(p) for p in team['pitchers']]
    if len(lineup) != 9 or not 1 <= len(pitchers) <= 13:
        raise ValueError('Each team needs nine batters and 1–13 pitchers')
    if sorted(p['position'] for p in lineup) != sorted(POSITIONS):
        raise ValueError('Lineup must contain C, 1B, 2B, 3B, SS, LF, CF, RF, DH exactly once')
    rotation_size=int(team.get('rotation_size',min(3,max(1,len(pitchers)-1))))
    if not 1<=rotation_size<=len(pitchers): raise ValueError('Rotation size must fit the pitching staff')
    return {'name': str(team.get('name', 'Team'))[:60], 'lineup': lineup, 'pitchers': pitchers, 'rotation_size':rotation_size}

def simulate(request, *, max_innings=12):
    if not isinstance(request, dict):
        raise ValueError('Request must be an object')
    teams = [validate_team(request['away']), validate_team(request['home'])]
    seed = str(request.get('seed', 'opening-day'))[:100]
    rng = random.Random(seed)
    running_rng=random.Random(seed+':running')
    park = float(request.get('park', 1))
    if not .7 <= park <= 1.3:
        raise ValueError('Park factor must be 0.7–1.3')
    score, hits, errors, order, active = [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]
    counts = [[0] * len(t['pitchers']) for t in teams]
    batting = [[dict(name=p['name'], AB=0, H=0, HR=0, BB=0, HBP=0, SF=0, SO=0, RBI=0, SB=0, CS=0, R=0, D=0, T=0) for p in t['lineup']] for t in teams]
    pitching = [[dict(name=p['name'], pitches=0, outs=0, H=0, R=0, BB=0, SO=0, BF=0, HR=0, HBP=0) for p in t['pitchers']] for t in teams]
    for side,t in enumerate(teams):
        for group,stats in (('lineup',batting),('pitchers',pitching)):
            for p,row in zip(t[group],stats[side]):
                if 'player_id' in p:row['player_id']=p['player_id']
    innings, log = [[], []], []
    def chance(p):
        return rng.random() < max(.005, min(.995, p))
    for inning in range(1, max_innings + 1):
        for side in (0, 1):
            if inning >= 9 and side == 1 and score[1] > score[0]:
                break
            defense = 1 - side
            outs, bases, runs, pa_count = 0, [None, None, None], 0, 0
            while outs < 3:
                pa_count += 1
                if pa_count > 250:
                    raise ValueError('Simulation exceeded the half-inning safety limit; try another seed')
                pi = active[defense]
                pitcher = teams[defense]['pitchers'][pi]
                limit = (45 + pitcher['stamina'] * .85)*(.35+.65*pitcher['energy']/100)
                if counts[defense][pi] >= limit and pi + 1 < len(counts[defense]):
                    active[defense] += 1
                    pi += 1
                    pitcher = teams[defense]['pitchers'][pi]
                ps = pitching[defense][pi]
                catcher = next(p for p in teams[defense]['lineup'] if p['position'] == 'C')
                # Imported cat belongs to the catcher. A neutral 50 adds no modifier.
                sequencing = max(0, min(100, pitcher['sequencing'] + catcher['sequencing'] - 50))
                if bases[0] and not bases[1] and running_rng.random()<max(.01,min(.35,.12+(bases[0]['speed']-50)*.003)):
                    stealing=bases[0];bases[0]=None
                    success=running_rng.random()<max(.15,min(.95,.76+(stealing['speed']-50)*.0035-(catcher['arm']-50)*.003))
                    batting[side][stealing['slot']]['SB' if success else 'CS']+=1
                    if success: bases[1]=stealing
                    else: outs+=1;ps['outs']+=1
                    log.append({'inning':inning,'half':'Top' if side==0 else 'Bottom','batter':stealing['name'],'pitcher':pitcher['name'],'outcome':'Stolen base' if success else 'Caught stealing','runs':0,'outs':outs,'bases':[p['name'] if p else None for p in bases],'score':score[:],'pitches':[],'plate_appearance':False})
                    if outs==3: break
                bi = order[side] % 9
                order[side] += 1
                batter = teams[side]['lineup'][bi]
                bs = batting[side][bi]
                ps['BF'] += 1
                balls, strikes, pitches, previous = 0, 0, [], None
                start_outs = outs
                runs_this = 0
                def run(runner):
                    nonlocal runs, runs_this
                    if inning >= 9 and side == 1 and score[1] > score[0] and outcome != 'Home run':
                        return
                    batting[side][runner['slot']]['R'] += 1
                    score[side] += 1
                    runs += 1
                    runs_this += 1
                    pitching[defense][runner['pitcher']]['R'] += 1
                runner = {'name': batter['name'], 'pitcher': pi,'speed':batter['speed'],'slot':bi}
                for pitch_number in range(30):
                    fatigue = max(0, counts[defense][pi] - (35 + pitcher['stamina'] * .65)) * .35+(100-pitcher['energy'])*.25
                    control = pitcher['control'] - fatigue
                    movement = pitcher['movement'] - fatigue
                    velocity = pitcher['velocity'] - fatigue
                    # Two-strike breaking balls; fastballs when behind. Better sequencing varies pitches.
                    pitch_types = ['fastball', 'slider', 'changeup']
                    weights = [5 + balls, 3 + strikes * 2, 2 + strikes]
                    if previous:
                        weights[pitch_types.index(previous)] *= 1.2 - sequencing * .008
                    kind = rng.choices(pitch_types, weights)[0]
                    repeat = previous == kind
                    deception = (sequencing - 50) * .0015 + (0.025 if not repeat else -.025)
                    previous = kind
                    counts[defense][pi] += 1
                    ps['pitches'] += 1
                    if rng.random() < max(.0005, MODEL['hbp'] + (50-control)*.000015):
                        result = 'hit by pitch'
                        pitches.append({'type': kind, 'result': result, 'count': f'{balls}-{strikes}'})
                        break
                    zone = chance(MODEL['zone'] + (control - 50) * .002)
                    swing = chance((MODEL['swing_zone'] - (batter['eye'] - 50) * .001) if zone else (MODEL['chase'] - (batter['eye'] - 50) * .003))
                    if not swing:
                        result = 'called strike' if zone else 'ball'
                        if zone: strikes += 1
                        else: balls += 1
                    elif not chance(MODEL['contact'] + (batter['contact'] - 50) * .003 - (velocity - 50) * .0015 - (movement - 50) * .001 - deception - (0 if zone else .13)):
                        strikes += 1
                        result = 'swinging strike'
                    elif chance(MODEL['foul']):
                        strikes = min(2, strikes + 1)
                        result = 'foul'
                    else:
                        result = 'in play'
                    pitches.append({'type': kind, 'result': result, 'count': f'{balls}-{strikes}'})
                    if balls == 4 or strikes == 3 or result == 'in play':
                        break
                else:
                    result = 'in play'
                    pitches[-1]['result'] = 'in play (pitch cap)'
                if balls == 4 or result == 'hit by pitch':
                    outcome = 'Walk' if balls == 4 else 'Hit by pitch'
                    bs['BB' if balls == 4 else 'HBP'] += 1
                    if balls == 4: ps['BB'] += 1
                    else: ps['HBP'] += 1
                    if bases[0]:
                        if bases[1]:
                            if bases[2]: run(bases[2])
                            bases[2] = bases[1]
                        bases[1] = bases[0]
                    bases[0] = runner
                else:
                    bs['AB'] += 1
                    if strikes == 3:
                        outcome = 'Strikeout'
                        outs += 1
                        bs['SO'] += 1
                        ps['SO'] += 1
                    elif chance((MODEL['homer'] + (batter['power'] - 50) * .001 - (movement - 50) * .00045) * park):
                        outcome = 'Home run'
                        for occupied in bases:
                            if occupied: run(occupied)
                        run(runner)
                        bases = [None, None, None]
                        bs['H'] += 1
                        bs['HR'] += 1
                        ps['HR'] += 1
                        hits[side] += 1
                        ps['H'] += 1
                    else:
                        fielder = rng.choice([p for p in teams[defense]['lineup'] if p['position'] != 'DH'])
                        error = chance(MODEL['error'] + (fielder['error'] - 50) * .0003)
                        defensive_skill = fielder['range']
                        infield_speed=(batter['speed']-50)*.0006 if fielder['position'] in ('1B','2B','3B','SS') else 0
                        hit = not error and chance(MODEL['hit'] + (batter['contact'] - 50) * .0015 - (defensive_skill - 50) * .002+infield_speed)
                        if error or hit:
                            triples=max(.2,MODEL['triple']+(batter['speed']-50)*.025)
                            distance = 1 if error else rng.choices([1, 2, 3], [100-MODEL['double']-triples, MODEL['double'] * park, triples])[0]
                            outcome = 'Error' if error else {1: 'Single', 2: 'Double', 3: 'Triple'}[distance]
                            if error: errors[defense] += 1
                            else:
                                hits[side] += 1
                                bs['H'] += 1
                                if distance==2:bs['D']+=1
                                if distance==3:bs['T']+=1
                                ps['H'] += 1
                            advanced = [None, None, None]
                            for index in (2, 1, 0):
                                if bases[index]:
                                    target = index + distance
                                    arm = (fielder['arm'] - 50) * .004-(bases[index]['speed']-50)*.006
                                    if not error and distance == 1 and index == 1 and chance(MODEL['score_second'] - arm): target = 3
                                    if not error and distance == 1 and index == 0 and advanced[2] is None and chance(MODEL['first_to_third'] - arm): target = 2
                                    if not error and distance == 2 and index == 0 and chance(MODEL['score_first_double'] - arm): target = 3
                                    if target >= 3: run(bases[index])
                                    else: advanced[target] = bases[index]
                            advanced[distance - 1] = runner
                            bases = advanced
                        else:
                            outcome = 'Field out'
                            outs += 1
                            if bases[0] and start_outs < 2 and chance(MODEL['double_play'] + (fielder['arm'] + defensive_skill - 100) * .001-(batter['speed']-50)*.0015):
                                outcome = 'Double play'
                                outs += 1
                                bases[0] = None
                            elif start_outs < 2 and chance(MODEL['productive_out'] - (fielder['arm']-50)*.002):
                                if bases[2]:
                                    outcome = 'Sacrifice fly'
                                    bs['AB'] -= 1
                                    bs['SF'] += 1
                                    run(bases[2])
                                    bases[2] = None
                                elif bases[1]:
                                    bases[2], bases[1] = bases[1], None
                ps['outs'] += outs - start_outs
                if outcome != 'Error': bs['RBI'] += runs_this
                log.append({'inning': inning, 'half': 'Top' if side == 0 else 'Bottom', 'batter': batter['name'], 'pitcher': pitcher['name'], 'outcome': outcome, 'runs': runs_this, 'outs': outs, 'bases': [p['name'] if p else None for p in bases], 'score': score[:], 'pitches': pitches})
                if inning >= 9 and side == 1 and score[1] > score[0]: break
            innings[side].append(runs)
        if inning >= 9 and score[0] != score[1]: break
    return {'model_version': MODEL_VERSION, 'seed': seed, 'teams': [t['name'] for t in teams], 'score': score, 'hits': hits, 'errors': errors, 'innings': innings, 'batting': batting, 'pitching': pitching, 'log': log, 'tie': score[0] == score[1]}
