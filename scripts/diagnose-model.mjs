// Local-only diagnostic: reads this project's selected model secret without printing it.
import fs from 'node:fs/promises';
import path from 'node:path';
import {providers,validateSetupKey,diagnoseProviderFailure} from './model-setup-provider.mjs';
const root=path.resolve(import.meta.dirname,'..');
let content;try{content=await fs.readFile(path.join(root,'.dev.vars'),'utf8');}catch{console.log(JSON.stringify({ready:false,reason:'configuration_not_saved',message:'先在本机向导保存配置；令牌无需发到聊天。'}));process.exit(2);}
const values={};for(const line of content.split(/\r?\n/)){const match=line.match(/^(LLM_(?:PROVIDER|API_KEY|BASE_URL|MODEL|FREE_ONLY|VERIFIED))=(.*)$/);if(!match)continue;try{values[match[1]]=String(JSON.parse(match[2]));}catch{values[match[1]]=match[2].trim();}}
const id=values.LLM_PROVIDER,key=values.LLM_API_KEY,model=values.LLM_MODEL;
if(!providers[id]||values.LLM_BASE_URL!==providers[id].base||values.LLM_FREE_ONLY!=='true'||!model||(id==='modelscope'?model.includes(':'):!(model.endsWith(':free')||model==='openrouter/free')))throw Error('诊断仅支持已保存的免费入口，已停止。');
validateSetupKey(id,key);
function redact(value){return String(value??'').replaceAll(key,'[REDACTED]').replace(/\b(?:ms-|sk-)[\w-]{8,}/g,'[REDACTED]').replace(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/g,'[EMAIL]').replace(/\b\d{1,3}(?:\.\d{1,3}){3}\b/g,'[IP]').replace(/\b1[3-9]\d{9}\b/g,'[PHONE]').slice(0,500);}
const request={model,messages:[{role:'user',content:'仅回复 OK /no_think'}],max_tokens:32,...(id==='modelscope'?{enable_thinking:false}:{provider:{require_parameters:true,allow_fallbacks:false}})};
let diagnostic={provider:id,model,at:new Date().toISOString(),maxOutputTokens:32,freeOnly:true};
try{
 const response=await fetch(providers[id].base+'/chat/completions',{method:'POST',headers:{Authorization:'Bearer '+key,'Content-Type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(45000),redirect:'error'});
 const contentType=response.headers.get('content-type')??'';let body;try{body=await response.json();}catch{}
 const message=body?.error?.message??body?.message??body?.Message??body?.detail??'';
 const code=body?.error?.code??body?.code??body?.Code;
 diagnostic={...diagnostic,status:response.status,contentType,responseFormat:body?'json':'non_json',reason:response.ok?'connected':diagnoseProviderFailure(response.status,{message}).reason,...(typeof code==='string'?{providerCode:redact(code)}:{}),...(message?{providerMessage:redact(typeof message==='string'?message:JSON.stringify(message))}:{})};
 if(response.ok){const answer=body?.choices?.[0]?.message?.content;diagnostic.textReturned=typeof answer==='string'&&answer.trim().length>0;diagnostic.usage=Object.fromEntries(['prompt_tokens','completion_tokens','total_tokens'].map(name=>[name,typeof body?.usage?.[name]==='number'&&Number.isFinite(body.usage[name])?body.usage[name]:null]));if(!diagnostic.textReturned)diagnostic.reason='empty_text_response';}
 // Never record the successful answer or original response, only diagnostic metadata.
}catch(error){diagnostic={...diagnostic,reason:'network_error',errorType:error?.name??'Error'};}
if(JSON.stringify(diagnostic).includes(key))throw Error('诊断脱敏校验未通过，停止输出。');
await fs.mkdir(path.join(root,'.sites-runtime'),{recursive:true});await fs.writeFile(path.join(root,'.sites-runtime/model-diagnostic.json'),JSON.stringify(diagnostic,null,2));
console.log(JSON.stringify(diagnostic,null,2));
