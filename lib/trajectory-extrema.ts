// Extrema of the existing prescribed quintic demand, not a vehicle controller.
// Coefficients are ascending. Derivative roots partition each polynomial into
// monotone intervals, so bisection finds every root including tangent roots.
function value(coefficients:number[],x:number){return coefficients.reduceRight((sum,c)=>sum*x+c,0);}
export function polynomialRootsInInterval(input:number[],lo:number,hi:number):number[]{
 const coefficients=[...input],scale=Math.max(1,...coefficients.map(Math.abs));
 while(coefficients.length>1&&Math.abs(coefficients.at(-1)!)<1e-13*scale)coefficients.pop();
 if(coefficients.length<=1||hi<lo)return [];
 if(coefficients.length===2){const root=-coefficients[0]/coefficients[1];return root>=lo-1e-12&&root<=hi+1e-12?[Math.max(lo,Math.min(hi,root))]:[];}
 const derivative=coefficients.slice(1).map((c,i)=>c*(i+1));
 const knots=[lo,...polynomialRootsInInterval(derivative,lo,hi).filter(x=>x>lo&&x<hi),hi];
 const roots=knots.filter(x=>Math.abs(value(coefficients,x))<=1e-11*scale);
 for(let i=1;i<knots.length;i++){
  let a=knots[i-1],b=knots[i],fa=value(coefficients,a),fb=value(coefficients,b);
  if(fa===0||fb===0||Math.sign(fa)===Math.sign(fb))continue;
  for(let n=0;n<70;n++){const middle=(a+b)/2,fm=value(coefficients,middle);if(Math.sign(fa)===Math.sign(fm)){a=middle;fa=fm;}else{b=middle;fb=fm;}}
  roots.push((a+b)/2);
 }
 return roots.sort((a,b)=>a-b).filter((x,i,all)=>i===0||Math.abs(x-all[i-1])>1e-10);
}

type DemandInput={speedMps:number;decel:number;braking:boolean;width:number;time:number;reaction:number;duration:number;wheelbase:number;steeringRatio:number;minimumSpeedMps:number};
export function quinticDemandExtrema(p:DemandInput){
 const k=p.braking?p.decel*p.time:0;
 const activeEnd=Math.max(0,Math.min(1,(p.duration-p.reaction)/p.time,k>0?p.speedMps/k:1));
 const validSteeringEnd=Math.min(activeEnd,k>0?Math.max(0,(p.speedMps-p.minimumSpeedMps)/k):activeEnd);
 const f=(u:number)=>60*u-180*u*u+120*u*u*u;
 const lateral=(u:number)=>p.width/p.time**2*f(u);
 const lateralCandidates=[0,activeEnd,...[(3-Math.sqrt(3))/6,(3+Math.sqrt(3))/6].filter(u=>u>0&&u<activeEnd)];
 let maxLateral=0,lateralPeakTime=p.reaction;
 for(const u of lateralCandidates){const demand=Math.abs(lateral(u));if(demand>maxLateral){maxLateral=demand;lateralPeakTime=p.reaction+u*p.time;}}
 const steeringRoots=polynomialRootsInInterval([p.speedMps,-6*p.speedMps+k,6*p.speedMps,-2*k],0,validSteeringEnd);
 let maxSteering=0,steeringPeakTime=p.reaction;
 for(const u of [0,validSteeringEnd,...steeringRoots]){
  const v=p.speedMps-k*u;
  if(v<=0||v<p.minimumSpeedMps-1e-10)continue;
  const demand=Math.abs(Math.atan(p.wheelbase*lateral(u)/v**2)*180/Math.PI*p.steeringRatio);
  if(demand>maxSteering){maxSteering=demand;steeringPeakTime=p.reaction+u*p.time;}
 }
 return {maxLateral,maxSteering,lateralPeakTime,steeringPeakTime,activeEnd,validSteeringEnd,lowSpeedLateralDemand:activeEnd>validSteeringEnd+1e-12};
}
