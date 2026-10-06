# Player careers

Open **Player careers** from the league or team page, or click a player name on your team. The page keeps regular-season and playoff batting/pitching statistics separate, offers Standard and Advanced views, and shows each team stint, league season ratings, and recorded roster/development events. Stable player IDs keep players with identical names separate.

Imported `{S, Seed}` saves retain the entire original `S` object, including every `pastab` age, traits, and original career statistics. Seed is ignored. Starting age initializes current ability; it does not discard other ages. Original career statistics are shown as reference data and never added to simulated league totals. Normalized ability history supplies development slopes; potential remains a reference peak rather than a hard ceiling.

Older imports retain whatever history was saved at the time. Reimport the original career to restore its raw source details. Missing old events or ratings cannot be reconstructed reliably and are not invented.

League ghost players start with every displayed ability at 20 at age 16, rise linearly to 50 at age 26, remain average through age 31, then follow aging. These values include fielding/error prevention, speed and sequencing. Existing identifiable placeholders adopt this curve once; imported careers keep their own histories. Ghosts remain ineligible for trades.

WAR now includes baserunning and defensive run estimates; see [WAR methodology](WAR.md). New games record the required opportunities. Old games cannot provide these event-level values retrospectively, so incomplete WAR coverage is displayed as unavailable rather than zero.
