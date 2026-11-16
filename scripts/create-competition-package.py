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
assert validation['softwareChecksPassed'] and validation['analysisTests']>=27
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
       (ROOT/'docs/evidence/engineering-review-20261116.json','09-工程复核记录.json'),
       (ROOT/'docs/evidence/analysis-review-20261116.json','10-AI证据链复核记录.json'),
       (ROOT/'docs/competition/RULES-REVIEW-20261116.json','11-赛事要求核对.json'),
       (ROOT/'docs/competition/team.json','12-报名信息核对.json'),
       (OUT/'DriveLab-参赛演示-制作与格式验收.json','13-视频验收.json')]
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

本包已制作技术PDF、普通话1080p演示视频、字幕与逐字稿、源码、完整Git历史、许可与验收记录。
本包不等于报名系统已接收，不含虚构身份或人工签署。

必须由团队补齐/确认
1. team.json与README中的队名、学校、组别、队长、实际成员分工、指导教师。原开发文档两名拟定成员没有被当作完成贡献证明。
2. 仓库继续Private。按组委会提供的具体评审账号或认可方式授权并验证可读；当前本人可访问不能代表评委可访问。完整Git bundle是离线备份，不能擅自替代赛事的仓库访问要求。
3. 核对本人报名后台的报名/缴费/提交阶段、精确截止时间及最终入口。公开整理材料列11月18日，不能推断已报名或提交成功。

恢复完整源码与历史
git clone 15-DriveLab-完整Git历史.bundle drivelab
cd drivelab
pnpm install --frozen-lockfile
pnpm run db:local
pnpm run dev
环境、免费模型配置与验证命令见README。模型令牌自行保存在本机/授权服务端，不在本包中。

证据与边界
工程复核验证假设内的软件实现，不等同实车标定、持证工程签署或车辆安全认证。
视频由真实界面、实际计算结果与功能流程示意剪辑而成，普通话采用AI合成解说，不是连续实时录屏或真人配音。
结构和引用校验不证明所有自然语言语义。0.1s采样需求峰值不保证连续时间极值；公开路段仅作数据导入演示。
不以测试数量、单次模型通过或公开数据对比宣称实车准确率或保证获奖。
'''
(DEST/'00-提交前必读.txt').write_text(notice,encoding='utf-8')
files=[]
expected_names={name for _,name in assets}|{source_zip.name,bundle.name,'00-提交前必读.txt'}
for name in sorted(expected_names):
    file=DEST/name
    files.append({'name':file.name,'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
manifest={'preparedOn':'2026-11-17','revision':'产品演示与逐句字幕修订版','sourceCommit':revision,'engineVersion':validation['engineVersion'],
          'technicalPdfPages':len(pdf.pages),'videoDurationSeconds':duration,'sourceAndHistoryScan':scan_result,
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
         'pending':['报名身份及实际分工','指定评审仓库访问','报名后台最终阶段和时点']}
(OUT/'DriveLab-材料包验收.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
