"""Assemble the three-entry formal submission and separate editable outputs."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT.parents[1]/'outputs/最终交付-20261118')
    parser.add_argument('--qa-dir',type=Path,default=ROOT/'.sites-runtime/final121')
    args=parser.parse_args()
    output=args.output_dir.resolve();output.mkdir(parents=True,exist_ok=True)
    evidence=output/'验收';evidence.mkdir(exist_ok=True)
    qa=args.qa_dir.resolve()
    validation_path=ROOT/'docs/competition/FINAL-VALIDATION.json'
    validation=json.loads(validation_path.read_text('utf-8'))
    technical=json.loads((ROOT/'docs/competition/TECHNICAL-PDF-QA-121.json').read_text('utf-8'))
    checklist=json.loads((ROOT/'docs/competition/CHECKLIST-QA-121.json').read_text('utf-8'))
    video=json.loads((ROOT/'docs/competition/VIDEO-FINAL-121.json').read_text('utf-8'))
    assert validation['softwareChecksPassed'] and validation['engineVersion']=='1.2.1'
    assert technical['finalized'] and technical['sameContentSource'] and technical['nativeEditable'] and technical['pageCount']<=30
    assert checklist['finalized'] and checklist['nativeEditable']
    assert video['status']=='passed_final_technical_and_sampled_visual_review'
    assert 300<=video['format']['durationSeconds']<=480
    assert video['format']['width']>=1920 and video['format']['height']>=1080
    sources={
        'DriveLab-参赛技术文档.docx':qa/'technical.docx',
        'DriveLab-参赛技术文档.pdf':qa/'technical.pdf',
        'DriveLab-最终修改核对单.docx':qa/'checklist.docx',
        'DriveLab-最终修改核对单.pdf':qa/'checklist.pdf',
        'DriveLab-参赛演示.mp4':output/'视频制作'/video['output'],
    }
    assert sha(sources['DriveLab-参赛技术文档.docx'])==technical['docxSha256']
    assert sha(sources['DriveLab-参赛技术文档.pdf'])==technical['sha256']
    assert sha(sources['DriveLab-参赛演示.mp4'])==video['outputSha256']
    for name,source in sources.items():
        shutil.copy2(source,output/name)
        assert sha(source)==sha(output/name)
    for suffix in ['docx','pdf']:
        shutil.copy2(output/f'DriveLab-参赛技术文档.{suffix}',output/f'DriveLab-参赛技术文档-简洁版.{suffix}')
    link=output/'DriveLab-仓库链接.txt'
    link.write_text('DriveLab 智能驾驶工况仿真与辅助分析平台\n产品 V1.0 / 引擎 1.2.1\n\n源码仓库（含完整 Git 历史）：\nhttps://github.com/qiuyimei/drivelab\n\n仓库保持私有，访问权限未在本次材料制作中调整。\n','utf-8',newline='\n')
    entries={
        '01-DriveLab-参赛技术文档.pdf':output/'DriveLab-参赛技术文档.pdf',
        '02-DriveLab-参赛演示.mp4':output/'DriveLab-参赛演示.mp4',
        '03-DriveLab-仓库链接.txt':link,
    }
    archive=output/'DriveLab-正式提交材料-简洁版.zip'
    with ZipFile(archive,'w',ZIP_DEFLATED,compresslevel=9) as package:
        for name,path in entries.items():package.write(path,name)
    with ZipFile(archive) as package:
        assert package.namelist()==list(entries) and package.testzip() is None
        assert all(hashlib.sha256(package.read(name)).hexdigest()==sha(path) for name,path in entries.items())
    validation['materialFormats']={
        'status':'passed final native document and revised video QA','engineVersion':'1.2.1',
        'technicalPdfPages':technical['pageCount'],'technicalSha256':technical['sha256'],
        'editableTechnicalDocxSha256':technical['docxSha256'],'sameContentSource':True,
        'editorialStyle':'plain student project report; user-requested simpler wording and layout; screenshots and factual results retained',
        'technicalNativeTables':technical['nativeTables'],'technicalFigureGroups':technical['actualFigureGroups'],
        'checklistPages':checklist['pageCount'],'checklistExcludedFromSubmissionZip':True,
        'videoDurationSeconds':video['format']['durationSeconds'],'videoResolution':[1920,1080],
        'videoSha256':video['outputSha256'],'videoRemadeFor121Materials':True,
        'videoActualTaskUiVersion':'1.2.0','voice':'installed Windows Microsoft Huihui offline',
        'newTtsNetworkRequests':0,'newLiveModelRequestsInThisMaterialsTask':0,
        'formalZipEntries':list(entries),'formalZipSha256':sha(archive),
    }
    validation['submissionReadiness']['materialFormats']=f"passed {technical['pageCount']}-page same-content PDF/editable DOCX in revised plain report style, separately reviewed checklist and 7:43.833 1080p offline-Mandarin video; three-entry ZIP verified"
    validation['submissionReadiness']['currentDeployment']='Final publication outcome is recorded alongside delivered artifacts after this source snapshot is frozen.'
    validation['currentOnlineUi']={'engineVersion':'1.2.1','status':'publication receipt recorded outside frozen source','historicalDeployment':'1.2.0 retained in historicalOnlineUi120','receipt':'最终交付-20261118/验收/发布记录.json','audience':'owner-only private; unchanged'}
    validation_path.write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n','utf-8',newline='\n')
    record={
        'reviewedOn':'2026-11-18','engineVersion':'1.2.1','submissionPerformed':False,
        'formalArchive':str(archive),'formalZipSha256':sha(archive),
        'formalEntries':{name:{'sha256':sha(path),'bytes':path.stat().st_size} for name,path in entries.items()},
        'separateFiles':{name:{'sha256':sha(output/name),'bytes':(output/name).stat().st_size} for name in sources if not name.endswith('.mp4')},
        'technicalPages':technical['pageCount'],'videoSeconds':video['format']['durationSeconds'],
        'zipCrcAndByteEqualityPassed':True,'editableWordAndChecklistExcludedFromFormalZip':True,
        'registrationAndPermissionsNotHandled':True,
    }
    for name in ['TECHNICAL-PDF-QA-121.json','CHECKLIST-QA-121.json','VIDEO-FINAL-121.json','FINAL-VALIDATION.json']:
        shutil.copy2(ROOT/'docs/competition'/name,evidence/name)
    for path in [evidence/'最终材料清单.json',ROOT/'docs/competition/FINAL-PACKAGE-121.json']:
        path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf-8',newline='\n')
    print(json.dumps({'formalArchive':str(archive),'entryCount':len(entries),'archiveSha256':sha(archive),'technicalPages':technical['pageCount'],'checklistPages':checklist['pageCount'],'videoSeconds':video['format']['durationSeconds']},ensure_ascii=False))


if __name__=='__main__':main()
