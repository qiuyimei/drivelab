import type {Segment} from './rag';
export type ImportedDocument={title:string;body:string;segments:Segment[];kind:'pdf'|'docx'|'text';sourceName:string};
export async function importKnowledgeFile(file:File):Promise<ImportedDocument>{
 if(file.size>15*1024*1024)throw Error('资料文件上限为 15 MB');let segments:Segment[]=[],kind:ImportedDocument['kind']='text';
 if(/\.pdf$/i.test(file.name)){
  kind='pdf';const pdfjs=await import('pdfjs-dist/legacy/build/pdf.mjs');pdfjs.GlobalWorkerOptions.workerSrc='/pdf.worker.min.mjs';const pdf=await pdfjs.getDocument({data:new Uint8Array(await file.arrayBuffer())}).promise;
  if(pdf.numPages>200)throw Error('单份资料最多 200 页，请选择相关章节');let length=0;for(let page=1;page<=pdf.numPages;page++){const p=await pdf.getPage(page);const content=await p.getTextContent();const text=content.items.flatMap(item=>'str'in item?[item.str+('hasEOL'in item&&item.hasEOL?'\n':' ')]:[]).join('').trim();length+=text.length;if(length>60000)throw Error('提取正文超过 60,000 字，请只上传相关章节');if(text)segments.push({text,page,section:'第 '+page+' 页'});p.cleanup();}await pdf.destroy();
  if(!segments.length)throw Error('PDF 中没有可提取文字。扫描件请先完成 OCR，再导入文本；本平台不会伪造识别结果。');
 }else if(/\.docx$/i.test(file.name)){
  kind='docx';const mammoth=await import('mammoth');const result=await mammoth.extractRawText({arrayBuffer:await file.arrayBuffer()});segments=result.value.split(/\n\s*\n/).map((text,i)=>({text:text.trim(),section:'段落 '+(i+1)})).filter(s=>s.text);
 }else if(/\.(txt|md)$/i.test(file.name)){
  segments=(await file.text()).replace(/^\uFEFF/,'').split(/\n\s*\n/).map((text,i)=>({text:text.trim(),section:'段落 '+(i+1)})).filter(s=>s.text);
 }else throw Error('支持 PDF、DOCX、TXT 和 Markdown 资料');
 const body=segments.map(s=>s.text).join('\n\n');if(!body.trim())throw Error('资料中没有有效正文');if(body.length>60000)throw Error('正文超过 60,000 字，请选择相关章节');return{title:file.name.replace(/\.[^.]+$/,''),body,segments,kind,sourceName:file.name};
}

