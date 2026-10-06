const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const groups=['lineup','bench','pitchers'];
let who={role:'commissioner'},state,draft,localVault=[],dirty=false,busy=false,teamId,revision,epoch,careerFile;
function say(s){$('status').textContent=s;}
async function api(path,body){
  const r=await fetch(path,{method:body?'POST':'GET',cache:'no-store',headers:{Authorization:'Bearer '+(sessionStorage.getItem('diamond-auth')||''),...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
  if(!(r.headers.get('content-type')||'').includes('application/json'))throw Error('Restart the latest server.py and reload.');
  const data=await r.json();if(!r.ok)throw Error(data.error||'Request failed');return data;
}
function started(){return state.schedule.some(g=>g.score!==null);}
function players(t){return groups.flatMap(group=>t[group].map((p,slot)=>({...p,group,slot})));}
async function chooseLeague(){
  state=await api('/api/league?id='+encodeURIComponent($('league').value));
  $('team').innerHTML=state.teams.map((t,i)=>who.role==='manager'&&i!==who.team?'':`<option value="${i}">${esc(t.name)}</option>`).join('');
}
async function load(){
  if(busy)return;
  try{
    state=await api('/api/league?id='+encodeURIComponent($('league').value));teamId=+$('team').value;
    draft=structuredClone(state.teams[teamId]);if(!draft)throw Error('Select a team');
    revision=state.team_versions?.[teamId]||0;epoch=state.lineup_epoch||0;dirty=false;
    $('editor').hidden=$('tradePanel').hidden=false;$('title').textContent=draft.name;
    $('name').value=draft.name;$('name').disabled=started();
    $('rules').textContent='Reorder the lineup, rotate your staff, or swap a reserve into a starting slot. Save lineup edits before importing, replacing or trading.';
    try{localVault=JSON.parse(localStorage.getItem('diamond-vault')||'[]');if(!Array.isArray(localVault))localVault=[];}catch{localVault=[];}
    $('localVault').innerHTML='<option value="">Choose a local player…</option>'+localVault.map((p,i)=>`<option value="${i}">${esc(p.name)} · age ${esc(p.age)}</option>`).join('');
    const active=new Set(state.teams.flatMap(t=>players(t).map(p=>p.career_id)));
    $('vault').innerHTML='<option value="">Choose an available career…</option>'+Object.entries(state.library||{}).map(([id,p])=>`<option value="${id}" ${active.has(id)?'disabled':''}>${esc(p.name)} · age ${(state.released?.[id]||p).age}${active.has(id)?' · on a team':''}</option>`).join('');
    render();renderTrades();
  }catch(e){say(e.message);}
}
function render(){
  $('autoRest').checked=draft.auto_rest!==false;
  $('calendar').textContent=`${state.calendar_date} · Day ${state.calendar_day} · 26 players · condition after latest games`;
  $('aging').innerHTML=(state.development_report||[]).filter(r=>r.team===teamId).map(r=>`<details><summary>${esc(r.name)} · age ${r.age_before} → ${r.age_after}</summary>${Object.entries(r.changes).map(([k,v])=>{const sign=k==='error'?-1:1,c=r.components?.[k];return `<p>${esc(k==='error'?'error prevention':k)}: ${v*sign>=0?'+':''}${(v*sign*.6).toFixed(1)}${c?` · ${esc(c.source)} ${(c.base*.6).toFixed(2)}, performance ${(c.performance*.6).toFixed(2)}, variation ${(c.random*.6).toFixed(2)}`:''}</p>`;}).join('')}</details>`).join('')||'<p class="muted">Offseason changes appear after starting the next season.</p>';
  const prior=$('detailsPlayer').value;
  $('detailsPlayer').innerHTML=players(draft).map((p,i)=>`<option value="${i}">${esc(p.name)} · age ${p.age}</option>`).join('');
  if(prior)$('detailsPlayer').value=prior;ratingDetails();
  for(const group of groups){
    $(group==='lineup'?'batters':group).innerHTML=draft[group].map((p,i)=>`<div class="member"><span><strong>${esc(p.name)}</strong><br><small>${group==='pitchers'?(i<draft.rotation_size?'SP':'RP'):esc(p.position)} · age ${p.age} · ${Math.round(p.energy??100)}% condition · ${p.career_id?'Career player':'Ghost / legacy player'}</small></span><select aria-label="Order for ${esc(p.name)}" data-group="${group}" data-order="${i}">${draft[group].map((_,j)=>`<option value="${j}" ${i===j?'selected':''}>${j+1}</option>`).join('')}</select>${group==='bench'?`<select aria-label="Start ${esc(p.name)}" data-swap="${i}"><option value="">Start…</option>${draft.lineup.map((a,j)=>`<option value="${j}">${j+1} · ${esc(a.position)}</option>`).join('')}</select>`:''}<button class="quiet" data-group="${group}" data-assign="${i}" ${busy||state.phase==='complete'||(state.phase!=='regular'&&p.career_id)?'disabled':''}>Replace</button></div>`).join('');
  }
  $('rotation').innerHTML=draft.pitchers.slice(0,-1).map((_,i)=>`<option value="${i+1}">${i+1} starters / ${draft.pitchers.length-i-1} relievers</option>`).join('');
  $('rotation').value=String(draft.rotation_size);
  $('save').disabled=$('ready').disabled=busy||state.phase==='complete';
  $('dirty').textContent=dirty?'Unsaved lineup edits.':'Lineup saved.';
}
function changed(){dirty=true;render();}
$('autoRest').onchange=()=>{draft.auto_rest=$('autoRest').checked;changed();};
$('editor').onchange=e=>{
  if(e.target.dataset.swap!==undefined&&e.target.value!==''){
    const b=+e.target.dataset.swap,l=+e.target.value,pos=draft.lineup[l].position;
    [draft.lineup[l],draft.bench[b]]=[draft.bench[b],draft.lineup[l]];draft.lineup[l].position=pos;changed();
  }else if(e.target.dataset.order!==undefined){const a=+e.target.dataset.order,b=+e.target.value,list=draft[e.target.dataset.group];[list[a],list[b]]=[list[b],list[a]];changed();}
};
async function transaction(action,extra){
  if(busy)return;
  if(dirty)return say('Save or discard your lineup edits first.');
  busy=true;render();
  try{await api('/api/transactions/'+action,{id:state.id,version:state.version,team:teamId,...extra});busy=false;await load();say('Saved: '+action+'.');}
  catch(e){say(e.message);}finally{busy=false;render();}
}
$('editor').onclick=e=>{const b=e.target.closest('[data-assign]');if(!b)return;if(!$('vault').value)return say('Import or choose an available career in the league library above.');transaction('assign',{career_id:$('vault').value,group:b.dataset.group,slot:+b.dataset.assign});};
$('name').oninput=()=>{draft.name=$('name').value;dirty=true;$('dirty').textContent='Unsaved lineup edits.';};
$('rotation').onchange=()=>{draft.rotation_size=+$('rotation').value;changed();};
async function save(ready){if(busy)return;busy=true;render();try{await api('/api/team/save',{id:state.id,team:teamId,version:revision,lineup_epoch:epoch,roster:draft,ready});busy=false;await load();say(ready?'Team saved and ready.':'Team saved.');}catch(e){say(e.message);}finally{busy=false;render();}}
$('save').onclick=()=>save(false);$('ready').onclick=()=>save(true);
$('load').onclick=$('reload').onclick=$('refreshTrades').onclick=load;
$('league').onchange=()=>{if(dirty){$('league').value=state.id;return say('Save or discard lineup edits before changing leagues.');}chooseLeague().then(load).catch(e=>say(e.message));};
$('team').onchange=()=>{if(dirty){$('team').value=teamId;return say('Save or discard lineup edits before changing teams.');}load();};
function ratingDetails(){const p=players(draft)[+$('detailsPlayer').value];if(!p)return;const scale=(k,v)=>(20+.6*(k==='error'?100-v:v)).toFixed(1);$('ratings').innerHTML='<table><thead><tr><th>Ability</th><th>Current</th><th>Historical peak</th></tr></thead><tbody>'+Object.keys(ratingAliases).map(k=>`<tr><td>${k==='error'?'Error prevention':k}</td><td>${scale(k,p[k]??50)}</td><td>${scale(k,p.potential?.[k]??p[k]??50)}</td></tr>`).join('')+'</tbody></table>';}
$('detailsPlayer').onchange=ratingDetails;
$('careerFile').onchange=async e=>{try{const f=e.target.files[0];if(!f)return;if(f.size>1000000)throw Error('Use a JSON file under 1 MB.');careerFile=JSON.parse(await f.text());const p=importCareer(careerFile);$('entryAge').innerHTML=Object.keys(p.history).sort((a,b)=>a-b).map(a=>`<option>${a}</option>`).join('');if(!$('entryAge').options.length)$('entryAge').innerHTML=`<option>${p.age}</option>`;$('careerInfo').textContent=`${p.name} · ${Object.keys(p.history).length} years of ability history. Source ratings use the Yakyolife 20–80 clamp.`;$('careerPreview').hidden=false;}catch(e){careerFile=null;$('careerPreview').hidden=true;say(e.message);}};
$('importCareer').onclick=()=>{try{if(!careerFile)throw Error('Choose a career file.');transaction('import',{player:importCareer(careerFile,+$('entryAge').value)});}catch(e){say(e.message);}};
$('publishVault').onclick=()=>{const value=$('localVault').value;if(value==='')return say('Choose a local Vault player.');transaction('import',{player:localVault[+value]});};
function renderTrades(){
  const eligible=players(draft).filter(p=>p.career_id);
  $('tradeGive').innerHTML='<option value="">Choose your career player…</option>'+eligible.map(p=>`<option value="${p.player_id}">${esc(p.name)} · ${p.group==='pitchers'?'P':'Batter'}</option>`).join('');
  $('tradeTeam').innerHTML=state.teams.map((t,i)=>i===teamId?'':`<option value="${i}">${esc(t.name)}</option>`).join('');tradeTargets();
  $('propose').disabled=busy||state.phase!=='regular';
  $('offers').innerHTML=(state.trades||[]).filter(o=>o.from===teamId||o.to===teamId).slice().reverse().map(o=>`<article class="offer"><strong>${esc(state.teams[o.from].name)} → ${esc(state.teams[o.to].name)}</strong><p>${esc(o.give_name)} for ${esc(o.take_name)} · ${esc(o.status)} · season ${o.season}</p>${o.status==='pending'?(o.to===teamId?`<button data-trade="accept" data-offer="${o.id}">Accept</button><button class="quiet" data-trade="reject" data-offer="${o.id}">Reject</button>`:`<button class="quiet" data-trade="cancel" data-offer="${o.id}">Cancel offer</button>`):''}</article>`).join('')||'<p class="muted">No offers yet. Import career players to both teams to make a trade.</p>';
}
function tradeTargets(){const other=state.teams[+$('tradeTeam').value],give=players(draft).find(p=>p.player_id===$('tradeGive').value);$('tradeTake').innerHTML='<option value="">Choose their career player…</option>'+(other?players(other).filter(p=>p.career_id&&(!give||(p.group==='pitchers')===(give.group==='pitchers'))).map(p=>`<option value="${p.player_id}">${esc(p.name)} · age ${p.age}</option>`).join(''):'');}
$('tradeTeam').onchange=$('tradeGive').onchange=tradeTargets;
$('propose').onclick=()=>{if(!$('tradeGive').value||!$('tradeTake').value)return say('Choose both players. Ghost players are not tradeable.');transaction('propose',{other:+$('tradeTeam').value,give:$('tradeGive').value,take:$('tradeTake').value});};
$('offers').onclick=e=>{const b=e.target.closest('[data-trade]');if(b)transaction(b.dataset.trade,{offer:b.dataset.offer});};
(async()=>{try{const health=await api('/api/health');if(health.lan)who=await api('/api/lan/me');$('access').textContent=health.lan?(who.role==='commissioner'?'Commissioner: manage any team.':'Manager: manage your assigned team; the league library is shared.'):'Solo mode: manage any team without a login.';const all=await api('/api/leagues');const leagues=all.filter(l=>who.role!=='manager'||l.id===who.league_id);$('league').innerHTML=leagues.map(l=>`<option value="${l.id}">${esc(l.name)}</option>`).join('');if(!leagues.length)return say('Create a league first.');const active=localStorage.getItem('diamond-active-league');if(leagues.some(l=>l.id===active))$('league').value=active;await chooseLeague();await load();}catch(e){say(e.message+' In LAN mode, sign in through the LAN lobby first.');}})();
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
