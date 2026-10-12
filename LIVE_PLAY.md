# Live practice

Open `/live.html` or **LIVE PRACTICE** on the home page. Play three offensive innings with mouse/touch aiming and swing timing. Press Next pitch, aim your cursor, and click or press Space as the ball arrives. On touch screens drag to aim and use Swing. Take pitch lets it pass. Four balls award a walk; three strikes retire the batter; three outs clear the bases and advance the inning.

The field view uses metres and seconds. Batted-ball launch speed, direction and angle come from aim, timing, contact and power. Fielders react, run toward the ball, attempt catches/pickups, and throw to a base. Runners travel the basepaths; the throw's arrival determines an out or safe play. Send runners advances them toward the next base and Hold stops optional advancement at the next base. Steal second starts a runner/catcher race with first occupied and second empty.

Use Players & practice setup to change ratings or select players from a saved league. Source ratings display on 20–80. League defense uses the second team's starting lineup. Catcher range is ignored; catching/pickup errors and arm still matter.

This is a standalone first prototype. Practice results do not enter league statistics or standings. Field geometry, reaction times, movement, launch physics and throws are experimental and not calibrated to MLB. Defense currently makes one throw per play; tag-ups, relays, collisions, injuries and catcher framing are not implemented. Zone hitting uses a simplified trajectory, not a full pitch repertoire. The simulation league continues to use the existing calibrated engine. Key-moment league integration requires a resumable game engine and is a later step.

Zone contact now uses cursor offset to set launch angle and timing to set spray direction. Poor alignment/timing reduces exit speed even for high-power hitters. A drawn pitcher winds up and releases each pitch; slider and changeup have opposite horizontal break, with changeups slower and showing more late drop. These are illustrative practice trajectories, not measured pitch physics.
