import {spawnSync} from 'node:child_process';
for(const file of ['scripts/test-core.mjs','scripts/test-analysis.mjs','scripts/test-workflow.mjs','scripts/validate-benchmarks.mjs','scripts/test-model-setup.mjs']){const r=spawnSync(process.execPath,[file],{stdio:'inherit'});if(r.status!==0)process.exit(r.status??1);}
