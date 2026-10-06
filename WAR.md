# Simulator WAR estimate

The League page defaults to **Standard** batting/pitching statistics. **Advanced** adds rate statistics and WAR* without removing any standard counters. Both views use the selected regular-season or playoff data.

WAR* is an original approximate wins-above-replacement model, not fWAR or bWAR. It uses 10 runs per win. Batting and pitching contributions are separate; add both for a two-way player. Values accumulate with playing time rather than being projected to 162 games.

- Batting runs: `(wOBA* - league wOBA*) / 1.20 * PA`. Fixed weights for BB/HBP/1B/2B/3B/HR are .69/.72/.89/1.27/1.62/2.10. The denominator is PA (AB+BB+HBP+SF); the engine does not model intentional walks or sacrifice bunts.
- Stolen-base runs: `.20*SB - .40*CS`, centered on the league's PA-weighted rate. Other advancement is not included.
- Position runs per 162 recorded starts: C +12.5, SS +7.5, 2B/3B/CF +2.5, LF/RF -7.5, 1B -12.5, DH -17.5. Starts approximate workload; individual fielding is treated as neutral.
- Replacement runs: `20*PA/600`.
- Batting WAR*: `(batting runs + stolen-base runs + position runs + replacement runs)/10`.
- Pitching WAR*: `(league FIP* + 1.00 - pitcher FIP*) * IP/9/10`. League FIP* is innings-weighted. The fixed 3.10 FIP constant cancels in the relative comparison. The replacement allowance is the same for starters and relievers.

There are no park, leverage, fielding, framing or league-wide WAR-total corrections. This is a transparent simulator estimate, not a calibrated reproduction of a published WAR system. Missing legacy doubles/triples or positional-start history yield unavailable batting WAR; incomplete league event counters also disable the affected league baseline. No past positional usage is guessed from the player's current roster slot. Stats remain separated by team stint after trades, with additive WAR within a shared phase baseline.

Framework references: [position-player WAR](https://library.fangraphs.com/war/war-position-players/), [pitcher WAR](https://library.fangraphs.com/war/calculating-war-pitchers/), [wOBA](https://library.fangraphs.com/offense/woba/). Fixed simulator coefficients and omissions are described above and in the UI.
