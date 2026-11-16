import {simulate,type Config,type Simulation} from './simulation';
import {channels,channelMeta,compare,type Channel,type LogData} from './logs';
export const ENGINE_VERSION='1.1.2';
export const defaultThresholds:Record<Channel,number>={speed:2,yaw:2,pressure:5,steering:10};
export type Fact={id:string;label:string;value:number;unit:string;origin:'simulation'|'log';detail?:string};
export function validatedThresholds(input:unknown):Record<Channel,number>{if(input===undefined)return {...defaultThresholds};if(!input||typeof input!=='object')throw Error('容差格式无效');const values={} as Record<Channel,number>;for(const k of channels){const v=(input as Record<string,unknown>)[k];if(typeof v!=='number'||!Number.isFinite(v)||v<0||v>10000)throw Error(channelMeta[k].label+'容差必须是 0–10000 的有限数值');values[k]=v;}return values;}
export function validatedLog(input:unknown):LogData|null{
 if(input===null||input===undefined)return null;
 if(!input||typeof input!=='object')throw Error('日志格式无效');const v=input as LogData;
 if(typeof v.name!=='string'||v.name.length>200||!Array.isArray(v.rows)||v.rows.length<2||v.rows.length>20000)throw Error('日志需要 2–20000 行有效数据');
 let previous=-Infinity;for(const r of v.rows){if(!r||!Number.isFinite(r.time)||r.time<=previous)throw Error('日志时间必须有效且严格递增，请重新导入');previous=r.time;let valid=0;for(const k of channels){if(r[k]!==undefined){if(!Number.isFinite(r[k])||Math.abs(r[k]!)>1e6)throw Error('日志通道必须为有效数值且绝对值不超过 1,000,000，请检查采集单位');valid++;}}if(!valid)throw Error('日志行缺少有效采集通道');}
 if(!Number.isFinite(v.offset)||Math.abs(v.offset)>60)throw Error('时间偏移无效');
 return {name:v.name,rows:v.rows.map(r=>Object.fromEntries(Object.entries(r).filter(([k])=>k==='time'||channels.includes(k as Channel))) as LogData['rows'][number]),offset:v.offset,dropped:Number.isInteger(v.dropped)&&v.dropped>=0?v.dropped:0,duplicates:Number.isInteger(v.duplicates)&&v.duplicates>=0?v.duplicates:0,missing:channels.filter(k=>!v.rows.some(r=>r[k]!==undefined))};
}
function interpolate(data:LogData['rows'],time:number,k:Channel){let lo=0,hi=data.length-1;while(hi-lo>1){const m=(lo+hi)>>1;if(data[m].time<=time)lo=m;else hi=m;}const a=data[lo],b=data[hi];return a[k]!+(b[k]!-a[k]!)*(time-a.time)/(b.time-a.time);}
export function detailedComparison(s:Simulation,log:LogData,thresholds:Record<Channel,number>){return compare(s.rows,log,thresholds).map(stat=>{
 const data=log.rows.filter(r=>r[stat.key]!==undefined);const start=stat.overlapStart,end=stat.overlapEnd;
 const pairs=data.length>=2?s.rows.filter(r=>r.time>=data[0].time&&r.time<=data.at(-1)!.time).map(r=>({time:r.time,error:interpolate(data,r.time,stat.key)-r[stat.key]})):[];
 return {...stat,threshold:thresholds[stat.key],unit:channelMeta[stat.key].unit,label:channelMeta[stat.key].label,bias:pairs.length?pairs.reduce((a,b)=>a+b.error,0)/pairs.length:null,peakTime:stat.peakTime,start,end,coverage:stat.peakSamples?Math.max(0,end!-start!)/s.config.duration:0};
});}
export type Comparison=ReturnType<typeof detailedComparison>;
export function evidenceFor(config:Config,rawLog?:unknown,rawThresholds?:unknown){
 const simulation=simulate(config),log=validatedLog(rawLog),thresholds=validatedThresholds(rawThresholds),comparison=log?detailedComparison(simulation,log,thresholds):[];
 const facts:Fact[]=[{id:'SIM_UTILIZATION',label:'峰值附着利用率',value:simulation.maxUtil*100,unit:'%',origin:'simulation'},{id:'SIM_LATERAL',label:'峰值侧向加速度',value:simulation.maxLat,unit:'m/s²',origin:'simulation'},{id:'SIM_STEERING',label:'方向盘转角峰值',value:simulation.maxSteer,unit:'°',origin:'simulation'}];
 if(simulation.braking){facts.push({id:'SIM_STOPPING_DISTANCE',label:'解析停车距离',value:simulation.stoppingDistance,unit:'m',origin:'simulation'},{id:'SIM_STOP_TIME',label:'解析停车时间',value:simulation.stopTime,unit:'s',origin:'simulation'},{id:'SIM_GAP',label:'全过程预测最小间距',value:simulation.predictedMinGap!,unit:'m',origin:'simulation'});}
 for(const c of comparison)for(const [metric,label] of [['mae','MAE'],['rmse','RMSE'],['max','最大绝对误差'],['bias','平均偏差']] as const){const value=c[metric];if(typeof value==='number'&&Number.isFinite(value))facts.push({id:`LOG_${c.key.toUpperCase()}_${metric.toUpperCase()}`,label:channelMeta[c.key].label+' '+label,value,unit:c.unit,origin:'log',detail:`共同区间 ${c.start?.toFixed(3)}–${c.end?.toFixed(3)} s；${metric==='max'?`两网格并集 ${c.peakSamples} 个判定点，峰值时刻 ${c.peakTime?.toFixed(3)} s`:`原仿真网格 ${c.n} 个等权统计点`}；原始采集 ${c.overlapSourceSamples} 点`});}
 const limitations=['水平路面与运动学需求模型，不包含轮胎非线性、载荷转移和闭环控制。','工程阈值与制动力增益为可配置初始值，需要车型标定与专业审核。'];
 if(log?.name.includes('演示'))limitations.push('本次绑定的是合成演示日志，不能作为实车标定证据。');
 if(log)limitations.push('误差仅描述两组数据的差异；未经工况、车型和采样一致性确认，不能当成模型精度或传感器故障证据。');
 if(log?.name.includes('comma2k19'))limitations.push('comma2k19 公开样本仅演示导入、单位与时间轴，不是本模型的受控工况验证数据。');
 if(log?.missing.length)limitations.push('缺少通道：'+log.missing.map(k=>channelMeta[k as Channel].label).join('、')+'，不会补造。');
 if(!log)limitations.push('本次未绑定测量日志，不能诊断具体实车偏差。');
 if(comparison.some(c=>c.peakSamples&&c.coverage<.5))limitations.push('部分通道共同时间覆盖率小于 50%，误差统计的代表性有限。');
 for(const c of comparison)for(const warning of c.qualityWarnings)limitations.push(c.label+'：'+warning);
 return {engineVersion:ENGINE_VERSION,simulation,log,thresholds,comparison,facts,limitations};
}
export type Evidence=ReturnType<typeof evidenceFor>;
export function compactEvidence(e:Evidence){return {engineVersion:e.engineVersion,config:e.simulation.config,risk:e.simulation.risk,findings:e.simulation.findings,facts:e.facts,comparison:e.comparison,log:e.log?{name:e.log.name,rowCount:e.log.rows.length,offset:e.log.offset,missing:e.log.missing}:null,limitations:e.limitations};}
export type CandidateEvidence={id:string;kind:'default'|'tool';label:string;patch:Partial<Config>;baselineFingerprint:string;toolCallId?:string;applied:false;evidence:ReturnType<typeof compactEvidence>};
export function createCandidateEvidence(id:string,baseline:Evidence,patch:Partial<Config>,kind:CandidateEvidence['kind'],label:string,baselineFingerprint:string,toolCallId?:string):CandidateEvidence{
 if(!/^CAND_[1-9]\d*$/.test(id))throw Error('候选证据编号无效');
 const candidate=compactEvidence(evidenceFor({...baseline.simulation.config,...patch},null,baseline.thresholds));
 return {id,kind,label,patch:{...patch},baselineFingerprint,...(toolCallId?{toolCallId}:{}),applied:false,evidence:{...candidate,facts:candidate.facts.map(f=>({...f,id:id+'__'+f.id}))}};
}
export function scenarioAlternatives(e:Evidence){const c=e.simulation.config;const proposals:{label:string;patch:Partial<Config>}[]=[];if(c.speed>0)proposals.push({label:'初始车速降低 20%',patch:{speed:c.speed*.8}});if(['lane','avoid'].includes(c.scenario)&&c.laneTime<12){const laneTime=Math.min(12,c.laneTime*1.25);proposals.push({label:'换道时长延长至 '+Number(laneTime.toFixed(3))+' s',patch:{laneTime}});}if(e.simulation.braking&&c.distance<1000){const distance=Math.min(1000,c.distance+20);proposals.push({label:'初始间距增加至 '+Number(distance.toFixed(3))+' m',patch:{distance}});}return proposals.flatMap(p=>{try{const r=simulate({...c,...p.patch});return [{...p,before:{risk:e.simulation.risk,utilization:e.simulation.maxUtil,lateral:e.simulation.maxLat,gap:e.simulation.predictedMinGap},after:{risk:r.risk,utilization:r.maxUtil,lateral:r.maxLat,gap:r.predictedMinGap},note:'独立候选重算，不会自动修改当前工况；不能由此认定实车安全。'}];}catch{return [];}});}
