const $=id=>document.getElementById(id),{FieldPlay,contact,BASES,random,clamp}=LiveBaseball;
const field=$('field'),fc=field.getContext('2d'),zone=$('zone'),zc=zone.getContext('2d');
let rng=random(Date.now()),inning=1,outs=0,runs=0,balls=0,strikes=0,bases=[],play=null,pitch=null,phase='ready',aim={x:.5,y:.5},last=0,atbat=1,seed=1,hits=0,walks=0,strikeouts=0,seen=0,defenders=[];
let batter={name:'Practice batter',contact:50,power:50,speed:50,eye:50},pitcher={name:'Practice pitcher',velocity:50,movement:50,control:50,sequencing:50},leaguePlayers=[];
const source=v=>20+.6*v,engine=v=>(Number(v)-20)/.6;
function say(text){$('call').textContent=text;}
function log(text){const li=document.createElement('li');li.textContent='Inning '+inning+' · '+text;$('plays').prepend(li);}
function score(){ $('score').textContent=`Inning ${Math.min(inning,3)} · ${runs} runs · ${outs} outs`;$('count').textContent=`${balls} balls · ${strikes} strikes`;$('totals').textContent=`${hits} hits · ${walks} walks · ${strikeouts} strikeouts · ${seen} pitches`;
  $('pitch').disabled=phase!=='ready';$('take').disabled=$('swing').disabled=phase!=='pitch';$('advance').disabled=$('hold').disabled=phase!=='field';$('steal').disabled=phase!=='ready'||!bases.some(r=>r.base===1)||bases.some(r=>r.base===2);$('restart').disabled=phase==='field'||phase==='pitch';
  for(const id of ['league','batter','pitcher','contact','power','speed','velocity'])$(id).disabled=phase==='field'||phase==='pitch';
}
function nextBatter(){balls=0;strikes=0;atbat++;if(outs>=3){inning++;outs=0;bases=[];log('Side retired');}phase=inning>3?'finished':'ready';say(phase==='finished'?`Practice complete — ${runs} runs. Restart to play again.`:'Ready · '+batter.name+' at bat');score();}
function freeBase(){walks++;let forced=true;for(let b=1;b<=3;b++){const r=bases.find(r=>r.base===b);if(!r){forced=false;break;}if(forced){if(b===3){runs++;bases=bases.filter(q=>q!==r);}else r.newBase=b+1;}}for(const r of bases){if(r.newBase){r.base=r.newBase;delete r.newBase;}}bases.push({name:batter.name+' #'+atbat,base:1,speed:batter.speed});log('Walk');nextBatter();}
function strike(foul=false){if(!foul||strikes<2)strikes++;if(strikes>=3){outs++;strikeouts++;log('Strikeout');nextBatter();}else{phase='ready';say(foul?'Foul ball':'Strike');score();}}
function deliver(){if(phase!=='ready')return;const types=['Fastball','Slider','Changeup'],type=types[Math.floor(rng()*types.length)],velocity=type==='Fastball'?1:type==='Slider'?.9:.8;
  const inZone=rng()<(.5+(pitcher.control-50)*.002),x=inZone?.2+rng()*.6:(rng()<.5?-.05-rng()*.1:1.05+rng()*.1),y=.12+rng()*.76;
  const duration=(1.65-pitcher.velocity*.006)*velocity+(type==='Changeup'?.35:0);
  pitch={x,y,type,duration,elapsed:0,break:(type==='Slider'?.20:.05)*(pitcher.movement/100),taken:false};phase='pitch';seen++;$('pitchName').textContent=type;say('Watch the pitch. Aim, then swing.');score();zone.focus();
}
function take(){if(phase==='pitch'){pitch.taken=true;say('Taking this pitch…');}}
function swing(){if(phase!=='pitch'||pitch.taken)return;const timing=pitch.elapsed-pitch.duration,result=contact({aim,pitch,timing,contact:batter.contact,power:batter.power,rng});
  $('detail').textContent=`${pitch.type} · ${timing<-.08?'Early':timing>.08?'Late':'On time'} · ${Math.round(Math.abs(timing)*1000)} ms from arrival`;
  if(result.kind==='miss'){strike();return;}if(result.kind==='foul'){strike(true);return;}
  play=new FieldPlay({seed:seed++,runners:bases,batter:{name:batter.name+' #'+atbat,speed:batter.speed},defenders,launch:result,outs});phase='field';say('Ball in play — send or hold your runners.');score();
}
function steal(){if($('steal').disabled)return;play=new FieldPlay({seed:seed++,runners:bases,defenders,steal:true,outs});phase='field';say('Runner goes!');score();}
function finishPlay(){const wasSteal=play.steal,events=play.events.slice();runs+=play.runs;outs+=play.outs;bases=play.survivors();
  if(!wasSteal&&!play.error&&play.runners.find(r=>r.base===0)?.alive)hits++;
  const summary=events.join(' · ')||'Play complete';log(summary);play=null;
  if(wasSteal&&outs<3){phase='ready';say(summary);score();}else{nextBatter();say(phase==='finished'?`Practice complete — ${runs} runs. Restart to play again.`:summary);}
}
function fieldPoint(p){return {x:400+p.x*3.25,y:580-p.y*4.9};}
function path(points,fill,stroke){fc.beginPath();for(let i=0;i<points.length;i++){const p=fieldPoint(points[i]);i?fc.lineTo(p.x,p.y):fc.moveTo(p.x,p.y);}fc.closePath();if(fill){fc.fillStyle=fill;fc.fill();}if(stroke){fc.strokeStyle=stroke;fc.stroke();}}
function dot(p,color,label,radius=8){const q=fieldPoint(p);fc.fillStyle='#0005';fc.beginPath();fc.ellipse(q.x,q.y+5,radius+2,4,0,0,Math.PI*2);fc.fill();fc.fillStyle=color;fc.beginPath();fc.arc(q.x,q.y,radius,0,Math.PI*2);fc.fill();fc.fillStyle='#eaf0e3';fc.font='12px sans-serif';fc.textAlign='center';fc.fillText(label,q.x,q.y-14);}
function drawField(){fc.clearRect(0,0,800,640);fc.fillStyle='#112c20';fc.fillRect(0,0,800,640);const outline=[{x:0,y:0}];for(let a=-Math.PI/4;a<=Math.PI/4+.001;a+=Math.PI/80)outline.push({x:Math.sin(a)*100,y:Math.cos(a)*100});path(outline,'#254c32','#72955a');
  fc.save();fc.globalAlpha=.13;for(let y=30;y<570;y+=48){fc.fillStyle='#b9d394';fc.fillRect(65,y,670,24);}fc.restore();path([BASES[0],BASES[1],BASES[2],BASES[3]],'#977954','#c7b385');path([{x:0,y:5},{x:14,y:19.4},{x:0,y:33},{x:-14,y:19.4}],'#315b36');
  for(const b of BASES.slice(0,4)){const p=fieldPoint(b);fc.fillStyle='#f4f0d6';fc.fillRect(p.x-5,p.y-5,10,10);}const m=fieldPoint({x:0,y:18});fc.fillStyle='#a18c68';fc.beginPath();fc.ellipse(m.x,m.y,15,9,0,0,Math.PI*2);fc.fill();
  const fs=play?.fielders||[['C',0,2],['P',0,18],['1B',24,24],['2B',12,37],['SS',-14,37],['3B',-24,24],['LF',-42,63],['CF',0,82],['RF',42,63]].map(([position,x,y])=>({position,x,y}));
  fs.forEach(f=>dot(f,'#84c6ff',f.position));(play?.runners||bases.map(r=>({...r,...BASES[r.base],alive:true}))).filter(r=>r.alive&&!r.scored).forEach(r=>dot(r,'#d7f783',r.name?.split(' ')[0]||'Runner',7));
  if(play){const q=fieldPoint(play.ball);fc.fillStyle='#0008';fc.beginPath();fc.ellipse(q.x,q.y,5,3,0,0,Math.PI*2);fc.fill();fc.fillStyle='#fff9df';fc.beginPath();fc.arc(q.x,q.y-play.ball.z*9,5,0,Math.PI*2);fc.fill();if(play.throw){const a=fieldPoint(play.throw.from),b=fieldPoint(play.throw.to);fc.setLineDash([4,5]);fc.strokeStyle='#ffca81';fc.beginPath();fc.moveTo(a.x,a.y);fc.lineTo(b.x,b.y);fc.stroke();fc.setLineDash([]);}}
  fc.fillStyle='#b1c9ac';fc.font='12px sans-serif';fc.textAlign='center';fc.fillText('100 m fence · LIVE PRACTICE',400,35);
}
function drawZone(){zc.clearRect(0,0,480,360);zc.fillStyle='#0c1815';zc.fillRect(0,0,480,360);zc.fillStyle='#294037';zc.fillRect(145,65,190,220);zc.strokeStyle='#9ab79c';zc.strokeRect(145,65,190,220);zc.globalAlpha=.35;for(let n=1;n<3;n++){zc.beginPath();zc.moveTo(145+190*n/3,65);zc.lineTo(145+190*n/3,285);zc.moveTo(145,65+220*n/3);zc.lineTo(335,65+220*n/3);zc.stroke();}zc.globalAlpha=1;
  const cx=145+aim.x*190,cy=65+aim.y*220,r=(.14+batter.contact*.0015)*190;zc.strokeStyle='#d7f783';zc.fillStyle='#d7f78318';zc.beginPath();zc.ellipse(cx,cy,r,r*220/190,0,0,Math.PI*2);zc.fill();zc.stroke();zc.fillStyle='#d7f783';zc.fillRect(cx-2,cy-2,4,4);
  if(phase==='pitch'){const t=clamp(pitch.elapsed/pitch.duration,0,1),x=145+pitch.x*190+Math.sin(t*Math.PI)*pitch.break*190,y=65+pitch.y*220-(1-t)*100;zc.strokeStyle='#f5ae69';zc.beginPath();zc.arc(x,y,7+(1-t)*60,0,Math.PI*2);zc.stroke();zc.fillStyle='#fff6dd';zc.beginPath();zc.arc(x,y,3+4*t,0,Math.PI*2);zc.fill();}
  zc.fillStyle='#a6b5ab';zc.font='12px sans-serif';zc.textAlign='center';zc.fillText(phase==='pitch'?'Swing at arrival':phase==='field'?'Ball in play — watch the field':'Press Next pitch to begin',240,330);
}
function frame(now){const dt=Math.min(.04,(now-last)/1000||0);last=now;if(phase==='pitch'){pitch.elapsed+=dt;if(pitch.elapsed>pitch.duration+.32){const inside=pitch.x>=0&&pitch.x<=1&&pitch.y>=0&&pitch.y<=1;if(inside)strike();else{balls++;if(balls===4)freeBase();else{phase='ready';say('Ball');score();}}}}if(phase==='field'){play.update(dt);if(play.homeRun){say('HOME RUN! Runners round the bases.');$('advance').disabled=$('hold').disabled=true;}if(play.done)finishPlay();}drawField();drawZone();requestAnimationFrame(frame);}
function pointer(e){const rect=zone.getBoundingClientRect();aim={x:clamp(((e.clientX-rect.left)*480/rect.width-145)/190,-.3,1.3),y:clamp(((e.clientY-rect.top)*360/rect.height-65)/220,-.3,1.3)};}
zone.onpointermove=pointer;zone.onpointerdown=e=>{pointer(e);if(e.pointerType==='mouse')swing();else zone.setPointerCapture(e.pointerId);};
document.addEventListener('keydown',e=>{if(e.code==='Space'&&!['INPUT','SELECT','BUTTON','SUMMARY'].includes(document.activeElement?.tagName)){e.preventDefault();swing();}});
$('pitch').onclick=deliver;$('take').onclick=take;$('swing').onclick=swing;$('steal').onclick=steal;$('advance').onclick=()=>play?.send();$('hold').onclick=()=>play?.hold();
function abilities(){ $('abilities').textContent=`${batter.name}: contact ${Math.round(source(batter.contact))}, power ${Math.round(source(batter.power))}, speed ${Math.round(source(batter.speed))}. ${pitcher.name}: velocity ${Math.round(source(pitcher.velocity))}. Ratings 20–80.`; }
for(const key of ['contact','power','speed','velocity'])$(key).oninput=()=>{(key==='velocity'?pitcher:batter)[key]=engine($(key).value);abilities();};
function reset(){inning=1;outs=runs=balls=strikes=hits=walks=strikeouts=seen=0;atbat=1;bases=[];play=pitch=null;phase='ready';$('plays').replaceChildren();say('Ready for the first pitch.');score();}
$('restart').onclick=reset;
function selectPlayer(kind){const p=leaguePlayers.find(p=>p.player_id===$(kind).value);if(!p)return;if(kind==='batter'){batter={...p};for(const key of ['contact','power','speed'])$(key).value=source(p[key]??50);}else{pitcher={...p};$('velocity').value=source(p.velocity);}abilities();}
$('batter').onchange=()=>selectPlayer('batter');$('pitcher').onchange=()=>selectPlayer('pitcher');
async function json(path){const r=await fetch(path);if(!r.ok)throw Error('Could not load league');return r.json();}
$('league').onchange=async()=>{try{if(!$('league').value){leaguePlayers=[];defenders=[];batter={name:'Practice batter',contact:50,power:50,speed:50,eye:50};pitcher={name:'Practice pitcher',velocity:50,movement:50,control:50,sequencing:50};$('batter').replaceChildren();$('pitcher').replaceChildren();for(const id of ['contact','power','speed','velocity'])$(id).value=50;abilities();return;}
  const s=await json('/api/league?id='+encodeURIComponent($('league').value));leaguePlayers=s.teams.flatMap(t=>[...t.lineup,...t.bench,...t.pitchers]);for(const kind of ['batter','pitcher']){$(kind).replaceChildren();for(const p of leaguePlayers.filter(p=>kind==='pitcher'?p.position==='P':p.position!=='P')){const option=document.createElement('option');option.value=p.player_id;option.textContent=p.name;$(kind).append(option);}}defenders=s.teams[1]?.lineup||[];selectPlayer('batter');selectPlayer('pitcher');}catch(e){say(e.message);}};
(async()=>{try{for(const l of await json('/api/leagues')){const o=document.createElement('option');o.value=l.id;o.textContent=l.name;$('league').append(o);}}catch{say('Practice ready. League players will be available when the server is running.');}})();
abilities();score();requestAnimationFrame(frame);
