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
  sequencing: ['cat','sequencing','pitchSequencing','pitch_sequencing'], speed:['spd','speed']
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
function unwrapCareer(value) {
  const s=value.S??value.state??value;
  if (!s||typeof s!=='object'||Array.isArray(s)) throw Error('S must be a JSON object containing the career history.');
  return s;
}
function careerPotential(history, current, scale, mappings, higherBetter=true) {
  const potential={...current};
  for (const [key, aliases] of Object.entries(ratingAliases)) {
    const field=mappings?.[key];
    if (mappings&&!field) continue;
    for (const [age,value] of Object.entries(history)) {
      if (!/^\d+$/.test(age)||!value||typeof value!=='object') continue;
      const source=value.ratings||value.abilities||value;
      const f=field||aliases.find(a=>Number.isFinite(source[a]));
      if (!f||!Number.isFinite(source[f])) continue;
      const n=normalizeRating(source[f],scale);
      const rating=key==='error'&&f==='fld'&&higherBetter?100-n:n;
      potential[key]=key==='error'?Math.min(potential[key],rating):Math.max(potential[key],rating);
    }
  }
  return potential;
}
if (typeof module !== 'undefined') module.exports = { normalizeRating, ratingAliases, detectRole, mapSnapshot, unwrapCareer, careerPotential };

function normalizedHistory(history,scale='yakyolife',mappings=null,higherBetter=true){
  return Object.fromEntries(Object.entries(history).filter(([a,r])=>/^\d+$/.test(a)&&+a>=10&&+a<=100&&r&&typeof r==='object').map(([a,r])=>{
    const source=r.ratings||r.abilities||r, mapped=mapSnapshot(source,scale,mappings,higherBetter);
    return [a,Object.fromEntries(Object.entries(mapped).filter(([k])=>{const field=mappings?mappings[k]:ratingAliases[k].find(f=>Number.isFinite(source[f]));return field&&Number.isFinite(source[field]);}))];
  }));
}
function importCareer(value,entryAge=null){
  const s=unwrapCareer(value),raw=s.pastab||s.history||{[s.age||25]:s.ratings||s};
  const ages=Object.keys(raw).filter(a=>/^\d+$/.test(a)&&+a>=10&&+a<=100).map(Number).sort((a,b)=>a-b);
  if(!ages.length)throw Error('No career ages found in pastab.');
  const age=entryAge===null?ages[0]:Number(entryAge);
  if(!ages.includes(age))throw Error('Entry age must be one of: '+ages.join(', '));
  const record=raw[age];
  if(!record||typeof record!=='object'||Array.isArray(record))throw Error('Each pastab age must contain an ability object.');
  const source=record.ratings||record.abilities||record;
  if(!Object.values(ratingAliases).flat().some(k=>Number.isFinite(source[k])))throw Error('No recognized numeric Yakyolife abilities at this age.');
  const current=mapSnapshot(source,'yakyolife'),role=detectRole(source);
  return {name:s.name||'Imported player',age,position:role==='pitcher'?'P':role==='catcher'?'C':'DH',...current,history:normalizedHistory(raw),potential:careerPotential(raw,current,'yakyolife')};
}
if(typeof module!=='undefined')Object.assign(module.exports,{normalizedHistory,importCareer});
