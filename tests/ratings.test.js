const { test } = require('node:test');
const assert = require('node:assert/strict');
const { normalizeRating } = require('../public/ratings.js');

test('Yakyolife clamps source ratings before normalizing, retaining a neutral 50', () => {
  for (const [source, expected] of [[0,0],[19,0],[20,0],[35,25],[50,50],[65,75],[80,100],[95,100]]) {
    assert.equal(normalizeRating(source, 'yakyolife'), expected);
  }
  assert.throws(() => normalizeRating(NaN, 'yakyolife'));
  assert.throws(() => normalizeRating(Infinity, 'yakyolife'));
});
test('Existing engine and strict source scales remain available', () => {
  assert.equal(normalizeRating(75, '100'), 75);
  assert.equal(normalizeRating(10, '20'), 50);
  assert.equal(normalizeRating(2.5, '5'), 50);
  assert.equal(normalizeRating(50, '80'), 50);
  assert.throws(() => normalizeRating(10, '80'));
});
