import type {AnalysisInput,AnalysisResult,Trace} from './analysis';
export async function streamAnalysis(input:AnalysisInput,onProgress:(trace:Trace)=>void,signal?:AbortSignal):Promise<AnalysisResult>{
 const response=await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json',Accept:'text/event-stream'},body:JSON.stringify(input),signal});
 if(!response.ok){let message='分析请求失败';try{message=(await response.json() as {error:string}).error;}catch{}throw Error(message);}
 if(!response.body)throw Error('浏览器不支持流式响应');
 const reader=response.body.getReader(),decoder=new TextDecoder();let pending='',result:AnalysisResult|undefined;
 while(true){const {value,done}=await reader.read();pending+=decoder.decode(value??new Uint8Array(),{stream:!done});let boundary;while((boundary=pending.indexOf('\n\n'))>=0){const block=pending.slice(0,boundary);pending=pending.slice(boundary+2);const event=block.split('\n').find(l=>l.startsWith('event: '))?.slice(7),line=block.split('\n').find(l=>l.startsWith('data: '));if(!line)continue;const data=JSON.parse(line.slice(6));if(event==='progress')onProgress(data);else if(event==='error')throw Error(data.error);else if(event==='result')result=data;}if(done)break;}
 if(!result)throw Error('分析响应中断，没有返回完整结果');return result;
}
