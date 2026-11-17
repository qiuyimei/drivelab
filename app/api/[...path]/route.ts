import {env} from 'cloudflare:workers';
import {getChatGPTUser} from '../../chatgpt-auth';
import {getDb} from '../../../db';
import {records,documents} from '../../../db/schema';
import {eq,and,desc} from 'drizzle-orm';
import {simulate,validateConfig} from '../../../lib/simulation';
import {runAnalysis,fingerprint} from '../../../lib/analysis';
import {validatedLog,validatedThresholds,ENGINE_VERSION} from '../../../lib/evidence';
import {validatedAnalysisBundle} from '../../../lib/analysis-snapshot';
import {indexDocument,type Segment} from '../../../lib/rag';
import {providerSettings,type ModelSettings} from '../../../lib/provider';

export const dynamic='force-dynamic';
const json=(value:unknown,status=200)=>Response.json(value,{status,headers:{'Cache-Control':'no-store'}});
async function body(request:Request){if(Number(request.headers.get('content-length'))>5500000)throw Error('请求超过大小限制');const raw=await request.text();if(raw.length>5500000)throw Error('请求超过大小限制');return JSON.parse(raw);}
async function handler(request:Request){try{
 const path=new URL(request.url).pathname.slice(5),method=request.method;
 const origin=request.headers.get('origin');if(method!=='GET'&&origin&&origin!==new URL(request.url).origin)return json({error:'请求来源不匹配'},403);
 const data=method==='POST'?await body(request):{};
 if(path==='simulate'&&method==='POST')return json(simulate(data));
 if(path==='status'){
  let settings;let modelError:string|null=null;try{settings=providerSettings(env as ModelSettings);}catch(e){modelError=(e as Error).message;}
  return json({engineVersion:ENGINE_VERSION,database:!!env.DB,llm:settings?.configured??false,model:settings?.model??null,provider:settings?.provider??null,freeOnly:settings?.freeOnly??true,verified:settings?.verified??false,modelError});
 }
 const user=await getChatGPTUser();if(!user)return json({error:'请先登录，以保存工况和使用知识库。',signin:'/signin-with-chatgpt?return_to=/'},401);
 const db=getDb(),owner=user.userId;
 if(path==='records'&&method==='GET')return json(await db.select({id:records.id,name:records.name,scenario:records.scenario,risk:records.risk,created:records.created}).from(records).where(eq(records.owner,owner)).orderBy(desc(records.created)).limit(100));
 if(path.startsWith('records/')&&method==='GET'){const rows=await db.select().from(records).where(and(eq(records.id,path.slice(8)),eq(records.owner,owner))).limit(1);return rows.length?json(rows[0]):json({error:'记录不存在或无权访问'},404);}
 if(path==='records'&&method==='POST'){
  const result=simulate(validateConfig(data.config));const log=validatedLog(data.log),thresholds=validatedThresholds(data.thresholds),signature=await fingerprint(result.config,log,thresholds);
  const incoming=validatedAnalysisBundle(data.analysisBundle);
  const bundle=incoming?.fingerprint===signature&&incoming.engineVersion===ENGINE_VERSION?incoming:null;
  const payload=JSON.stringify({schemaVersion:2,engineVersion:ENGINE_VERSION,config:result.config,log,thresholds,analysis:typeof data.analysis==='string'?data.analysis.slice(0,24000):'',analysisBundle:bundle,fingerprint:signature});
  if(payload.length>2500000)throw Error('记录过大，请减少日志行数');
  const row={id:crypto.randomUUID(),owner,name:result.config.name,scenario:result.config.scenario,risk:result.risk,created:new Date().toISOString(),payload};await db.insert(records).values(row);return json(row,201);
 }
 if(path.startsWith('records/')&&method==='DELETE'){await db.delete(records).where(and(eq(records.id,path.slice(8)),eq(records.owner,owner)));return json({ok:true});}
 if(path==='knowledge'&&method==='GET')return json(await db.select({id:documents.id,title:documents.title,body:documents.body,created:documents.created,metadata:documents.metadata}).from(documents).where(eq(documents.owner,owner)));
 if(path==='knowledge'&&method==='POST'){
  if(typeof data.title!=='string'||typeof data.body!=='string'||!data.title.trim()||!data.body.trim()||data.title.length>100||data.body.length>60000)throw Error('资料标题或内容无效，正文上限 60,000 字');
  const existing=await db.select({id:documents.id}).from(documents).where(eq(documents.owner,owner));if(existing.length>=40)throw Error('当前最多保存 40 份自定义资料');
  const segments:Segment[]|undefined=data.segments;if(segments){if(!Array.isArray(segments)||segments.length>2000||segments.some(s=>typeof s.text!=='string'||(s.page!==undefined&&(!Number.isInteger(s.page)||s.page<1)))||segments.map(s=>s.text).join('\n\n')!==data.body)throw Error('文档分段与正文不一致');}
  const metadata=JSON.stringify({kind:['pdf','docx','text'].includes(data.kind)?data.kind:'text',sourceName:typeof data.sourceName==='string'?data.sourceName.slice(0,200):null,importedAt:new Date().toISOString(),reviewStatus:'unreviewed',segments});
  const row={id:crypto.randomUUID(),owner,title:data.title,body:data.body,created:new Date().toISOString(),metadata};const documentIndex=JSON.stringify(indexDocument(row));await db.insert(documents).values({...row,documentIndex});return json({...row,chunkCount:JSON.parse(documentIndex).length},201);
 }
 if(path.startsWith('knowledge/')&&method==='DELETE'){await db.delete(documents).where(and(eq(documents.id,path.slice(10)),eq(documents.owner,owner)));return json({ok:true});}
 if(path==='analyze'&&method==='POST'){
  const extra=await db.select().from(documents).where(eq(documents.owner,owner));const input={config:data.config,question:data.question,log:data.log,thresholds:data.thresholds,mode:data.mode};
  if(!request.headers.get('accept')?.includes('text/event-stream'))return json(await runAnalysis(input,extra,env as ModelSettings));
  const encoder=new TextEncoder();const stream=new ReadableStream({async start(controller){const send=(event:string,value:unknown)=>controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(value)}\n\n`));try{const result=await runAnalysis(input,extra,env as ModelSettings,trace=>send('progress',trace));send('result',result);}catch(error){send('error',{error:error instanceof Error?error.message:'分析失败'});}finally{controller.close();}}});
  return new Response(stream,{headers:{'Content-Type':'text/event-stream; charset=utf-8','Cache-Control':'no-cache, no-transform','X-Accel-Buffering':'no'}});
 }
 return json({error:'接口不存在'},404);
 }catch(error){return json({error:error instanceof Error?error.message:'服务处理失败'},400);}}
export const GET=handler;export const POST=handler;export const DELETE=handler;
