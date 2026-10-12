const {test}=require('node:test'),assert=require('node:assert/strict');
const {FieldPlay,contact}=require('../public/live-model.js');
function finish(p){for(let i=0;i<1000&&!p.done;i++)p.update(.04);assert.equal(p.done,true);return p;}
test('Zone location and timing determine contact',()=>{
  const setup={aim:{x:.5,y:.5},pitch:{x:.5,y:.5},timing:0,rng:()=>.5};
  assert.equal(contact(setup).kind,'fair');
  assert.equal(contact({...setup,timing:.8}).kind,'miss');
  assert.equal(contact({...setup,aim:{x:1.2,y:1.2}}).kind,'miss');
  assert.ok(contact({...setup,power:90}).speed>contact({...setup,power:10}).speed);
});
test('Live field results are reproducible and runners reconcile',()=>{
  for(let seed=0;seed<50;seed++){
    const setup={seed,batter:{speed:50},runners:[{name:'Lead',base:1,speed:50}],launch:{speed:25,angle:.4,direction:.3}};
    const a=finish(new FieldPlay(setup)),b=finish(new FieldPlay(setup));
    assert.deepEqual(a.events,b.events);assert.deepEqual(a.survivors(),b.survivors());
    assert.equal(a.runners.filter(r=>!r.alive).length,a.outs);
    assert.equal(a.runners.filter(r=>r.scored).length,a.runs);
  }
});
test('A deep airborne ball clears the fence and scores all runners',()=>{
  const p=finish(new FieldPlay({runners:[{base:1,speed:50},{base:3,speed:50}],launch:{speed:45,angle:.7,direction:0}}));
  assert.equal(p.runs,3);assert.equal(p.outs,0);assert.equal(p.survivors().length,0);
});
test('Speed changes the actual race on a steal; catcher range does not',()=>{
  const setup={steal:true,runners:[{base:1,speed:0}],defenders:[{position:'C',arm:50,range:0}]};
  const slow=finish(new FieldPlay(setup)),fast=finish(new FieldPlay({...setup,runners:[{base:1,speed:100}]}));
  assert.equal(slow.outs,1);assert.equal(fast.outs,0);
  assert.deepEqual(slow.events,finish(new FieldPlay({...setup,defenders:[{position:'C',arm:50,range:100}]})).events);
});
test('Hold preserves forced advancement and send requests another base',()=>{
  const p=new FieldPlay({runners:[{name:'First',base:1,speed:50},{name:'Third',base:3,speed:50}],launch:{speed:24,angle:.1,direction:.2}});
  p.send();p.hold();
  assert.ok(p.runners.find(r=>r.base===1).target>=2);
  assert.equal(p.runners.find(r=>r.base===3).target,3);
  assert.ok(p.runners.find(r=>r.base===0).target>=1);
});
test('Outfield hits move outfielders and return to a covering infielder without a cheap force',()=>{
  const p=new FieldPlay({seed:10,runners:[{base:1,speed:50}],launch:{speed:35,angle:.32,direction:-.4},defenders:[{position:'LF',error:0}]});
  assert.ok(['LF','CF','RF'].includes(p.chaser.position));
  const before=p.fielders.filter(f=>['LF','CF','RF'].includes(f.position)).map(f=>({x:f.x,y:f.y}));
  for(let i=0;i<30;i++)p.update(.04);
  const after=p.fielders.filter(f=>['LF','CF','RF'].includes(f.position)).map(f=>({x:f.x,y:f.y}));
  assert.ok(after.every((f,i)=>Math.hypot(f.x-before[i].x,f.y-before[i].y)>1));
  finish(p);assert.equal(p.outs,0);
  assert.ok(p.events.some(e=>e.includes('covering second')));
  assert.ok(p.events.some(e=>e.includes('receives the throw')));
  assert.deepEqual(p.survivors().map(r=>r.base).sort(),[1,2]);
});
test('Infield throws require a receiver at the bag',()=>{
  const p=new FieldPlay({seed:4,launch:{speed:23,angle:.05,direction:.4},defenders:[{position:'P',error:0}]});
  let checked=false;
  for(let i=0;i<1000&&!p.done;i++){
    p.update(.04);
    if(p.throw){checked=true;assert.ok(p.throw.receiver);assert.notEqual(p.throw.receiver,p.chaser);}
  }
  assert.ok(checked);assert.ok(p.events.some(e=>e.includes('receives the throw')));
});
