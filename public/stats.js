// Innings are always derived from outs. Undefined legacy counters stay unavailable.
function battingRates(p){
  const pa=p.AB+p.BB+p.HBP+p.SF,avg=p.AB?p.H/p.AB:null,obp=pa?(p.H+p.BB+p.HBP)/pa:null;
  const tb=Number.isFinite(p.D)&&Number.isFinite(p.T)?p.H+p.D+2*p.T+3*p.HR:null;
  const slg=p.AB&&tb!==null?tb/p.AB:null,den=p.AB-p.SO-p.HR+p.SF;
  return {...p,PA:pa,AVG:avg,OBP:obp,SLG:slg,OPS:obp!==null&&slg!==null?obp+slg:null,ISO:slg!==null&&avg!==null?slg-avg:null,BABIP:den>0?(p.H-p.HR)/den:null,Kpct:pa?p.SO/pa:null,BBpct:pa?p.BB/pa:null};
}
function pitchingRates(p){
  const ip=p.outs/3,bf=p.complete!==false?p.BF:0;
  return {...p,IP:Math.floor(p.outs/3)+'.'+p.outs%3,RA9:ip?p.R*9/ip:null,WHIP:ip?(p.H+p.BB)/ip:null,K9:ip?p.SO*9/ip:null,BB9:ip?p.BB*9/ip:null,Kpct:bf?p.SO/bf:null,BBpct:bf?p.BB/bf:null,KBBpct:bf?(p.SO-p.BB)/bf:null,FIP:ip&&p.complete!==false?(13*p.HR+3*(p.BB+p.HBP)-2*p.SO)/ip+3.1:null};
}
if(typeof module!=='undefined')module.exports={battingRates,pitchingRates};

// Original simulator WAR estimate; fixed weights, not published fWAR/bWAR.
const positionRuns={C:12.5,'1B':-12.5,'2B':2.5,'3B':2.5,SS:7.5,LF:-7.5,CF:2.5,RF:-7.5,DH:-17.5};
function weightedOnBase(p){
  const pa=p.AB+p.BB+p.HBP+p.SF;
  if(!pa||!Number.isFinite(p.D)||!Number.isFinite(p.T))return null;
  return (.69*p.BB+.72*p.HBP+.89*(p.H-p.D-p.T-p.HR)+1.27*p.D+1.62*p.T+2.10*p.HR)/pa;
}
function warContext(batters,pitchers){
  let pa=0,weighted=0,steals=0,valid=true,ip=0,fipRuns=0,pitchValid=true;
  for(const p of batters){const n=p.AB+p.BB+p.HBP+p.SF;if(!n)continue;const w=weightedOnBase(p);if(w===null){valid=false;continue;}pa+=n;weighted+=w*n;steals+=.2*(p.SB||0)-.4*(p.CS||0);}
  for(const p of pitchers){const n=p.outs/3;if(!n)continue;const f=pitchingRates(p).FIP;if(f===null){pitchValid=false;continue;}ip+=n;fipRuns+=f*n;}
  return {woba:valid&&pa?weighted/pa:null,stealRate:valid&&pa?steals/pa:null,fip:pitchValid&&ip?fipRuns/ip:null};
}
function battingWAR(p,context){
  const rates=battingRates(p),woba=weightedOnBase(p),starts=p.position_games||{},known=Object.values(starts).reduce((a,b)=>a+b,0)===p.G&&Object.keys(starts).every(k=>k in positionRuns);
  const bat=woba!==null&&context.woba!==null?(woba-context.woba)/1.20*rates.PA:null;
  const run=context.stealRate!==null?.2*(p.SB||0)-.4*(p.CS||0)-context.stealRate*rates.PA:null;
  const pos=known?Object.entries(starts).reduce((n,[k,g])=>n+positionRuns[k]*g/162,0):null;
  const replacement=20*rates.PA/600;
  return {...rates,wOBA:woba,BatRuns:bat,RunRuns:run,PosRuns:pos,RepRuns:replacement,WAR:bat!==null&&run!==null&&pos!==null?(bat+run+pos+replacement)/10:null};
}
function pitchingWAR(p,context){
  const rates=pitchingRates(p),ip=p.outs/3;
  // Replacement is modeled as one run per nine innings worse than league FIP.
  return {...rates,WAR:rates.FIP!==null&&context.fip!==null?(context.fip+1-rates.FIP)*ip/9/10:null};
}
if(typeof module!=='undefined')Object.assign(module.exports,{weightedOnBase,warContext,battingWAR,pitchingWAR});
