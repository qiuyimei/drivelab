// Deterministic report examples; no model, network, API or user database calls.
import fs from 'node:fs';
import {defaults,simulate} from '../.sites-runtime/core-tests/simulation.mjs';
import {ENGINE_VERSION} from '../.sites-runtime/core-tests/evidence.mjs';
const highway=[['baseline',{}],['lowerSpeed',{speed:80}],['largerGap',{distance:100}]].map(([id,patch])=>{
 const result=simulate({...defaults,...patch});
 return {id,config:result.config,stoppingDistance:result.stoppingDistance,stopTime:result.stopTime,predictedMinGap:result.predictedMinGap,risk:result.risk};
});
const lane=[5,6.25].map(laneTime=>{
 const result=simulate({...defaults,name:'动态换道需求复算示例',scenario:'lane',speed:90,duration:15,laneTime});
 return {config:result.config,maxLateral:result.maxLat,maxSteering:result.maxSteer,maxFrictionUtilization:result.maxUtil};
});
const result={engineVersion:ENGINE_VERSION,reviewedOn:'2026-11-18',scope:'Pure current-engine computations for explanatory report examples; not new UI actions, live model calls or vehicle measurements.',highway,lane};
fs.writeFileSync('docs/evidence/APPLICATION-CASES-121.json',JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({engineVersion:ENGINE_VERSION,highway:highway.map(({id,stoppingDistance,predictedMinGap})=>({id,stoppingDistance,predictedMinGap})),lane:lane.map(({config,maxLateral,maxSteering})=>({laneTime:config.laneTime,maxLateral,maxSteering})),newLiveModelRequests:0}));
