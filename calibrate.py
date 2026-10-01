"""Training sample evaluator. Never uses the holdout seeds in checks.py."""
import argparse
from collections import Counter
import json
from checks import team, record, summarize, MLB
from engine import simulate, MODEL

def evaluate(games):
    totals = Counter()
    away, home = team('Away'), team('Home')
    for i in range(games):
        r = simulate({'away': away, 'home': home, 'seed': f'train-v2-{i}'})
        totals['R'] += sum(r['score'])
        for event in r['log']: record(totals, event)
    stats = summarize(totals)
    stats.update({'R/G': totals['R']/(games*2), 'HR/G': totals['Home run']/(games*2)})
    return stats

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--games', type=int, default=2000)
    p.add_argument('--set', default='{}', help='JSON coefficient overrides for this process only')
    args = p.parse_args()
    MODEL.update(json.loads(args.set))
    print(json.dumps({'coefficients': MODEL, 'training': evaluate(args.games), 'target': MLB}, indent=2), flush=True)
