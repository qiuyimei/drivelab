import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import ts from 'typescript';

// Offline: use the application's current calculation functions. No live data,
// model request, UI automation or external service is involved.
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const runtime=path.join(root,'.sites-runtime','engineering-demo-modules');
await fs.mkdir(runtime,{recursive:true});
const sourceSha256={};
for(const name of ['simulation','logs','evidence']){
 const source=await fs.readFile(path.join(root,'lib',name+'.ts'),'utf8');
 sourceSha256['lib/'+name+'.ts']=createHash('sha256').update(source).digest('hex');
 const js=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText.replace(/from ['"]\.\/([a-z-]+)['"]/g,"from './$1.mjs'");
 await fs.writeFile(path.join(runtime,name+'.mjs'),js);
}
const {defaults,simulate,MIN_LATERAL_SPEED_KMH}=await import(pathToFileURL(path.join(runtime,'simulation.mjs')));
const {parseLog,compare}=await import(pathToFileURL(path.join(runtime,'logs.mjs')));
const {ENGINE_VERSION,defaultThresholds,evidenceFor,scenarioAlternatives}=await import(pathToFileURL(path.join(runtime,'evidence.mjs')));
const snapshot=s=>({
 config:s.config,
 classification:'application_synthetic_simulation',
 risk:s.risk,
 metrics:{effectiveDecelMps2:s.effectiveDecel,stoppingDistanceM:s.stoppingDistance,stopTimeS:s.stopTime,minimumDisplayedGapM:s.minGap,predictedMinimumFullBrakingGapM:s.predictedMinGap,maximumSampledUtilization:s.maxUtil,maximumSampledLateralMps2:s.maxLat,maximumSampledSteeringDeg:s.maxSteer},
 applicability:s.modelApplicability,
 findings:s.findings,
 curveColumns:['time_s','speed_kmh','distance_m','acceleration_mps2','lateral_acceleration_mps2','yaw_rate_degps','steering_wheel_deg','estimated_pressure_bar','gap_m','utilization_ratio','lateral_position_m'],
 curves:s.rows.map(r=>[r.time,r.speed,r.distance,r.accel,r.lateral,r.yaw,r.steering,r.pressure,r.gap,r.utilization,r.y]),
 sampleCount:s.rows.length
});
const baseline=simulate({...defaults});
const lowMu=simulate({...defaults,mu:.2});
const spikeConfig={...defaults,name:'50 ms 合成尖峰回归',scenario:'curve',speed:36,duration:5};
const spikeSimulation=simulate(spikeConfig);
const spikeCSV='time_s,speed_kmh\n0,36\n0.05,136\n0.1,36\n5,36';
const spikeLog=parseLog(spikeCSV,'合成50ms尖峰夹具.csv');
const spikeComparison=compare(spikeSimulation.rows,spikeLog,defaultThresholds);
const speedSpike=spikeComparison.find(c=>c.key==='speed');
assert.equal(speedSpike.max,100);assert.equal(speedSpike.peakTime,.05);assert.equal(speedSpike.pass,false);assert.equal(speedSpike.mae,0);assert.equal(speedSpike.rmse,0);
const lowSpeedConfig={...defaults,name:'极低速换道边界检查',scenario:'lane',speed:.1,duration:12};
let rejection;
try{simulate(lowSpeedConfig);throw Error('Expected low-speed input to be rejected');}catch(error){rejection={accepted:false,error:error.message};}
assert.match(rejection.error,/适用范围/);
const lane5=simulate({...defaults,name:'最低适用速度换道对照',scenario:'lane',speed:5,duration:12});
const lane60=simulate({...defaults,name:'60 km/h 换道对照',scenario:'lane',speed:60,duration:12});
const boundaryEvidence=evidenceFor({...lane5.config,laneTime:12,duration:20});
const payload={
 generatedAt:new Date().toISOString(),
 engineVersion:ENGINE_VERSION,
 classification:'reproducible_application_outputs_and_synthetic_regression_fixture',
 generatedBy:'node scripts/engineering-demo.mjs',
 sourceSha256,
 limitations:[
  '所有仿真曲线均由当前应用简化模型计算，不是实车测量、车型标定或安全认证。',
  '50 ms +100 km/h 尖峰是明确构造的合成日志回归夹具，不是实测道路事件。',
  '附着、侧向与方向盘峰值是 0.1 s 网格采样峰值；不能据此保证连续时间的严格阈值满足。',
  '换道/避障初始速度 5 km/h 是当前软件模型适用边界，非法规或通用车辆下限；被接受不等于约束通过。',
  '默认跟驰假设前车恒速 60 km/h；解析自车停车距离与跟驰最小间距是不同指标。'
 ],
 defaultHighway:snapshot(baseline),
 lowAdhesionComparison:{baselineMu:defaults.mu,changedMu:.2,changedParameters:['mu'],baseline:snapshot(baseline),lowAdhesion:snapshot(lowMu),delta:{stoppingDistanceM:lowMu.stoppingDistance-baseline.stoppingDistance,stopTimeS:lowMu.stopTime-baseline.stopTime,predictedMinimumFullBrakingGapM:lowMu.predictedMinGap-baseline.predictedMinGap}},
 subgridSpike:{classification:'synthetic_regression_fixture',simulation:snapshot(spikeSimulation),logCSV:spikeCSV,log:spikeLog,thresholds:defaultThresholds,comparison:spikeComparison,demonstratedBehavior:'原仿真网格 MAE/RMSE 为 0，但两网格并集准确报告 0.05 s 的 100 km/h 峰值并判超差。'},
 rejectedLowSpeedLane:{config:lowSpeedConfig,minimumApplicableInitialSpeedKmh:MIN_LATERAL_SPEED_KMH,...rejection},
 acceptedLaneComparison:{changedParameters:['speed'],at5Kmh:snapshot(lane5),at60Kmh:snapshot(lane60),note:'同一五次横向位移需求下比较方向盘需求；5 km/h 虽达到输入下限，仍可能因转向超限得到高风险。'},
 invalidAlternativeBoundary:{config:boundaryEvidence.simulation.config,alternatives:scenarioAlternatives(boundaryEvidence),note:'5 km/h 下的 20% 降速候选被跳过；当前工况仍可独立分析。'}
};
const output=path.join(root,'.sites-runtime','engineering-demo.json');
await fs.writeFile(output,JSON.stringify(payload,null,2)+'\n');
console.log(JSON.stringify({output,defaultMetrics:payload.defaultHighway.metrics,lowMuMetrics:payload.lowAdhesionComparison.lowAdhesion.metrics,spike:{max:speedSpike.max,peakTime:speedSpike.peakTime,mae:speedSpike.mae,rmse:speedSpike.rmse,pass:speedSpike.pass},lowSpeed:rejection,lane:{speed5:{risk:lane5.risk,maxSteering:lane5.maxSteer},speed60:{risk:lane60.risk,maxSteering:lane60.maxSteer}}},null,2));
