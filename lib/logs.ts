import type { Sample } from './simulation';
export const channels=['speed','yaw','pressure','steering'] as const;
export type Channel=typeof channels[number];
export type LogRow={time:number}&Partial<Record<Channel,number>>;
export type LogData={name:string;rows:LogRow[];dropped:number;duplicates:number;missing:string[];offset:number};
export const IMPORTED_LOG_SOURCE_NOTICE='导入日志来源未核验；文件名不能证明实测、合成或公开数据出处。公开或演示数据不能作为本模型的车型标定证据。';
export const channelMeta={speed:{label:'车速',unit:'km/h',threshold:2},yaw:{label:'横摆角速度',unit:'°/s',threshold:2},pressure:{label:'制动压力',unit:'bar',threshold:5},steering:{label:'方向盘转角',unit:'°',threshold:10}};
const aliases:Record<string,string[]>={time:['time','t','timestamp','time_s','timestamp_ms','time_ms','时间','时间戳'],speed:['speed','speed_kmh','vehicle_speed','velocity','车速','speed_mps'],yaw:['yaw','yaw_rate','yaw_rate_dps','横摆角速度','yaw_rate_rad'],pressure:['pressure','brake_pressure','brake_pressure_bar','制动压力'],steering:['steering','steering_angle','steering_angle_deg','方向盘转角','转向角']};
function csv(text:string){const lines:string[][]=[];let row:string[]=[],cell='',quoted=false;const sep=text.split(/\r?\n/)[0].includes('\t')?'\t':',';for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){cell+='"';i++;}else quoted=!quoted;}else if(c===sep&&!quoted){row.push(cell.trim());cell='';}else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell.trim());if(row.some(Boolean))lines.push(row);row=[];cell='';}else cell+=c;}if(quoted)throw Error('CSV 引号未闭合');row.push(cell.trim());if(row.some(Boolean))lines.push(row);const heads=lines.shift();if(!heads)throw Error('文件为空');return lines.map(r=>Object.fromEntries(heads.map((h,i)=>[h,r[i]??''])));}
export function parseLog(text:string,name:string,options:{timeUnit?:string;speedUnit?:string;yawUnit?:string;offset?:number}={}):LogData{
 if(text.length>5*1024*1024)throw Error('文件不能超过 5 MB');
 let input:Record<string,unknown>[];
 if(name.toLowerCase().endsWith('.json')){const v=JSON.parse(text);input=Array.isArray(v)?v:v&&typeof v==='object'?v.data??v.rows:undefined;if(!Array.isArray(input))throw Error('JSON 需要记录数组，或包含 data / rows 数组');}else input=csv(text.replace(/^\uFEFF/,''));
 if(input.length>20000)throw Error('单次最多导入 20,000 行');
 if(!input.length)throw Error('文件中没有数据');
 const keys=Array.from(new Set(input.flatMap(r=>r&&typeof r==='object'?Object.keys(r):[])));
 const map=Object.fromEntries(Object.entries(aliases).map(([k,a])=>[k,keys.find(key=>a.includes(key.trim().toLowerCase()))]));
 if(!map.time)throw Error('未找到时间列，支持 time、time_s、timestamp_ms 或 时间');
 const missing=channels.filter(k=>!map[k]);if(missing.length===4)throw Error('至少需要车速、横摆角速度、制动压力、方向盘转角中的一列');
 const rows:LogRow[]=[];let dropped=0;
 const numeric=(v:unknown)=>(typeof v==='number'||typeof v==='string')&&String(v).trim()!==''&&Number.isFinite(Number(v))?Number(v):undefined;
 for(const r of input){if(!r||typeof r!=='object'){dropped++;continue;}const t=numeric(r[map.time!]);if(t===undefined){dropped++;continue;}const item:LogRow={time:t/((options.timeUnit==='ms'||(options.timeUnit!=='s'&&map.time!.trim().toLowerCase().includes('_ms')))?1000:1)};for(const k of channels){if(!map[k])continue;const v=numeric(r[map[k]!]);if(v!==undefined)item[k]=v*(k==='speed'&&(options.speedUnit==='m/s'||(options.speedUnit!=='km/h'&&map[k]!.trim().toLowerCase()==='speed_mps'))?3.6:k==='yaw'&&(options.yawUnit==='rad/s'||(options.yawUnit!=='deg/s'&&map[k]!.trim().toLowerCase()==='yaw_rate_rad'))?180/Math.PI:1);}if(channels.every(k=>item[k]===undefined)){dropped++;continue;}rows.push(item);}
 rows.sort((a,b)=>a.time-b.time);const unique=[...new Map(rows.map(r=>[r.time,r])).values()];if(unique.length<2)throw Error('至少需要两个不同时间点的有效数据');
 const origin=unique[0].time,offset=options.offset??0;if(!Number.isFinite(offset)||Math.abs(offset)>60)throw Error('偏移必须在 ±60 秒内');
 if(unique.some(r=>!Number.isFinite(r.time-origin+offset)||channels.some(k=>r[k]!==undefined&&Math.abs(r[k]!)>1e6)))throw Error('日志数值超出导入范围，请检查时间格式和采集单位（通道绝对值不超过 1,000,000）');
 return{name,rows:unique.map(r=>({...r,time:r.time-origin+offset})),dropped,duplicates:rows.length-unique.length,missing:channels.filter(k=>!unique.some(r=>r[k]!==undefined)),offset};
}
// A quality warning threshold, not a universal sensor sampling requirement.
export const LONG_INTERPOLATION_GAP_S=1;
const metricBasis='MAE/RMSE 按共同区间内原仿真时间网格作等点权平均；最大误差/峰值时刻按两时间网格并集上的分段线性差值计算。插值不代表采样间的真实连续测量。';
function interpolatedValue<T extends {time:number}>(data:T[],time:number,value:(row:T)=>number){
 let lo=0,hi=data.length-1;
 while(hi-lo>1){const mid=(lo+hi)>>1;if(data[mid].time<=time)lo=mid;else hi=mid;}
 const a=data[lo],b=data[hi];
 return value(a)+(value(b)-value(a))*(time-a.time)/(b.time-a.time);
}
// Plot-only clipping of the same per-channel piecewise-linear series used by
// compare(). Boundary vertices are interpolated, never new measured samples;
// do not write them back to LogData or use them to count/statistically compare.
export function clipLogChannelToWindow(rows:readonly LogRow[],channel:Channel,start:number,end:number):LogRow[]{
 if(!Number.isFinite(start)||!Number.isFinite(end)||end<start)return [];
 const data=rows.filter(row=>row[channel]!==undefined);
 if(!data.length)return [];
 const lo=Math.max(start,data[0].time),hi=Math.min(end,data.at(-1)!.time);
 if(lo>hi)return [];
 if(data.length===1)return [{time:data[0].time,[channel]:data[0][channel]}];
 const existing=new Map(data.map(row=>[row.time,row[channel]!]));
 const times=[...new Set([lo,...data.filter(row=>row.time>=lo&&row.time<=hi).map(row=>row.time),hi])].sort((a,b)=>a-b);
 return times.map(time=>({time,[channel]:existing.get(time)??interpolatedValue(data,time,row=>row[channel]!)}));
}
export function compare(sim:Sample[],log:LogData,thresholds:Record<Channel,number>){
 return channels.map(k=>{
  const data=log.rows.filter(r=>r[k]!==undefined);
  let i=0;const errors:number[]=[];
  // Keep the original uniform simulation-grid MAE/RMSE and n contract.
  for(const s of sim){
   if(data.length<2||s.time<data[0].time||s.time>data[data.length-1].time)continue;
   while(i<data.length-2&&data[i+1].time<s.time)i++;
   const a=data[i],b=data[i+1];
   const value=a[k]!+(b[k]!-a[k]!)*(s.time-a.time)/(b.time-a.time);
   errors.push(Math.abs(value-s[k]));
  }
  const n=errors.length;
  const start=sim.length>=2&&data.length>=2?Math.max(sim[0].time,data[0].time):null;
  const end=sim.length>=2&&data.length>=2?Math.min(sim.at(-1)!.time,data.at(-1)!.time):null;
  const hasOverlap=start!==null&&end!==null&&start<=end;
  // The difference of two piecewise-linear series is linear between their
  // combined knots. Its absolute maximum occurs at one of these knots.
  const peakTimes=hasOverlap?[...new Set([start!,end!,...sim.map(r=>r.time),...data.map(r=>r.time)].filter(t=>t>=start!&&t<=end!))].sort((a,b)=>a-b):[];
  let max:number|null=null,peakTime:number|null=null,peakError:number|null=null;
  for(const time of peakTimes){
   const error=interpolatedValue(data,time,r=>r[k]!)-interpolatedValue(sim,time,r=>r[k]);
   if(max===null||Math.abs(error)>max){max=Math.abs(error);peakTime=time;peakError=error;}
  }
  let maxInterpolationGap:number|null=null;
  if(hasOverlap)for(let j=1;j<data.length;j++){
   if(Math.min(data[j].time,end!)>Math.max(data[j-1].time,start!))maxInterpolationGap=Math.max(maxInterpolationGap??0,data[j].time-data[j-1].time);
  }
  const overlapSourceSamples=hasOverlap?data.filter(r=>r.time>=start!&&r.time<=end!).length:0;
  const qualityWarnings:string[]=[];
  if(data.length<2)qualityWarnings.push('该通道不足两个有效采集点，无法建立分段线性对比。');
  else if(!hasOverlap)qualityWarnings.push('该通道与仿真没有共同时间区间，未计算误差或外推。');
  else{
   if(overlapSourceSamples<=2)qualityWarnings.push(`共同区间内只有 ${overlapSourceSamples} 个原始采集点，插值后的点数不能视为独立测量数量。`);
   if(maxInterpolationGap!==null&&maxInterpolationGap>LONG_INTERPOLATION_GAP_S)qualityWarnings.push(`采集点最大间隔 ${maxInterpolationGap.toFixed(3)} s 超过 ${LONG_INTERPOLATION_GAP_S} s 提醒阈值；线性插值无法确认停采间隙内的实际变化。`);
   if(!n)qualityWarnings.push('共同区间内没有原仿真网格点，MAE/RMSE 不可用，仅报告两网格并集峰值。');
   if(start===end)qualityWarnings.push('共同时间范围只有单点，不能代表一段持续工况。');
  }
  return {key:k,n,mae:n?errors.reduce((a,b)=>a+b,0)/n:null,rmse:n?Math.sqrt(errors.reduce((a,b)=>a+b*b,0)/n):null,
   max,pass:max===null?null:max<=thresholds[k],peakTime,peakError,peakSamples:peakTimes.length,gridMax:n?Math.max(...errors):null,
   sourceSamples:data.length,overlapSourceSamples,maxInterpolationGap,overlapStart:hasOverlap?start:null,overlapEnd:hasOverlap?end:null,
   qualityWarnings,metricBasis};
 });
}
export function sampleCSV(rows:Sample[],demo=false){return '\uFEFFtime_s,speed_kmh,yaw_rate_dps,brake_pressure_bar,steering_angle_deg\n'+rows.map((r,i)=>[String(r.time),(r.speed+(demo?Math.sin(i*.2)*.7:0)).toFixed(3),(r.yaw+(demo?Math.sin(i*.1)*.3:0)).toFixed(3),(r.pressure+(demo?Math.abs(Math.sin(i*.12))*.8:0)).toFixed(3),(r.steering+(demo?Math.sin(i*.15)*1.5:0)).toFixed(3)].join(',')).join('\n');}

