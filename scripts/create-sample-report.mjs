import fs from 'node:fs/promises';
import {defaults,simulate} from '../.sites-runtime/core-tests/simulation.mjs';
import {parseLog,sampleCSV} from '../.sites-runtime/core-tests/logs.mjs';
import {runAnalysis} from '../.sites-runtime/core-tests/analysis.mjs';
import {createReportPdf} from '../.sites-runtime/core-tests/pdf-report.mjs';
const simulation=simulate(defaults),log=parseLog(sampleCSV(simulation.rows,true),'合成演示日志.csv'),thresholds={speed:2,yaw:2,pressure:5,steering:10};
const analysis=await runAnalysis({config:defaults,question:'分析工况与日志差异',log,thresholds,mode:'rules'},[],{});
const bytes=await createReportPdf(simulation,log,thresholds,analysis,'',await fs.readFile('public/fonts/NotoSansSC-Regular.ttf'));
await fs.mkdir('.sites-runtime/pdf-qa',{recursive:true});await fs.writeFile('.sites-runtime/pdf-qa/report-sample.pdf',bytes);console.log(JSON.stringify({file:'.sites-runtime/pdf-qa/report-sample.pdf',bytes:bytes.length}));
