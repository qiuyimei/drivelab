import './sites-env.mjs';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import path from 'node:path';
import crypto from 'node:crypto';
// Keep SQLite state paths below common Windows native path-length limits.
const base=path.resolve('.sites-runtime','dbqa-'+crypto.randomUUID().slice(0,8));
const env={...process.env,CI:'true',WRANGLER_SEND_METRICS:'false'};
function command(args,extra={}){const r=spawnSync(process.execPath,args,{env:{...env,...extra},encoding:'utf8'});if(r.status!==0)throw Error(r.stdout+'\n'+r.stderr);return r.stdout;}
function execute(state,options){return command(['node_modules/wrangler/bin/wrangler.js','d1','execute','DB','--local','--config','wrangler.local.json','--persist-to',state,...options,'--json']);}
function query(state,sql){return JSON.parse(execute(state,['--command',sql])).flatMap(result=>result.results??[]);}
function init(state){return command(['scripts/init-local-db.mjs'],{DRIVELAB_LOCAL_STATE:state});}
const fresh=path.join(base,'fresh');init(fresh);init(fresh);
assert.equal(query(fresh,'SELECT COUNT(*) AS n FROM d1_migrations')[0].n,2);
assert.ok(query(fresh,'PRAGMA table_info(documents)').some(row=>row.name==='document_index'));
const legacy=path.join(base,'legacy');execute(legacy,['--file','drizzle/0000_majestic_mulholland_black.sql']);
query(legacy,"INSERT INTO records (id,owner,name,scenario,risk,created,payload) VALUES ('bootstrap-fixture','qa','保留数据夹具','curve','约束内','2026-11-15','{}')");
init(legacy);init(legacy);
assert.equal(query(legacy,"SELECT name FROM records WHERE id='bootstrap-fixture'")[0].name,'保留数据夹具');
assert.equal(query(legacy,'SELECT COUNT(*) AS n FROM d1_migrations')[0].n,2);
assert.ok(query(legacy,'PRAGMA table_info(documents)').some(row=>row.name==='metadata'));
console.log('PASS local database: fresh install, repeat startup, legacy adoption and record preservation');
