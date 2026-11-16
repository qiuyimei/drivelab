// Local delivery gate: secret travels to git grep only through stdin, never argv/logs.
import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
const git=(args,options={})=>spawnSync('git',args,{encoding:'utf8',maxBuffer:8*1024*1024,...options});
const list=git(['ls-tree','-r','--name-only','HEAD']);if(list.status!==0)throw Error('无法读取交付源树');
const paths=list.stdout.trim().split(/\r?\n/);
if(paths.some(p=>/(^|\/)(\.dev\.vars(?:\.|$)|\.env(?!\.example$)|\.wrangler\/|\.sites-runtime\/)/.test(p)))throw Error('源树包含禁止交付的本机配置或运行数据');
const revisions=git(['rev-list','--all']);if(revisions.status!==0)throw Error('无法读取完整历史');
let key;try{const line=fs.readFileSync('.dev.vars','utf8').split(/\r?\n/).find(l=>l.startsWith('LLM_API_KEY='));if(line)key=JSON.parse(line.slice('LLM_API_KEY='.length));}catch{}
const commits=revisions.stdout.trim().split(/\r?\n/).filter(Boolean);
if(key){for(const revision of commits){const found=git(['grep','-F','-l','-f','-',revision,'--'],{input:key+'\n'});if(found.status===0)throw Error('检测到交付历史包含本机模型凭证，已停止');if(found.status!==1)throw Error('历史凭证扫描无法完成，已停止');}}
console.log(JSON.stringify({trackedFiles:paths.length,commits:commits.length,localConfigExcluded:true,knownModelKeyChecked:!!key,knownModelKeyAbsent:!!key}));
