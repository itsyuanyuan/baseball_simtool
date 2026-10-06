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
