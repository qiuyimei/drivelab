"""Independent, offline V2 subtitle audit. Never calls TTS or changes production files.

Run without flags for script/SRT/ASS/PCM checks. Use --final only after the
producer freezes the canonical MP4 and metadata; it decodes the FINAL MP4,
compares caption glyph masks to independently rendered canonical sentences,
checks blank boundaries (including scene joins), and checks AAC/PCM alignment.
"""
from __future__ import annotations
import argparse, array, hashlib, json, math, re, subprocess, wave
from datetime import datetime
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.sites-runtime/competition-video-v2'
OUTPUTS=ROOT.parent.parent/'outputs'
SCRIPT=ROOT/'docs/competition/video-script.json'
QA=CACHE/'independent-qa'
FPS,SR,SPF=24,24000,1000
METHOD='complete-sentence-pcm-frames-v2'
FFMPEG=imageio_ffmpeg.get_ffmpeg_exe()

def require(condition,message):
    if not condition:raise AssertionError(message)
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def pcm(path):
    with wave.open(str(path),'rb') as f:
        require((f.getnchannels(),f.getsampwidth(),f.getframerate())==(1,2,SR),'PCM format: '+str(path))
        n=f.getnframes();return f.readframes(n),n
def srt_ms(text):
    h,m,s,ms=map(int,re.fullmatch(r'(\d+):(\d+):(\d+),(\d{3})',text).groups())
    return ((h*60+m)*60+s)*1000+ms
def ass_cs(text):
    h,m,s,cs=map(int,re.fullmatch(r'(\d+):(\d+):(\d+)\.(\d{2})',text).groups())
    return ((h*60+m)*60+s)*100+cs
def ass_clock(frame):
    total=frame*100//FPS;h,total=divmod(total,360000);m,total=divmod(total,6000);s,cs=divmod(total,100)
    return f'{h}:{m:02}:{s:02}.{cs:02}'
def run(args,log):
    result=subprocess.run([str(v) for v in args],capture_output=True,text=True,encoding='utf-8',errors='replace',cwd=log.parent)
    log.write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
    require(result.returncode==0,'FFmpeg failed: '+str(log))
    return result.stderr

