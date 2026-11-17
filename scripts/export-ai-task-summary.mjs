// A deterministic, allowlisted public view of the existing evaluation record.
// Reads no credentials, calls no API, and never rewrites the source record.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const sourceRelative='docs/evidence/ai-task-evaluation-20261117.json';
const outputRelative='public/validation/ai-task-results.json';
const sha256=bytes=>createHash('sha256').update(bytes).digest('hex');
const uuid=/\b[\da-f]{8}-(?:[\da-f]{4}-){3}[\da-f]{12}\b/gi;
function publicText(value){return String(value??'').replace(/\b(?:ms-|sk-)[\w-]{8,}/g,'[REDACTED]').replace(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/g,'[EMAIL]').replace(uuid,'[DOCUMENT_ID]').replace(/[A-Za-z]:[\\/][^\s，。；]+/g,'[LOCAL_PATH]');}
function excerpt(task){
 const r=task.result,s=r.structured;let text,source;
 if(!s){text=r.answer;source='answer';}
 else if(task.id==='T02-KNOWN-SHIFT'){text=[s.observations[0]?.text,s.recommendations[0]?.text].filter(Boolean).join(' ');source='structured.observations[0] + recommendations[0]';}
 else if(task.id==='T05-CURVE-SQUARE'){text=[s.observations[1]?.text,s.observations[2]?.text].filter(Boolean).join(' ');source='structured.observations[1..2]';}
 else if(task.id==='T07-PROJECT-RETRIEVAL'){text=s.observations.slice(1,4).map(x=>x.text).join(' ');source='structured.observations[1..3]';}
 else if(task.id==='T08-UNKNOWN-CALIBRATION'){text=[s.observations[1]?.text,s.recommendations[0]?.text].filter(Boolean).join(' ');source='structured.observations[1] + recommendations[0]';}
 else {text=s.observations[0]?.text??s.summary;source='structured.observations[0]';}
 const clean=publicText(text),chars=Array.from(clean),truncated=chars.length>200;
 return {kind:s?'model_answer_excerpt':'rules_fallback_excerpt',label:s?'固定评测记录：实际模型回答节选':'固定评测记录：降级后的规则回答节选',text:chars.slice(0,200).join('')+(truncated?'…':''),truncated,recordField:source};
}
const reviewLabels={
 main_answer_supported_with_citation_caveat:'主要结论一致，具体断言的引用支持范围有限',
 model_narrative_not_delivered_fallback_retained:'模型叙述未交付，保留规则结果与工具候选',
 main_answer_supported_with_wording_caveat:'主要结论一致，模型内计算不能当成实车验证',
 task_answer_supported:'回答与项目夹具及定位一致',
 appropriate_unknown_supported:'恰当承认资料未知项'
};
function publicTask(task){
 const r=task.result,review=r.semanticReview;
 assert.ok(review&&review.status!=='pending_independent_review','Independent semantic review is required');
 assert.equal(task.taskMetadataConsistent,true,'Application task metadata must match the fixed task');
 return {id:task.id,taskId:task.taskId,title:publicText(task.title),dataKind:'合成工况/项目样例',evaluatedEngineVersion:task.evaluatedEngineVersion,evaluatedSourceSetSha256:task.evaluatedSourceSetSha256,
  mode:r.mode,applicationTaskStatus:r.task.status,modelRequests:r.modelCalls,executedTools:[...r.executedTools],fallbackReason:r.fallbackReason?publicText(r.fallbackReason):null,
  semanticReview:{status:review.status,label:reviewLabels[review.status]??'参见逐题复核',mainTaskAnswer:review.mainTaskAnswer,citationSupport:review.citationSupport,
   findings:review.reviewedFindings.map(publicText),caveats:review.caveats.map(publicText),semanticAccuracy:null},
  comparison:review.comparison?Object.fromEntries(Object.entries(review.comparison).map(([key,value])=>[key,publicText(value)])):null,
  answerExcerpt:excerpt(task)};
}
function historicalSourceMap(sourceSet,record,previous){
 const candidates=[{sourceSetSha256:record.sourceSetSha256,sourceSha256:record.sourceSha256},
  {sourceSetSha256:previous?.provenance?.evaluatedLibrarySourceSetSha256,sourceSha256:previous?.provenance?.evaluatedLibrarySourceSha256},
  ...(previous?.live?.provenance?.evaluations??[])];
 const match=candidates.find(item=>item.sourceSetSha256===sourceSet&&item.sourceSha256&&sha256(JSON.stringify(item.sourceSha256))===sourceSet);
 return match?.sourceSha256??null;
}
export function buildPublicSummary(record,sourceBytes,previous=null){
 const offline=record.offline,assertions=offline.summary.fixedReferenceAssertions,runs=record.liveRuns,tasks=runs.flatMap(r=>r.tasks.map(t=>({...t,evaluatedEngineVersion:r.engineVersion,evaluatedSourceSetSha256:r.sourceSetSha256}))),review=record.independentReview;
 assert.equal(record.schemaVersion,1);assert.equal(offline.summary.taskCount,8);assert.equal(offline.tasks.length,8);
 assert.deepEqual([assertions.total,assertions.passed,assertions.distinctAssertions,assertions.variantCount],[72,72,24,3]);
 assert.equal(offline.summary.passed,true);assert.equal(tasks.length,6);assert.equal(new Set(tasks.map(t=>t.id)).size,6);
 assert.ok(review,'Top-level independent review is required');
 assert.equal(review.fixtureSha256,record.fixtureSha256);assert.ok(runs.some(r=>r.sourceSetSha256===review.sourceSetSha256),'Independent review must refer to an actual recorded live source set');
 assert.ok(runs.every(r=>r.fixtureSha256===record.fixtureSha256&&/^[a-f0-9]{64}$/.test(r.sourceSetSha256)),'Retain the live run own fixed-fixture and source identities');
 const modelRequests=tasks.reduce((sum,t)=>sum+t.result.modelCalls,0),acceptedModelAnswers=tasks.filter(t=>t.result.mode==='llm').length,fallbacks=tasks.filter(t=>t.result.mode==='fallback').length;
 assert.deepEqual([modelRequests,acceptedModelAnswers,fallbacks],[14,5,1]);
 assert.deepEqual([review.summary.modelRequests,review.summary.acceptedModelAnswers,review.summary.rulesOnlyFallbacks],[modelRequests,acceptedModelAnswers,fallbacks]);
 assert.ok(Object.keys(record.sourceSha256).every(key=>/^lib\/[a-z-]+\.ts$/.test(key)));
 assert.ok(Object.values(record.sourceSha256).every(value=>/^[a-f0-9]{64}$/.test(value)));
 assert.equal(sha256(JSON.stringify(record.sourceSha256)),record.sourceSetSha256,'Current offline file hash map must match its source set');
 const liveEvaluations=[...new Set(runs.map(r=>r.sourceSetSha256))].map(sourceSet=>({sourceSetSha256:sourceSet,sourceSha256:historicalSourceMap(sourceSet,record,previous),
  engineVersions:[...new Set(runs.filter(r=>r.sourceSetSha256===sourceSet).map(r=>r.engineVersion))],
  classification:sourceSet===record.sourceSetSha256?'recorded_live_run_for_current_sources':'historical_live_run_for_earlier_sources'}));
 const liveMatchesCurrentOfflineSources=runs.every(r=>r.sourceSetSha256===record.sourceSetSha256);
 const payload={schemaVersion:1,title:'AI 固定任务评测：合成项目样例',evaluatedEngineVersion:record.engineVersion,
  evaluatedAt:runs.at(-1).finishedAt,recordGeneratedAt:record.generatedAt,
  provenance:{record:sourceRelative,recordSha256:sha256(sourceBytes),fixtureSha256:record.fixtureSha256,
   evaluatedLibrarySourceSetSha256:liveEvaluations[0].sourceSetSha256,evaluatedLibrarySourceSha256:liveEvaluations[0].sourceSha256,
   note:'原报告包含最新离线重建及保留的真实模型记录；每组分别绑定被评测源码。兼容字段evaluatedLibrarySource*指首组真实模型的原源码，不指后来离线/应用源码。缺失历史逐文件map时保留原sourceSet且值为null，不能用当前文件反推。'},
  offline:{taskCount:8,distinctReferenceAssertions:24,variantCount:3,referenceAssertions:{passed:72,total:72},
   provenance:{engineVersion:offline.engineVersion,sourceSetSha256:record.sourceSetSha256,sourceSha256:{...record.sourceSha256},classification:'current_offline_rebuild'},
   variants:[{id:'rules_only',label:'无检索规则',realModel:false},{id:'rules_rag',label:'规则 + RAG',realModel:false},{id:'scripted_tool_contract',label:'脚本化工具契约',realModel:false}],
   extraBoundaryChecks:{...offline.summary.extraBoundaryChecks},scriptedCandidateChecks:{...offline.summary.scriptedCandidateChecks},scriptedRetrievalAnchors:{...offline.summary.scriptedRetrievalAnchors},scriptedToolPlans:{...offline.summary.scriptedToolPlans},
   tasks:offline.tasks.map(t=>({id:t.id,taskId:t.taskId,title:publicText(t.title),dataKind:'合成工况/项目夹具'})),
   note:'24项固定参考在3个软件变体上各核对一次，共72条断言；不是72个独立任务。脚本响应不计真实模型效果。'},
  live:{taskCount:tasks.length,acceptedModelAnswers,fallbacks,modelRequests,workflowComplete:tasks.filter(t=>t.result.task.status==='complete').length,
   provenance:{evaluations:liveEvaluations,matchesCurrentOfflineSources:liveMatchesCurrentOfflineSources,label:liveMatchesCurrentOfflineSources?'既有真实模型记录（与本次离线源码相同）':'历史真实模型记录（早于本次离线源码，未重跑六题）'},
   executedToolCount:tasks.reduce((sum,t)=>sum+t.result.executedTools.length,0),provider:runs[0].provider,model:runs[0].model,freeOnly:runs.every(r=>r.freeOnly),
   tasks:tasks.map(publicTask),semanticAccuracy:null,
   note:'固定6题：5个模型回答被接收，1个因引用遗漏降级，共14次请求（含应用内纠正）。这是流程记录，不是83.3%语义准确率；单独UI联调不计入本组。'+(liveMatchesCurrentOfflineSources?'':'这六题绑定原lib sourceSet，不能当成后来引用诊断补丁的真实重验。')},
  interpretation:{dataKind:'合成工况与人工编写的项目样例，不是实车数据。',
   corpusIsolation:'离线规则/RAG使用内置与夹具资料；真实API还检索到既有项目演示资料，语料未严格隔离，不能把差异归因于单一因素。',
   automatedMetricsAreSemanticAccuracy:false,userStudyPerformed:false,timeSavingMeasured:false,vehicleCalibrationPerformed:false,
   limitations:review.limitations.map(publicText),observedValue:publicText(review.observedValue)}};
 const text=JSON.stringify(payload,null,2)+'\n';
 assert.ok(!/LLM_API_KEY|__key|Authorization|"Cookie"|[A-Za-z]:[\\/]/i.test(text),'Private transport/config fields must not enter public summary');
 assert.ok(!new RegExp(uuid.source,'i').test(text),'Raw document/account UUIDs must not enter public summary');
 assert.equal(payload.live.tasks.filter(t=>t.mode==='fallback').length,1,'Failure must remain visible');
 return {payload,text};
}
export async function main(args=process.argv.slice(2)){
 assert.ok(args.every(x=>x==='--check'),'Usage: node scripts/export-ai-task-summary.mjs [--check]');
 const source=await fs.readFile(path.join(root,sourceRelative)),record=JSON.parse(source.toString('utf8'));let previous=null;
 try{previous=JSON.parse(await fs.readFile(path.join(root,outputRelative),'utf8'));}catch{}
 const {payload,text}=buildPublicSummary(record,source,previous);
 if(args.includes('--check'))assert.equal(await fs.readFile(path.join(root,outputRelative),'utf8'),text,'Public summary is stale; rebuild from the existing record');
 else {await fs.mkdir(path.dirname(path.join(root,outputRelative)),{recursive:true});await fs.writeFile(path.join(root,outputRelative),text,'utf8');}
 assert.deepEqual(await fs.readFile(path.join(root,sourceRelative)),source,'Source evaluation record must remain unchanged');
 console.log(JSON.stringify({action:args.includes('--check')?'checked':'exported',path:outputRelative,engineVersion:payload.evaluatedEngineVersion,offlineTasks:payload.offline.taskCount,offlineAssertions:payload.offline.referenceAssertions.total,liveTasks:payload.live.taskCount,accepted:payload.live.acceptedModelAnswers,fallbacks:payload.live.fallbacks,modelRequests:payload.live.modelRequests,sourceSha256:payload.provenance.recordSha256,bytes:Buffer.byteLength(text)},null,2));
 return payload;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))main().catch(error=>{console.error(error.message);process.exitCode=1;});
