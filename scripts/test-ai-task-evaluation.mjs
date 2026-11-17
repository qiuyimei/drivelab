// Focused evaluation-harness checks; does not run the old full suite or call a provider.
import assert from 'node:assert/strict';
import {loadFixture,validateFixture,analyticReference,answerScreen,citationScreen,main} from './evaluate-ai-tasks.mjs';
let count=0;async function test(name,fn){await fn();count++;console.log('PASS '+name);}
const fixture=await loadFixture();
await test('固定八题、预选六题、18请求上限且夹具明示合成',()=>{
 assert.deepEqual(validateFixture(fixture),[]);assert.equal(fixture.cases.length,8);assert.equal(fixture.cases.filter(c=>c.liveSelected).length,6);
 assert.equal(fixture.limits.maxTotalRequests,18);assert.ok(fixture.cases.every(c=>/合成/.test(c.provenance)));assert.match(fixture.projectFixture.provenance,/不是外部标准/);
});
await test('自定义候选参考来自独立解析关系而非默认80kmh/100m',()=>{
 const task=fixture.cases.find(c=>c.id==='T04-CUSTOM-CANDIDATES');assert.deepEqual(task.gold.candidates.map(c=>c.patch),[{speed:90},{distance:110}]);
 const speed=analyticReference({...fixture.baseConfig,speed:90}),distance=analyticReference({...fixture.baseConfig,distance:110});
 assert.equal(speed.SIM_STOPPING_DISTANCE,82.5);assert.equal(speed.SIM_STOP_TIME,5.8);assert.ok(Math.abs(distance.SIM_GAP-88.76543209876543)<1e-12);
 const corrupted=structuredClone(fixture);corrupted.cases.find(c=>c.id===task.id).gold.candidates[0].facts.SIM_STOPPING_DISTANCE=82.6;assert.ok(validateFixture(corrupted).length>0);
});
await test('恒减速时移的3.6kmh参考可在未用应用函数时推导',()=>{
 for(const t of [.5,1,2.7,5])assert.ok(Math.abs((36-7.2*(t-.5))-(36-7.2*t)-3.6)<1e-12);
});
await test('数字出现筛查不会声称语义正确',()=>{
 const task=fixture.cases.find(c=>c.id==='T05-CURVE-SQUARE'),screen=answerScreen('无关物品编号0.64',task);
 assert.equal(screen.numericMentions[0].matched,true);assert.equal(screen.semanticAccuracy,null);assert.match(screen.basis,/不判断/);
});
await test('有效引用标识不会被评测包装成语义蕴含证明',()=>{
 const result={evidence:{facts:[{id:'SIM_LATERAL'}]},sources:[],structured:{observations:[{text:'未检查的任意文字',factIds:['SIM_LATERAL'],sourceIds:[]}],recommendations:[]}};
 const screen=citationScreen(result);assert.equal(screen.validIdentifiers,true);assert.equal(screen.relevanceOrEntailmentValidated,false);
});
const report=await main([]);
await test('当前应用逐题匹配固定参考且四个自定义候选真正经工具重算',()=>{
 assert.equal(report.offline.summary.passed,true);assert.equal(report.offline.summary.taskCount,8);assert.deepEqual(report.offline.summary.scriptedCandidateChecks,{passed:4,total:4});
 assert.equal(report.offline.summary.scriptedToolPlans.passed,8);assert.equal(report.offline.summary.baselineInputsUnchanged,true);
 for(const task of report.offline.tasks){assert.equal(task.variants.scripted_tool_contract.task.id,task.taskId);assert.equal(task.variants.scripted_tool_contract.task.status,'complete');assert.equal(task.variants.rules_rag.task.status,'rules-only');}
});
await test('脚本化响应排除出AI回答效果，离线重建保留既有live记录',()=>{
 for(const task of report.offline.tasks){assert.equal(task.variants.scripted_tool_contract.answerScreen.excluded,true);assert.equal(task.variants.scripted_tool_contract.semanticReview.status,'not_applicable_scripted');}
 assert.equal(report.offline.summary.aiSemanticAccuracy,null);assert.equal(report.scope.userStudyPerformed,false);assert.equal(report.scope.timeSavingMeasured,false);
 if(!report.liveRuns.length)assert.equal(report.liveStatus,'not_run_waiting_for_stable_server');
});
console.log('PASS AI task evaluation harness: '+count+' groups; no live model request');
