'use client';
import {useState} from 'react';
import {ArrowRight,BookOpen,CheckCircle2,ChevronDown,Download,Loader2,Sparkles,TriangleAlert} from 'lucide-react';
import type {AnalysisResult,Trace} from '../../lib/analysis';
import type {Config} from '../../lib/simulation';
type Props={result:AnalysisResult|null;legacyAnswer:string;traces:Trace[];busy:boolean;stale:boolean;configured:boolean;question:string;setQuestion:(q:string)=>void;onAnalyze:(question?:string,mode?:'auto'|'rules')=>void;onCancel:()=>void;onApply:(patch:Partial<Config>)=>void};
export function AnalysisPanel(p:Props){
 const [expanded,setExpanded]=useState<string|null>(null);
 const result=p.result;
 function exportEvidence(){if(!result)return;const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='DriveLab-分析证据-'+result.fingerprint+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 return <div className="analysis"><div className="analysis-intro"><span className="ai-icon"><Sparkles size={20}/></span><div><h3>依据计算与日志，解释本次工况</h3><p>{p.configured?'免费模型已配置 · 工程判断以计算结果为准':'尚未连接免费模型 · 可以先运行完整规则分析'}</p></div></div>
 <div className="prompt-chips">{['分析当前工况风险','解释本次日志超差与排查顺序','比较降低车速与增加间距的效果'].map(q=><button key={q} disabled={p.busy} onClick={()=>{p.setQuestion(q);p.onAnalyze(q);}}>{q}<ArrowRight size={13}/></button>)}</div>
 {p.stale&&<p className="notice"><TriangleAlert size={14}/> 参数、日志或容差已改变，以下是旧分析。请重新分析后再保存为当前证据。</p>}
 {(p.traces.length>0||result)&&<div className="analysis-trace" aria-label="分析执行记录">{(p.traces.length?p.traces:result?.trace??[]).map(t=><div key={t.id} className={'trace-row '+t.status}>{t.status==='running'&&p.busy?<Loader2 className="spin" size={14}/>:t.status==='warning'?<TriangleAlert size={14}/>:<CheckCircle2 size={14}/>}<div><b>{t.label}</b><small>{t.detail}</small></div></div>)}</div>}
 {p.busy&&<div className="flex between analyzing"><span><Loader2 className="spin" size={17}/> 正在分析本次证据…</span><button className="text-button" onClick={p.onCancel}>停止等待</button></div>}
 {result&&<><div className="analysis-result-heading"><span className="tiny-tag">{result.mode==='llm'?'免费模型 RAG 分析':result.mode==='fallback'?'模型不可用 · 规则结果':'可复现规则分析'}</span><small>{result.engineVersion} · {result.modelCalls} 次模型请求</small><button className="text-button" onClick={exportEvidence}><Download size={13}/>证据 JSON</button></div>
 {result.fallbackReason&&<p className="notice">{result.fallbackReason}。计算和日志结果已保留，没有切换付费服务。</p>}
 <div className="evidence-grid">{result.evidence.facts.slice(0,9).map(f=><div key={f.id}><small>{f.label}</small><b>{f.value.toFixed(2)} <em>{f.unit}</em></b><span>{f.origin==='log'?'采集日志对标':'物理模型计算'}</span></div>)}</div>
 <div className="answer"><p>{result.answer}</p></div>
 <div className="source-list">{result.sources.map(s=><details key={s.chunkId} open={expanded===s.chunkId}><summary onClick={e=>{e.preventDefault();setExpanded(expanded===s.chunkId?null:s.chunkId);}}><BookOpen size={13}/>{s.title}<span>{s.page?'第 '+s.page+' 页':s.section}</span><ChevronDown size={12}/></summary><p>{s.body}</p><small>{s.chunkId} · 字符 {s.start}–{s.end}<br/>{s.reviewStatus}<br/>{s.locator}</small>{s.referenceUrl&&<p><a href={s.referenceUrl} target="_blank" rel="noreferrer">查看公开工程依据 ↗</a></p>}</details>)}</div>
 <div className="candidate-list"><h3>候选方案重算</h3><p className="muted small">候选仅改变控制或工况参数，路面条件保持原值；以下结论不代表实车安全认证。</p>{result.alternatives.map(a=><div key={a.label}><b>{a.label}</b><small>附着需求 {(a.before.utilization*100).toFixed(1)}% → {(a.after.utilization*100).toFixed(1)}% · 模型评估 {a.after.risk}</small><button className="text-button" disabled={p.busy||p.stale} onClick={()=>p.onApply(a.patch)}>载入参数<ArrowRight size={12}/></button></div>)}</div>
 <p className="evidence-fingerprint">证据指纹 {result.fingerprint} · {new Date(result.generatedAt).toLocaleString('zh-CN')}</p></>}
 {!result&&p.legacyAnswer&&<div className="answer"><span className="tiny-tag">旧版分析文本，请重新分析以生成证据链</span><p>{p.legacyAnswer}</p></div>}
 <form className="question-form" onSubmit={e=>{e.preventDefault();p.onAnalyze();}}><input aria-label="工况分析问题" value={p.question} maxLength={2000} placeholder="询问本次工况、日志超差或候选策略…" onChange={e=>p.setQuestion(e.target.value)}/><button className="button primary" disabled={p.busy}><Sparkles size={15}/>开始分析</button></form>
 <button className="text-button muted" disabled={p.busy} onClick={()=>p.onAnalyze(undefined,'rules')}>只运行规则与检索（不占模型额度）</button>
 </div>;
}
