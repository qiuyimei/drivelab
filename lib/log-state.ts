import {simulate,validateConfig} from './simulation';
import {validatedLog,validatedThresholds} from './evidence';
import type {LogData} from './logs';

// Restored snapshots already use canonical units; never reapply source-unit conversion.
export function realignSavedLog(input:LogData,offset:number):LogData{
 if(!Number.isFinite(offset)||Math.abs(offset)>60)throw Error('偏移必须在 ±60 秒内');
 const log=validatedLog(input)!;const delta=offset-log.offset;
 return {...log,offset,rows:log.rows.map(row=>({...row,time:row.time+delta}))};
}

export function restoreInputSnapshot(payload:string){
 const p=JSON.parse(payload);const config=validateConfig(p.config);
 // Calculate and validate everything before the UI applies any restored state.
 const simulation=simulate(config),log=validatedLog(p.log),thresholds=validatedThresholds(p.thresholds);
 return {config,simulation,log,thresholds,analysis:typeof p.analysis==='string'?p.analysis:'',analysisBundle:p.analysisBundle??null};
}
