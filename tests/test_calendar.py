from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import league, rosters, lan
from engine import demo_team

class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=patch.object(league,'DB',Path(self.tmp.name)/'league.db');self.db.start()
        self.s=league.create(dict(teams=[demo_team('A'),demo_team('B')],games_per_opponent=8,playoff_teams=2,best_of=1))
    def tearDown(self):
        self.db.stop();self.tmp.cleanup()
    def step(self,action='day'):
        self.s=league.advance(dict(id=self.s['id'],version=self.s['version'],action=action))
        return self.s
    def test_daily_fatigue_off_day_and_persistence(self):
        self.assertEqual(sum(len(self.s['teams'][0][g]) for g in rosters.GROUPS),26)
        self.step()
        first=self.s['teams'][0]['pitchers'][0]['energy']
        self.assertLess(first,100)
        self.assertEqual(self.s,league.get(self.s['id']))
        self.step()
        self.assertGreater(self.s['teams'][0]['pitchers'][0]['energy'],first)
        while self.s['calendar_day']<6:self.step()
        before=deepcopy(self.s)
        self.step()
        self.assertEqual(self.s['calendar_day'],7)
        self.assertEqual(self.s['stats'],before['stats'])
        self.assertEqual(self.s['calendar_date'],'2026-04-07')
        self.assertTrue(all(p['energy']>=q['energy'] for g in rosters.GROUPS for p,q in zip(self.s['teams'][0][g],before['teams'][0][g])))
        self.step();self.assertEqual(self.s['calendar_day'],8)
    def test_automatic_replacement_and_stats_identity(self):
        t=self.s['teams'][0];t['lineup'][0]['energy']=0;t['pitchers'][0]['energy']=0
        reserve=t['bench'][0]['player_id'];original=t['lineup'][0]['player_id']
        with league.connect() as c:league.save(c,self.s)
        self.step()
        self.assertIn('0:'+reserve,self.s['stats']['regular'])
        self.assertNotIn('0:'+original,self.s['stats']['regular'])
        self.assertEqual(self.s['stats']['regular']['0:'+reserve]['position_games'],{'C':1})
        row=self.s['stats']['regular']['0:'+reserve]
        self.assertEqual(row['value_games'],1)
        self.assertIn('catcher_throw_runs',row)
        self.assertEqual(league.get(self.s['id'])['stats']['regular']['0:'+reserve],row)
        t=self.s['teams'][0]
        self.assertEqual(t['lineup'][0]['player_id'],original)
        self.assertLess(t['bench'][0]['energy'],100)
        self.assertLess(t['pitchers'][1]['energy'],100)
        self.assertLess(t['pitchers'][0]['energy'],40)
    def test_manual_bench_swap_preserves_condition_and_abilities(self):
        self.step();t=deepcopy(self.s['teams'][0]);reserve=t['bench'][0];old=t['lineup'][0]
        t['lineup'][0],t['bench'][0]=reserve,old
        t['lineup'][0]['contact']=100;t['lineup'][0]['energy']=100
        s=lan.submit(dict(id=self.s['id'],team=0,version=0,lineup_epoch=self.s['lineup_epoch'],roster=t),{'role':'commissioner'})
        self.assertEqual(s['teams'][0]['lineup'][0],self.s['teams'][0]['bench'][0])
        self.assertEqual(s['teams'][0]['bench'][0],old)
    def test_legacy_playoff_id_recovery(self):
        while self.s['phase']=='regular':self.step('batch')
        self.step('playoffs');self.step('next')
        self.s=league.next_season(dict(id=self.s['id'],version=self.s['version']))
        while self.s['phase']=='regular':self.step('batch')
        self.step('playoffs')
        self.s['rounds'][0]['series'][0]['id']='p1s1'
        self.s.pop('roster_version')
        with league.connect() as c:league.save(c,self.s)
        self.step('next')
        self.assertEqual(self.s['phase'],'complete')
        self.assertEqual(self.s['rounds'][0]['series'][0]['games'][0]['id'],'y2p1s1g1')
    def test_veterans_and_bench_age_and_condition_resets(self):
        for g in rosters.GROUPS:
            for p in self.s['teams'][0][g]:p['age']=36
        with league.connect() as c:league.save(c,self.s)
        while self.s['phase']=='regular':self.step('batch')
        self.step('playoffs');self.step('next');old=deepcopy(self.s)
        self.s=league.next_season(dict(id=self.s['id'],version=self.s['version']))
        for g in rosters.GROUPS:
            for p,q in zip(self.s['teams'][0][g],old['teams'][0][g]):
                self.assertEqual(p['age'],37);self.assertLess(p['stamina'],q['stamina']);self.assertEqual(p['energy'],100)
        self.assertEqual(len(self.s['development_report']),52)
