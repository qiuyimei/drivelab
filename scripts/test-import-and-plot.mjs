// Targeted regressions for the actual upload/plot failures found in review.
// Independent transpilation cache; no server, model, or old core-test cache used.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),out=path.join(root,'.sites-runtime/import-plot-tests');
await fs.mkdir(out,{recursive:true});
const transpile=(source,jsx=false)=>ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022,...(jsx?{jsx:ts.JsxEmit.ReactJSX}:{})}}).outputText;
const localImports=code=>code.replace(/from ['"](?:\.\/|\.\.\/\.\.\/lib\/)([a-z-]+)['"]/g,"from './$1.mjs'");
for(const name of ['trajectory-extrema','simulation','logs','evidence','fingerprint','analysis-tasks','analysis-snapshot'])await fs.writeFile(path.join(out,name+'.mjs'),localImports(transpile(await fs.readFile(path.join(root,'lib',name+'.ts'),'utf8'))));
await fs.writeFile(path.join(out,'SimulationViews.mjs'),localImports(transpile(await fs.readFile(path.join(root,'app/ui/SimulationViews.tsx'),'utf8'),true)));
const load=name=>import(pathToFileURL(path.join(out,name+'.mjs')).href);
const {defaults,simulate}=await load('simulation'),{parseLog,compare,clipLogChannelToWindow}=await load('logs'),{Chart}=await load('SimulationViews');
let count=0;async function test(name,fn){await fn();count++;console.log('PASS '+name);}
const thresholds={speed:2,yaw:2,pressure:5,steering:10},s=simulate({...defaults,scenario:'curve',speed:36,radius:100,duration:5});
await test('跨越整个窗口的两个日志点在SVG中显示完整线段，统计不造采样点',()=>{
 const log=parseLog('time_s,speed_kmh\n0,36\n7,36','合成边界.csv',{offset:-1}),before=JSON.stringify(log),stats=compare(s.rows,log,thresholds);
 const plot=clipLogChannelToWindow(log.rows,'speed',0,5);assert.deepEqual(plot,[{time:0,speed:36},{time:5,speed:36}]);
 const html=renderToStaticMarkup(React.createElement(Chart,{result:s,log,channel:'speed'}));const orange=[...html.matchAll(/<polyline ([^>]+)>/g)].map(m=>m[1]).find(p=>p.includes('stroke="#f17b42"'));
 assert.ok(orange);assert.ok(!orange.includes('points=""'));assert.equal(JSON.stringify(log),before);assert.deepEqual(compare(s.rows,log,thresholds),stats);
 assert.equal(stats[0].n,51);assert.equal(stats[0].sourceSamples,2);assert.equal(stats[0].overlapSourceSamples,0);assert.equal(stats[0].max,0);
});
await test('裁边按通道插值但不外推，保留真实中间点与单点接触',()=>{
 const rows=[{time:-1,speed:10},{time:2,speed:40},{time:6,speed:80}];
 assert.deepEqual(clipLogChannelToWindow(rows,'speed',0,5),[{time:0,speed:20},{time:2,speed:40},{time:5,speed:70}]);
 assert.deepEqual(clipLogChannelToWindow(rows,'yaw',0,5),[]);assert.deepEqual(clipLogChannelToWindow(rows,'speed',7,8),[]);
 assert.deepEqual(clipLogChannelToWindow([{time:5,speed:36},{time:6,speed:36}],'speed',0,5),[{time:5,speed:36}]);
});

// Capture the real report writer's geometry, without creating a PDF artifact.
const pdfStub=`export const rgb=(r,g,b)=>({r,g,b});export const PDFDocument={async create(){const pages=[];return {registerFontkit(){},async embedFont(){return {getCharacterSet(){return Array.from({length:65536},(_,i)=>i)},widthOfTextAtSize(t,s){return Array.from(t).length*s*.55}}},setTitle(){},setAuthor(){},setProducer(){},setSubject(){},addPage(){let section='';const p={drawText(t,o){if(/^\\d+ /.test(t))section=t;globalThis.__plotCapture.push({kind:'text',section,text:t,...o})},drawLine(o){globalThis.__plotCapture.push({kind:'line',section,...o})},drawRectangle(){}};pages.push(p);return p},getPages(){return pages},async save(){return new Uint8Array()}}}};`;
const pdfSpecifier='data:text/javascript;base64,'+Buffer.from(pdfStub).toString('base64');
let pdfCode=localImports(transpile(await fs.readFile(path.join(root,'lib/pdf-report.ts'),'utf8')));pdfCode=pdfCode.replace(/from ['"]pdf-lib['"]/g,'from '+JSON.stringify(pdfSpecifier));await fs.writeFile(path.join(out,'pdf-report.mjs'),pdfCode);
const {createReportPdf}=await load('pdf-report');
await test('PDF使用同一裁边线段，允许的负车速仍留在图框内',async()=>{
 for(const log of [parseLog('time_s,speed_kmh\n0,36\n7,36','合成边界.csv',{offset:-1}),parseLog('time_s,speed_kmh\n0,-100\n5,-100','合成负值.csv')]){
  globalThis.__plotCapture=[];await createReportPdf(s,log,thresholds,null,'',new Uint8Array([0]));
  const lines=globalThis.__plotCapture.filter(c=>c.kind==='line'&&c.section==='3 速度时序');const grid=lines.filter(c=>c.thickness===.4),orange=lines.filter(c=>c.color.r===.92&&c.color.g===.4&&c.color.b===.2);
  assert.equal(grid.length,5);assert.ok(orange.length>0);const lo=Math.min(...grid.map(c=>c.start.y)),hi=Math.max(...grid.map(c=>c.start.y));
  for(const line of orange)for(const point of [line.start,line.end])assert.ok(point.y>=lo-1e-9&&point.y<=hi+1e-9);
  assert.equal(orange[0].start.x,grid[0].start.x);assert.equal(orange.at(-1).end.x,grid[0].end.x);
 }
 delete globalThis.__plotCapture;
});

const parserStub='data:text/javascript;base64,'+Buffer.from('export const GlobalWorkerOptions={};export function getDocument(){return globalThis.__pdfFactory()}').toString('base64');
const importCode=transpile(await fs.readFile(path.join(root,'lib/document-import.ts'),'utf8')).replace(/(['"])pdfjs-dist\/legacy\/build\/pdf[.]mjs\1/g,JSON.stringify(parserStub));await fs.writeFile(path.join(out,'document-import.mjs'),importCode);
const {importKnowledgeFile}=await load('document-import');
const pdfFile=()=>new File([new Uint8Array([0])],'fixture.pdf',{type:'application/pdf'});
function parser({pages=1,text='项目说明',loadFailure=false,textFailure=false}={}){const calls={destroy:0,pageCleanup:0};globalThis.__pdfFactory=()=>({promise:loadFailure?Promise.reject(Error('parser failure')):Promise.resolve({numPages:pages,async getPage(){return {async getTextContent(){if(textFailure)throw Error('text failure');return {items:[{str:text,hasEOL:true}]}},cleanup(){calls.pageCleanup++}}}}),async destroy(){calls.destroy++}});return calls;}
await test('超过200页拒绝时仍释放PDF loadingTask',async()=>{const calls=parser({pages:201});await assert.rejects(()=>importKnowledgeFile(pdfFile()),/200/);assert.deepEqual(calls,{destroy:1,pageCleanup:0});});
await test('提取正文超过60000字时清理页面并释放任务',async()=>{const calls=parser({text:'字'.repeat(60001)});await assert.rejects(()=>importKnowledgeFile(pdfFile()),/60,000/);assert.deepEqual(calls,{destroy:1,pageCleanup:1});});
await test('解析失败与页面提取失败的资源清理同样执行',async()=>{
 const loading=parser({loadFailure:true});await assert.rejects(()=>importKnowledgeFile(pdfFile()),/parser failure/);assert.deepEqual(loading,{destroy:1,pageCleanup:0});
 const content=parser({textFailure:true});await assert.rejects(()=>importKnowledgeFile(pdfFile()),/text failure/);assert.deepEqual(content,{destroy:1,pageCleanup:1});
});
await test('正常PDF保留正文和页锚，TXT导入不调用PDF解析器',async()=>{
 const calls=parser();const doc=await importKnowledgeFile(pdfFile());assert.equal(doc.body,'项目说明');assert.deepEqual(doc.segments,[{text:'项目说明',page:1,section:'第 1 页'}]);assert.deepEqual(calls,{destroy:1,pageCleanup:1});
 globalThis.__pdfFactory=()=>{throw Error('TXT must not load PDF parser')};const text=await importKnowledgeFile(new File(['甲段\n\n乙段'],'notes.txt'));assert.equal(text.body,'甲段\n\n乙段');assert.equal(text.segments.length,2);
});
delete globalThis.__pdfFactory;
console.log(count+' import/plot regression groups passed; no HTTP/model or PDF artifact');
