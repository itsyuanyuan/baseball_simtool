const $=id=>document.getElementById(id),esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let profile;
const query=new URLSearchParams(location.search),keys=Object.keys(ratingAliases);
const fmt=(v,n=3)=>Number.isFinite(v)?v.toFixed(n):'—',pct=v=>Number.isFinite(v)?(v*100).toFixed(1)+'%':'—';
const rating=(k,v)=>Number.isFinite(v)?(20+.6*(k==='error'?100-v:v)).toFixed(1):'—';
const table=(cols,rows)=>rows.length?'<table><thead><tr>'+cols.map(c=>'<th>'+esc(c)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(c=>'<td>'+esc(c??'—')+'</td>').join('')+'</tr>').join('')+'</tbody></table>':'<p class="muted">No recorded appearances yet.</p>';
async function api(path){const r=await fetch(path,{cache:'no-store'});if(!(r.headers.get('content-type')||'').includes('application/json'))throw Error('Restart the latest server.py.');const data=await r.json();if(!r.ok)throw Error(data.error||'Request failed');return data;}
async function players(preferred){
  const list=await api('/api/players?id='+encodeURIComponent($('league').value));
  $('player').innerHTML=list.map(p=>`<option value="${esc(p.id)}">${esc(p.name)}${p.age!==null?' · age '+p.age:''} · ${esc(p.status)}</option>`).join('');
  if(preferred&&list.some(p=>p.id===preferred))$('player').value=preferred;
  if(!list.length){$('profile').hidden=true;return;}
  await load();
}
async function load(){
  try{profile=await api('/api/player?id='+encodeURIComponent($('league').value)+'&player='+encodeURIComponent($('player').value));render();history.replaceState(null,'','player.html?league='+encodeURIComponent(profile.league_id)+'&player='+encodeURIComponent(profile.player_id));$('status').textContent='';}
  catch(e){$('status').textContent=e.message;}
}
function render(){
  const p=profile.player;$('profile').hidden=false;$('title').textContent=p.name;
  $('subtitle').textContent=profile.league_name+' · '+profile.status+(profile.team_name?' · '+profile.team_name:'');
  $('facts').innerHTML=[['Age',p.age??'Unknown'],['Type',p.is_ghost?'Ghost':'Career player'],['Condition',Number.isFinite(p.energy)?Math.round(p.energy)+'%':'—'],['Recorded seasons',profile.seasons.length]].map(([label,value])=>`<div class="fact">${esc(label)}<strong>${esc(value)}</strong></div>`).join('');
  $('currentRatings').innerHTML=table(['Ability','Current / last recorded','Historical peak'],keys.map(k=>[k==='error'?'Error prevention':k,rating(k,p[k]),rating(k,p.potential?.[k])]));
  $('abilityHistory').innerHTML=table(['Season','Age','Team','Recorded',...keys.map(k=>k==='error'?'Error prevention':k)],profile.seasons.filter(y=>y.ratings).map(y=>[y.season,y.age,y.team_name||'Off roster',y.rating_status,...keys.map(k=>rating(k,y.ratings[k]))]));
  $('events').innerHTML=profile.events.map(e=>`<div class="history-event"><strong>Season ${e.season} · ${e.day?'day '+e.day:'offseason'}</strong><p>${esc(e.text)}</p>${e.changes?`<details><summary>Ability changes</summary><p>${Object.entries(e.changes).map(([k,v])=>`${esc(k==='error'?'Error prevention':k)}: ${((k==='error'?-v:v)*.6).toFixed(2)}`).join(' · ')}</p></details>`:''}</div>`).join('')||'<p class="muted">No identified transactions or offseason events recorded yet. Older name-only records are not guessed.</p>';
  const source=Object.entries(profile.history||{}).sort((a,b)=>+a[0]-+b[0]);
  $('sourceNote').textContent=p.is_ghost?'Ghost baseline: all 20 at age 16, rising evenly to 50 at age 26; average through age 31, then normal aging.':source.length?`All ${source.length} recorded ages are retained (${source[0][0]}–${source.at(-1)[0]}). Starting age initializes current ability only.`:'This older player has no retained ability history. Re-import the original career file to retain it.';
  $('sourceHistory').innerHTML=table(['Age',...keys.map(k=>k==='error'?'Error prevention':k)],source.map(([age,r])=>[age,...keys.map(k=>rating(k,r[k]))]));
  $('rawSource').hidden=!profile.source_career;$('sourceJson').textContent=profile.source_career?JSON.stringify(profile.source_career,null,2):'';
  stats();
}
function stats(){
  if(!profile)return;const phase=$('phase').value,advanced=$('view').value==='advanced';let bat=[],pitch=[];
  for(const year of profile.seasons){
    const c=year.contexts[phase],context=warContext([c.batting],[c.pitching]);
    for(const stint of year.batting.filter(r=>r.phase===phase)){const p=battingWAR(stint.stats,context),lead=[year.season,year.age,stint.team_name];bat.push(advanced?[...lead,p.PA,fmt(p.OPS),fmt(p.ISO),fmt(p.BABIP),pct(p.Kpct),pct(p.BBpct),fmt(p.BaserunningRuns,2),fmt(p.FieldRuns,2),fmt(p.WAR,2)]:[...lead,p.G,p.AB,p.R??'—',p.H,p.D??'—',p.T??'—',p.HR,p.RBI,p.BB,p.SO,p.SB||0,p.CS||0,fmt(p.AVG),fmt(p.OBP),fmt(p.SLG)]);}
    for(const stint of year.pitching.filter(r=>r.phase===phase)){const p=pitchingWAR(stint.stats,context),lead=[year.season,year.age,stint.team_name];pitch.push(advanced?[...lead,p.IP,fmt(p.K9,2),fmt(p.BB9,2),pct(p.Kpct),pct(p.BBpct),pct(p.KBBpct),fmt(p.FIP,2),fmt(p.WAR,2)]:[...lead,p.G,p.GS,p.IP,p.H,p.R,p.HR,p.BB,p.SO,p.pitches,fmt(p.RA9,2),fmt(p.WHIP,2)]);}
  }
  $('batting').innerHTML=table(advanced?['Season','Age','Team','PA','OPS','ISO','BABIP','K%','BB%','BsR*','Def Runs*','WAR*']:['Season','Age','Team','G','AB','R','H','2B','3B','HR','RBI','BB','SO','SB','CS','AVG','OBP','SLG'],bat);
  $('pitching').innerHTML=table(advanced?['Season','Age','Team','IP','K/9','BB/9','K%','BB%','K−BB%','FIP*','WAR*']:['Season','Age','Team','G','GS','IP','H','R','HR','BB','SO','Pitches','RA9','WHIP'],pitch);
}
$('phase').onchange=$('view').onchange=stats;$('player').onchange=load;$('league').onchange=()=>players().catch(e=>$('status').textContent=e.message);$('reload').onclick=()=>players($('player').value).catch(e=>$('status').textContent=e.message);
(async()=>{try{const leagues=await api('/api/leagues');$('league').innerHTML=leagues.map(l=>`<option value="${l.id}">${esc(l.name)}</option>`).join('');if(!leagues.length)return $('status').textContent='Create a league first.';const wanted=query.get('league')||localStorage.getItem('diamond-active-league');if(leagues.some(l=>l.id===wanted))$('league').value=wanted;await players(query.get('player'));}catch(e){$('status').textContent=e.message;}})();
