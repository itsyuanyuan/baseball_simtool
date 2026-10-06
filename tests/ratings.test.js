const { test } = require('node:test');
const assert = require('node:assert/strict');
const { normalizeRating } = require('../public/ratings.js');
const { mapSnapshot, detectRole } = require('../public/ratings.js');
const {unwrapCareer,careerPotential}=require('../public/ratings.js');

test('Whole original career survives import independently of starting age',()=>{
  const {importCareer}=require('../public/ratings.js');
  const S={name:'Career',pastab:{16:{con:20,spd:20},26:{con:70,spd:60},38:{con:40,spd:30}},trait:'Patient','career stat':{H:1000}};
  const p=importCareer({S,Seed:123},26);
  assert.equal(p.age,26);
  assert.deepEqual(Object.keys(p.history),['16','26','38']);
  assert.deepEqual(p.source_career,S);
  S.trait='Changed';assert.equal(p.source_career.trait,'Patient');
});

test('S envelope ignores Seed; potential takes per-ability peaks including speed and inverted errors',()=>{
  const s=unwrapCareer({Seed:'ignored',S:{name:'A',pastab:{16:{con:30,spd:40,fld:25},24:{con:80,spd:70,fld:75},36:{con:60,spd:30,fld:65}}}});
  const current=mapSnapshot(s.pastab[16],'yakyolife');
  const p=careerPotential(s.pastab,current,'yakyolife');
  assert.equal(current.contact,17);assert.equal(p.contact,100);
  assert.equal(current.speed,33);assert.equal(p.speed,83);
  assert.equal(current.error,92);assert.equal(p.error,8);
  assert.equal(p.velocity,50);
});

test('Actual partial role saves map abbreviated abilities without a catching field', () => {
  const saves = [
    ['pitcher',{sta:66,vel:73,ctl:82,brk:15}],
    ['fielder',{sta:66,con:58,pow:52,eye:48,rng:73,fld:15,arm:82}],
    ['catcher',{sta:66,con:58,pow:52,eye:48,cat:73,fld:15,arm:82}],
    ['two-way',{sta:66,con:58,pow:52,eye:48,vel:73,brk:15,ctl:82}]
  ];
  for (const [role, source] of saves) {
    assert.equal(detectRole(source), role);
    const p=mapSnapshot(source,'yakyolife');
    assert.equal(p.stamina,77);
    assert.equal(Object.hasOwn(p,'catching'),false);
    assert.equal(p.sequencing,role==='catcher'?88:50);
    if (source.fld!==undefined) assert.equal(p.error,100);
    if (role==='catcher') assert.equal(p.range,50);
  }
  assert.equal(mapSnapshot({fld:80,cat:80},'yakyolife').error,0);
  assert.equal(mapSnapshot({fld:80,cat:80},'yakyolife').sequencing,100);
  assert.equal(mapSnapshot({error:80},'100').error,80);
});

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
