// Read-only legacy knowledge fixtures: real retrieval, rule analysis and UI render.
// The cache is isolated from core tests and no HTTP/model/database is used.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),out=path.join(root,'.sites-runtime/rag-legacy-tests');
await fs.mkdir(out,{recursive:true});
const transpile=(source,jsx=false)=>ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,...(jsx?{jsx:ts.JsxEmit.ReactJSX}:{})}}).outputText;
const localImports=code=>code.replace(/from ['"]\.\/([a-z-]+)['"]/g,"from './$1.mjs'");
for(const name of ['trajectory-extrema','simulation','logs','knowledge-sources','rag','retrieval','evidence','provider','fingerprint','analysis-tasks','analysis','analysis-snapshot'])await fs.writeFile(path.join(out,name+'.mjs'),localImports(transpile(await fs.readFile(path.join(root,'lib',name+'.ts'),'utf8'))));
await fs.writeFile(path.join(out,'AnalysisPanel.mjs'),transpile(await fs.readFile(path.join(root,'app/ui/AnalysisPanel.tsx'),'utf8'),true));
const load=name=>import(pathToFileURL(path.join(out,name+'.mjs')).href);
const {defaults}=await load('simulation'),{indexDocument,hybridSearch}=await load('rag'),{runAnalysis}=await load('analysis'),{validatedAnalysisBundle}=await load('analysis-snapshot'),{AnalysisPanel}=await load('AnalysisPanel');
const query='LEGACY_SECTION_FIXTURE',body=query+' 旧资料中的共同时间区间与车速单位说明。';
const base={id:'legacy-doc',title:query,body};
const render=result=>renderToStaticMarkup(React.createElement(AnalysisPanel,{result,legacyAnswer:'',traces:[],busy:false,stale:false,configured:false,question:query,setQuestion(){},onAnalyze(){},onCancel(){},onApply(){}}));
const analyze=doc=>runAnalysis({config:defaults,question:query,mode:'rules'},[doc],{},undefined,()=>{throw Error('Legacy fixtures must not call a model');});
let count=0;async function test(name,fn){await fn();count++;console.log('PASS '+name);}
await test('旧持久化索引中的对象章节在真实规则分析和来源UI中安全回退',async()=>{
 const chunks=indexDocument(base),stored=JSON.stringify(chunks.map(c=>({...c,section:{label:'旧对象章节'}}))),doc={...base,documentIndex:stored};
 const result=await analyze(doc),source=result.sources.find(s=>s.id===doc.id);
 assert.ok(source);assert.doesNotThrow(()=>render(result));assert.equal(source.section,'段落 1');assert.equal(source.body,body);assert.equal(source.chunkId,chunks[0].chunkId);assert.equal(source.start,chunks[0].start);assert.equal(source.end,chunks[0].end);
 assert.match(render(result),/段落 1/);assert.equal(result.modelCalls,0);assert.ok(validatedAnalysisBundle(result,result.fingerprint));assert.equal(doc.documentIndex,stored);
});
await test('没有缓存索引的旧metadata章节对象同样回退且保留页锚与正文',async()=>{
 for(const page of [undefined,3]){
  const metadata=JSON.stringify({segments:[{text:body,page,section:{label:'旧metadata章节'}}]}),doc={...base,metadata},result=await analyze(doc),source=result.sources.find(s=>s.id===doc.id);
  assert.ok(source);assert.equal(source.section,page?'第 3 页':'段落 1');assert.equal(source.page,page??null);assert.equal(source.body,body);assert.equal(source.start,0);assert.equal(source.end,body.length);assert.match(render(result),page?/第 3 页/:/段落 1/);assert.equal(doc.metadata,metadata);
 }
});
await test('旧缓存与metadata的非法类型和超长章节均归一而合法章节保持原文',()=>{
 const invalid=[{label:'对象'},['数组'],42,true,null,'x'.repeat(201),'   '];
 for(const page of [undefined,5])for(const section of invalid){
  const metadata=JSON.stringify({segments:[{text:body,page,section}]}),doc={...base,metadata},chunks=indexDocument(doc);
  assert.equal(chunks[0].section,page?'第 5 页':'段落 1');assert.equal(chunks[0].body,body);
  const stored=JSON.stringify(chunks.map(c=>({...c,section}))),cached={...doc,documentIndex:stored},hit=hybridSearch(query,[cached])[0];
  assert.ok(hit);assert.equal(hit.section,page?'第 5 页':'段落 1');assert.equal(hit.body,body);assert.equal(cached.documentIndex,stored);assert.equal(doc.metadata,metadata);
 }
 for(const section of ['4.2 日志协议','字'.repeat(200)]){
  const doc={...base,metadata:JSON.stringify({segments:[{text:body,section}]})},chunks=indexDocument(doc),hit=hybridSearch(query,[{...doc,documentIndex:JSON.stringify(chunks)}])[0];
  assert.equal(chunks[0].section,section);assert.equal(hit.section,section);assert.deepEqual(hit.vector,chunks[0].vector);
 }
});
await test('旧metadata根值异常不会阻断保留正文的重新索引',()=>{
 for(const metadata of ['null','[]','42','{broken',JSON.stringify({segments:[null,42,{section:{old:true}}]})]){
  const chunks=indexDocument({...base,metadata});assert.ok(chunks.length);assert.equal(chunks.map(c=>c.body).join(''),body);assert.equal(typeof chunks[0].section,'string');
 }
});
console.log(count+' legacy knowledge regression groups passed; no HTTP/model/database or stored-data mutation');
