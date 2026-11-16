import assert from 'node:assert/strict';
import {defaults,simulate} from '../.sites-runtime/core-tests/simulation.mjs';
import {runAnalysis,validateNarrative,fingerprint} from '../.sites-runtime/core-tests/analysis.mjs';
import {evidenceFor,validatedLog,validatedThresholds,defaultThresholds,scenarioAlternatives} from '../.sites-runtime/core-tests/evidence.mjs';
import {indexDocument,hybridSearch} from '../.sites-runtime/core-tests/rag.mjs';
import {providerSettings} from '../.sites-runtime/core-tests/provider.mjs';
let count=0;async function test(name,fn){await fn();count++;console.log('PASS '+name);}
const c={...defaults,scenario:'curve',duration:5,speed:36};const sim=simulate(c);const log={name:'合成固定偏差夹具.csv',rows:sim.rows.map(r=>({time:r.time,speed:r.speed+2})),offset:0,dropped:0,duplicates:0,missing:['yaw','pressure','steering']};
await test('服务端证据保留实际日志误差与缺失通道',()=>{const e=evidenceFor(c,log,defaultThresholds);assert.equal(e.comparison[0].bias,2);assert.equal(e.comparison[0].rmse,2);assert.equal(e.facts.find(f=>f.id==='LOG_SPEED_RMSE').value,2);assert.ok(e.limitations.some(x=>x.includes('缺少通道')));});
await test('拒绝伪造的重复时间和非法容差',()=>{assert.throws(()=>validatedLog({...log,rows:[{time:0,speed:1},{time:0,speed:2}]}));assert.throws(()=>validatedThresholds({...defaultThresholds,speed:-1}));assert.throws(()=>validatedThresholds({...defaultThresholds,yaw:Infinity}));});
await test('免费保护拒绝付费服务及付费模型',()=>{assert.throws(()=>providerSettings({LLM_API_KEY:'fixture',LLM_BASE_URL:'https://api.deepseek.com',LLM_MODEL:'deepseek-flash'}),/免费/);assert.throws(()=>providerSettings({LLM_API_KEY:'fixture',LLM_BASE_URL:'https://openrouter.ai/api/v1',LLM_MODEL:'paid-model'}),/免费/);assert.ok(providerSettings({LLM_API_KEY:'fixture',LLM_BASE_URL:'https://openrouter.ai/api/v1',LLM_MODEL:'openrouter/free'}).configured);});
await test('没有密钥时只运行可追溯规则分析',async()=>{const r=await runAnalysis({config:c,question:'检查车速对标偏差',log},[],{},undefined,()=>{throw Error('不应请求模型');});assert.equal(r.mode,'rules');assert.equal(r.modelCalls,0);assert.ok(r.answer.includes('2.000'));assert.ok(r.trace.some(t=>t.kind==='retrieval'));});
const settings={LLM_API_KEY:'fixture-not-real',LLM_BASE_URL:'https://openrouter.ai/api/v1',LLM_MODEL:'example:free'};
const valid={summary:'本次对标存在车速差异，需核对工况与标定。',observations:[{text:'车速存在持续的平均偏差。',factIds:['LOG_SPEED_BIAS'],sourceIds:[]}],recommendations:[{text:'先核对车速传感器单位和基线工况。',factIds:['LOG_SPEED_RMSE'],sourceIds:[]}],limitations:['该结果不代表传感器故障定位。']};
await test('模型实际调用受限工具后生成有证据的结构化解释',async()=>{let calls=0;const r=await runAnalysis({config:c,question:'检查对标偏差',log},[],settings,undefined,async()=>++calls===1?{choices:[{message:{tool_calls:[{id:'fixture-call',type:'function',function:{name:'compare_measurement',arguments:'{}'}}]}}]}:{choices:[{message:{content:JSON.stringify(valid)}}],usage:{prompt_tokens:100,completion_tokens:90}});assert.equal(r.mode,'llm');assert.equal(calls,2);assert.ok(r.trace.some(t=>t.label.includes('compare_measurement')));assert.equal(r.usage.input,100);});
await test('模型伪造引用会被拒绝并保留规则结果',async()=>{const bad={...valid,observations:[{text:'错误结论',factIds:['LOG_FAKE_RMSE'],sourceIds:[]}]};const r=await runAnalysis({config:c,question:'分析',log},[],settings,undefined,async()=>({choices:[{message:{content:JSON.stringify(bad)}}]}));assert.equal(r.mode,'fallback');assert.match(r.fallbackReason,/不存在/);assert.ok(r.answer.includes('2.000'));});
await test('禁止未经授权的工具和无限循环',async()=>{const r=await runAnalysis({config:c,question:'分析',log},[],settings,undefined,async()=>({choices:[{message:{tool_calls:[{id:'bad',function:{name:'delete_database',arguments:'{}'}}]}}]}));assert.equal(r.mode,'fallback');assert.match(r.fallbackReason,/未授权/);assert.equal(r.modelCalls,1);});
await test('免费额度耗尽时明确降级，不切换付费服务',async()=>{const r=await runAnalysis({config:c,question:'分析',log},[],settings,undefined,async()=>{throw Error('免费额度达到上限');});assert.equal(r.mode,'fallback');assert.ok(r.evidence.facts.length>0);assert.match(r.fallbackReason,/免费额度/);});
await test('分析指纹随工况、日志或容差变化而改变',async()=>{const a=await fingerprint(c,log,defaultThresholds);assert.notEqual(a,await fingerprint({...c,speed:30},log,defaultThresholds));assert.notEqual(a,await fingerprint(c,{...log,offset:.2},defaultThresholds));assert.notEqual(a,await fingerprint(c,log,{...defaultThresholds,speed:3}));});
await test('资料索引持久化保留页码、段落与字符锚点',()=>{const doc={id:'fixture-doc',title:'制动标定',body:'响应时间影响停车距离',metadata:JSON.stringify({segments:[{text:'响应时间影响停车距离',page:3,section:'制动测试'}]})};const chunks=indexDocument(doc);const hits=hybridSearch('停车距离响应时间',[{...doc,documentIndex:JSON.stringify(chunks)}]);assert.equal(hits[0].page,3);assert.equal(hits[0].chunkId,'fixture-doc#c1');assert.equal(hits[0].start,0);assert.equal(hits[0].end,doc.body.length);});
await test('完全无关问题不捏造检索命中',()=>{assert.equal(hybridSearch('alien telescope volcano',[{id:'x',title:'制动距离',body:'车速和减速度决定停车距离'}]).length,0);});
await test('规范化日志的键顺序不改变分析指纹',async()=>{const ordered={...log,rows:log.rows.map(({time,speed})=>({speed,time}))};assert.equal(await fingerprint(c,ordered,defaultThresholds),await fingerprint(c,validatedLog(ordered),defaultThresholds));});
await test('失败请求计数准确，流式步骤更新至完成或警告状态',async()=>{const events=[];const r=await runAnalysis({config:c,question:'分析',log},[],settings,t=>events.push({...t}),async()=>{throw Error('免费额度达到上限');});assert.equal(r.modelCalls,1);assert.ok(r.trace.every(t=>t.status!=='running'));const modelEvents=events.filter(t=>t.kind==='model');assert.equal(modelEvents[0].id,modelEvents.at(-1).id);assert.equal(modelEvents.at(-1).status,'warning');});
await test('候选参数触及边界时描述准确，静止工况不自动加速',()=>{const a=scenarioAlternatives(evidenceFor({...c,scenario:'urban',speed:0,distance:1000}));assert.equal(a.length,0);const b=scenarioAlternatives(evidenceFor({...c,scenario:'avoid',distance:990,laneTime:11}));assert.ok(b.some(p=>p.patch.distance===1000&&p.label.includes('1000')));assert.ok(b.some(p=>p.patch.laneTime===12&&p.label.includes('12')));});
for(const provider of ['modelscope','openrouter'])await test(provider+' 三轮工具分析保持服务商兼容参数和严格校验',async()=>{
 const env=provider==='modelscope'?{LLM_API_KEY:'fixture-not-real',LLM_BASE_URL:'https://api-inference.modelscope.cn/v1',LLM_MODEL:'Qwen/Qwen3.5-27B',LLM_PROVIDER:'modelscope'}:{...settings,LLM_PROVIDER:'openrouter'};
 let round=0;const r=await runAnalysis({config:c,question:'分析对标偏差',log},[],env,undefined,async(_,payload)=>{
  round++;assert.equal(payload.enable_thinking,provider==='modelscope'?false:undefined);
  if(round<3){assert.ok(Array.isArray(payload.tools));assert.equal(payload.tool_choice,'auto');assert.equal(Object.hasOwn(payload,'response_format'),false);if(round===2)assert.ok(payload.messages.some(m=>m.role==='tool'&&m.tool_call_id==='round-1'));return {choices:[{message:{tool_calls:[{id:'round-'+round,type:'function',function:{name:'compare_measurement',arguments:'{}'}}]}}]};}
  assert.equal(Object.hasOwn(payload,'tools'),false);assert.equal(Object.hasOwn(payload,'response_format'),provider!=='modelscope');if(provider!=='modelscope')assert.deepEqual(payload.response_format,{type:'json_object'});
  assert.ok(payload.messages.some(m=>m.role==='tool'&&m.tool_call_id==='round-2'));
  return {choices:[{message:{content:JSON.stringify(valid)}}]};
 });assert.equal(round,3);assert.equal(r.modelCalls,3);assert.equal(r.mode,'llm');assert.ok(r.structured);assert.equal(r.fallbackReason,null);
});
await test('魔搭返回非对象 JSON 仍被拒绝并保留规则结果',async()=>{
 let round=0;const env={LLM_API_KEY:'fixture-not-real',LLM_BASE_URL:'https://api-inference.modelscope.cn/v1',LLM_MODEL:'Qwen/Qwen3.5-27B',LLM_PROVIDER:'modelscope'};
 const r=await runAnalysis({config:c,question:'分析',log},[],env,undefined,async()=>++round<3?{choices:[{message:{tool_calls:[{id:'scalar-'+round,type:'function',function:{name:'compare_measurement',arguments:'{}'}}]}}]}:{choices:[{message:{content:'5000000000'}}]});
 assert.equal(r.mode,'fallback');assert.equal(r.structured,null);assert.equal(r.modelCalls,3);assert.match(r.fallbackReason,/结构不符合/);assert.ok(r.answer.includes('2.000'));assert.ok(r.trace.every(t=>t.status!=='running'));
});
await test('工具后缺引用时利用剩余轮次纠正并保留新增资料标识',async()=>{
 let round=0;const broken={...valid,observations:[{text:'遗漏引用',factIds:[],sourceIds:[]}]};const docs=[{id:'REPAIR',title:'QA_REPAIR_SOURCE_XYZ',body:'QA_REPAIR_SOURCE_XYZ'}];
 const r=await runAnalysis({config:c,question:'分析对标偏差',log},docs,settings,undefined,async(_,payload)=>{
  round++;
  if(round===1)return {choices:[{message:{tool_calls:[{id:'repair-search',type:'function',function:{name:'search_knowledge',arguments:JSON.stringify({query:'QA_REPAIR_SOURCE_XYZ'})}}]}}]};
  if(round===2)return {choices:[{message:{content:JSON.stringify(broken)}}]};
  assert.equal(Object.hasOwn(payload,'tools'),false);const feedback=JSON.parse(payload.messages.at(-1).content);assert.match(feedback.reason,/没有引用/);assert.ok(feedback.factIds.includes('LOG_SPEED_RMSE'));assert.ok(feedback.sourceIds.includes('REPAIR#c1'));assert.ok(payload.messages.some(m=>m.role==='assistant'&&m.content===JSON.stringify(broken)));assert.ok(payload.messages.some(m=>m.role==='tool'&&m.tool_call_id==='repair-search'));
  return {choices:[{message:{content:JSON.stringify(valid)}}]};
 });assert.equal(r.modelCalls,3);assert.equal(r.mode,'llm');assert.ok(r.structured);assert.ok(r.trace.some(t=>t.label==='纠正模型输出'));assert.ok(r.trace.every(t=>t.status!=='running'));
});
await test('坏 JSON 可在剩余轮次内纠正，纠正阶段不再提供工具',async()=>{
 let calls=0;const r=await runAnalysis({config:c,question:'分析',log},[],settings,undefined,async(_,payload)=>{
  if(++calls===1)return {choices:[{message:{content:'{"summary":'}}]};
  assert.equal(Object.hasOwn(payload,'tools'),false);assert.equal(JSON.parse(payload.messages.at(-1).content).reason,'JSON格式无效');return {choices:[{message:{content:JSON.stringify(valid)}}]};
 });assert.equal(r.mode,'llm');assert.equal(r.modelCalls,2);
});
await test('连续格式失败最多三次请求后降级，纠正不能绕过工具轮次',async()=>{
 const r=await runAnalysis({config:c,question:'分析',log},[],settings,undefined,async()=>({choices:[{message:{content:'5000000000'}}]}));assert.equal(r.modelCalls,3);assert.equal(r.mode,'fallback');assert.equal(r.structured,null);assert.ok(r.answer.includes('2.000'));assert.ok(r.trace.every(t=>t.status!=='running'));
 let count=0;const tool=await runAnalysis({config:c,question:'分析',log},[],settings,undefined,async()=>++count===1?{choices:[{message:{content:'bad-json'}}]}:{choices:[{message:{tool_calls:[{id:'unexpected-repair-tool',function:{name:'inspect_simulation',arguments:'{}'}}]}}]});assert.equal(tool.mode,'fallback');assert.equal(tool.modelCalls,2);assert.match(tool.fallbackReason,/轮次限制/);
});
console.log(`${count} analysis tests passed`);
