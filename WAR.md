# Simulator WAR estimate

The League page defaults to **Standard** batting/pitching statistics. **Advanced** adds rate statistics and WAR* without removing any standard counters. Both views use the selected regular-season or playoff data.

WAR* is an original approximate wins-above-replacement model, not fWAR or bWAR. It uses 10 runs per win. Batting and pitching contributions are separate; add both for a two-way player. Values accumulate with playing time rather than being projected to 162 games.

- Batting runs: `(wOBA* - league wOBA*) / 1.20 * PA`. Fixed weights for BB/HBP/1B/2B/3B/HR are .69/.72/.89/1.27/1.62/2.10. The denominator is PA (AB+BB+HBP+SF); the engine does not model intentional walks or sacrifice bunts.
- Stolen-base runs: `.20*SB - .40*CS`, centered on the league's PA-weighted rate. Extra-base advancement and double-play avoidance are added separately (below).
- Position runs per 162 recorded starts: C +12.5, SS +7.5, 2B/3B/CF +2.5, LF/RF -7.5, 1B -12.5, DH -17.5. Starts approximate workload; tracked individual defense is added separately.
- Replacement runs: `20*PA/600`.
- Batting WAR*: `(batting runs + BsR + defensive runs + position runs + replacement runs)/10`. BsR includes stolen-base, advancement and double-play-avoidance runs.
- Pitching WAR*: `(league FIP* + 1.00 - pitcher FIP*) * IP/9/10`. League FIP* is innings-weighted. The fixed 3.10 FIP constant cancels in the relative comparison. The replacement allowance is the same for starters and relievers.

There are no park, leverage, framing or league-wide WAR-total corrections. This is a transparent simulator estimate, not a calibrated reproduction of a published WAR system. Missing legacy doubles/triples or positional-start history yield unavailable batting WAR; incomplete league event counters also disable the affected league baseline. No past positional usage is guessed from the player's current roster slot. Stats remain separated by team stint after trades, with additive WAR within a shared phase baseline.

Framework references: [position-player WAR](https://library.fangraphs.com/war/war-position-players/), [pitcher WAR](https://library.fangraphs.com/war/calculating-war-pitchers/), [wOBA](https://library.fangraphs.com/offense/woba/). Fixed simulator coefficients and omissions are described above and in the UI.


## Opportunity-based running and defense (engine 0.6)

The `value_events` game ledger records the play index, player identity/slot, component, observed result, neutral probability, fixed run weight, and resulting contribution. Box scores and season totals include opportunity counts and component sums. The new Fielding / running view shows standard counts and advanced components. Existing Standard batting and pitching stats remain intact.

For a beneficial outcome, contribution is `(observed success - neutral success probability) * run weight`. Neutral replaces only the relevant skill(s) with engine rating 50, keeping the opposing player and the actual opportunity fixed. Probabilities use the same bounds/formulas as simulation. Values are outcome-based residuals, so luck matters: a neutral player can gain or lose runs in one game; the expectation is zero over many matched opportunities. They are not automatic bonuses for high ratings. No extra RNG calls or altered game outcomes are introduced by accounting.

| Component | Recorded opportunity | Neutral comparison | Run weight |
|---|---|---|---|
| Advancement | First to third on a single | Runner speed 50, same fielder arm | .20 |
| Advancement | Second to home on a single; first to home on a double | Runner speed 50, same fielder arm | .40 |
| DP avoidance | Field out with first occupied and fewer than two outs | Batter speed 50, same fielder | .45 |
| Fielding | Non-HR ball directed at selected fielder | Range/error 50, same batter contact and speed; success means no hit/error | .75 |
| Fielding DP | Eligible double-play opportunity | Fielder range/arm 50, same batter speed | .45 |
| Arm | Runner advancement on a hit | Fielder arm 50, same runner speed | .20/.40 |
| Arm | Productive-out advance from second or third | Fielder arm 50 | .20/.40 |
| Catcher throws | Attempt to steal second | Catcher arm 50, same runner speed | .60 |

A fielding out and a double play refer to separate outs. Productive-out arm value is counted only with an eligible runner. Optional advancement is not credited after a walk-off has already ended the contest. Catcher throwing values are defensive contributions; framing and sequencing value remain deferred. Position adjustment is distinct from individual fielding performance.

`BsR = league-centered stolen-base runs + advance_runs + avoid_dp_runs`.
`Def Runs = fielding_runs + arm_runs + catcher_throw_runs`.
WAR adds each of these once. Speed-created infield hits and triples remain in batting value; they receive no additional running bonus. The selected fielder gets fielding credit; the engine does not split assists across a double-play combination. Pitcher WAR stays FIP-based and does not separately credit these ball-in-play/throwing outcomes.

This is still a simplified simulator valuation, not empirical UZR/DRS or a base/out run-expectancy model. Weights are fixed approximations; fielders are chosen by the existing uniform selection model, not a measured batted-ball trajectory. The 50-rated neutral benchmark need not equal a custom league's actual average talent.

Only newly simulated games have this ledger. `value_games` counts covered appearances; mixed old/new season totals show tracked-game counts and opportunity totals, but full-season BsR, defensive runs and WAR remain unavailable unless all appearances are covered. Old games are not replayed or reconstructed from current ratings. New player identities (including bench starters and traded team stints) preserve attribution. This extends the formula, so older WAR displays may become unavailable until a fully tracked season is played.
