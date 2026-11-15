import type { Sample } from './simulation';
export const channels=['speed','yaw','pressure','steering'] as const;
export type Channel=typeof channels[number];
export type LogRow={time:number}&Partial<Record<Channel,number>>;
export type LogData={name:string;rows:LogRow[];dropped:number;duplicates:number;missing:string[];offset:number};
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
 return{name,rows:unique.map(r=>({...r,time:r.time-origin+offset})),dropped,duplicates:rows.length-unique.length,missing,offset};
}
export function compare(sim:Sample[],log:LogData,thresholds:Record<Channel,number>){
 return channels.map(k=>{const data=log.rows.filter(r=>r[k]!==undefined);let i=0;const errors:number[]=[];for(const s of sim){if(data.length<2||s.time<data[0].time||s.time>data[data.length-1].time)continue;while(i<data.length-2&&data[i+1].time<s.time)i++;const a=data[i],b=data[i+1];const value=a[k]!+(b[k]!-a[k]!)*(s.time-a.time)/(b.time-a.time);errors.push(Math.abs(value-s[k]));}const n=errors.length;return{key:k,n,mae:n?errors.reduce((a,b)=>a+b,0)/n:null,rmse:n?Math.sqrt(errors.reduce((a,b)=>a+b*b,0)/n):null,max:n?Math.max(...errors):null,pass:n?Math.max(...errors)<=thresholds[k]:null};});
}
export function sampleCSV(rows:Sample[],demo=false){return '\uFEFFtime_s,speed_kmh,yaw_rate_dps,brake_pressure_bar,steering_angle_deg\n'+rows.map((r,i)=>[String(r.time),(r.speed+(demo?Math.sin(i*.2)*.7:0)).toFixed(3),(r.yaw+(demo?Math.sin(i*.1)*.3:0)).toFixed(3),(r.pressure+(demo?Math.abs(Math.sin(i*.12))*.8:0)).toFixed(3),(r.steering+(demo?Math.sin(i*.15)*1.5:0)).toFixed(3)].join(',')).join('\n');}

