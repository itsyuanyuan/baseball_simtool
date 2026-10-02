import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from collections import Counter
import league
from engine import demo_team

class LeagueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=patch.object(league,'DB',Path(self.tmp.name)/'test.sqlite3')
        self.db.start()
    def tearDown(self):
        self.db.stop();self.tmp.cleanup()
    def create(self,n=4,best=3):
        return league.create(dict(name='Test',teams=[demo_team(f'Team {i}',i) for i in range(n)],games_per_opponent=2,playoff_teams=n,best_of=best))
    def step(self,s,action='batch'):
        return league.advance(dict(id=s['id'],version=s['version'],action=action))
    def test_balanced_schedule(self):
        for n in range(2,17,2):
            games=league.schedule(n,4)
            counts=Counter((g['away'],g['home']) for g in games)
            self.assertEqual(len(games),n*(n-1)*2)
            self.assertTrue(all(counts[a,b]==2 for a in range(n) for b in range(n) if a!=b))
            for day in set(g['day'] for g in games):
                participants=[t for g in games if g['day']==day for t in (g['away'],g['home'])]
                self.assertEqual(sorted(participants),list(range(n)))
    def test_full_season_resume_playoffs_and_stats(self):
        s=self.create()
        with self.assertRaises(ValueError):self.step(s,'playoffs')
        s=self.step(s)
        self.assertEqual(s,league.get(s['id']))
        self.assertEqual(s['phase'],'ready')
        self.assertEqual(sum(r['W'] for r in s['standings']),12)
        self.assertEqual(sum(r['L'] for r in s['standings']),12)
        self.assertEqual(sum(r['RF'] for r in s['standings']),sum(r['RA'] for r in s['standings']))
        self.assertTrue(all(r['GP']==6 for r in s['standings']))
        self.assertEqual(sum(p['G'] for p in s['stats']['regular'].values()),4*6*9)
        old=s
        s=self.step(s,'playoffs')
        with self.assertRaises(ValueError):self.step(old,'playoffs')
        for _ in range(20):
            if s['phase']=='complete':break
            s=self.step(s,'day')
        self.assertEqual(s['phase'],'complete')
        self.assertIn(s['champion'],range(4))
        self.assertEqual(len(s['rounds']),2)
        self.assertEqual(s['standings'],old['standings'])
        for r in s['rounds']:
            for series in r['series']:
                self.assertEqual(max(series['wins']),2)
                self.assertLessEqual(len(series['games']),3)
                for game in series['games']:
                    detail=league.game(s['id'],game['id'])
                    self.assertFalse(detail['tie'])
                    self.assertEqual(detail['score'],game['score'])
    def test_rollback_on_failed_batch(self):
        s=self.create()
        with patch.object(league,'simulate',side_effect=ValueError('failure')):
            with self.assertRaises(ValueError):self.step(s)
        self.assertEqual(s,league.get(s['id']))
    def test_two_team_single_game_final(self):
        s=self.create(2,1)
        s=self.step(s);s=self.step(s,'playoffs');s=self.step(s)
        self.assertEqual(s['phase'],'complete')
        self.assertEqual(len(s['rounds'][0]['series'][0]['games']),1)

    def test_next_season_archives_and_preserves_league(self):
        s=self.create(2,1)
        s['teams'][0]['lineup'][0]['age']=19
        s['teams'][0]['lineup'][0]['contact']=30
        s['teams'][0]['lineup'][0]['potential']={'contact':90}
        with league.connect() as conn:league.save(conn,s)
        s=self.step(s);s=self.step(s,'playoffs');s=self.step(s)
        old_score=league.game(s['id'],'r1')['score'];old=s
        s=league.next_season({'id':s['id'],'version':s['version']})
        self.assertEqual(s['id'],old['id']);self.assertEqual(s['season'],2)
        self.assertEqual(s['teams'][0]['lineup'][0]['age'],20)
        self.assertGreater(s['teams'][0]['lineup'][0]['contact'],30)
        self.assertEqual(s['stats'],{'regular':{},'playoffs':{}})
        self.assertEqual(league.archive(s['id'],1)['champion'],old['champion'])
        self.assertEqual(league.game(s['id'],'r1')['score'],old_score)
        with self.assertRaises(ValueError):league.next_season({'id':s['id'],'version':old['version']})
        s=self.step(s)
        self.assertEqual(league.game(s['id'],'y2r1')['model_version'],s['model_version'])
        s=self.step(s,'playoffs');s=self.step(s)
        self.assertEqual(s['phase'],'complete')
        self.assertEqual(league.game(s['id'],'y2p1s1g1')['score'],s['rounds'][0]['series'][0]['games'][0]['score'])
        self.assertEqual(league.game(s['id'],'p1s1g1')['score'],old['rounds'][0]['series'][0]['games'][0]['score'])

if __name__=='__main__':unittest.main()