def check_prepared():
    script,meta,timelines=load(SCRIPT),load(CACHE/'video-metadata.json'),load(CACHE/'timeline.json')
    require(script['schemaVersion']=='product-sentences-v2','Unexpected script schema')
    require(sha(SCRIPT)==meta['scriptSha256'],'Script changed after preparation')
    require(meta['sentenceSubtitleChecks']['method']==METHOD,'Wrong subtitle method')
    require(meta['fps']==FPS,'Wrong FPS')
    require(meta['sentenceSubtitleChecks']['pcmSampleRate']==SR,'Wrong sample rate')
    require(meta['sentenceSubtitleChecks']['samplesPerVideoFrame']==SPF,'Wrong samples/frame')
    require(len(script['scenes'])==len(timelines)==12,'Scene timeline count')
    expected=[text for scene in script['scenes'] for text in scene['sentences']]
    cues=meta['sentenceSubtitleChecks']['perSentence']
    require(len(expected)==len(cues)==meta['sentenceSubtitleChecks']['sentenceCount'],'Sentence/cue count mismatch')
    require([c['text'] for c in cues]==expected,'Canonical cue text differs from script')
    require(all(text[-1:]=='。' and text.count('。')==1 for text in expected),'Not one full sentence per cue')
    visible=[v for scene in script['scenes'] for v in [scene['chapter'],scene['title'],*scene['points'],*scene['sentences']]]
    prohibited=re.compile('工程复核|修.?BUG|尖峰|修复|回归|普通话|合成解说|语义嵌入|embedding',re.I)
    require(not any(prohibited.search(v) for v in visible),'Prohibited production/debug narration in visible script')
    font=ImageFont.truetype(str(ROOT/'public/fonts/NotoSansSC-Regular.ttf'),42)
    max_width=max(font.getlength(text) for text in expected)
    require(max_width<=1700,'Sentence does not fit a single subtitle line')
    source_pcm,source_n=pcm(CACHE/'narration.wav')
    offset=0;flat=[];gap_checks=0;scene_records=[]
    for scene,timeline in zip(script['scenes'],timelines):
        sid=scene['id'];require(timeline['id']==sid,'Scene order mismatch')
        local=timeline['cues'];require(len(local)==len(scene['sentences']),'Local sentence count: '+sid)
        require(local==load(CACHE/sid/'sentence-timeline.json'),'Local timeline copies differ: '+sid)
        scene_pcm,scene_n=pcm(CACHE/sid/'scene.wav')
        require(scene_n==timeline['frames']*SPF,'Scene PCM/frame length: '+sid)
        require(scene_pcm==source_pcm[offset*SPF*2:(offset+timeline['frames'])*SPF*2],'Global PCM differs from scene: '+sid)
        require(local[0]['startFrame']==4 and timeline['frames']-local[-1]['endFrame']==8,'Scene prefix/tail: '+sid)
        require(not any(scene_pcm[:4*SPF*2]) and not any(scene_pcm[local[-1]['endFrame']*SPF*2:]),'Non-silent scene prefix/tail: '+sid)
        dialogue=[line.split(',',9) for line in (CACHE/sid/'subtitles.ass').read_text(encoding='utf-8').splitlines() if line.startswith('Dialogue:')]
        require(len(dialogue)==len(local),'ASS sentence count: '+sid)
        for i,(text,cue,ass) in enumerate(zip(scene['sentences'],local,dialogue),1):
            label=f'{sid}/{i:03}'
            require(cue['sentenceIndex']==i and cue['scene']==sid,'Sentence identity: '+label)
            require(cue['text']==cue['ttsInput']==text,'Cue/TTS text mismatch: '+label)
            require(isinstance(cue['startFrame'],int) and isinstance(cue['endFrame'],int),'Fractional frame index: '+label)
            record=load(CACHE/sid/f'sentence-{i:03}.json')
            clip_path=CACHE/cue['audioFile'];clip,n=pcm(clip_path)
            require(record['method']==METHOD and record['text']==record['ttsInput']==text,'TTS source metadata: '+label)
            signature=hashlib.sha256((METHOD+'|'+script['voice']['name']+'|'+script['voice']['rate']+'|'+text).encode()).hexdigest()
            require(record['signature']==signature,'TTS cache signature: '+label)
            require(sha(clip_path)==record['wavSha256']==cue['wavSha256'],'PCM hash: '+label)
            require(n==record['pcmSamples']==cue['pcmSamples'] and n>0,'PCM sample count: '+label)
            padded=((n+SPF-1)//SPF)*SPF
            require(cue['paddedSamples']==padded and cue['paddingSamples']==padded-n,'PCM padding: '+label)
            require((cue['endFrame']-cue['startFrame'])*SPF==padded,'Cue frames do not enclose exactly one padded PCM clip: '+label)
            a,b=cue['startFrame']*SPF*2,cue['endFrame']*SPF*2
            require(scene_pcm[a:a+len(clip)]==clip and not any(scene_pcm[a+len(clip):b]),'PCM content/padding mismatch: '+label)
            require(ass[9]==text,'ASS text is not this exact full sentence: '+label)
            require(ass_cs(ass[1])==cue['startFrame']*100//FPS and ass_cs(ass[2])==cue['endFrame']*100//FPS,'ASS quantized timing: '+label)
            require(ass_cs(ass[1])<ass_cs(ass[2]),'Empty ASS cue: '+label)
            g=dict(cue);g['startFrame']+=offset;g['endFrame']+=offset;g['startSeconds']=g['startFrame']/FPS;g['endSeconds']=g['endFrame']/FPS;g['cueIndex']=len(flat)+1
            require(g==cues[len(flat)],'Global/local timeline disagreement: '+label);flat.append(g)
            if i>1:
                previous=local[i-2];require(cue['startFrame']-previous['endFrame']==6,'Not six blank frames: '+label)
                require(not any(scene_pcm[previous['endFrame']*SPF*2:a]),'Audio sentence gap is not zero PCM: '+label);gap_checks+=1
        scene_records.append({'scene':sid,'frames':timeline['frames'],'sentences':len(local),'startFrame':offset})
        offset+=timeline['frames']
    require(offset*SPF==source_n,'Global PCM duration differs from exact frame duration')
    require(flat==cues,'Global timeline has unverified trailing sentences')
    require(abs(offset/FPS-meta['plannedDurationSeconds'])<1e-9,'Prepared duration mismatch')
    blocks=(OUTPUTS/'DriveLab-参赛演示.srt').read_text(encoding='utf-8-sig').strip().split('\n\n')
    require(len(blocks)==len(cues),'SRT cue count')
    for index,(block,cue) in enumerate(zip(blocks,cues),1):
        number,times,text=block.split('\n',2);a,b=times.split(' --> ')
        require(int(number)==index and text==cue['text'],'SRT identity/full text mismatch: '+str(index))
        require(srt_ms(a)==cue['startFrame']*1000//FPS and srt_ms(b)==cue['endFrame']*1000//FPS,'SRT timing: '+str(index))
    require(all(a['endFrame']<b['startFrame'] for a,b in zip(cues,cues[1:])),'Cross-sentence subtitle overlap')
    for a,b in zip(cues,cues[1:]):
        require(a['endFrame']*100//FPS<b['startFrame']*100//FPS,'ASS quantization overlap')
        require(a['endFrame']*1000//FPS<b['startFrame']*1000//FPS,'SRT quantization overlap')
        require(not any(source_pcm[a['endFrame']*SPF*2:b['startFrame']*SPF*2]),'Global sentence/scene gap not silent')
    report={'stage':'script-subtitles-pcm-passed','notFinalVideoAcceptance':True,'scriptSha256':sha(SCRIPT),'sentenceCount':len(cues),'sceneCount':len(timelines),'totalFrames':offset,'durationSeconds':offset/FPS,'pcmSamples':source_n,'exactTextAndAudioClipMapping':True,'exactPcmAssembly':True,'perSentencePcmHashesPassed':len(cues),'withinSceneSixFrameGapsPassed':gap_checks,'crossSceneBlankGapsPassed':len(timelines)-1,'quantizedAssAndSrtNoOverlap':True,'maxSubtitleWidthAt42px':max_width,'scenes':scene_records,'limitations':['No human speech/listening or pronunciation audit claimed.','Prepared metadata is not final MP4 acceptance.']}
    save(QA/'prepared-audit.json',report)
    return script,meta,cues,report,source_pcm

def white_mask(path):
    im=Image.open(path).convert('RGB');mask=Image.new('1',im.size);mask.putdata([r>165 and g>165 and b>165 for r,g,b in im.getdata()]);return mask
def white_count(mask):return mask.convert('L').histogram()[255]

def sum_expression(terms):
    # A flat expression for hundreds of boundaries exceeds FFmpeg's parser depth.
    require(bool(terms),'Empty frame selection')
    if len(terms)==1:return terms[0]
    middle=len(terms)//2
    return '('+sum_expression(terms[:middle])+'+'+sum_expression(terms[middle:])+')'

def check_final(script,meta,cues,report,source_pcm):
    require(meta['mode'] in ['rendered-awaiting-independent-sentence-review','product_video_and_subtitles_acceptance_passed'],'Producer has not rendered final media')
    canonical=load(OUTPUTS/'DriveLab-参赛演示-制作与格式验收.json')
    for key in ['version','scriptSha256','outputSha256','sentenceSubtitleChecks']:
        require(canonical[key]==meta[key],'Canonical/cache metadata disagreement: '+key)
    video=OUTPUTS/meta['output'];digest=sha(video);require(digest==meta['outputSha256'],'Final MP4 hash differs from metadata')
    directory=QA/('final-'+datetime.now().strftime('%Y%m%d-%H%M%S'));directory.mkdir(parents=True)
    requests={0:None,report['totalFrames']-1:None}
    for index,cue in enumerate(cues):
        for frame,current in [(cue['startFrame']-1,None),(cue['startFrame'],index),(cue['endFrame']-1,index),(cue['endFrame'],None)]:
            require(frame not in requests or requests[frame]==current,'Conflicting expected captions at same frame')
            requests[frame]=current
    frames=sorted(requests);expression=sum_expression([f'eq(n,{f})' for f in frames]+[f'gte(n,{report["totalFrames"]})'])
    log=run([FFMPEG,'-hide_banner','-loglevel','info','-y','-i',video,'-an','-vf',f"select='{expression}',showinfo,crop=1750:100:85:940",'-fps_mode','vfr',directory/'actual-%04d.png'],directory/'actual-extract.log')
    actual_files=sorted(directory.glob('actual-*.png'));require(len(actual_files)==len(frames),'Final video has missing or additional frames')
    pts=[float(v) for v in re.findall(r'\bn:\s*\d+\s+pts:\s*\d+\s+pts_time:([\d.]+)',log)]
    require(len(pts)==len(frames),'Could not verify actual MP4 frame PTS')
    require(all(abs(t-f/FPS)<0.0006 for t,f in zip(pts,frames)),'Final MP4 frame PTS drift')
    ass_header=(CACHE/script['scenes'][0]['id']/'subtitles.ass').read_text(encoding='utf-8').split('Dialogue:',1)[0]
    expected=ass_header+''.join(f'Dialogue: 0,{ass_clock(i*6)},{ass_clock((i+1)*6)},Default,,0,0,0,,{cue["text"]}\n' for i,cue in enumerate(cues))
    (directory/'expected.ass').write_text(expected,encoding='utf-8')
    fontdir=str((CACHE/'fonts').resolve()).replace('\\','/').replace(':','\\:')
    selection=sum_expression([f'eq(n,{i*6+2})' for i in range(len(cues))])
    run([FFMPEG,'-hide_banner','-loglevel','error','-y','-f','lavfi','-i',f'color=c=0x173147:s=1920x1080:r=24:d={len(cues)/4}','-vf',f"ass=filename=expected.ass:fontsdir='{fontdir}',select='{selection}',crop=1750:100:85:940",'-fps_mode','vfr',directory/'expected-%04d.png'],directory/'expected-render.log')
    references=sorted(directory.glob('expected-*.png'));require(len(references)==len(cues),'Expected-sentence render incomplete')
    masks=[white_mask(path) for path in references];checks=[]
    for frame,path,pt in zip(frames,actual_files,pts):
        actual=white_mask(path);n=white_count(actual);index=requests[frame]
        if index is None:require(n<=30,f'Previous subtitle remains in blank frame {frame}: {n} bright pixels');iou=None
        else:
            reference=masks[index];union=white_count(ImageChops.logical_or(actual,reference));intersection=white_count(ImageChops.logical_and(actual,reference));iou=intersection/union if union else 0
            require(iou>=.82,f'Frame {frame} does not render the exact expected sentence {index+1}: glyph-mask IoU {iou:.3f}')
        checks.append({'frame':frame,'actualPtsSeconds':pt,'sentenceIndex':index+1 if index is not None else None,'expectedText':cues[index]['text'] if index is not None else '', 'brightPixels':n,'expectedGlyphMaskIoU':iou,'image':str(path.relative_to(CACHE))})
    files_by_frame=dict(zip(frames,actual_files));contacts=[]
    font=ImageFont.truetype(str(ROOT/'public/fonts/NotoSansSC-Regular.ttf'),24)
    def contact(previous,following,name):
        selected=[previous['endFrame']-1,previous['endFrame'],following['startFrame']-1,following['startFrame']]
        sheet=Image.new('RGB',(1750,600),'white');draw=ImageDraw.Draw(sheet)
        for row,frame in enumerate(selected):
            index=requests[frame];label=f'frame {frame} / {frame/FPS:.4f}s / '+(f'句 {index+1}: '+cues[index]['text'] if index is not None else '应无字幕')
            draw.text((12,row*150+8),label,font=font,fill='#173147');sheet.paste(Image.open(files_by_frame[frame]),(0,row*150+43))
        path=directory/(name+'.png');sheet.save(path);contacts.append(str(path.relative_to(CACHE)))
    for sid in [s['id'] for s in script['scenes']]:
        local=[c for c in cues if c['scene']==sid]
        contact(local[0],local[1],'within-scene-'+sid)
    for previous,following in zip(cues,cues[1:]):
        if previous['scene']!=following['scene']:contact(previous,following,'scene-join-'+previous['scene']+'-'+following['scene'])
    # A single MP4 AAC encode must stay aligned with the verified assembled PCM.
    run([FFMPEG,'-hide_banner','-loglevel','error','-y','-i',video,'-map','0:a:0','-ac','1','-ar',SR,'-c:a','pcm_s16le',directory/'decoded-final.wav'],directory/'audio-decode.log')
    decoded,decoded_n=pcm(directory/'decoded-final.wav');original=array.array('h');original.frombytes(source_pcm);encoded=array.array('h');encoded.frombytes(decoded)
    correlations=[]
    for cue in cues:
        a=cue['startFrame']*SPF;b=a+cue['pcmSamples'];x=original[a:b:8];y=encoded[a:b:8]
        require(len(x)==len(y),'Final AAC truncated a sentence')
        xx=sum(v*v for v in x);yy=sum(v*v for v in y);corr=sum(u*v for u,v in zip(x,y))/math.sqrt(xx*yy) if xx and yy else 0
        require(corr>=.93,'Final AAC is not aligned with sentence PCM: '+str(cue['cueIndex']));correlations.append(corr)
    require(sha(video)==digest,'Producer changed MP4 during independent audit')
    final={**report,'stage':'final-mp4-sentence-audit-passed','notFinalVideoAcceptance':False,'outputSha256':digest,'output':str(video),'decodedBoundaryFrames':len(checks),'blankFramesVerified':sum(c['sentenceIndex'] is None for c in checks),'captionFramesComparedToCanonicalGlyphs':sum(c['sentenceIndex'] is not None for c in checks),'minCaptionGlyphMaskIoU':min(c['expectedGlyphMaskIoU'] for c in checks if c['expectedGlyphMaskIoU'] is not None),'allSentenceAndSceneTransitionsIncluded':True,'maxSelectedFramePtsErrorSeconds':max(abs(t-f/FPS) for t,f in zip(pts,frames)),'decodedFinalAudioSamples':decoded_n,'minimumPerSentencePcmAacCorrelation':min(correlations),'frameChecks':checks,'boundaryContactSheets':contacts,'limitations':['No human listening/pronunciation, ASR transcript, screenshot-claim or final whole-frame editorial audit claimed.','Glyph comparison verifies canonical caption text; it does not establish the truth of the narration.']}
    save(QA/'final-audit.json',final)
    return final

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--final',action='store_true');args=parser.parse_args()
    script,meta,cues,report,source=check_prepared()
    if args.final:report=check_final(script,meta,cues,report,source)
    print(json.dumps({k:report[k] for k in ['stage','sentenceCount','sceneCount','totalFrames','durationSeconds','notFinalVideoAcceptance']},ensure_ascii=False))
