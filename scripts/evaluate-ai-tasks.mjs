import identity from '../config/identity.json' with {type:'json'};
// Controlled software task evaluation. Offline is the default; --live is explicit.
// No model secret is read. Live calls use the existing local app and its free-only guard.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import ts from 'typescript';

export const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
export const fixturePath=path.join(root,'validation/ai-task-cases.json');
export const reportPath=path.join(root,'docs/evidence/ai-task-evaluation-20261117.json');
const moduleNames=['trajectory-extrema','simulation','logs','knowledge-sources','rag','retrieval','evidence','provider','fingerprint','analysis-tasks','analysis'];
const hash=text=>createHash('sha256').update(text).digest('hex');
const close=(a,b,tolerance=1e-8)=>typeof a==='number'&&Number.isFinite(a)&&Math.abs(a-b)<=tolerance;
const samePatch=(a,b)=>Object.keys(a).length===Object.keys(b).length&&Object.entries(b).every(([key,value])=>a[key]===value);
const scrub=value=>String(value??'').replace(/\b(?:ms-|sk-)[\w-]{8,}/g,'[REDACTED]').slice(0,1200);

export async function loadFixture(){return JSON.parse(await fs.readFile(fixturePath,'utf8'));}
export function analyticReference(config){
 const v=config.speed/3.6,a=Math.min(config.decel,config.brakeLimit,config.mu*9.81);
 const q=Math.max((config.speed-(config.scenario==='highway'?config.leadSpeed:0))/3.6,0);
 return {SIM_STOPPING_DISTANCE:v*config.reaction+v*v/(2*a),SIM_STOP_TIME:v>0?config.reaction+v/a:0,
  SIM_GAP:config.distance-q*config.reaction-q*q/(2*a),
  SIM_LATERAL:config.scenario==='curve'?v*v/config.radius:config.scenario==='lane'?(10*Math.sqrt(3)/3)*config.laneWidth/config.laneTime**2:null};
}
export function validateFixture(fixture){
 const failures=[];if(fixture.cases.length!==8)failures.push('exactly eight fixed cases required');
 if(fixture.cases.filter(c=>c.liveSelected).length!==6)failures.push('exactly six preselected live cases required');
 for(const task of fixture.cases){
  const config={...fixture.baseConfig,...task.configPatch},reference=analyticReference(config);
  for(const [key,value] of Object.entries(task.gold.facts??{}))if(key.startsWith('SIM_')&&!close(reference[key],value))failures.push(task.id+': independent '+key);
  for(const candidate of task.gold.candidates??[]){const next=analyticReference({...config,...candidate.patch});for(const [key,value] of Object.entries(candidate.facts))if(!close(next[key],value))failures.push(task.id+': independent candidate '+key);}
 }
 if(fixture.limits.maxTotalRequests!==18||fixture.limits.maxRequestsPerTask!==3)failures.push('request cap must remain 18 / 3');
 return failures;
}
export async function loadApplication(){
 const contents=await Promise.all(moduleNames.map(async name=>[name,await fs.readFile(path.join(root,'lib',name+'.ts'),'utf8')]));
 const sourceSha256=Object.fromEntries(contents.map(([name,code])=>['lib/'+name+'.ts',hash(code)]));
 const sourceSetSha256=hash(JSON.stringify(sourceSha256)),out=path.join(root,'.sites-runtime/ai-task-evaluation/compiled-'+sourceSetSha256.slice(0,16));
 await fs.mkdir(out,{recursive:true});
 for(const [name,code] of contents){const js=ts.transpileModule(code,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText.replace(/from ['"]\.\/([a-z-]+)['"]/g,"from './$1.mjs'");await fs.writeFile(path.join(out,name+'.mjs'),js,'utf8');}
 const modules=await Promise.all(['simulation','logs','evidence','analysis','retrieval'].map(name=>import(pathToFileURL(path.join(out,name+'.mjs')).href)));
 return {simulation:modules[0],logs:modules[1],evidence:modules[2],analysis:modules[3],retrieval:modules[4],sourceSha256,sourceSetSha256};
}
export function projectDocument(fixture,id=fixture.projectFixture.id){const d=fixture.projectFixture;return {id,title:d.title,body:d.body,metadata:JSON.stringify({kind:'text',sourceName:'合成项目资料夹具.txt',segments:[{text:d.body,page:d.page,section:d.section}],reviewStatus:'unreviewed'})};}
export function buildInput(task,fixture,app,offsetOverride){
 const config={...fixture.baseConfig,...task.configPatch};let log=null;
 if(task.log){const spec=task.log,count=Math.round(spec.duration/spec.step),lines=['time_s,speed_kmh'];
  for(let i=0;i<=count;i++){const time=Math.min(i*spec.step,spec.duration),speed=spec.value+(spec.kind==='linear'?spec.slope*time:0);lines.push((17+time)+','+speed);}
  log=app.logs.parseLog(lines.join('\n'),'合成评测-'+task.id+'.csv',{offset:offsetOverride??spec.offset});
 }
 return {config,log,thresholds:{...fixture.thresholds},question:task.question,taskId:task.taskId};
}
function check(label,actual,expected,tolerance=1e-8){return {label,actual:actual??null,expected,pass:typeof expected==='number'?close(actual,expected,tolerance):actual===expected};}
export function numericChecks(result,task){
 const e=result.evidence,checks=[];
 for(const [key,value] of Object.entries(task.gold.facts??{}))checks.push(check(key,e.facts.find(f=>f.id===key)?.value,value));
 if(task.gold.comparison){const stat=e.comparison.find(c=>c.key==='speed');for(const [key,value] of Object.entries(task.gold.comparison))checks.push(check('speed.'+key,stat?.[key],value));}
 if(task.gold.missing)checks.push({label:'missing_channels',actual:e.log?.missing??[],expected:task.gold.missing,pass:JSON.stringify(e.log?.missing)===JSON.stringify(task.gold.missing)});
 return checks;
}
export function candidateChecks(result,task,requireTool=false){return (task.gold.candidates??[]).map(expected=>{
 const candidate=(result.candidates??[]).find(c=>samePatch(c.patch,expected.patch)&&(!requireTool||c.kind==='tool'));
 const checks=Object.entries(expected.facts).map(([key,value])=>check(key,candidate?.evidence.facts.find(f=>f.id.endsWith('__'+key))?.value,value));
 checks.push(check('reaction_unchanged',candidate?.evidence.config.reaction,result.evidence.config.reaction));
 checks.push(check('not_automatically_applied',candidate?.applied,false));
 return {patch:expected.patch,requiredKind:requireTool?'tool':'any',candidateId:candidate?.id??null,available:!!candidate,checks,pass:!!candidate&&checks.every(c=>c.pass)};
});}
export function answerScreen(answer,task){
 // Number presence and regex matches are transparent screening signals, not semantic correctness.
 const numbers=[...String(answer).matchAll(/[-+]?(?:\d+\.\d+|\d+)/g)].map(m=>Number(m[0]));
 const signals=(task.answerSignals??[]).map(s=>({id:s.id,matched:new RegExp(s.pattern,'iu').test(answer)}));
 const mentions=(task.gold.answerNumbers??[]).map(m=>({...m,matched:numbers.some(n=>Math.abs(n-m.value)<=m.tolerance)}));
 return {basis:'数字出现与显式正则筛查；不判断数字所属对象、因果关系、引用相关性或完整语义。',signals,numericMentions:mentions,matched:signals.filter(x=>x.matched).length+mentions.filter(x=>x.matched).length,total:signals.length+mentions.length,semanticAccuracy:null};
}
export function citationScreen(result){
 if(!result.structured)return {applicable:false,reason:'规则回答无模型结构化逐条引用'};
 const facts=new Set((result.factRegistry??result.evidence.facts).map(f=>f.id)),sources=new Set(result.sources.map(s=>s.chunkId));
 const claims=[...result.structured.observations,...result.structured.recommendations];
 return {applicable:true,claimCount:claims.length,withCitation:claims.filter(c=>c.factIds.length+c.sourceIds.length>0).length,
  validIdentifiers:claims.every(c=>c.factIds.every(id=>facts.has(id))&&c.sourceIds.every(id=>sources.has(id))),
  relevanceOrEntailmentValidated:false,note:'标识有效不保证引用支持对应文字。'};
}
export function retrievalCheck(result,task,documentId){
 if(!task.gold.retrieval)return null;const expected=task.gold.retrieval,source=result.sources.find(s=>s.id===(documentId??expected.documentId));
 return {expectedDocumentId:documentId??expected.documentId,found:!!source,page:source?.page??null,section:source?.section??null,
  correctAnchor:source?.page===expected.page&&source?.section===expected.section,terms:expected.terms.map(term=>({term,present:!!source?.body.includes(term)})),
  sourceKind:source?.textKind??null,reviewStatus:source?.reviewStatus??null};
}
function summarize(result,task,{kind,documentId,scripted=false}={}){
 return {mode:scripted?'scripted_transport':result.mode??kind,applicationMode:result.mode??null,executionKind:kind,isRealModel:kind==='live_full_workflow'&&result.mode==='llm',answer:result.answer,structured:result.structured??null,engineVersion:result.engineVersion,
  evidence:result.evidence,candidates:result.candidates??[],sources:result.sources??[],trace:result.trace??[],task:result.task??null,
  numericChecks:numericChecks(result,task),candidateChecks:candidateChecks(result,task,kind==='scripted_tool_contract'||kind==='live_full_workflow'),
  retrieval:retrievalCheck(result,task,documentId),answerScreen:scripted?{excluded:true,reason:'人工脚本响应不计入AI回答效果'}:answerScreen(result.answer,task),citations:citationScreen(result),
  executedTools:(result.trace??[]).filter(t=>t.label.startsWith('执行工具：')).map(t=>t.label.slice('执行工具：'.length)),
  modelCalls:result.modelCalls??0,usage:result.usage??{input:0,output:0},durationMs:result.durationMs??null,provider:result.provider??null,model:result.model??null,fallbackReason:result.fallbackReason??null,
  semanticReview:{status:scripted?'not_applicable_scripted':'pending_independent_review',accuracy:null,note:scripted?'只检查工具和证据契约，不是模型效果。':'自动筛查不能代替逐题文字语义审查；没有实车精度或用户节时结论。'}};
}
function scriptedTransport(task){let round=0;return async(_,payload)=>{
 if(++round===1)return {choices:[{message:{tool_calls:task.toolPlan.map((p,i)=>({id:'offline-'+task.id+'-'+i,type:'function',function:{name:p.name,arguments:JSON.stringify(p.arguments)}}))}}]};
 const initial=JSON.parse(payload.messages.find(m=>m.role==='user').content),toolMessages=payload.messages.filter(m=>m.role==='tool').map(m=>JSON.parse(m.content));
 const observations=[];
 for(const tool of toolMessages){if(tool.candidate){const facts=tool.candidate.facts.filter(f=>/__(SIM_STOPPING_DISTANCE|SIM_GAP|SIM_LATERAL)$/.test(f.id));observations.push({text:'脚本化合成候选 '+JSON.stringify(tool.patch)+'：'+facts.map(f=>f.label+'='+f.value+' '+f.unit).join('；'),factIds:facts.map(f=>f.id),sourceIds:[]});}
  else if(Array.isArray(tool)&&tool.length){observations.push({text:'脚本化检索契约：'+tool[0].body,factIds:[],sourceIds:[tool[0].chunkId]});}
  else if(tool.comparison){const fact=initial.factRegistry.find(f=>f.id==='LOG_SPEED_RMSE');observations.push({text:'脚本化合成日志对比，仅保留已计算的误差与缺失边界。',factIds:[fact?.id??'SIM_LATERAL'],sourceIds:[]});}}
 if(!observations.length)observations.push({text:'脚本化基线证据。',factIds:['SIM_LATERAL'],sourceIds:[]});
 const citation=observations[0];return {choices:[{message:{content:JSON.stringify({summary:'人工脚本响应夹具，仅用于离线工具和引用契约验证。',observations:observations.slice(0,6),recommendations:[{text:'候选未自动应用；资料与合成日志均不能证明实车精度或安全认证。',factIds:citation.factIds,sourceIds:citation.sourceIds}],limitations:['人工脚本响应不是模型输出，不计入AI任务成功率。']})}}]};
};}
export async function evaluateOffline(fixture,app){
 const tasks=[],docs=[projectDocument(fixture)];
 for(const task of fixture.cases){const input=buildInput(task,fixture,app),before=JSON.stringify(input),e=app.evidence.evidenceFor(input.config,input.log,input.thresholds);
  const rules={answer:app.analysis.groundedRules(input.question,e,[]),sources:[],evidence:app.evidence.compactEvidence(e),candidates:[],engineVersion:app.evidence.ENGINE_VERSION,mode:'rules'};
  const rag=await app.analysis.runAnalysis({...input,mode:'rules'},docs,{});
  const full=await app.analysis.runAnalysis(input,docs,{LLM_API_KEY:'offline-fixture-not-a-secret',LLM_BASE_URL:'https://openrouter.ai/api/v1',LLM_MODEL:'fixture:free'},undefined,scriptedTransport(task));
  const extra=[];
  if(task.gold.correctedRmse!==undefined){const corrected=buildInput(task,fixture,app,0),ce=app.evidence.evidenceFor(corrected.config,corrected.log,corrected.thresholds);extra.push(check('known_shift_corrected_rmse',ce.comparison[0].rmse,task.gold.correctedRmse));}
  if(task.gold.noOverlap){const none=buildInput(task,fixture,app,task.gold.noOverlap.offset),ce=app.evidence.evidenceFor(none.config,none.log,none.thresholds);for(const [key,value] of Object.entries(task.gold.noOverlap))if(key!=='offset')extra.push(check('no_overlap.'+key,ce.comparison[0][key],value));}
  if(task.id==='T03-SPARSE-COVERAGE')extra.push({label:'sparse_sampling_warning',pass:e.comparison[0].qualityWarnings.some(w=>w.includes('独立测量数量'))&&e.comparison[0].qualityWarnings.some(w=>w.includes('停采间隙'))});
  tasks.push({id:task.id,taskId:task.taskId,title:task.title,provenance:task.provenance,question:task.question,reference:task.reference,gold:task.gold,
   conditionsUnchanged:JSON.stringify(input)===before,extraChecks:extra,
   variants:{rules_only:summarize(rules,task,{kind:'rules_only'}),rules_rag:summarize(rag,task,{kind:'rules_rag'}),scripted_tool_contract:summarize(full,task,{kind:'scripted_tool_contract',scripted:true})}});
  console.log('OFFLINE '+task.id+' complete');
 }
 const numeric=tasks.flatMap(t=>Object.values(t.variants).flatMap(v=>v.numericChecks)),extras=tasks.flatMap(t=>t.extraChecks),candidate=tasks.flatMap(t=>t.variants.scripted_tool_contract.candidateChecks);
 const retrieval=tasks.filter(t=>t.gold.retrieval).map(t=>t.variants.scripted_tool_contract.retrieval);
 const toolChecks=tasks.map((t,i)=>({id:t.id,pass:t.variants.scripted_tool_contract.applicationMode==='llm'&&JSON.stringify(t.variants.scripted_tool_contract.executedTools)===JSON.stringify(fixture.cases[i].toolPlan.map(p=>p.name))}));
 return {generatedAt:new Date().toISOString(),engineVersion:app.evidence.ENGINE_VERSION,tasks,
  summary:{taskCount:tasks.length,fixedReferenceAssertions:{passed:numeric.filter(c=>c.pass).length,total:numeric.length,distinctAssertions:numeric.length/3,variantCount:3,note:'相同24项固定参考在三个软件变体上各核对一次；不是72个独立任务，也不是模型文字数值准确率。'},extraBoundaryChecks:{passed:extras.filter(c=>c.pass).length,total:extras.length},
   scriptedCandidateChecks:{passed:candidate.filter(c=>c.pass).length,total:candidate.length},scriptedRetrievalAnchors:{passed:retrieval.filter(c=>c.found&&c.correctAnchor&&c.terms.every(t=>t.present)).length,total:retrieval.length},
   scriptedToolPlans:{passed:toolChecks.filter(c=>c.pass).length,total:toolChecks.length},baselineInputsUnchanged:tasks.every(t=>t.conditionsUnchanged),
   passed:numeric.every(c=>c.pass)&&extras.every(c=>c.pass)&&candidate.every(c=>c.pass)&&retrieval.every(c=>c.found&&c.correctAnchor&&c.terms.every(t=>t.present))&&toolChecks.every(c=>c.pass)&&tasks.every(t=>t.conditionsUnchanged),
   aiSemanticAccuracy:null,note:'离线脚本响应只证明软件契约；各变体的回答要点筛查是描述性信号，不是AI语义准确率或用户研究。'}};
}
async function saveReport(report){await fs.mkdir(path.dirname(reportPath),{recursive:true});await fs.writeFile(reportPath,JSON.stringify(report,null,2)+'\n','utf8');}
async function liveRun(fixture,app,report,base){
 const url=new URL(base);if(url.protocol!=='http:'||!['127.0.0.1','localhost','[::1]'].includes(url.hostname)||url.pathname!=='/'||url.search||url.username||url.password)throw Error('Live evaluation only accepts a local HTTP preview origin');
 base=url.origin;const statusResponse=await fetch(base+'/api/status'),status=await statusResponse.json();
 if(!statusResponse.ok||status.engineVersion!==app.evidence.ENGINE_VERSION||!status.llm||status.freeOnly!==true)throw Error('Local engine/free-only provider preflight failed; no model call made');
 const login=await fetch(base+identity.signInPath+'?return_to=/',{redirect:'manual'}),cookie=login.headers.getSetCookie().map(s=>s.split(';')[0]).join('; ');if(!cookie)throw Error('Local preview sign-in cookie unavailable');
 const api=async(route,method='GET',body)=>{const response=await fetch(base+'/api/'+route,{method,headers:{Cookie:cookie,Origin:base,...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(175000)});const data=await response.json();if(!response.ok)throw Error('HTTP '+response.status+': '+scrub(data.error));return data;};
 const existing=(report.liveRuns??[]).flatMap(r=>r.tasks??[]),reserved=existing.reduce((s,t)=>s+(t.requestReservation??0),0);
 const selected=fixture.cases.filter(t=>t.liveSelected&&!existing.some(done=>done.id===t.id));
 if(!selected.length)throw Error('All six fixed live tasks already attempted; automatic reruns are disabled');
 const run={startedAt:new Date().toISOString(),engineVersion:app.evidence.ENGINE_VERSION,fixtureSha256:report.fixtureSha256,sourceSetSha256:app.sourceSetSha256,provider:status.provider,model:status.model,freeOnly:true,localApi:true,readModelSecrets:false,taskOrder:selected.map(t=>t.id),tasks:[],requestBudget:fixture.limits.maxTotalRequests,previousReservations:reserved,cleanup:{created:false,deleted:false},semanticAccuracy:null};
 report.liveRuns??=[];report.liveRuns.push(run);await saveReport(report);let doc;
 try{
  const fixtureDoc=fixture.projectFixture;doc=await api('knowledge','POST',{title:fixtureDoc.title,body:fixtureDoc.body,kind:'text',sourceName:'合成评测夹具.txt',segments:[{text:fixtureDoc.body,page:fixtureDoc.page,section:fixtureDoc.section}]});run.cleanup={created:true,deleted:false};
  for(const task of selected){
   const currentSourceSha=Object.fromEntries(await Promise.all(moduleNames.map(async name=>['lib/'+name+'.ts',hash(await fs.readFile(path.join(root,'lib',name+'.ts'),'utf8'))])));
   if(hash(JSON.stringify(currentSourceSha))!==app.sourceSetSha256){run.stoppedReason='Frozen evaluation source changed; no further model request';break;}
   const used=reserved+run.tasks.reduce((s,t)=>s+t.requestReservation,0);if(used+3>fixture.limits.maxTotalRequests){run.stoppedReason='Conservative 18-request reservation cap';break;}
   const item={id:task.id,taskId:task.taskId,title:task.title,provenance:task.provenance,question:task.question,gold:task.gold,requestReservation:3,startedAt:new Date().toISOString(),status:'reserved_before_request'};run.tasks.push(item);await saveReport(report);
   const started=performance.now();try{
    const result=await api('analyze','POST',{...buildInput(task,fixture,app),mode:'auto'});
    item.result=summarize(result,task,{kind:'live_full_workflow',documentId:doc.id});item.apiDurationMs=Math.round(performance.now()-started);item.status=result.mode==='llm'?'model_answer_returned':'fallback_retained';
    item.taskMetadataConsistent=result.task?.id===task.taskId&&result.engineVersion===app.evidence.ENGINE_VERSION;
    const foreign=result.sources.filter(s=>!s.id.startsWith('KB-')&&s.id!==doc.id);
    if(foreign.length){item.uncontrolledCorpusSources=foreign.map(s=>({id:s.id,title:s.title}));item.result.semanticReview.note+=' 检索到夹具以外的项目资料，语料条件存在混杂。';}
    console.log('LIVE '+task.id+' '+result.mode+' requests='+result.modelCalls+' durationMs='+item.apiDurationMs);
    if(result.modelCalls>3)throw Error('Application exceeded three model requests');
    if(result.fallbackReason&&/额度|速率|付费|身份验证|认证|HTTP (?:401|402|429)/.test(result.fallbackReason)){run.stoppedReason='Quota/auth/payment failure; no automatic retry';await saveReport(report);break;}
   }catch(error){item.status='request_failed';item.apiDurationMs=Math.round(performance.now()-started);item.error=scrub(error.message);run.stoppedReason='Request failure retained; no automatic retry';await saveReport(report);break;}
   await saveReport(report);
  }
 }finally{
  if(doc){try{await api('knowledge/'+encodeURIComponent(doc.id),'DELETE');run.cleanup.deleted=true;}catch(error){run.cleanup.error=scrub(error.message);}}
  run.finishedAt=new Date().toISOString();run.observedModelRequests=run.tasks.reduce((s,t)=>s+(t.result?.modelCalls??0),0);run.reservedModelRequests=run.tasks.reduce((s,t)=>s+t.requestReservation,0);
  run.observedUsage=run.tasks.reduce((s,t)=>({input:s.input+(t.result?.usage.input??0),output:s.output+(t.result?.usage.output??0)}),{input:0,output:0});
  run.note='所有预选任务、失败及降级均保留；没有在应用三轮之外重试。数字/引用自动筛查不能等同语义准确率；未测真实用户或节时比例。';await saveReport(report);
 }
}
export async function main(args=process.argv.slice(2)){
 if(args.some(a=>a!=='--live'))throw Error('Usage: node scripts/evaluate-ai-tasks.mjs [--live]');
 const fixture=await loadFixture(),failures=validateFixture(fixture);if(failures.length)throw Error('Fixed reference validation failed: '+failures.join('; '));
 const app=await loadApplication(),fixtureSha256=hash(await fs.readFile(fixturePath,'utf8'));
 let previous=null;try{previous=JSON.parse(await fs.readFile(reportPath,'utf8'));}catch{}
 if(previous?.liveRuns?.length&&previous.fixtureSha256!==fixtureSha256)throw Error('Fixed cases changed after live attempts; preserve the previous evaluation before making a new suite');
 const report={schemaVersion:1,suiteId:fixture.suiteId,generatedAt:new Date().toISOString(),engineVersion:app.evidence.ENGINE_VERSION,fixtureSha256,sourceSha256:app.sourceSha256,sourceSetSha256:app.sourceSetSha256,
  scope:{data:'八个受控合成/项目资料夹具，不是实车验证。',comparison:'同题：无检索规则、规则+RAG、完整工具流程。脚本化流程不计AI效果；真实流程需显式--live。',generalization:'小型固定任务集，不能推出真实用户准确率、通用语义保证或节时比例。',userStudyPerformed:false,timeSavingMeasured:false,vehicleCalibrationPerformed:false},
  limits:fixture.limits,rebuild:{offline:'node scripts/evaluate-ai-tasks.mjs',live:'node scripts/evaluate-ai-tasks.mjs --live',liveOriginEnvironment:'可选环境变量DRIVELAB_TEST_URL；仅允许本机HTTP预览，默认http://127.0.0.1:5173。固定6题已尝试后禁止自动重跑。',tests:'node scripts/test-ai-task-evaluation.mjs'},
  offline:await evaluateOffline(fixture,app),liveRuns:previous?.liveRuns??[],liveStatus:previous?.liveRuns?.length?'attempts_preserved':'not_run_waiting_for_stable_server',
  independentReview:previous?.independentReview??null,
  independentReviewMatchesCurrentSources:!!previous?.independentReview&&previous.independentReview.sourceSetSha256===app.sourceSetSha256&&previous.independentReview.fixtureSha256===fixtureSha256};
 await saveReport(report);if(!report.offline.summary.passed)throw Error('Offline reference/tool checks failed; report retained, live not started');
 if(args.includes('--live')){report.liveStatus='attempted';await liveRun(fixture,app,report,process.env.DRIVELAB_TEST_URL??'http://127.0.0.1:5173');}
 console.log(JSON.stringify({engineVersion:report.engineVersion,offline:report.offline.summary,liveStatus:report.liveStatus,report:'docs/evidence/ai-task-evaluation-20261117.json'},null,2));
 return report;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))main().catch(error=>{console.error(scrub(error.message));process.exitCode=1;});
