import {knowledge, type Simulation} from './simulation';
import {hybridSearch,type KnowledgeDoc} from './rag';
export type Doc={id:string;title:string;body:string;category?:string;basis?:string};
function vector(s:string){const v=new Float64Array(512);const words=s.toLowerCase().match(/[a-z0-9]+|[\u4e00-\u9fff]/g)??[];const terms=[...words,...words.slice(1).map((w,i)=>words[i]+w)];for(const t of terms){let h=2166136261;for(const ch of t)h=Math.imul(h^ch.charCodeAt(0),16777619);v[(h>>>0)%v.length]++;}const norm=Math.hypot(...v)||1;return Array.from(v,x=>x/norm);}
export function retrieve(question:string,extra:KnowledgeDoc[]=[]){return hybridSearch(question,[...knowledge,...extra]);}
export function ruleAnswer(question:string,s:Simulation,sources:ReturnType<typeof retrieve>){let text=`当前「${s.config.name}」的模型评估为：${s.risk}。\n\n`+s.findings.map(f=>`${f.title}：${f.detail}`).join('\n\n');
 if(s.config.scenario==='curve')text+=`\n\n按当前侧向阈值与附着条件估算，弯道评估速度上限约 ${s.safeCurveSpeed.toFixed(1)} km/h。`;
 text+='\n\n建议：'+(s.maxUtil>1?'先降低车速或减小制动与转向的联合需求，再重新运行评估。':s.maxLat>s.config.lateralLimit?'降低弯道速度，或延长换道时长；再检查侧向加速度。':(s.predictedMinGap??s.minGap)<=0&&s.braking?'增加初始间距、缩短响应延迟或降低初始车速，再校验全时序最小间距。':'保留当前参数作为基线，导入实车日志，检查单位、时延与执行器增益。');
 if(/偏差|日志|对标|误差|传感器/.test(question))text+='\n\n日志复盘：先核对方向盘角与前轮转角定义，确认横摆单位和采样时间；只在共同时间区间计算误差，逐项排查时钟偏移、传感器零偏与制动增益。';
 text+=sources.length?'\n\n依据：'+sources.map(x=>`[${x.id}] ${x.title}`).join('；')+'。':'\n\n知识库没有检索到足够相关段落，以上仅为规则计算结果。';
 return text+'\n\n模型用于前期辅助评估，结论需结合实车标定与车辆工程审核。';}

