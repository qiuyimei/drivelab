import http from 'node:http';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import {spawn} from 'node:child_process';
const root=path.resolve(import.meta.dirname,'..');
const nonce=crypto.randomUUID(),host='http://127.0.0.1:5174';
const providers={modelscope:{base:'https://api-inference.modelscope.cn/v1',label:'魔搭免费推理'},openrouter:{base:'https://openrouter.ai/api/v1',label:'OpenRouter 免费模型'}};
function json(res,status,value){res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(JSON.stringify(value));}
async function provider(id,key,endpoint,payload){const p=providers[id];if(!p)throw Error('仅支持已核实的免费服务入口');const r=await fetch(p.base+'/'+endpoint,{method:payload?'POST':'GET',headers:{...(key?{Authorization:'Bearer '+key}:{}),'Content-Type':'application/json'},body:payload?JSON.stringify(payload):undefined,signal:AbortSignal.timeout(50000)});const v=await r.json();if(!r.ok)throw Error(r.status===401?'令牌无效，请检查官方平台的访问令牌':r.status===429?'免费额度或速率已达到上限，稍后再试；不会切换付费':r.status===402?'当前服务不可用或需要付费，已停止；请检查免费入口和账户状态':`服务商返回 HTTP ${r.status}，请检查账户开通状态`);return v;}
function freeModels(id,list){return list.filter(m=>id==='modelscope'?!m.id.includes(':'):(m.id.endsWith(':free')&&Number(m.pricing?.prompt??0)===0&&Number(m.pricing?.completion??0)===0)).map(m=>({id:m.id,tools:m.supported_parameters?.includes('tools')??null}));}
const server=http.createServer(async(req,res)=>{try{
 if(req.headers.host!=='127.0.0.1:5174')return json(res,403,{error:'仅允许本机访问'});
 if(req.method==='GET'&&req.url==='/'){const html=(await fs.readFile(path.join(root,'scripts/setup-ui.html'),'utf8')).replace('__NONCE__',JSON.stringify(nonce));res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','X-Frame-Options':'DENY','Content-Security-Policy':"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'"});return res.end(html);}
 if(req.method!=='POST'||req.headers.origin!==host||req.headers['x-setup-token']!==nonce)return json(res,403,{error:'请求来源不匹配'});
 let body='';for await(const chunk of req){body+=chunk;if(body.length>12000)return json(res,413,{error:'输入过大'});}const data=JSON.parse(body);const id=String(data.provider??'modelscope');if(!providers[id])throw Error('服务商无效');const key=String(data.key??'').trim();if(key&&(/\s/.test(key)||key.length<12||key.length>512))throw Error('访问令牌格式无效');
 const models=freeModels(id,(await provider(id,key,'models')).data??[]);
 if(req.url==='/models')return json(res,200,{models});
 if(req.url!=='/save')return json(res,404,{error:'接口不存在'});
 if(!key)throw Error('请在本机页面填写访问令牌');
 const model=String(data.model??'').trim();if(!models.some(m=>m.id===model))throw Error('请选择当前免费目录中的模型，不允许付费回退');
 let tested=false;if(data.test){const payload={model,messages:[{role:'user',content:'仅回答：DriveLab连接成功 /no_think'}],max_tokens:128,...(id==='modelscope'?{enable_thinking:false}:{provider:{require_parameters:true}})};const v=await provider(id,key,'chat/completions',payload);if(!v.choices?.[0]?.message?.content)throw Error('模型没有返回文本，请换一个可用免费模型');tested=true;}
 const file=path.join(root,'.dev.vars');let old='';try{old=await fs.readFile(file,'utf8');}catch{}const retained=old.split(/\r?\n/).filter(line=>!/^LLM_(BASE_URL|MODEL|API_KEY|PROVIDER|VERIFIED|FREE_ONLY)=/.test(line));const values={LLM_BASE_URL:providers[id].base,LLM_MODEL:model,LLM_API_KEY:key,LLM_PROVIDER:id,LLM_VERIFIED:tested?'true':'false',LLM_FREE_ONLY:'true'};
 await fs.writeFile(file,retained.join('\n').trim()+'\n'+Object.entries(values).map(([k,v])=>k+'='+JSON.stringify(v)).join('\n')+'\n',{mode:0o600});
 await fs.mkdir(path.join(root,'.sites-runtime'),{recursive:true});await fs.writeFile(path.join(root,'.sites-runtime/model-setup.json'),JSON.stringify({provider:id,model,tested,freeOnly:true,cloudAuthorized:!!data.cloud,savedAt:new Date().toISOString()},null,2));
 console.log('MODEL_SETUP_SAVED '+JSON.stringify({provider:id,model,tested,freeOnly:true,cloudAuthorized:!!data.cloud}));
 return json(res,200,{message:(tested?'免费模型连接测试成功。':'已保存配置，尚未调用模型测试。')+'\n仅使用免费入口；额度耗尽时停止，不自动付费。\n请回到聊天告诉我“配置已保存”，不用发送密钥。'});
 }catch(e){json(res,400,{error:e instanceof Error?e.message:'配置失败'});}});
server.listen(5174,'127.0.0.1',()=>{console.log('MODEL_SETUP_URL='+host);if(process.platform==='win32')spawn('rundll32.exe',['url.dll,FileProtocolHandler',host],{stdio:'ignore',windowsHide:true});});
