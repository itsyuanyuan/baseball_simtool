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
if (typeof module !== 'undefined') module.exports = { normalizeRating };
