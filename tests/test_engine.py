import unittest
from engine import simulate, demo_team, player
from checks import team, record, summarize
from collections import Counter

class EngineTests(unittest.TestCase):
    def request(self, seed='test'):
        return {'away': demo_team('Away', 1), 'home': demo_team('Home', 2), 'seed': seed}
    def test_reproducible(self):
        self.assertEqual(simulate(self.request()), simulate(self.request()))
    def test_accounting(self):
        for seed in range(100):
            r = simulate(self.request(seed))
            for side in (0, 1):
                self.assertEqual(sum(r['innings'][side]), r['score'][side])
                self.assertEqual(sum(p['H'] for p in r['batting'][side]), r['hits'][side])
                self.assertEqual(sum(p['R'] for p in r['pitching'][1-side]), r['score'][side])
                self.assertEqual(sum(p['pitches'] for p in r['pitching'][1-side]), sum(len(p['pitches']) for p in r['log'] if p['half'] == ('Top' if side == 0 else 'Bottom')))
            self.assertTrue(all(0 <= p['outs'] <= 3 for p in r['log']))
            self.assertTrue(9 <= len(r['innings'][0]) <= 12)
    def test_reject_bad_roster(self):
        req = self.request()
        req['away']['lineup'].pop()
        with self.assertRaises(ValueError): simulate(req)
    def test_reject_nonfinite(self):
        p = demo_team('Test')['lineup'][0]
        p['contact'] = float('nan')
        with self.assertRaises(ValueError): player(p)
    def test_contact_changes_strikeouts(self):
        totals = []
        for contact in (10, 90):
            strikeouts = 0
            for seed in range(60):
                req = self.request(seed)
                for p in req['away']['lineup']: p['contact'] = contact
                strikeouts += sum(p['SO'] for p in simulate(req)['batting'][0])
            totals.append(strikeouts)
        self.assertGreater(totals[0], totals[1] * 1.5)

    def test_hbp_sacrifice_and_walkoff_accounting(self):
        outcomes = Counter()
        for seed in range(150):
            r = simulate(self.request(f'accounting-v2-{seed}'))
            for side, half in enumerate(('Top', 'Bottom')):
                events = [p for p in r['log'] if p['half'] == half]
                stats = r['batting'][side]
                self.assertEqual(len(events), sum(p['AB']+p['BB']+p['HBP']+p['SF'] for p in stats))
                for outcome, stat in [('Walk', 'BB'), ('Hit by pitch', 'HBP'), ('Sacrifice fly', 'SF')]:
                    self.assertEqual(sum(p['outcome']==outcome for p in events), sum(p[stat] for p in stats))
                for p in events:
                    outcomes[p['outcome']] += 1
                    if p['inning'] >= 9 and half == 'Bottom' and p['score'][1] > p['score'][0] and p['outcome'] != 'Home run':
                        self.assertEqual(p['score'][1], p['score'][0]+1)
        self.assertGreater(outcomes['Hit by pitch'], 0)
        self.assertGreater(outcomes['Sacrifice fly'], 0)

    def test_average_baseline_regression(self):
        counts = Counter()
        runs = 0
        for seed in range(1000):
            r = simulate({'away': team('Away'), 'home': team('Home'), 'seed': f'regression-v2-{seed}'})
            runs += sum(r['score'])
            for p in r['log']: record(counts, p)
        stats = summarize(counts)
        for key, target, tolerance in [('AVG', .245, .008), ('OBP', .315, .008), ('SLG', .404, .015), ('K%', 22.22, 1.5), ('BB%', 8.41, .8)]:
            self.assertAlmostEqual(stats[key], target, delta=tolerance, msg=key)
        self.assertAlmostEqual(runs/2000, 4.45, delta=.35)
        self.assertAlmostEqual(counts['Home run']/2000, 1.16, delta=.12)

    def test_catcher_sequencing_affects_pitching(self):
        totals=[]
        for rating in (0,100):
            strikeouts=0
            for seed in range(100):
                req={'away':team('Away'),'home':team('Home'),'seed':f'catcher-{seed}'}
                req['home']['lineup'][0]['sequencing']=rating
                result=simulate(req)
                strikeouts+=sum(p['SO'] for p in result['batting'][0])
            totals.append(strikeouts)
        self.assertGreater(totals[1],totals[0])

if __name__ == '__main__': unittest.main()
