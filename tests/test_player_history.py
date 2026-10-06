import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import development, ghosts, league, player_history, transactions
from engine import demo_team


class PlayerHistoryTests(unittest.TestCase):
    def test_ghost_curve_and_aging(self):
        p=ghosts.initialize({'name':'Ghost','age':16})
        self.assertTrue(all(20+.6*(100-v if k=='error' else v)==20 for k,v in ghosts.ratings(16).items()))
        for age in range(17,32):
            development.develop(p,age,{'AB':600,'H':300})
            self.assertEqual(p['age'],age)
            self.assertEqual({k:p[k] for k in ghosts.KEYS},ghosts.ratings(age))
        self.assertTrue(all(v==50 for v in ghosts.ratings(26).values()))
        development.develop(p,32)
        self.assertLess(p['speed'],50)
        self.assertGreater(p['error'],50)

    def test_full_source_and_two_season_history(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(league,'DB',Path(tmp)/'league.sqlite3'):
            s=league.create(dict(name='History',teams=[demo_team('A',1),demo_team('B',2)],games_per_opponent=2,playoff_teams=2,best_of=1))
            original={'name':'Career','pastab':{'16':{'con':20},'26':{'con':70}},'trait':'Patient','career stat':{'H':123}}
            p={**ghosts.ratings(16),'name':'Career','age':16,'contact':0,'history':{'16':{'contact':0},'26':{'contact':83}},'source_career':original}
            def transaction(action,**kw):
                return transactions.transact(dict(id=s['id'],version=s['version'],team=0,**kw),{'role':'commissioner'},action)
            s=transaction('import',player=p)
            career=next(iter(s['library']))
            departed=s['teams'][0]['lineup'][0]['player_id']
            s=transaction('assign',group='lineup',slot=0,career_id=career)
            active=s['teams'][0]['lineup'][0];pid=active['player_id']
            self.assertNotIn('source_career',active)
            first=player_history.profile(s['id'],pid)
            self.assertEqual(first['source_career'],original)
            self.assertEqual(set(first['history']),{'16','26'})
            self.assertTrue(first['events'])
            self.assertEqual(player_history.profile(s['id'],departed)['status'],'Departed')
            for action in ('batch','playoffs','batch'):
                s=league.advance(dict(id=s['id'],version=s['version'],action=action))
            self.assertEqual(s['phase'],'complete')
            s=league.next_season(dict(id=s['id'],version=s['version']))
            second=player_history.profile(s['id'],pid)
            self.assertEqual([r['season'] for r in second['seasons']],[1,2])
            self.assertEqual([r['age'] for r in second['seasons']],[16,17])
            self.assertTrue(second['seasons'][0]['batting'])
            self.assertEqual(second['source_career'],original)
            self.assertEqual(league.get(s['id']),s)
            self.assertIn(pid,{p['id'] for p in player_history.directory(s['id'])})
            with self.assertRaises(ValueError):player_history.profile(s['id'],'missing')
