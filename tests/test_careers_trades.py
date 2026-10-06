import tempfile,unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import league,lan,transactions
from engine import demo_team,player
from development import develop

class CareerLeagueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.patches=[patch.object(league,'DB',Path(self.tmp.name)/'league.db'),patch.object(lan,'KEY_FILE',Path(self.tmp.name)/'key')]
        for p in self.patches:p.start()
        self.s=league.create(dict(teams=[demo_team('A'),demo_team('B'),demo_team('C'),demo_team('D')],games_per_opponent=2,playoff_teams=2,best_of=1))
        self.managers=[]
        for team in (0,1):self.managers.append(lan.identity(lan.invite(dict(id=self.s['id'],team=team))['key']))
        self.s=league.get(self.s['id'])
    def tearDown(self):
        for p in self.patches:p.stop()
        self.tmp.cleanup()
    def call(self,action,team=0,who=None,**extra):
        self.s=transactions.transact(dict(id=self.s['id'],version=self.s['version'],team=team,**extra),who or self.managers[team],action)
        return self.s
    def career(self,name):
        p=demo_team('Import')['lineup'][0];p.pop('is_ghost');p.update(name=name,age=19,contact=40,potential={'contact':60},history={'19':{'contact':40,'error':30},'20':{'contact':50,'error':25},'28':{'contact':60,'error':20}})
        return p
    def add(self,team,name,group='lineup',slot=0):
        self.call('import',team,player=self.career(name));career=next(k for k,p in self.s['library'].items() if p['name']==name)
        self.call('assign',team,career_id=career,group=group,slot=slot)
        return self.s['teams'][team][group][slot]['player_id']
    def step(self):
        self.s=league.advance(dict(id=self.s['id'],version=self.s['version'],action='day',override_ready=True))
    def test_midseason_import_shared_library_and_acl(self):
        self.step();self.add(0,'Real A')
        self.assertIn('history',self.s['teams'][0]['lineup'][0])
        self.assertEqual(len(self.s['teams'][0]['lineup']),9)
        with self.assertRaises(PermissionError):self.call('assign',1,who=self.managers[0],career_id=next(iter(self.s['library'])),group='lineup',slot=1)
        with self.assertRaises(ValueError):self.call('assign',1,career_id=next(iter(self.s['library'])),group='lineup',slot=1)
        self.assertEqual(len(league.get(self.s['id'])['library']),1)
    def test_late_invited_manager_can_fill_postseason_ghosts(self):
        self.add(0,'First career')
        while self.s['phase']=='regular':self.step()
        self.s=league.advance(dict(id=self.s['id'],version=self.s['version'],action='playoffs'))
        self.call('import',player=self.career('Late career'))
        career=next(k for k,p in self.s['library'].items() if p['name']=='Late career')
        with self.assertRaises(ValueError):self.call('assign',career_id=career,group='lineup',slot=0)
        self.call('assign',career_id=career,group='bench',slot=0)
        self.assertEqual(self.s['teams'][0]['bench'][0]['name'],'Late career')

    def test_ghost_rejection(self):
        with self.assertRaises(ValueError):self.call('import',player=demo_team('Ghost')['lineup'][0])
        give=self.s['teams'][0]['lineup'][0]['player_id'];take=self.s['teams'][1]['lineup'][0]['player_id']
        with self.assertRaises(ValueError):self.call('propose',other=1,give=give,take=take)
    def test_trade_consent_identity_workload_and_stat_stints(self):
        give=self.add(0,'Real A');take=self.add(1,'Real B');self.step()
        a=deepcopy(self.s['teams'][0]['lineup'][0]);b=deepcopy(self.s['teams'][1]['lineup'][0])
        self.call('propose',other=1,give=give,take=take);offer=self.s['trades'][-1]['id']
        with self.assertRaises(PermissionError):self.call('accept',offer=offer)
        self.call('accept',1,offer=offer)
        self.assertEqual(self.s['teams'][0]['lineup'][0],b);self.assertEqual(self.s['teams'][1]['lineup'][0],a)
        self.assertFalse(self.s['ready']['0']);self.assertFalse(self.s['ready']['1'])
        self.step()
        self.assertEqual(self.s['stats']['regular']['0:'+give]['G'],1)
        self.assertEqual(self.s['stats']['regular']['1:'+give]['G'],1)
        with self.assertRaises(ValueError):self.call('accept',1,offer=offer)
    def test_stale_offer_and_revoked_invite(self):
        give=self.add(0,'Real A');take=self.add(1,'Real B')
        self.call('propose',other=1,give=give,take=take);offer=self.s['trades'][-1]['id']
        self.add(1,'Replacement')
        with self.assertRaises(ValueError):self.call('accept',1,offer=offer)
        self.assertEqual(self.s['trades'][-1]['status'],'pending')
        lan.invite(dict(id=self.s['id'],team=0));self.s=league.get(self.s['id'])
        with self.assertRaises(PermissionError):self.call('cancel',offer=offer)
    def test_pitcher_batter_trade_blocked_and_stale_revision(self):
        give=self.add(0,'Bat');take=self.add(1,'Pitch',group='pitchers')
        with self.assertRaises(ValueError):self.call('propose',other=1,give=give,take=take)
        with self.assertRaises(ValueError):transactions.transact(dict(id=self.s['id'],version=-1,team=0,player=self.career('X')),self.managers[0],'import')
    def test_replacement_reacquisition_keeps_energy_age_identity(self):
        identity=self.add(0,'A');self.step();original=deepcopy(self.s['teams'][0]['lineup'][0]);self.add(0,'B')
        self.call('assign',career_id=original['career_id'],group='lineup',slot=0)
        self.assertEqual(self.s['teams'][0]['lineup'][0],original)
    def test_pitching_accounting_and_backfill(self):
        self.step();stats=self.s['pitching_stats']['regular'];bat=self.s['stats']['regular']
        self.assertEqual(sum(p['SO'] for p in stats.values()),sum(p['SO'] for p in bat.values()))
        self.assertEqual(sum(p['HR'] for p in stats.values()),sum(p['HR'] for p in bat.values()))
        self.assertEqual(sum(p['R'] for p in stats.values()),sum(p['R'] for p in bat.values()))
        self.assertEqual(sum(p['BF'] for p in stats.values()),sum(p['AB']+p['BB']+p['HBP']+p['SF'] for p in bat.values()))
        self.assertEqual(sum(p['GS'] for p in stats.values()),4)
        self.s.pop('pitching_stats')
        with league.connect() as c:league.save(c,self.s)
        self.assertEqual(league.get(self.s['id'])['pitching_stats']['regular'],stats)
    def test_legacy_pitching_events_backfill_without_new_counters(self):
        import json
        self.step();expected=deepcopy(self.s['pitching_stats'])
        with league.connect() as c:
            for game_id,body in c.execute('SELECT game_id,result FROM games WHERE league_id=?',(self.s['id'],)).fetchall():
                result=json.loads(body)
                for side in result['pitching']:
                    for p in side:
                        for key in ('player_id','BF','HR','HBP'):p.pop(key,None)
                c.execute('UPDATE games SET result=? WHERE league_id=? AND game_id=?',(json.dumps(result),self.s['id'],game_id))
            self.s.pop('pitching_stats');league.save(c,self.s)
        self.assertEqual(league.get(self.s['id'])['pitching_stats'],expected)

    def test_roster_edit_cannot_turn_ghost_into_tradeable_career(self):
        t=deepcopy(self.s['teams'][0]);t['lineup'][0].update(career_id='forged',is_ghost=False)
        result=lan.submit(dict(id=self.s['id'],team=0,version=0,lineup_epoch=0,roster=t),self.managers[0])
        self.assertTrue(result['teams'][0]['lineup'][0]['is_ghost'])
        self.assertNotIn('career_id',result['teams'][0]['lineup'][0])

    def test_history_growth_performance_and_exceeding_peak(self):
        p=player(self.career('Youth'));p['contact']=59;p['potential']['contact']=60
        other=deepcopy(p);good={'AB':400,'H':150,'BB':80,'HBP':0,'SF':5};bad={'AB':400,'H':50,'BB':10,'HBP':0,'SF':5}
        r=develop(p,'same',good);develop(other,'same',bad)
        self.assertGreater(p['contact'],60);self.assertGreater(p['contact'],other['contact']);self.assertEqual(p['potential']['contact'],60)
        self.assertEqual(r['components']['contact']['source'],'history');self.assertEqual(r['components']['contact']['base'],10)
        self.assertLess(p['error'],30)
        self.assertEqual(player(p)['potential']['contact'],60)
    def test_history_decline_interpolation_and_pitching_performance(self):
        p=player(self.career('Pitch'));p.update(age=35,velocity=80,history={'34':{'velocity':80},'36':{'velocity':70}})
        other=deepcopy(p);r=develop(p,'same',pitching={'BF':600,'SO':220,'BB':30});develop(other,'same',pitching={'BF':600,'SO':80,'BB':100})
        self.assertLess(p['velocity'],80);self.assertGreater(p['velocity'],other['velocity']);self.assertEqual(r['components']['velocity']['base'],-5)
    def test_save_preserves_identity_before_opening_day(self):
        identity=self.add(0,'Real A');t=deepcopy(self.s['teams'][0]);t['lineup'][0]['contact']=100
        self.s=lan.submit(dict(id=self.s['id'],team=0,version=self.s['team_versions']['0'],lineup_epoch=self.s.get('lineup_epoch',0),roster=t),self.managers[0])
        self.assertEqual(self.s['teams'][0]['lineup'][0]['player_id'],identity);self.assertEqual(self.s['teams'][0]['lineup'][0]['contact'],40)

if __name__=='__main__':unittest.main()
