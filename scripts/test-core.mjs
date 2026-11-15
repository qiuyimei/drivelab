import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import ts from 'typescript';
const out=path.resolve('.sites-runtime/core-tests');await fs.mkdir(out,{recursive:true});
for(const name of ['simulation','logs','knowledge-sources','rag','retrieval','evidence','provider','fingerprint','analysis','pdf-report']){const code=await fs.readFile(`lib/${name}.ts`,'utf8');const js=ts.transpileModule(code,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText.replace(/from ['"]\.\/([a-z-]+)['"]/g,"from './$1.mjs'");await fs.writeFile(path.join(out,name+'.mjs'),js);}
const {defaults,simulate,templates,validateConfig}=await import(new URL('../.sites-runtime/core-tests/simulation.mjs',import.meta.url));
const {parseLog,compare,sampleCSV}=await import(new URL('../.sites-runtime/core-tests/logs.mjs',import.meta.url));
const {retrieve}=await import(new URL('../.sites-runtime/core-tests/retrieval.mjs',import.meta.url));
let count=0;const test=(name,fn)=>{fn();count++;console.log('PASS '+name);};
test('恒减速数值积分与解析停车距离一致',()=>{const c={...defaults,scenario:'urban',leadSpeed:0,distance:200};const s=simulate(c);assert.ok(Math.abs(s.rows.at(-1).distance-s.stoppingDistance)<1e-8);assert.equal(s.rows.at(-1).speed,0);assert.ok(s.rows.every(r=>r.speed>=0));});
test('响应时刻不落在采样点时仍正确积分',()=>{const s=simulate({...defaults,reaction:.83});assert.ok(Math.abs(s.rows.at(-1).distance-s.stoppingDistance)<1e-8);});
test('低附着限制有效减速度并增加停车距离',()=>{const s=simulate({...defaults,mu:.2});assert.equal(s.effectiveDecel,.2*9.81);assert.ok(s.stoppingDistance>simulate(defaults).stoppingDistance);assert.ok(s.findings.some(f=>f.title==='制动请求被约束'));});
test('弯道稳态加速度与横摆符合解析值',()=>{const c={...defaults,scenario:'curve',speed:72,radius:100};const s=simulate(c);assert.equal(s.maxLat,4);assert.ok(Math.abs(s.rows[0].yaw-4/20*180/Math.PI)<1e-9);assert.ok(s.findings.some(f=>f.level==='warn'));});
test('过大侧向需求触发附着超限',()=>{const s=simulate({...defaults,scenario:'curve',speed:120,radius:30,mu:.3});assert.equal(s.risk,'高风险');assert.ok(s.maxUtil>1);});
test('五类标准工况均生成有限时序数据',()=>{for(const t of templates){const s=simulate({...defaults,...t.config});assert.equal(s.rows.length,s.config.duration*10+1);assert.ok(s.rows.every(r=>Object.values(r).every(Number.isFinite)));}});
test('非法与非数参数被拒绝',()=>{assert.throws(()=>simulate({...defaults,speed:NaN}));assert.throws(()=>simulate({...defaults,mu:0}));assert.throws(()=>validateConfig({...defaults,name:''}));});
test('CSV 自动单位转换、排序、去重和首时刻归零',()=>{const l=parseLog('timestamp_ms,speed_mps,yaw_rate_rad\n1200,10,1\n1000,20,0\n1200,30,2\ninvalid,2,3','test.csv');assert.equal(l.rows.length,2);assert.equal(l.rows[0].time,0);assert.ok(Math.abs(l.rows[1].time-.2)<1e-9);assert.equal(l.rows[1].speed,108);assert.ok(Math.abs(l.rows[1].yaw-2*180/Math.PI)<1e-9);assert.equal(l.duplicates,1);assert.equal(l.dropped,1);});
test('空单元格保持缺失，不自动补零',()=>{const l=parseLog('time,speed,yaw\n0,,1\n1,20,','test.csv');assert.equal(l.rows[0].speed,undefined);assert.equal(l.rows[1].yaw,undefined);});
test('JSON 包装数组与时间偏移',()=>{const l=parseLog(JSON.stringify({data:[{time:20,speed:1},{time:21,speed:2}]}),'test.json',{offset:2});assert.equal(l.rows[0].time,2);assert.equal(l.rows[1].time,3);});
test('插值对标只取共同区间，输出正确 MAE 与 RMSE',()=>{const rows=[0,1,2,3].map(time=>({time,speed:10*time}));const log=parseLog('time,speed\n0,2\n2,22','test.csv',{offset:1});const s=compare(rows,log,{speed:9,yaw:2,pressure:5,steering:10})[0];assert.equal(s.n,3);assert.equal(s.mae,8);assert.equal(s.rmse,8);assert.equal(s.max,8);assert.equal(s.pass,true);});
test('无时间重叠时不外推数据',()=>{const l=parseLog('time,speed\n0,1\n1,2','test.csv',{offset:40});const s=compare(simulate(defaults).rows,l,{speed:2,yaw:2,pressure:5,steering:10})[0];assert.equal(s.n,0);assert.equal(s.pass,null);});
test('损坏 CSV、缺时间列与单时间点均拒绝',()=>{assert.throws(()=>parseLog('time,speed\n0,"1','bad.csv'));assert.throws(()=>parseLog('speed\n1\n2','bad.csv'));assert.throws(()=>parseLog('time,speed\n0,1\n0,2','bad.csv'));});
test('仿真导出可再次导入并精确对标',()=>{const sim=simulate(defaults);const log=parseLog(sampleCSV(sim.rows),'roundtrip.csv');const s=compare(sim.rows,log,{speed:.001,yaw:.001,pressure:.001,steering:.001});assert.ok(s.every(x=>x.n===sim.rows.length&&x.pass));});
test('知识检索返回可追溯来源并接受自定义资料',()=>{assert.ok(retrieve('制动距离响应时间').some(s=>s.id==='KB-004'));assert.ok(retrieve('特殊车型XYZ标定参数',[{id:'CUSTOM',title:'特殊车型XYZ标定参数',body:'特殊车型XYZ标定参数说明'}]).some(s=>s.id==='CUSTOM'));});
test('短窗口不能漏掉完整制动过程中的碰撞风险',()=>{const s=simulate({...defaults,scenario:'urban',speed:100,leadSpeed:0,distance:150,reaction:5,duration:5});assert.ok(s.minGap>0);assert.ok(s.predictedMinGap<0);assert.equal(s.risk,'高风险');assert.ok(s.findings.some(f=>f.title==='仿真覆盖范围'&&f.level==='warn'));});
test('完整跟驰预测采用前车恒速，不把停车距离直接当跟驰间距',()=>{const s=simulate({...defaults,duration:5});const closing=(defaults.speed-defaults.leadSpeed)/3.6;assert.ok(Math.abs(s.predictedMinGap-(defaults.distance-closing*defaults.reaction-closing**2/(2*s.effectiveDecel)))<1e-9);assert.ok(s.findings.some(f=>f.title==='仿真覆盖范围'));});
test('零速换道与避障参数被拒绝，停车制动仍可计算',()=>{assert.throws(()=>simulate({...defaults,scenario:'lane',speed:0}),/非零/);assert.throws(()=>simulate({...defaults,scenario:'avoid',speed:0}),/非零/);assert.equal(simulate({...defaults,scenario:'urban',speed:0}).rows.at(-1).distance,0);});
test('避障停车后不再出现原地横移',()=>{const s=simulate({...defaults,...templates.find(t=>t.id==='avoid').config});const stopped=s.rows.filter(r=>r.speed===0);assert.ok(stopped.length>2);assert.ok(stopped.every(r=>r.y===stopped[0].y));assert.ok(stopped[0].y<s.config.laneWidth);});
test('未覆盖完整换道轨迹时明确提示',()=>{const s=simulate({...defaults,scenario:'lane',duration:5,laneTime:12});assert.ok(s.findings.some(f=>f.title==='换道覆盖范围'&&f.level==='warn'));assert.notEqual(s.risk,'约束内');});
test('大写与空白日志列名保持相同的自动单位转换',()=>{const l=parseLog(' TIMESTAMP_MS , SPEED_MPS , YAW_RATE_RAD \n1000,10,1\n2000,20,2','units.csv');assert.equal(l.rows[1].time,1);assert.equal(l.rows[0].speed,36);assert.ok(Math.abs(l.rows[1].yaw-2*180/Math.PI)<1e-9);});
test('非整步长窗口严格在终点结束，导出时间不会因取两位小数被合并',()=>{for(const duration of [5.001,5.06,5.95]){const s=simulate({...defaults,scenario:'curve',duration,speed:36});assert.equal(s.rows.at(-1).time,duration);assert.ok(Math.abs(s.rows.at(-1).distance-10*duration)<1e-8);assert.ok(s.rows.every(r=>r.time<=duration));assert.equal(parseLog(sampleCSV(s.rows),'fraction.csv').rows.length,s.rows.length);}});
test('JSON 布尔值不当成车速，异常巨大数值与时间溢出被拒绝',()=>{const l=parseLog(JSON.stringify([{time:0,speed:10},{time:1,speed:false},{time:2,speed:20}]),'bool.json');assert.equal(l.rows.length,2);assert.equal(l.dropped,1);assert.throws(()=>parseLog('null','null.json'),/记录数组/);assert.throws(()=>parseLog('time,speed\n0,1e300\n1,2e300','huge.csv'),/超出导入范围/);assert.throws(()=>parseLog('time,speed\n-1e308,1\n1e308,2','time.csv'),/超出导入范围/);});
console.log(`${count} core tests passed`);



