import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import ts from 'typescript';

// Offline product comparison figures. Every numeric scenario result comes from
// the current application's simulate(), without model prose or measured data.
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const outputDirectory=path.join(root,'.sites-runtime','competition-video-v2');
const moduleDirectory=path.join(outputDirectory,'product-demo-modules');
await fs.mkdir(moduleDirectory,{recursive:true});
const source=await fs.readFile(path.join(root,'lib','simulation.ts'),'utf8');
const extremaSource=await fs.readFile(path.join(root,'lib','trajectory-extrema.ts'),'utf8');
const evidenceSource=await fs.readFile(path.join(root,'lib','evidence.ts'),'utf8');
const engineVersion=evidenceSource.match(/ENGINE_VERSION\s*=\s*['"]([^'"]+)['"]/)?.[1];
assert.ok(engineVersion,'Expected a declared application engine version');
const options={compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}};
await fs.writeFile(path.join(moduleDirectory,'trajectory-extrema.mjs'),ts.transpileModule(extremaSource,options).outputText);
const js=ts.transpileModule(source,options).outputText.replace(/from ['"]\.\/trajectory-extrema['"]/g,"from './trajectory-extrema.mjs'");
const moduleFile=path.join(moduleDirectory,'simulation.mjs');
await fs.writeFile(moduleFile,js);
const {defaults,simulate}=await import(pathToFileURL(moduleFile));

const summarize=config=>{
 const result=simulate(config);
 return {
  config:result.config,
  braking:result.braking,
  stoppingDistanceM:result.braking?result.stoppingDistance:null,
  stopTimeS:result.braking?result.stopTime:null,
  predictedMinimumFullBrakingGapM:result.predictedMinGap,
  maxLat:result.maxLat,
  risk:result.risk
 };
};
const highway={
 baseline:summarize({...defaults}),
 lowerSpeed:summarize({...defaults,speed:80}),
 increasedGap:summarize({...defaults,distance:100})
};
const curve={
 baseline:summarize({...defaults,name:'弯道侧向需求比较',scenario:'curve',speed:36,radius:100}),
 lowerSpeed:summarize({...defaults,name:'弯道侧向需求比较',scenario:'curve',speed:28.8,radius:100})
};
assert.ok(highway.lowerSpeed.stoppingDistanceM<highway.baseline.stoppingDistanceM);
assert.ok(Math.abs(highway.increasedGap.predictedMinimumFullBrakingGapM-highway.baseline.predictedMinimumFullBrakingGapM-20)<1e-9);
assert.ok(Math.abs(curve.baseline.maxLat-1)<1e-12);
assert.ok(Math.abs(curve.lowerSpeed.maxLat-.64)<1e-12);
assert.equal(curve.baseline.stoppingDistanceM,null);
const payload={
 schemaVersion:'product-comparisons-v1',
 generatedAt:new Date().toISOString(),
 generatedBy:'node scripts/product-demo.mjs',
 engineVersion,
 classification:'current_application_simulation_outputs',
 sourceSha256:{'lib/simulation.ts':createHash('sha256').update(source).digest('hex'),'lib/trajectory-extrema.ts':createHash('sha256').update(extremaSource).digest('hex')},
 units:{config:'Application Config units; speed/leadSpeed km/h, distance/radius m, decel m/s², reaction/duration s',stoppingDistanceM:'m',stopTimeS:'s',predictedMinimumFullBrakingGapM:'m',maxLat:'m/s²'},
 productComparisons:{highway,curve},
 interpretation:[
  'All scenario numbers are direct outputs of the current application; they are not measurements, model-generated claims or vehicle calibration.',
  'Highway comparisons use a constant-speed 60 km/h lead vehicle, a level road, 0.8 s response and 5 m/s² effective deceleration. Only the named speed or initial-gap parameter changes.',
  'predictedMinimumFullBrakingGapM is the analytical whole-braking minimum gap, not the rounded minimum of the displayed sample grid.',
  'Curve comparisons keep radius 100 m and change speed from 36 to 28.8 km/h. The lateral demand is 1 to 0.64 m/s² under the steady-circle model.',
  'Curve is a non-braking scenario. Stopping distance/time and braking minimum gap are null because those are not applicable display metrics for that scenario.',
  'maxLat is the continuous maximum absolute lateral demand in the prescribed model; the steady curve value is constant. A risk label describes the simplified model constraints.'
 ]
};
const output=path.join(outputDirectory,'product-demo.json');
await fs.writeFile(output,JSON.stringify(payload,null,2)+'\n');
console.log(JSON.stringify({output,engineVersion,productComparisons:payload.productComparisons},null,2));
