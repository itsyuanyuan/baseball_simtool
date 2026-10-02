import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import lan,league
from engine import demo_team
from server import LocalServer,Handler

class LANTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.patches=[patch.object(league,'DB',Path(self.tmp.name)/'league.db'),patch.object(lan,'KEY_FILE',Path(self.tmp.name)/'key')]
        for p in self.patches:p.start()
        self.s=league.create({'teams':[demo_team('A'),demo_team('B',1)],'playoff_teams':2,'games_per_opponent':2,'best_of':1})
        self.key=lan.invite({'id':self.s['id'],'team':0})['key'];self.who=lan.identity(self.key)
        self.server=LocalServer(('127.0.0.1',0),Handler);self.server.lan_mode=True
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        for p in self.patches:p.stop()
        self.tmp.cleanup()
    def post(self,path,body,key='',origin=None):
        headers={'Content-Type':'application/json','Authorization':'Bearer '+key}
        if origin:headers['Origin']=origin
        req=Request(f'http://127.0.0.1:{self.server.server_port}'+path,data=json.dumps(body).encode(),headers=headers)
        try:r=urlopen(req)
        except HTTPError as e:r=e
        return r.status,json.loads(r.read())
    def submission(self,ready=True):
        s=league.get(self.s['id'])
        return dict(id=s['id'],team=0,version=s.get('team_versions',{}).get('0',0),lineup_epoch=s.get('lineup_epoch',0),roster=s['teams'][0],ready=ready)
    def test_http_authorization(self):
        for key in ('',self.key):
            self.assertEqual(self.post('/api/league/advance',{},key)[0],403)
            self.assertEqual(self.post('/api/league/create',{},key)[0],403)
            self.assertEqual(self.post('/api/lan/invite',{},key)[0],403)
            self.assertEqual(self.post('/api/league/next-season',{},key)[0],403)
        self.assertEqual(self.post('/api/team/save',self.submission())[0],403)
        req=self.submission();req['team']=1
        self.assertEqual(self.post('/api/lan/submit',req,self.key)[0],403)
        self.assertEqual(self.post('/api/team/save',req,self.key)[0],403)
        self.assertEqual(self.post('/api/lan/submit',self.submission(),self.key,'http://evil.example')[0],403)
    def test_ready_override_stale_and_stat_identity(self):
        s=league.get(self.s['id'])
        status,_=self.post('/api/league/advance',dict(id=s['id'],version=s['version'],action='day'),lan.host_key())
        self.assertEqual(status,400)
        req=self.submission()
        status,s=self.post('/api/lan/submit',req,self.key);self.assertEqual(status,200)
        self.assertEqual(self.post('/api/lan/submit',req,self.key)[0],400)
        status,s=self.post('/api/league/advance',dict(id=s['id'],version=s['version'],action='day'),lan.host_key());self.assertEqual(status,200)
        self.assertFalse(s['ready']['0'])
        ids={p['name']:p['player_id'] for p in s['teams'][0]['lineup']}
        req=self.submission();req['roster']['lineup'].reverse()
        status,s=self.post('/api/lan/submit',req,self.key);self.assertEqual(status,200)
        status,s=self.post('/api/league/advance',dict(id=s['id'],version=s['version'],action='day'),lan.host_key());self.assertEqual(status,200)
        for p in s['stats']['regular'].values():self.assertEqual(p['G'],2)
        self.assertEqual(len(s['stats']['regular']),18)
        self.assertTrue(all(f'0:{id}' in s['stats']['regular'] for id in ids.values()))
    def test_revocation_and_locked_membership(self):
        stale_who=self.who
        lan.invite({'id':self.s['id'],'team':0})
        with self.assertRaises(PermissionError):lan.identity(self.key)
        with self.assertRaises(PermissionError):lan.submit(self.submission(),stale_who)
        s=league.get(self.s['id'])
        status,s=self.post('/api/league/advance',dict(id=s['id'],version=s['version'],action='day',override_ready=True),lan.host_key())
        self.assertEqual(status,200)
        key=lan.invite({'id':s['id'],'team':0})['key']
        req=self.submission();req['roster']['lineup'][0]['player_id']='fake'
        self.assertEqual(self.post('/api/lan/submit',req,key)[0],400)

    def test_managers_can_submit_independently_but_not_after_advance(self):
        other_key=lan.invite({'id':self.s['id'],'team':1})['key']
        first=self.submission()
        s=league.get(self.s['id'])
        second=dict(id=s['id'],team=1,version=0,lineup_epoch=0,roster=s['teams'][1],ready=True)
        self.assertEqual(self.post('/api/lan/submit',first,self.key)[0],200)
        status,s=self.post('/api/lan/submit',second,other_key)
        self.assertEqual(status,200)
        self.assertTrue(s['ready']['0'] and s['ready']['1'])
        pending=self.submission()
        status,_=self.post('/api/league/advance',dict(id=s['id'],version=s['version'],action='day'),lan.host_key())
        self.assertEqual(status,200)
        self.assertEqual(self.post('/api/lan/submit',pending,self.key)[0],400)

    def test_solo_team_save_without_login_and_rotation(self):
        self.server.lan_mode=False
        req=self.submission();req['roster']['rotation_size']=2
        status,s=self.post('/api/team/save',req)
        self.assertEqual(status,200);self.assertEqual(s['teams'][0]['rotation_size'],2)
        selected=league.roster(s,0,1)
        self.assertEqual(selected['pitchers'][0]['name'],s['teams'][0]['pitchers'][1]['name'])
        self.assertEqual(len(selected['pitchers']),12) # One starter and eleven relievers; other starter rests.

if __name__=='__main__':unittest.main()
