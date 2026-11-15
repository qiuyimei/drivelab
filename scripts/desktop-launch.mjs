import {spawn,spawnSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..');process.chdir(root);
const url='http://127.0.0.1:5173/';
function open(){spawn('rundll32.exe',['url.dll,FileProtocolHandler',url],{stdio:'ignore',windowsHide:true});}
async function ready(){try{const r=await fetch(url+'api/status',{signal:AbortSignal.timeout(1500)});const v=await r.json();return r.ok&&typeof v.database==='boolean';}catch{return false;}}
if(await ready()){console.log('DriveLab 已启动：'+url);open();process.exit(0);}
if(!fs.existsSync('node_modules/vinext')){console.error('尚未安装依赖。请先按 README.md 安装项目依赖。');process.exit(1);}
for(const script of ['scripts/prepare-assets.mjs','scripts/init-local-db.mjs']){const prepared=spawnSync(process.execPath,[script],{cwd:root,stdio:'inherit'});if(prepared.status!==0)process.exit(prepared.status??1);}
const child=spawn(process.execPath,['scripts/run-framework.mjs','dev'],{cwd:root,stdio:'inherit',env:{...process.env,PATH:path.join(root,'node_modules','.bin')+path.delimiter+process.env.PATH}});
const timer=setInterval(async()=>{if(await ready()){clearInterval(timer);open();console.log('\nDriveLab 已就绪。关闭此窗口会停止本地服务器。');}},1000);
child.on('exit',code=>{clearInterval(timer);process.exit(code??0);});process.on('SIGINT',()=>child.kill('SIGINT'));
