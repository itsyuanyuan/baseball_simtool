"""Opportunity-based run-value accounting; never draws random numbers.

Values are outcome residuals against a 50-rated replacement of the relevant
runner/fielder, with the opposing player and game opportunity held fixed.
These fixed run weights are simulator approximations, not empirical DRS/UZR.
"""
COMPONENTS=('advance_runs','avoid_dp_runs','fielding_runs','arm_runs','catcher_throw_runs')
COUNTERS=('advance_chances','extra_bases','dp_chances','double_plays_hit_into',
          'fielding_chances','fielding_outs','fielding_errors','dp_field_chances',
          'double_plays_turned','arm_chances','advances_allowed',
          'steal_attempts_against','caught_stealing_against')

def probability(value):
    return max(.005,min(.995,value))

class RunValueLedger:
    def __init__(self,teams,batting):
        self.teams=teams;self.batting=batting;self.events=[];self.play_index=0
        for side in batting:
            for p in side:
                p.update({k:0 for k in (*COMPONENTS,*COUNTERS)})
                p['value_games']=1

    def record(self,side,slot,component,kind,observed,neutral,weight,**counters):
        row=self.batting[side][slot]
        value=(int(observed)-neutral)*weight
        row[component]+=value
        for key,n in counters.items():row[key]+=n
        player=self.teams[side]['lineup'][slot]
        self.events.append(dict(play_index=self.play_index,team=side,slot=slot,
            player_id=player.get('player_id'),name=player['name'],component=component,
            kind=kind,observed=int(observed),neutral_probability=neutral,
            run_weight=weight,runs=value))
