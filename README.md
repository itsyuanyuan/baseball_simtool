# Diamond Lab

Standalone HTML/CSS/JavaScript frontend with a dependency-free Python 3 simulation backend. An original prototype inspired by baseball management games, not a recreation of OOTP's proprietary model.

## Run

Run `python server.py` from this directory, then open http://127.0.0.1:8000. Python 3.10+ is sufficient. Do not open the HTML directly: it needs the local API. The service binds to localhost only.

## League mode

Open `/league.html` to create a custom season with 2–16 teams (even counts), 2–20 games per opponent (even counts), a 2/4/8/16-team playoff field, and best-of-1/3/5/7 series. Each team plays every opponent equally, with balanced home/away games. Rename teams, assign imported Player Vault snapshots, and rearrange the batting order before creating the season. Rosters lock at creation. First three pitcher slots rotate as starters; the fourth relieves. Players currently recover fully between games; no injuries, roster transactions, fantasy point scoring, or persistent pitcher fatigue.

Simulate the next game, next day, or the rest of the regular season. Season simulation commits batches of at most 20 games and can be stopped between batches. Start playoffs after the regular season completes, then advance games or playoff days through the championship. Standings use win percentage, run differential, runs scored and original team order as tiebreakers. Playoffs reseed every round (highest versus lowest); higher seeds host odd games in shorter series and games 1,2,5,7 in best-of-seven. League games extend beyond twelve innings; a 100-inning safety limit rolls back the batch if no winner emerges. Exhibition games retain their twelve-inning limit.

Leagues, cumulative regular-season/postseason batting stats and full individual game records persist in `data/leagues.sqlite3`. Reopening the page loads your active league. Back up that database with the server stopped for a complete backup; the season JSON export includes rosters, schedule, standings, bracket and batting totals, but omits individual pitch logs and has no restore UI yet. Open a completed game to view batting/pitching box scores and pitch logs. Concurrent tabs use a revision check to prevent duplicate advancement; reopen the saved league after an ambiguous network failure. No authentication or remote hosting is provided. Engine version changes block continuation of older-version leagues.

## Use your Yakyolife players

1. Export a JSON object containing `name` and `pastab`, where each key is the player's age and each value contains that year's abilities. See `example-player.json`. A top-level age dictionary, `state.pastab`, and a single flat player are also accepted.
2. Import it in Player Vault, select an age and source rating scale, and map the numeric source fields to the engine ratings. Nested `ratings` or `abilities` containers are supported. Other custom structures must be flattened first.
3. Save the snapshot, then click a batting or pitching slot. The slot assigns the position. Repeat to build both teams; remaining slots use demo players.
4. Set a seed and park, then Play ball. Export the result JSON to keep a game record.

Saved snapshots persist in browser localStorage. Rosters and results currently last only for the page session. Re-importing can create duplicates. There is no connection to your other PC or automatic modification to retire.json/state.js; the exact upstream save integration needs your source files.

## Rating contract

All engine ratings are 0–100. Higher is better except `error`, where higher means more errors. Missing imported ratings visibly default to 50, or 20 for error. Velocity is a relative quality rating, not raw mph/km/h. The import scale applies to all mapped ratings; normalize mixed-unit saves before importing.

The importer defaults to **Yakyolife 0–80 (clamp to 20–80)**. It applies `round((clamp(raw, 20, 80) - 20) / 60 * 100)`, so raw 0–20 becomes engine 0, raw 50 remains engine 50, and raw 80 or above becomes engine 100. This applies to every mapped rating; missing-field defaults are already in engine units and are not converted again. Existing saved browser snapshots are left unchanged: re-import incorrectly scaled ones from the original save. The bundled `example-player.json` now uses the actual abbreviated source format; select **Yakyolife 0–80**. The API still expects normalized engine ratings; a future SQLite adapter should apply this conversion when reading raw JSON, not alter the original stored career history. SQLite integration is not implemented without the database schema/file. Test conversion with `node --test tests/ratings.test.js`.

`stamina`, `contact`, `power`, `eye`, `velocity`, `movement`, `control`, `range`, `error`, `arm`, `sequencing` are required by the API. Age is metadata: the selected snapshot already incorporates development/decline, so the engine does not apply age decline again. Pitch sequencing combines count-based pitch choice, a sequencing rating, and a repeated-pitch penalty.

## Model and limits

