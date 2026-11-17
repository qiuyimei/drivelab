import {z} from 'zod';
import {validateConfig,type Config} from './simulation';
import type {AnalysisResult} from './analysis';
import {buildAnalysisTaskResult,getAnalysisTaskDefinition} from './analysis-tasks';

// Shared persistence boundary: safe structure is not a signature or a proof
// that every natural-language claim is true.
const number=z.number().finite(),text=z.string().max(64000),id=z.string().min(1).max(300);
const risk=z.enum(['约束内','需关注','高风险']),channel=z.enum(['speed','yaw','pressure','steering']);
const nullableNumber=number.nullable();
const config=z.custom<Config>(v=>{try{validateConfig(v as Config);return true;}catch{return false;}});
const fact=z.object({id,label:text,value:number,unit:text,origin:z.enum(['simulation','log']),detail:text.optional()}).passthrough();
const finding=z.object({level:z.enum(['pass','warn','fail']),title:text,detail:text,source:id}).passthrough();
const comparison=z.object({key:channel,n:number.int().min(0),mae:nullableNumber,rmse:nullableNumber,max:nullableNumber,bias:nullableNumber,pass:z.boolean().nullable(),peakTime:nullableNumber,peakSamples:number.int().min(0),start:nullableNumber,end:nullableNumber,coverage:number.min(0).max(1),qualityWarnings:z.array(text),metricBasis:text}).passthrough();
const compact=z.object({engineVersion:id,config,risk,findings:z.array(finding).max(100),facts:z.array(fact).max(256),comparison:z.array(comparison).max(4),log:z.object({name:text,rowCount:number.int().min(2).max(20000),offset:number.min(-60).max(60),missing:z.array(channel).max(4)}).nullable(),limitations:z.array(text).max(100)}).passthrough();
const patch=z.record(z.string(),number).refine(v=>Object.keys(v).every(k=>['speed','distance','reaction','laneTime'].includes(k)));
const state=z.object({risk,utilization:number,lateral:number,gap:nullableNumber});
const claim=z.object({text,factIds:z.array(id).max(12),sourceIds:z.array(id).max(8)});
const structured=z.object({summary:text,observations:z.array(claim).min(1).max(6),recommendations:z.array(claim).min(1).max(6),limitations:z.array(text).min(1).max(8)});
const source=z.object({id,chunkId:id,title:text,body:text,start:number.int().min(0),end:number.int().min(0),page:number.int().positive().nullable(),section:text,basis:text,referenceUrl:text.nullable(),locator:text,reviewStatus:text}).passthrough();
const candidate=z.object({id:z.string().regex(/^CAND_[1-9]\d*$/),kind:z.enum(['default','tool']),label:text,patch,baselineFingerprint:z.string().regex(/^[a-f0-9]{24}$/),toolCallId:id.optional(),applied:z.literal(false),evidence:compact}).passthrough();
const task=z.object({id:z.enum(['risk-review','log-review','compare-options','knowledge-question']),title:z.string().min(1).max(100),goal:z.string().min(1).max(500),question:z.string().max(2000).optional(),status:z.enum(['complete','partial','rules-only']),checks:z.array(z.object({id:z.enum(['baseline-evidence','bound-log','measurement-tool','candidate-tool','knowledge-tool','knowledge-evidence','model-output']),label:z.string().min(1).max(100),passed:z.boolean(),detail:z.string().max(1000)}).strict()).min(1).max(8)}).strict();
const toolRecord=z.object({name:z.enum(['inspect_simulation','compare_measurement','search_knowledge','evaluate_parameters']),sourceIds:z.array(id).max(9).optional(),candidateId:id.optional()}).strict();
const schema=z.object({
 answer:text,structured:structured.nullable(),sources:z.array(source).max(30),mode:z.enum(['rules','llm','fallback']),fallbackReason:text.nullable(),evidence:compact,
 factRegistry:z.array(fact).max(512),candidates:z.array(candidate).max(30),
 alternatives:z.array(z.object({label:text,patch,before:state,after:state,note:text,candidateId:id,factIds:z.array(id)}).passthrough()).max(10),
 trace:z.array(z.object({id,label:text,kind:z.enum(['calculation','retrieval','model','validation']),status:z.enum(['running','complete','warning']),detail:text,durationMs:number.min(0).optional(),tool:toolRecord.optional()}).passthrough()).max(100),
 task:task.nullable().optional(),
 engineVersion:id,fingerprint:z.string().regex(/^[a-f0-9]{24}$/),generatedAt:z.string().refine(s=>Number.isFinite(Date.parse(s))),model:text.nullable(),provider:text.nullable(),modelCalls:number.int().min(0).max(3),usage:z.object({input:number.min(0),output:number.min(0)}),durationMs:number.min(0)
}).passthrough().superRefine((v,ctx)=>{
 const ids=v.factRegistry.map(f=>f.id),registered=new Set(ids),sourceIds=new Set(v.sources.map(s=>s.chunkId));
 const reject=(message:string)=>ctx.addIssue({code:'custom',message});
 if(registered.size!==ids.length)reject('重复事实编号');
 if(v.engineVersion!==v.evidence.engineVersion)reject('引擎版本不一致');
 for(const f of v.evidence.facts)if(!registered.has(f.id))reject('缺少基线事实');
 for(const c of v.candidates){
  if(c.baselineFingerprint!==v.fingerprint||c.evidence.engineVersion!==v.engineVersion)reject('候选基线不一致');
  for(const f of c.evidence.facts)if(!f.id.startsWith(c.id+'__')||!registered.has(f.id))reject('候选事实未登记');
 }
 for(const a of v.alternatives)if(!v.candidates.some(c=>c.id===a.candidateId)||a.factIds.some(f=>!registered.has(f)))reject('候选引用未登记');
 if(v.structured)for(const c of [...v.structured.observations,...v.structured.recommendations])if(c.factIds.some(f=>!registered.has(f))||c.sourceIds.some(s=>!sourceIds.has(s)))reject('分析引用未登记');
 for(const step of v.trace){if(!step.tool)continue;const tool=step.tool;
  if(step.status!=='complete'||step.label!=='执行工具：'+tool.name)reject('工具执行记录不一致');
  if(tool.name==='search_knowledge'){
   if(!tool.sourceIds||new Set(tool.sourceIds).size!==tool.sourceIds.length||tool.sourceIds.some(sourceId=>!sourceIds.has(sourceId))||tool.candidateId!==undefined)reject('工具资料记录未登记');
  }else if(tool.sourceIds!==undefined)reject('工具资料字段无效');
  if(tool.name==='evaluate_parameters'){
   if(!v.candidates.some(c=>c.id===tool.candidateId&&c.kind==='tool'))reject('工具候选记录未登记');
  }else if(tool.candidateId!==undefined)reject('工具候选字段无效');
 }
 if(v.task){
  const definition=getAnalysisTaskDefinition(v.task.id);
  if(v.task.title!==definition.title||v.task.goal!==definition.goal)reject('任务定义不一致');
  if(definition.requiresLog&&!v.evidence.log)reject('日志任务缺少日志');
  const expected=buildAnalysisTaskResult(v.task.id,v.task.question??'',v);
  if(v.task.status!==expected.status||JSON.stringify(v.task.checks)!==JSON.stringify(expected.checks))reject('任务检查与执行产物不一致');
 }
});

export function validatedAnalysisBundle(input:unknown):AnalysisResult|null{
 if(input===null||input===undefined)return null;
 const parsed=schema.safeParse(input);if(!parsed.success)throw Error('分析快照结构无效或不完整，请重新分析后保存');
 const value=parsed.data,original=input as AnalysisResult;
 // Keep existing valid snapshots stable; normalize only legacy missing fields.
 if(value.task&&value.task.question===undefined)return {...original,task:buildAnalysisTaskResult(value.task.id,'',value)};
 if(!Object.prototype.hasOwnProperty.call(input,'task'))return {...original,task:null};
 return original;
}
