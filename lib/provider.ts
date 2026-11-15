export type ModelSettings={LLM_BASE_URL?:string;LLM_MODEL?:string;LLM_API_KEY?:string;LLM_FREE_ONLY?:string;LLM_PROVIDER?:string;LLM_VERIFIED?:string};
export function providerSettings(env:ModelSettings){
 const base=(env.LLM_BASE_URL??'').replace(/\/$/,'');const model=env.LLM_MODEL??'';
 const freeOnly=env.LLM_FREE_ONLY!=='false';
 if(!env.LLM_API_KEY)return {configured:false,freeOnly,base,model,provider:env.LLM_PROVIDER??'none',verified:false};
 if(!base.startsWith('https://'))throw Error('模型接口必须使用 HTTPS');
 if(freeOnly){
  const scope=base==='https://api-inference.modelscope.cn/v1'&&!model.includes(':');
  const router=base==='https://openrouter.ai/api/v1'&&(model==='openrouter/free'||model.endsWith(':free'));
  if(!scope&&!router)throw Error('当前仅允许免费服务：魔搭 API-Inference 或 OpenRouter 免费模型；不会自动切换付费接口');
 }
 if(!/^[\w./:-]{1,140}$/.test(model))throw Error('模型名称无效');
 return {configured:true,freeOnly,base,model,provider:env.LLM_PROVIDER??(base.includes('modelscope')?'modelscope':base.includes('openrouter')?'openrouter':'compatible'),verified:env.LLM_VERIFIED==='true'};
}
