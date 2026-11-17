"""Package verified local contest artifacts; never submit or change access."""
from pathlib import Path
import hashlib, json, shutil, subprocess, zipfile
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parents[1]/'outputs'
DEST=OUT/'DriveLab-传智杯参赛材料'
DEST.mkdir(parents=True,exist_ok=True)

def git(*args):
    r=subprocess.run(['git',*map(str,args)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    if r.returncode: raise RuntimeError('Git交付操作失败：'+r.stderr[-600:])
    return r.stdout.strip()

status=git('status','--porcelain')
if status: raise RuntimeError('源码仍有未提交修改，请先同步最终源码再创建历史包。')
scan=subprocess.run(['node','scripts/check-delivery-secrets.mjs'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
if scan.returncode: raise RuntimeError('源码与历史凭证检查未通过。')
scan_result=json.loads(scan.stdout)
revision=git('rev-parse','HEAD')
team=json.loads((ROOT/'docs/competition/team.json').read_text(encoding='utf-8'))
validation=json.loads((ROOT/'docs/competition/FINAL-VALIDATION.json').read_text(encoding='utf-8'))
video_meta=json.loads((OUT/'DriveLab-参赛演示-制作与格式验收.json').read_text(encoding='utf-8'))
technical=OUT/'DriveLab-参赛技术文档.pdf'
pdf=PdfReader(technical)
assert 1<=len(pdf.pages)<=30
technical_qa=json.loads((ROOT/'docs/competition/TECHNICAL-PDF-QA-120.json').read_text(encoding='utf-8'))
assert technical_qa['engineVersion']=='1.2.0' and technical_qa['pageCount']==len(pdf.pages)
assert technical_qa['latestPdfSha256']==hashlib.sha256(technical.read_bytes()).hexdigest()
implementation=json.loads((ROOT/'docs/competition/implementation-results.json').read_text(encoding='utf-8'))
implementation_doc=OUT/'DriveLab 智能驾驶工况仿真与辅助分析 Web 平台 V1.0 软件实现与成果说明书.docx'
assert implementation['finalized'] and implementation['engineVersion']=='1.2.0'
assert implementation_doc.read_bytes()==(ROOT/'docs/competition/DriveLab-软件实现与成果说明书.docx').read_bytes()
implementation_qa=json.loads((ROOT/'docs/competition/IMPLEMENTATION-RESULTS-QA.json').read_text(encoding='utf-8'))
assert implementation_qa['engineVersion']=='1.2.0' and implementation_qa['finalized']
assert implementation_qa['visualReview']=='pass' and implementation_qa['visualReviewAllPages']
assert implementation_qa['outputRepositoryAndRenderInputByteIdentical']
assert not implementation_qa['remainingBlockingFindings']
assert implementation_qa['sha256']==hashlib.sha256(implementation_doc.read_bytes()).hexdigest()
assert validation['engineVersion']=='1.2.0'
assert validation['softwareChecksPassed'] and validation['coreTests']>=41 and validation['analysisTests']>=40
assert validation['savedWorkflowGroups']>=8 and validation['independentCases']>=130
assert validation['continuousExtremaReview']['cases']>=72
assert 'passed 10 checks' in validation.get('apiIntegration','')
engineering114=json.loads((ROOT/'docs/evidence/engineering-results-audit-20261117.json').read_text(encoding='utf-8'))
live114=json.loads((ROOT/'docs/competition/LIVE-ENGINE-114-QA.json').read_text(encoding='utf-8'))
assert engineering114['finalEngineVersion']=='1.1.4' and live114['engineVersion']=='1.1.4'
task_evaluation=json.loads((ROOT/'public/validation/ai-task-results.json').read_text(encoding='utf-8'))
assert task_evaluation['offline']['taskCount']==8
assert task_evaluation['live']['taskCount']==6 and task_evaluation['live']['acceptedModelAnswers']==5
assert task_evaluation['live']['fallbacks']==1 and task_evaluation['live']['modelRequests']==14
task_regression=json.loads((ROOT/'docs/evidence/AI-TASK-T06-REGRESSION-120.json').read_text(encoding='utf-8'))
ui_qa=json.loads((ROOT/'docs/competition/UI-ENGINE-120-QA.json').read_text(encoding='utf-8'))
assert ui_qa['status']=='passed' and ui_qa['supplement']['claimFactsVisible']
assert team['school']=='厦门大学嘉庚学院' and team['identityConfirmed']
assert [m['name'] for m in team['members']]==['邱益美','李聿昕','丁鑫炜']
video=OUT/'DriveLab-参赛演示.mp4'
assert video.exists() and video.stat().st_size>1_000_000
# Metadata is produced only after actual FFmpeg media and subtitle checks.
media_checks=video_meta.get('formatChecks',{})
duration=media_checks.get('durationSeconds')
if duration is None: raise RuntimeError('视频验收元数据缺少实际时长。')
assert 300<=duration<=480
assert media_checks.get('width')==1920 and media_checks.get('height')==1080 and media_checks.get('hasAudio')
assert video_meta.get('fullDecodeExitCode')==0
assert video_meta.get('audioVolumeChecks',{}).get('noDigitalPeakClipping')
assert video_meta.get('subtitleRenderChecks',{}).get('changingSubtitlePixels')
assert video_meta.get('outputSha256')==hashlib.sha256(video.read_bytes()).hexdigest()
video_revalidation=json.loads((ROOT/'docs/competition/VIDEO-120-REVALIDATION.json').read_text(encoding='utf-8'))
assert video_revalidation['engineVersion']=='1.2.0'
assert video_revalidation['numericComparisons']==11 and video_revalidation['unchangedWithinTolerance']
assert video_revalidation['mp4Sha256']==video_meta['outputSha256']
sentence_checks=video_meta.get('sentenceSubtitleChecks',{})
assert all(sentence_checks.get(key) for key in ['oneToOne','textExactMatch','noCrossSentenceConcatenation','noTimeOverlap','quantizedNoTimeOverlap'])
assert sentence_checks.get('boundaryRenderChecks'), '必须完成实际字幕交界帧检查'
assert video_meta.get('mode')=='product_video_and_subtitles_acceptance_passed'
assert video_meta.get('acceptance',{}).get('independentSentenceAuditPassed')
independent_qa=ROOT/'docs/competition/VIDEO-SUBTITLE-QA.json'
independent=json.loads(independent_qa.read_text(encoding='utf-8'))
assert independent['stage']=='final-mp4-sentence-audit-passed'
assert independent['outputSha256']==video_meta['outputSha256']
assert independent['scriptSha256']==hashlib.sha256((ROOT/'docs/competition/video-script.json').read_bytes()).hexdigest()
assert independent['allSentenceAndSceneTransitionsIncluded']
assert video_meta['acceptance']['independentQaSha256']==hashlib.sha256(independent_qa.read_bytes()).hexdigest()
assert video_meta['acceptance']['visualReviewPassed']

assets=[(technical,'01-参赛技术文档.pdf'),(video,'02-项目演示.mp4'),
       (OUT/'DriveLab-参赛演示.srt','03-演示字幕.srt'),
       (OUT/'DriveLab-参赛演示-逐字稿.txt','04-演示逐字稿.txt'),
       (OUT/'DriveLab-报告样张.pdf','05-工况报告样张.pdf'),
       (ROOT/'README.md','06-README.md'),
       (ROOT/'docs/competition/AI-AND-LICENSES.txt','07-AI使用与第三方许可说明.txt'),
       (ROOT/'docs/competition/FINAL-VALIDATION.json','08-工程与软件验收.json'),
       (ROOT/'docs/evidence/engineering-final-review-20261117.json','09-历史1.1.3工程复核记录.json'),
       (ROOT/'docs/evidence/analysis-final-review-20261117.json','10-历史1.1.3AI证据链复核记录.json'),
       (ROOT/'docs/competition/RULES-REVIEW-20261117.json','11-既有赛事规则核对-含历史113状态.json'),
       (ROOT/'docs/competition/team.json','12-报名信息核对.json'),
       (OUT/'DriveLab-参赛演示-制作与格式验收.json','13-视频验收.json'),
       (OUT/'DriveLab 智能驾驶工况仿真与辅助分析 Web 平台 V1.0 软件实现与成果说明书.docx','16-软件实现与成果说明书.docx'),
       (ROOT/'docs/evidence/engineering-results-audit-20261117.json','17-engineering-results-audit-20261117.json'),
       (ROOT/'docs/competition/LIVE-ENGINE-114-QA.json','18-历史1.1.4模型记录.json'),
       (ROOT/'docs/evidence/ai-task-evaluation-20261117.json','19-AI固定任务评测.json'),
       (ROOT/'docs/evidence/AI-TASK-T06-REGRESSION-120.json','20-换道单题回归与语义审阅.json'),
       (ROOT/'docs/competition/UI-ENGINE-120-QA.json','21-新任务界面验收.json'),
       (ROOT/'docs/evidence/ENGINE-120-CHANGE-SCOPE.json','22-计算模块版本与历史范围.json'),
       (ROOT/'docs/competition/VIDEO-120-REVALIDATION.json','23-旧视频数值复核范围.json'),
       (ROOT/'docs/competition/RULES-120-REVIEW.json','24-本轮赛事规则核对.json')]
for source,name in assets:
    if not source.is_file(): raise RuntimeError('缺少交付文件：'+source.name)
    shutil.copy2(source,DEST/name)

source_zip=DEST/'14-DriveLab-源码.zip'
bundle=DEST/'15-DriveLab-完整Git历史.bundle'
git('archive','--format=zip','--output='+str(source_zip),'HEAD')
git('bundle','create',bundle,'--all')
git('bundle','verify',bundle)
shutil.copy2(source_zip,OUT/'DriveLab-V1.0-源码.zip')
shutil.copy2(bundle,OUT/'DriveLab-完整Git历史.bundle')

notice='''DriveLab 传智杯参赛材料 使用与提交须知

当前产品V1.0，软件引擎1.2.0。包含技术PDF、详细成果DOCX、1080p普通话演示、字幕逐字稿、报告样张、源码、完整Git历史及验收。此包已准备，不代表报名系统已接收。

当前与历史记录
08是当前工程验收；16是详细成果说明书；19是固定任务评测，保留当前离线与较早六题真实模型各自源码hash；20单列T06初次失败和唯一额外回归，不能替换六题中的失败；21是新任务界面本机验收，22列明核心计算模块与114相同及历史复核范围，23列旧视频数值复核范围。
09/10为113历史审阅，17/18为114工程与模型历史。624组纵向/120组日志/72组极值保留执行版本，不冒称120全部新运行。11是此前赛事规则核对，含旧材料状态，不是本轮新浏览记录。

团队信息
厦门大学嘉庚学院；负责人邱益美，成员李聿昕、丁鑫炜，无指导老师。职责为用户授权的分工安排，不能推导历史工时或个人独立完成比例。队名、参赛组别、报名/缴费状态等未确认字段留空。

提交前仍需团队确认
1. 报名后台组别、队名、最终入口及精确截止时点；赛事正文列11月18日，后台状态未验证。
2. 仓库继续Private，线上平台仍仅本人可访问。需取得指定评审账号或认可方式后授权并验证；本人可读不代表评委可读。Git bundle是离线备份，不能替代赛事仓库访问要求。个人GitHub仓库协作者具有写权限，不将其误称只读。
3. 在赛事系统最终提交，材料准备不代表已报名/缴费/提交。

恢复源码及历史
git clone 15-DriveLab-完整Git历史.bundle drivelab
cd drivelab
pnpm install --frozen-lockfile
pnpm run db:local
pnpm run dev
完整环境和免费接口配置见README。首次安装依赖需要联网。令牌只在本机忽略配置或授权服务端环境中，不在材料包。

验证范围
41项核心、40项分析、8组保存恢复、10项API、130项独立参考等见08。8个合成任务的24项参考在3个变体重复核对，共72断言，不是72独立任务或AI准确率。初6道实际模型题14次请求，5接收1降级，日志引用支持不足及候选叙述失败保留。额外T06初3次失败后，授权唯一回归3次成功，仍有局部引用支持限制。没有真实用户耗时研究，不编造效率比例或实车准确率。
连续需求极值只覆盖恒减速/给定轨迹活动区间及适用速度域，避障低速段仍未完整评估。不含实车标定、轮胎饱和闭环求解或安全认证。日志名不能证明来源。输入指纹/引用登记不是真实性签名或完整语义验证。

视频
已验收V2视频387.54秒，1920×1080，含普通话合成解说，展示真实界面、计算结果与流程示意；不是连续实时录屏。视频未为120新首页重制；本轮同11数值字段重算一致，明确渲染读取6候选卡字段；不声称其余字段逐帧新核验。新任务流程用DOCX新图、21UI验收与20单题记录证明。
'''
(DEST/'00-提交前必读.txt').write_text(notice,encoding='utf-8')
files=[]
expected_names={name for _,name in assets}|{source_zip.name,bundle.name,'00-提交前必读.txt'}
for name in sorted(expected_names):
    file=DEST/name
    files.append({'name':file.name,'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
manifest={'preparedOn':'2026-11-17','revision':'AI任务流程与成果材料1.2.0','sourceCommit':revision,'engineVersion':validation['engineVersion'],
          'technicalPdfPages':len(pdf.pages),'videoDurationSeconds':duration,'sourceAndHistoryScan':scan_result,
          'currentStatusFiles':['08-工程与软件验收.json','19-AI固定任务评测.json','20-换道单题回归与语义审阅.json','21-新任务界面验收.json','22-计算模块版本与历史范围.json'],
          'historicalReviewFiles':['09-历史1.1.3工程复核记录.json','10-历史1.1.3AI证据链复核记录.json','11-既有赛事规则核对-含历史113状态.json','17-engineering-results-audit-20261117.json','18-历史1.1.4模型记录.json'],
          'videoRevalidation':{'engineVersion':'1.2.0','numericComparisons':11,'unchangedWithinTolerance':True,'mp4RemadeFor120':False,'materialEngineVersion':video_revalidation['videoEngineMaterial'],'record':'docs/competition/VIDEO-120-REVALIDATION.json'},
          'fileArtifactsPrepared':True,'teamConfirmed':team['confirmed'],
          'reviewerAccessVerified':False,'registrationVerified':False,'submissionReady':False,
          'files':files}
(DEST/'文件校验清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
archive=OUT/'DriveLab-传智杯参赛材料.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name in sorted(expected_names|{'文件校验清单.json'}):
        file=DEST/name
        z.write(file,arcname=DEST.name+'/'+file.name)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert not any('.dev.vars' in p or '.sites-runtime' in p for p in z.namelist())
summary={'archive':str(archive),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
         'files':len(files)+1,'sourceCommit':revision,'technicalPdfPages':len(pdf.pages),
         'videoDurationSeconds':duration,'fileArtifactsPrepared':True,'submissionReady':False,
         'pending':['队名与组别等未确认字段','指定评审仓库与平台访问','报名后台最终阶段、时点与提交']}
(OUT/'DriveLab-材料包验收.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