Each pitch resolves zone location, swing decision, contact, and ball in play. Fatigue lowers pitching quality; the bullpen replaces tired pitchers between batters. Batted balls resolve home runs, fielding errors, hits, outs, and double plays. Runner advancement depends on hit type and the fielder's arm. Lineups use a universal DH and each defensive position once. Games use nine innings, walk-offs, and up to twelve innings; unresolved games are ties.

Version 0.2 calibrates aggregate batting and scoring to the 2025 MLB baseline, with tunable coefficients in `engine.py`. It adds HBP, sacrifice flies, and extra-base advancement. Individual player profiles remain experimental. It omits handedness, pitch repertoires, steals/speed, sacrifice bunts, wild pitches, injuries, position proficiency, earned runs, and tactical substitutions. Fielders are sampled uniformly rather than from a batted-ball trajectory. Productive outs are simplified; non-homer walk-offs stop scoring at the winning run, although official hit-type reduction is not implemented. Pitcher R includes inherited runners charged to their original pitcher. Error tendency is a rating, not a literal percentage. A 30-pitch plate-appearance cap forces a ball in play; an extreme 250-PA half inning returns an error. Pitch counts remain low (about 3.36 pitches/PA); pitch-level distributions have not been calibrated.

## API and validation

### Statistical checks

Run `python checks.py` to reproduce 10,000 average-vs-average validation games and 5,000 fresh-pitcher plate appearances for each of six hitter/pitcher pairings. Open `/checks.html` for the comparison with the 2025 MLB average and the Schwarber-like/Ichiro-like archetypes. `public/checks.json` records results, sample sizes, model hash and coefficients; `public/checks-before.json` preserves version 0.1. Optional `--games` and `--matchups` arguments adjust sample sizes. First-PA experiments deliberately exclude fatigue, bullpen differences and runner context; the full-game baseline retains those effects.

Calibration used up to 4,000 `train-v2-*` seeds through `python calibrate.py --games 4000`. Coefficients were frozen before evaluating 10,000 separate `holdout-v2-*` seeds. The regression test uses a third `regression-v2-*` seed set. The holdout produced .2477 AVG, .3163 OBP, .4062 SLG, 4.416 runs/team-game, 1.194 HR/team-game, 22.10% K and 8.38% BB. Targets are .245/.315/.404, 4.45 runs, 1.160 HR, 22.22% K and 8.41% BB, from the rounded 2025 Baseball-Reference league-average row. This matches selected aggregate metrics, not every MLB statistic or the full distribution of player ability. No deGrom-specific tuning has been done. Seed reproducibility applies within an engine version; v0.2 changes previous game outcomes.

`GET /api/demo` returns two example teams. `POST /api/simulate` accepts `{away, home, seed, park}`; each team has `name`, nine `lineup` players with positions C/1B/2B/3B/SS/LF/CF/RF/DH, and 1–12 `pitchers`. Park is 0.7–1.3. Response includes scores, innings, batting/pitching stats, and pitch logs.

Run `python -m unittest discover -s tests -v`. Seven tests cover deterministic seeds, score/hit/pitch/run accounting, HBP/SF/PA accounting and walk-offs, input validation, contact's effect on strikeouts, and aggregate regression tolerances across 1,000 games. No third-party Python packages required. Fonts optionally load from Google Fonts; system fonts work offline.


## Actual Yakyolife save fields

The importer maps `sta` → stamina, `con` → contact, `pow` → power, `eye` → eye, `vel` → velocity, `brk` → movement, `ctl` → control, `rng` → defensive range, `arm` → arm, and `cat` → pitch sequencing. There is no catching ability. Higher `fld` means better error prevention: normalize it, then invert it for the engine's lower-is-better error tendency (`100 - normalized fld`). This is the default; the importer also retains a manual error-tendency option for other formats.

Pitcher-only, fielder, catcher and two-way snapshots may omit unrelated abilities. Missing engine ratings default to 50, except error tendency defaults to 20, and these defaults are displayed before saving. A catcher without `rng` uses neutral range; `cat` is never used as defensive range. Role detection uses the fields in the selected age snapshot. A combined batting/pitching snapshot is two-way, even if it also contains `cat`.

The catcher's sequencing modifies the current pitcher's sequencing as `clamp(pitcher sequencing + catcher sequencing - 50, 0, 100)`. Thus a source pitcher without `cat` defaults to 50, and the catcher supplies the sequencing quality. This is a simple original model, not a verified Yakyolife formula. Neutral catchers preserve the calibrated all-50 baseline. Existing stored snapshots are not rewritten; re-import from the original JSON to apply corrected mappings. Assign a catcher to the C slot for their sequencing to apply.
