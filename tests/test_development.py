from copy import deepcopy
import unittest
from development import develop
from engine import demo_team, player

class DevelopmentTests(unittest.TestCase):
    def test_current_potential_and_deterministic_growth(self):
        p=demo_team('Prospect')['lineup'][0]
        p['age']=19;p['contact']=30;p['speed']=35;p['error']=80
        p['potential']={'contact':90,'speed':80,'error':10}
        p=player(p);other=deepcopy(p)
        r=develop(p,'year2');self.assertEqual(r,develop(other,'year2'))
        self.assertEqual(p,other);self.assertEqual(p['age'],20)
        self.assertTrue(30<p['contact']<=90)
        self.assertTrue(10<=p['error']<80)
        self.assertEqual(p['potential']['contact'],90)
    def test_older_player_declines_without_losing_historical_ceiling(self):
        p=player(demo_team('Veteran')['lineup'][0]);p['age']=36;p['speed']=70;p['potential']={'speed':95}
        develop(p,'year2')
        self.assertLess(p['speed'],70);self.assertEqual(p['potential']['speed'],95)
