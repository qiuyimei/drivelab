'use client';
import {ArrowRight,BookOpen,CheckCircle2,FileText,Gauge,Save,Download,TriangleAlert} from 'lucide-react';
import {analysisTaskDefinitions,type AnalysisTaskId} from '../../lib/analysis-tasks';
import type {Config} from '../../lib/simulation';
import type {LogData} from '../../lib/logs';
import type {AnalysisResult,Trace} from '../../lib/analysis';
import {AnalysisPanel} from './AnalysisPanel';

type Props={config:Config;log:LogData|null;documentCount:number;dirty:boolean;busy:boolean;taskId:AnalysisTaskId;onTask:(id:AnalysisTaskId)=>void;result:AnalysisResult|null;answer:string;traces:Trace[];stale:boolean;configured:boolean;question:string;onQuestion:(q:string)=>void;onAnalyze:(q?:string,mode?:'auto'|'rules')=>void;onCancel:()=>void;onApply:(patch:Partial<Config>,candidateId?:string)=>void;onWorkbench:()=>void;onLogs:()=>void;onKnowledge:()=>void;onSave:()=>void;onReport:()=>void};
export function AITaskWorkspace(p:Props){
 const task=analysisTaskDefinitions.find(t=>t.id===p.taskId)!;
 const taskMismatch=!!p.result?.task&&p.result.task.id!==task.id;
 const blocked=p.dirty?'当前参数尚未计算，请先到工作台运行仿真。':task.requiresLog&&!p.log?'日志复盘需要先导入采集文件，也可以使用明确标注的合成演示日志。':'';
 return <div className="ai-task-workspace">
  <section className="panel padded task-setup"><div className="section-heading"><div><h2>先明确这次要解决的问题</h2><p>选择目标，核对输入，再让模型结合资料与工具完成复盘。</p></div><span className="badge gray">1 准备 → 2 执行 → 3 核对 → 4 归档</span></div>
   <div className="task-options">{analysisTaskDefinitions.map(t=><button key={t.id} aria-pressed={task.id===t.id} className={'task-option '+(task.id===t.id?'selected':'')} onClick={()=>p.onTask(t.id)} disabled={p.busy}><b>{t.title}</b><span>{t.goal}</span></button>)}</div>
   <div className="task-inputs"><div><Gauge size={18}/><span><small>计算基线</small><b>{p.config.name}</b><small>{p.config.speed} km/h · {p.config.duration} s{p.dirty?' · 待重新计算':''}</small></span><button className="text-button" onClick={p.onWorkbench}>查看参数<ArrowRight size={13}/></button></div><div><FileText size={18}/><span><small>日志输入</small><b>{p.log?p.log.name:'尚未导入日志'}</b><small>{p.log?p.log.rows.length+' 行 · 偏移 '+p.log.offset+' s':'风险与方案任务可先使用模型工况'}</small></span><button className="text-button" onClick={p.onLogs}>{p.log?'核对日志':'导入日志'}<ArrowRight size={13}/></button></div><div><BookOpen size={18}/><span><small>资料范围</small><b>{p.documentCount} 份内置与个人资料</b><small>生成结果中可以展开实际检索段落</small></span><button className="text-button" onClick={p.onKnowledge}>查看资料<ArrowRight size={13}/></button></div></div>
   <p className="task-goal"><CheckCircle2 size={16}/><span><b>本次目标：</b>{task.goal}</span></p>
  </section>
  <section className="panel padded task-results"><div className="section-heading"><div><h2>任务结果与可核对依据</h2><p>执行后查看资料、计算事实和候选参数；模型不会直接改动当前工况。</p></div></div>
   {taskMismatch&&<p className="notice"><TriangleAlert size={15}/>下方保留的是“{p.result!.task!.title}”结果。执行当前任务后，再保存为本次记录。</p>}
   <AnalysisPanel result={p.result} legacyAnswer={p.answer} traces={p.traces} busy={p.busy} stale={p.stale||taskMismatch} configured={p.configured} question={p.question} setQuestion={p.onQuestion} onAnalyze={p.onAnalyze} onCancel={p.onCancel} onApply={p.onApply} taskTitle={task.title} blockedReason={blocked}/>
   <div className="task-delivery"><span className="muted small">确认结果后，可保存输入与分析快照，或生成中文报告。</span><button className="button" disabled={p.busy||p.dirty||taskMismatch||!p.result} onClick={p.onSave}><Save size={14}/>保存复盘记录</button><button className="button dark" disabled={p.busy||p.dirty||taskMismatch||!p.result} onClick={p.onReport}><Download size={14}/>导出本次报告</button></div>
  </section>
 </div>;
}
