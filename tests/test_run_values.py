import hashlib,json,math,unittest
from collections import defaultdict
from copy import deepcopy
from engine import simulate,demo_team
from checks import team
from run_values import COMPONENTS,COUNTERS

class RunValueTests(unittest.TestCase):
    def test_catcher_range_has_no_effect(self):
        for seed in range(20):
            a,b=demo_team('A'),demo_team('B',2)
            for t in (a,b):t['lineup'][0]['range']=0
            low=simulate(dict(away=a,home=b,seed=seed))
            for t in (a,b):t['lineup'][0]['range']=100
            high=simulate(dict(away=a,home=b,seed=seed))
            for key in ('score','log','batting','value_events'):
                self.assertEqual(low[key],high[key])

    def test_slow_runners_rarely_attempt_steals(self):
        from engine import steal_attempt_probability as attempt
        self.assertEqual(attempt(0,50),0)
        self.assertLess(attempt(10,50),.005)
        self.assertLess(attempt(25,50),attempt(50,50)/4)
        self.assertAlmostEqual(attempt(50,50),.12)
        self.assertGreater(attempt(80,50),attempt(50,50))
        self.assertLess(attempt(25,90),attempt(25,20))

    def test_event_ledger_reconciles_and_outs_errors_steals_match(self):
        for seed in range(60):
            r=simulate(dict(away=demo_team('A'),home=demo_team('B',2),seed=f'ledger-{seed}'))
            sums=defaultdict(float)
            for e in r['value_events']:
                self.assertGreaterEqual(e['neutral_probability'],0);self.assertLessEqual(e['neutral_probability'],1)
                self.assertAlmostEqual(e['runs'],(e['observed']-e['neutral_probability'])*e['run_weight'])
                self.assertLess(e['play_index'],len(r['log']))
                sums[e['team'],e['slot'],e['component']]+=e['runs']
            for side in (0,1):
                bat=r['batting'][side]
                for slot,p in enumerate(bat):
                    for k in COMPONENTS:self.assertAlmostEqual(p[k],sums[side,slot,k])
                    self.assertEqual(p['value_games'],1)
                self.assertEqual(sum(p['fielding_errors'] for p in bat),r['errors'][side])
                self.assertEqual(sum(p['fielding_outs']+p['double_plays_turned']+p['caught_stealing_against'] for p in bat),sum(p['outs']-p['SO'] for p in r['pitching'][side]))
                self.assertEqual(sum(p['steal_attempts_against'] for p in bat),sum(p['SB']+p['CS'] for p in r['batting'][1-side]))
                self.assertEqual(sum(p['caught_stealing_against'] for p in bat),sum(p['CS'] for p in r['batting'][1-side]))
                self.assertEqual(bat[8]['fielding_chances'],0) # DH has no defensive opportunities.
                self.assertEqual(sum(p['double_plays_turned'] for p in bat),sum(p['double_plays_hit_into'] for p in r['batting'][1-side]))

    def test_neutral_players_average_near_zero_per_opportunity(self):
        sums=defaultdict(float);variance=defaultdict(float)
        for i in range(300):
            r=simulate(dict(away=team('A'),home=team('B'),seed=f'neutral-values-{i}'))
            for e in r['value_events']:
                sums[e['component']]+=e['runs']
                variance[e['component']]+=e['neutral_probability']*(1-e['neutral_probability'])*e['run_weight']**2
        for k in COMPONENTS:
            self.assertGreater(variance[k],0)
            self.assertLess(abs(sums[k]),5*math.sqrt(variance[k]),k)

    def test_speed_and_defense_improve_opportunity_values(self):
        totals=[]
        for level in (10,90):
            summed=defaultdict(float)
            for i in range(160):
                a=team('A');b=team('B')
                for p in a['lineup']:p['speed']=level
                for p in b['lineup']:p.update(range=level,arm=level,error=100-level)
                r=simulate(dict(away=a,home=b,seed=f'value-ratings-{i}'))
                for p in r['batting'][0]:
                    for k in ('advance_runs','avoid_dp_runs','advance_chances','dp_chances'):summed[k]+=p[k]
                for p in r['batting'][1]:
                    for k in ('fielding_runs','arm_runs','catcher_throw_runs','fielding_chances','arm_chances','steal_attempts_against'):summed[k]+=p[k]
            totals.append(summed)
        for value,opps in (('advance_runs','advance_chances'),('avoid_dp_runs','dp_chances'),('fielding_runs','fielding_chances'),('arm_runs','arm_chances'),('catcher_throw_runs','steal_attempts_against')):
            self.assertGreater(totals[1][value]/totals[1][opps],totals[0][value]/totals[0][opps],value)

if __name__=='__main__':unittest.main()
