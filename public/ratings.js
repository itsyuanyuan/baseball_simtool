// Source ratings are independent of the engine's calibrated 0–100 scale.
function normalizeRating(raw, scale) {
  if (!Number.isFinite(raw)) throw new Error('Rating must be a finite number.');
  if (scale === 'yakyolife') {
    return Math.round((Math.max(20, Math.min(80, raw)) - 20) / 60 * 100);
  }
  const size = Number(scale);
  const normalized = size === 80 ? (raw - 20) / 60 * 100 : raw / size * 100;
  if (!Number.isFinite(normalized) || normalized < 0 || normalized > 100) {
    throw new Error('Rating is outside the selected source scale.');
  }
  return Math.round(normalized);
}
const ratingAliases = {
  stamina: ['sta','stamina'], contact: ['con','contact'], power: ['pow','power'], eye: ['eye'],
  velocity: ['vel','velocity'], movement: ['brk','movement'], control: ['ctl','control'],
  range: ['rng','range','defensiveRange','defensive_range'],
  error: ['fld','error','errorRate','error_rate'], arm: ['arm'],
  sequencing: ['cat','sequencing','pitchSequencing','pitch_sequencing']
};
function detectRole(source) {
  const has = key => ratingAliases[key].some(k => Number.isFinite(source[k]));
  const pitches = ['velocity','movement','control'].some(has);
  const bats = ['contact','power','eye'].some(has);
  if (pitches && bats) return 'two-way';
  if (pitches) return 'pitcher';
  if (Number.isFinite(source.cat)) return 'catcher';
  return 'fielder';
}
function mapSnapshot(source, scale, mappings, fieldingHigherBetter=true) {
  const result = {};
  for (const [key, aliases] of Object.entries(ratingAliases)) {
    const field = mappings ? mappings[key] : aliases.find(k => Number.isFinite(source[k]));
    if (!field) { result[key] = key === 'error' ? 20 : 50; continue; }
    const n = normalizeRating(source[field], scale);
    result[key] = key === 'error' && field === 'fld' && fieldingHigherBetter ? 100-n : n;
  }
  return result;
}
if (typeof module !== 'undefined') module.exports = { normalizeRating, ratingAliases, detectRole, mapSnapshot };
