import './sites-env.mjs';
import {spawnSync} from 'node:child_process';
import path from 'node:path';
const root=process.cwd(),state=path.resolve(process.env.DRIVELAB_LOCAL_STATE??'.wrangler/state');
if(!state.startsWith(root+path.sep))throw Error('本地数据库状态目录必须位于当前项目中。');
const common=['--local','--config','wrangler.local.json','--persist-to',state];
const env={...process.env,CI:'true',WRANGLER_SEND_METRICS:'false'};
function execute(sql){
 const result=spawnSync(process.execPath,['node_modules/wrangler/bin/wrangler.js','d1','execute','DB',...common,'--command',sql,'--json'],{encoding:'utf8',env});
 if(result.status!==0)throw Error('本地数据库检查失败：'+result.stderr);
 return JSON.parse(result.stdout).flatMap(part=>part.results??[]);
}
const tables=new Set(execute("SELECT name FROM sqlite_master WHERE type='table'").map(row=>row.name));
// Earlier releases applied the initial SQL directly, without Wrangler's migration journal.
// Adopt only a verified legacy schema; never recreate/drop tables or rewrite user records.
if(!tables.has('d1_migrations')&&(tables.has('documents')||tables.has('records'))){
 const docs=new Set(execute('PRAGMA table_info(documents)').map(row=>row.name));
 const records=new Set(execute('PRAGMA table_info(records)').map(row=>row.name));
 if(!['id','owner','title','body','created'].every(name=>docs.has(name))||!['id','owner','name','scenario','risk','created','payload'].every(name=>records.has(name)))throw Error('现有数据库结构不完整，已停止自动升级，请保留数据后检查。');
 if(docs.has('metadata')!==docs.has('document_index'))throw Error('知识索引迁移只完成了一部分，已停止自动升级以保留数据。');
 const names=['0000_majestic_mulholland_black.sql',...(docs.has('metadata')?['0001_graceful_lightspeed.sql']:[])];
 execute("CREATE TABLE d1_migrations (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL);"+names.map(name=>`INSERT INTO d1_migrations (name) VALUES ('${name}');`).join(''));
 console.log('已识别并保留旧版数据，接入迁移记录。');
}
const result=spawnSync(process.execPath,['node_modules/wrangler/bin/wrangler.js','d1','migrations','apply','DB',...common],{stdio:'inherit',env});
if(result.status!==0)process.exit(result.status??1);
console.log('本地数据库已就绪，重复运行不会重新建表。');
