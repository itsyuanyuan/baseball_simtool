/* Standalone practice model: metres, seconds, seeded decisions. */
(function(root){
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),distance=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
const BASES=[{x:0,y:0},{x:19.4,y:19.4},{x:0,y:38.8},{x:-19.4,y:19.4},{x:0,y:0}];
const positions=[['C',0,2],['P',0,18],['1B',24,24],['2B',12,37],['SS',-14,37],['3B',-24,24],['LF',-42,63],['CF',0,82],['RF',42,63]];
function random(seed){let s=seed>>>0;return()=>{s=(1664525*s+1013904223)>>>0;return s/4294967296;};}
function move(p,target,speed,dt){const d=distance(p,target),step=speed*dt;if(d<=step){p.x=target.x;p.y=target.y;return true;}p.x+=(target.x-p.x)*step/d;p.y+=(target.y-p.y)*step/d;return false;}
class FieldPlay{
  constructor({seed=1,runners=[],batter={speed:50},defenders=[],launch=null,steal=false,outs=0}={}){
    this.rng=random(seed);this.time=0;this.outs=0;this.runs=0;this.startOuts=outs;this.events=[];this.done=false;this.throw=null;this.owner=null;this.steal=steal;
    this.fielders=positions.map(([position,x,y],i)=>({position,x,y,home:{x,y},...{range:50,error:50,arm:50},...(defenders.find(p=>p.position===position)||{}),x,y,home:{x,y}}));
    this.runners=runners.map(r=>({...r,...BASES[r.base],target:r.base,progress:r.base,alive:true,forced:false,speed:r.speed??50}));
    if(steal){const r=this.runners.find(r=>r.base===1);if(!r)throw Error('No runner on first');r.target=2;r.forced=false;const lead=4/distance(BASES[1],BASES[2]);r.progress=1+lead;r.x+= (BASES[2].x-r.x)*lead;r.y+=(BASES[2].y-r.y)*lead;this.ball={x:0,y:2,z:1};this.owner=this.fielders[0];this.state='steal';}
    else{
      this.runners.push({...batter,...BASES[0],base:0,target:1,progress:0,alive:true,forced:true});
      let force=true;for(let base=1;base<=3;base++){const r=this.runners.find(r=>r.base===base);if(!r){force=false;continue;}r.forced=force;r.target=base+(force?1:0);}
      this.launch=launch;this.ball={x:0,y:0,z:1};this.state='flight';this.catchable=launch.angle>.35;this.landed=false;
      this.v={x:Math.sin(launch.direction)*launch.speed*Math.cos(launch.angle),y:Math.cos(launch.direction)*launch.speed*Math.cos(launch.angle),z:launch.speed*Math.sin(launch.angle)};
      const flight=(this.v.z+Math.sqrt(this.v.z*this.v.z+19.62))/9.81;
      this.landing={x:this.v.x*flight,y:this.v.y*flight};
      this.chaser=this.fielders.reduce((a,b)=>distance(a,this.landing)<distance(b,this.landing)?a:b);
    }
  }
  send(){for(const r of this.runners)if(r.alive&&r.target<4&&!r.scored){r.target=Math.min(4,Math.max(r.target,Math.floor(r.progress)+1));}}
  hold(){for(const r of this.runners)if(r.alive&&!r.forced)r.target=Math.min(r.target,Math.ceil(r.progress));}
  record(text){this.events.push(text);}
  retire(r,text){if(!r?.alive)return;r.alive=false;this.outs++;this.record(text);if(this.startOuts+this.outs>=3){this.done=true;if(r.forced||r.base===0)this.runs=0;this.record('Third out — inning over');}}
  launchThrow(base){const target=BASES[base],f=this.owner;this.throw={from:{x:f.x,y:f.y},to:target,base,duration:distance(f,target)/(19+f.arm*.18)+.18,elapsed:0};this.owner=null;this.state='throw';}
  update(dt){
    if(this.done)return;dt=clamp(dt,0,.04);this.time+=dt;
    for(const r of this.runners){
      if(!r.alive||r.scored||r.progress>=r.target)continue;
      // On an airborne ball existing runners wait to avoid being doubled off.
      if(!this.steal&&this.catchable&&!this.landed&&r.base>0)continue;
      const next=Math.min(4,Math.floor(r.progress+1e-6)+1),a=BASES[next-1],b=BASES[next];
      const speed=4.7+r.speed*.032,acceleration=clamp(this.time/1.0,.35,1);
      if(move(r,b,speed*acceleration,dt)){r.progress=next;if(next===4){r.scored=true;this.runs++;this.record((r.name||'Runner')+' scores');}}
      else r.progress=next-1+distance(a,r)/distance(a,b);
    }
    if(this.state==='flight'){
      const f=this.chaser,reaction=f.position==='C'?.5:.75-f.range*.005;
      if(this.time>reaction)move(f,this.landing, f.position==='C'?6:4.8+f.range*.032,dt);
      this.ball.x+=this.v.x*dt;this.ball.y+=this.v.y*dt;this.ball.z+=this.v.z*dt;this.v.z-=9.81*dt;
      if(Math.hypot(this.ball.x,this.ball.y)>100&&this.ball.z>2.4){this.record('Home run — over the fence');for(const r of this.runners)if(r.alive&&!r.scored){r.scored=true;this.runs++;}this.done=true;return;}
      if(this.catchable&&this.v.z<0&&this.ball.z>0&&this.ball.z<2.4&&distance(f,this.ball)<1.6){
        if(this.rng()<f.error*.0015){this.record(f.position+' drops the catch');this.error=true;this.catchable=false;}
        else{const batter=this.runners.find(r=>r.base===0);this.retire(batter,f.position+' makes the catch');this.landed=true;for(const r of this.runners)if(r.alive&&!r.scored){r.x=BASES[r.base].x;r.y=BASES[r.base].y;r.progress=r.base;r.target=r.base;r.forced=false;}this.done=true;return;}
      }
      if(this.ball.z<=0){this.ball.z=0;this.landed=true;this.state='ground';this.v.x*=.45;this.v.y*=.45;this.record('Ball lands — runners go');}
    }else if(this.state==='ground'){
      this.ball.x+=this.v.x*dt;this.ball.y+=this.v.y*dt;this.v.x*=Math.exp(-1.5*dt);this.v.y*=Math.exp(-1.5*dt);
      const f=this.chaser;move(f,this.ball,f.position==='C'?6:4.8+f.range*.032,dt);
      if(distance(f,this.ball)<1.0&&this.time>(this.retry||0)){
        if(this.rng()<f.error*.0015){this.retry=this.time+1.0;this.error=true;this.record(f.position+' bobbles the pickup');}
        else{this.owner=f;this.state='gather';this.readyAt=this.time+.25+f.error*.002;this.record(f.position+' fields it');}
      }
    }else if(this.state==='gather'&&this.time>=this.readyAt){
      const candidates=this.runners.filter(r=>r.alive&&!r.scored&&r.forced&&r.progress<r.base+1);
      const lead=candidates.sort((a,b)=>b.base-a.base)[0];
      const advancing=this.runners.filter(r=>r.alive&&!r.scored&&r.progress<r.target).sort((a,b)=>b.progress-a.progress)[0];
      if(lead)this.launchThrow(lead.base+1);else if(advancing)this.launchThrow(Math.ceil(advancing.progress));else{this.done=true;this.record('Runners safe — play complete');}
    }else if(this.state==='steal'&&this.time>1.9){this.launchThrow(2);this.record('Catcher throws to second');}
    else if(this.state==='throw'){
      const t=this.throw;t.elapsed+=dt;const ratio=clamp(t.elapsed/t.duration,0,1);this.ball={x:t.from.x+(t.to.x-t.from.x)*ratio,y:t.from.y+(t.to.y-t.from.y)*ratio,z:1+Math.sin(ratio*Math.PI)*2};
      if(ratio===1){
        const r=this.runners.find(r=>r.alive&&!r.scored&&(r.forced?r.base+1===t.base:r.target>=t.base&&r.progress<t.base));
        if(r&&r.progress<t.base){this.retire(r,this.steal?'Caught stealing':'Throw beats '+(r.name||'runner')+' to '+['','first','second','third','home'][t.base]);if(r.base===0)for(const q of this.runners)q.forced=false;}
        else this.record('Safe at '+['','first','second','third','home'][t.base]);
        this.throw=null;this.state='settle';this.settleAt=this.time+.3;
      }
    }else if(this.state==='settle'&&this.time>this.settleAt){
      if(!this.runners.some(r=>r.alive&&!r.scored&&r.progress<r.target))this.done=true;
    }
    if(this.time>30){this.done=true;this.record('Play complete');}
  }
  survivors(){return this.runners.filter(r=>r.alive&&!r.scored&&r.progress>=1&&r.progress<4).map(r=>({name:r.name,speed:r.speed,base:Math.floor(r.progress)}));}
}
function contact({aim,pitch,timing,contact=50,power=50,rng=Math.random}){
  const radius=.14+contact*.0015,offset=Math.hypot(aim.x-pitch.x,aim.y-pitch.y),window=.085+contact*.001;
  if(offset>radius*1.65||Math.abs(timing)>window*1.8)return {kind:'miss'};
  const quality=clamp(1-offset/(radius*1.65)-Math.abs(timing)/(window*1.8),0,1);
  if(quality<.2)return {kind:'foul'};
  const angle=clamp(.25+(aim.y-pitch.y)*2.4+rng()*.35,-.12,1.0);
  return {kind:'fair',quality,speed:17+power*.14+quality*12,angle,direction:clamp((pitch.x-aim.x)*2+timing*2,-.74,.74)};
}
root.LiveBaseball={FieldPlay,contact,BASES,random,clamp};
if(typeof module!=='undefined')module.exports=root.LiveBaseball;
})(typeof globalThis!=='undefined'?globalThis:this);

