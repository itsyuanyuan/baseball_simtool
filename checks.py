"""Repeatable holdout diagnostics of the production engine."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from engine import simulate, RATINGS, POSITIONS, MODEL, MODEL_VERSION

ROOT = Path(__file__).parent
PROFILES = {
    'Average': {'contact': 50, 'power': 50, 'eye': 50},
    'Schwarber-like': {'contact': 35, 'power': 95, 'eye': 90},
    'Ichiro-like': {'contact': 95, 'power': 20, 'eye': 55},
}
PITCHING = ('stamina', 'velocity', 'movement', 'control', 'sequencing')
MLB = {'AVG': .245, 'OBP': .315, 'SLG': .404, 'R/G': 4.45,
       'HR/G': 188/162, 'BB%': 513/6098*100, 'K%': 1355/6098*100}

def team(name):
    def p(pos):
        return dict(name=name, age=28, position=pos, **dict.fromkeys(RATINGS, 50))
    return {'name': name, 'lineup': [p(pos) for pos in POSITIONS], 'pitchers': [p('P') for _ in range(4)]}

def record(counts, event):
    if event.get('plate_appearance') is False: return
    counts['PA'] += 1
    counts[event['outcome']] += 1
    counts['pitches'] += len(event['pitches'])

def summarize(c):
    pa = c['PA']
    ab = pa - c['Walk'] - c['Hit by pitch'] - c['Sacrifice fly']
    hits = sum(c[k] for k in ('Single', 'Double', 'Triple', 'Home run'))
    tb = sum(c[k]*v for k,v in [('Single',1),('Double',2),('Triple',3),('Home run',4)])
    return {'PA': pa, 'AVG': hits/ab, 'OBP': (hits+c['Walk']+c['Hit by pitch'])/pa, 'SLG': tb/ab,
            'K%': c['Strikeout']/pa*100, 'BB%': c['Walk']/pa*100,
            'HR%': c['Home run']/pa*100, 'P/PA': c['pitches']/pa}

def run(games, matchups):
    away, home = team('Average away'), team('Average home')
    totals = Counter()
    for i in range(games):
        result = simulate({'away': away, 'home': home, 'seed': f'holdout-v2-{i}'})
        totals['R'] += sum(result['score'])
        for event in result['log']: record(totals, event)
    baseline = summarize(totals)
    baseline.update({'R/G': totals['R']/(games*2), 'HR/G': totals['Home run']/(games*2)})
    print('Baseline:', json.dumps(baseline), flush=True)
    rows = []
    # Only the first PA of each independent game is observed: fresh pitcher,
    # empty bases, average defense, neutral park. No bullpen/fatigue confound.
    for pitcher, rating in [('Average', 50), ('Elite', 90)]:
        for profile, abilities in PROFILES.items():
            away, home = team(profile), team(pitcher)
            away['lineup'][0].update(abilities)
            home['pitchers'][0].update(dict.fromkeys(PITCHING, rating))
            counts = Counter()
            for i in range(matchups):
                event = simulate({'away': away, 'home': home, 'seed': f'matchup-{i}'})['log'][0]
                record(counts, event)
            row = {'hitter': profile, 'pitcher': pitcher, **summarize(counts)}
            rows.append(row)
            print('Matchup:', json.dumps(row), flush=True)
    report = {'engine_sha256': hashlib.sha256((ROOT/'engine.py').read_bytes()).hexdigest(),
              'model_version': MODEL_VERSION, 'coefficients': MODEL, 'seed_prefix': 'holdout-v2-',
              'games': games, 'matchups_per_pair': matchups, 'baseline': baseline,
              'mlb_2025': MLB, 'profiles': PROFILES, 'pitching_ratings': {'Average': 50, 'Elite': 90},
              'matchups': rows, 'baseline_counts': dict(totals),
              'source': 'https://www.baseball-reference.com/tools/share.fcgi?id=j7IEM',
              'notes': ['All baseline ratings, including error tendency, are 50.',
                        'MLB reference is the rounded 2025 league-average row; BB% and K% derived from it.',
                        'Model includes HBP and sacrifice flies; no sacrifice bunts or catcher interference.',
                        'Ratings are illustrative archetypes, not fitted player ratings.',
                        'Each matchup samples the first PA of an independent seeded game.',
                        'Same seed set is reused across profiles; comparisons are paired, not independent.',
                        'Baseline fitted on train-v2 seeds; this report uses separate holdout-v2 seeds.']}
    (ROOT/'public'/'checks.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--games', type=int, default=10000)
    parser.add_argument('--matchups', type=int, default=5000)
    args = parser.parse_args()
    if min(args.games, args.matchups) < 1: parser.error('Sample sizes must be positive')
    run(args.games, args.matchups)
