const test=require('node:test'),assert=require('node:assert/strict');
const {battingRates,pitchingRates}=require('../public/stats.js');
const {importCareer}=require('../public/ratings.js');
test('Batting denominators and total bases',()=>{const p=battingRates({AB:100,H:30,D:6,T:2,HR:4,BB:12,HBP:2,SF:1,SO:20});assert.equal(p.SLG,.52);assert.equal(p.OBP,44/115);assert.ok(Math.abs(p.ISO-.22)<1e-12);assert.equal(p.BABIP,26/77);assert.equal(p.PA,115);});
test('Outs rather than decimal innings and empty denominators',()=>{const p=pitchingRates({outs:10,H:3,BB:1,R:2,HR:1,HBP:1,SO:5,BF:15});assert.equal(p.IP,'3.1');assert.equal(p.WHIP,1.2);assert.ok(Math.abs(p.RA9-5.4)<1e-12);assert.ok(Math.abs(p.FIP-5.8)<1e-12);assert.equal(pitchingRates({outs:0}).RA9,null);});
test('Older saves do not invent total bases or FIP',()=>{assert.equal(battingRates({AB:10,H:3,HR:1,BB:0,HBP:0,SF:0,SO:1}).SLG,null);assert.equal(pitchingRates({outs:3,complete:false}).FIP,null);});
test('Career imports preserve the whole trajectory and choose entry age only once',()=>{const save={S:{name:'Career',pastab:{16:{con:30,spd:50},25:{con:80,spd:70}}},Seed:123};const p=importCareer(save);assert.equal(p.age,16);assert.equal(p.history['25'].contact,100);assert.equal(p.potential.contact,100);assert.equal(importCareer(save,25).contact,100);assert.throws(()=>importCareer(save,20));});
