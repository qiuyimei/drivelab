"""Product demo V2: one complete sentence, one TTS clip, one subtitle.
All timings use 24000 Hz mono PCM / 24 fps / 1000 samples per frame.
No V1 paragraph cache or WordBoundary text concatenation is used.
"""
from __future__ import annotations
import argparse, asyncio, hashlib, json, re, shutil, subprocess, wave
from pathlib import Path
from datetime import datetime, timezone, timedelta
import edge_tts, imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT=Path(__file__).resolve().parent.parent
OUTPUTS=ROOT.parent.parent/'outputs'
CACHE=ROOT/'.sites-runtime/competition-video-v2'
SCRIPT=ROOT/'docs/competition/video-script.json'
SHOTS=ROOT/'docs/competition/screenshots'
DATA=CACHE/'product-demo.json'
LIVE=ROOT/'docs/competition/LIVE-ENGINE-112-QA.json'
FONT=ROOT/'public/fonts/NotoSansSC-Regular.ttf'
FFMPEG=imageio_ffmpeg.get_ffmpeg_exe()
ZONE=timezone(timedelta(hours=8))
METHOD='complete-sentence-pcm-frames-v2'
FPS,SR,SPF=24,24000,1000
GAP_FRAMES,PREFIX_FRAMES,TAIL_FRAMES=6,4,8
W,H=1920,1080
NAVY,ORANGE,TEAL,BG,MUTED='#173147','#ee6a36','#238e83','#f1f5f8','#607489'
NAMES=['DriveLab-参赛演示.mp4','DriveLab-参赛演示.srt','DriveLab-参赛演示-逐字稿.txt','DriveLab-参赛演示-制作与格式验收.json']

def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(args,log=None,check=True,cwd=None):
    r=subprocess.run([str(x) for x in args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
    if log:log.write_text(r.stdout+'\n'+r.stderr,encoding='utf-8')
    if check and r.returncode:raise RuntimeError(f'Command failed; inspect {log}: '+r.stderr[-700:])
    return r
def probe(path):
    r=run([FFMPEG,'-hide_banner','-i',path.name],cwd=path.parent,check=False)
    m=re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)',r.stderr)
    if not m:raise RuntimeError('Missing media duration: '+path.name)
    wh=re.search(r'Video: [^\n]*?\b(\d{3,5})x(\d{3,5})\b',r.stderr)
    return {'durationSeconds':int(m[1])*3600+int(m[2])*60+float(m[3]),'hasAudio':bool(re.search(r'Stream[^\n]*Audio:',r.stderr)),'width':int(wh[1]) if wh else None,'height':int(wh[2]) if wh else None,'inspection':r.stderr}
def read_pcm(path):
    with wave.open(str(path),'rb') as f:
        assert (f.getnchannels(),f.getsampwidth(),f.getframerate())==(1,2,SR)
        n=f.getnframes();return f.readframes(n),n
def write_pcm(path,parts):
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(SR)
        for part in parts:f.writeframes(part)
def backup_v1():
    target=OUTPUTS/'archive/demo-v1-20261117';target.mkdir(parents=True,exist_ok=True)
    for name in NAMES:
        source=OUTPUTS/name
        if source.exists() and not (target/name).exists():shutil.copyfile(source,target/name)

def clock(frame,scale):
    units=frame*scale//FPS;hour,units=divmod(units,3600*scale);minute,units=divmod(units,60*scale);second,part=divmod(units,scale)
    return f'{hour:02}:{minute:02}:{second:02},{part:03}' if scale==1000 else f'{hour}:{minute:02}:{second:02}.{part:02}'
def normalize(text):return ''.join(re.findall(r'\w',text)).casefold()
async def sentence_audio(scene,index,text,voice,rate,proxy,semaphore):
    directory=CACHE/scene;directory.mkdir(parents=True,exist_ok=True)
    stem=f'sentence-{index+1:03}';mp3=directory/(stem+'.mp3');pcm=directory/(stem+'.wav');meta=directory/(stem+'.json')
    signature=hashlib.sha256((METHOD+'|'+voice+'|'+rate+'|'+text).encode()).hexdigest()
    if meta.exists() and pcm.exists():
        saved=json.loads(meta.read_text(encoding='utf-8'))
        if saved.get('signature')==signature and saved.get('text')==text:
            _,n=read_pcm(pcm)
            if n==saved['pcmSamples']:return saved
    async with semaphore:
        for attempt in range(2):
            try:
                words=[];speaker=edge_tts.Communicate(text,voice,rate=rate,boundary='WordBoundary',proxy=proxy,receive_timeout=90)
                partial=directory/(stem+'.mp3.part')
                with partial.open('wb') as f:
                    async for chunk in speaker.stream():
                        if chunk['type']=='audio':f.write(chunk['data'])
                        elif chunk['type']=='WordBoundary':words.append(chunk['text'])
                partial.replace(mp3)
                if normalize(text)!=normalize(''.join(words)):raise RuntimeError('TTS returned words differing from this sentence')
                run([FFMPEG,'-hide_banner','-loglevel','error','-y','-i',mp3.name,'-ac','1','-ar',str(SR),'-c:a','pcm_s16le',pcm.name],cwd=directory)
                _,n=read_pcm(pcm)
                saved={'method':METHOD,'signature':signature,'text':text,'ttsInput':text,'voice':voice,'rate':rate,'pcmSamples':n,'actualAudioSeconds':n/SR,'wavSha256':sha(pcm),'mp3Sha256':sha(mp3),'timingWordsDiagnosticMatched':True}
                write_json(meta,saved);print(f'SENTENCE {scene}/{index+1:02} {n/SR:.2f}s',flush=True);return saved
            except Exception:
                if attempt:raise
                await asyncio.sleep(.8)

def font(size):return ImageFont.truetype(str(FONT),size)
def lines(text,size,width):
    f=font(size);result=[];line=''
    for char in text:
        if line and f.getlength(line+char)>width:result.append(line);line=char
        else:line+=char
    if line:result.append(line)
    return result
def text_block(draw,x,y,text,size=31,width=400,fill=NAVY):
    for line in lines(text,size,width):
        # Noto Sans SC lacks subscript zero; draw the same mathematical glyph
        # as a smaller lowered zero, preserving the exact source quotation.
        cursor=x
        for part in re.split('(₀)',line):
            if part=='₀':
                selected=font(round(size*.65));draw.text((cursor,y+round(size*.5)),'0',font=selected,fill=fill);cursor+=selected.getlength('0')
            else:
                selected=font(size);draw.text((cursor,y),part,font=selected,fill=fill);cursor+=selected.getlength(part)
        y+=size+10
    return y
def screenshot(scene,variant):
    sid=scene['id']
    if sid in ['05','06'] or (sid=='04' and variant==1):name='public-log.jpg'
    elif sid=='08':name='final-ai.jpg'
    elif sid=='11':name='final-report.jpg'
    else:name='lane-workbench.jpg'
    path=SHOTS/name
    if not path.exists():raise RuntimeError('Missing actual screenshot: '+name)
    im=Image.open(path).convert('RGB');w,h=im.size
    if name=='lane-workbench.jpg' and variant:im=im.crop((220,90 if variant==1 else 330,w-18,min(h,790 if variant==1 else h)))
    elif name=='public-log.jpg' and variant:im=im.crop((240,385 if sid=='04' or variant==2 else 140,w-20,h-10))
    elif name=='final-ai.jpg':im=im.crop((round(w*.45),round(h*.50),round(w*.985),round(h*.99)))
    elif name=='final-report.jpg' and variant==1:im=im.crop((round(w*.05),round(h*.25),round(w*.96),round(h*.87)))
    elif name=='final-report.jpg' and variant==2:im=im.crop((round(w*.05),round(h*.25),round(w*.96),round(h*.54)))
    return im
def flow(draw,steps,title):
    draw.text((100,215),title,font=font(39),fill=NAVY)
    for i,(heading,body) in enumerate(steps):
        x=105+(i%2)*610;y=335+(i//2)*220
        draw.rounded_rectangle((x,y,x+555,y+172),radius=18,fill='#edf4f7')
        draw.text((x+28,y+25),heading,font=font(34),fill=TEAL)
        text_block(draw,x+28,y+85,body,27,500,NAVY)
def product_card(scene,index,variant):
    im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
    d.rectangle((0,0,W,12),fill=ORANGE)
    d.text((56,34),'DriveLab',font=font(40),fill=NAVY)
    d.text((300,47),'智能驾驶工况仿真与辅助分析',font=font(25),fill=MUTED)
    d.text((1730,43),f'{index+1:02} / 12',font=font(28),fill=ORANGE)
    d.text((56,100),scene['title'],font=font(36),fill=NAVY)
    d.rounded_rectangle((56,150,1864,156),radius=3,fill='#dbe4ec');d.rounded_rectangle((56,150,56+1808*(index+1)/12,156),radius=3,fill=ORANGE)
    box=(56,180,1372,884);d.rounded_rectangle(box,radius=18,fill='white',outline='#d9e2eb',width=2)
    sid=scene['id']
    if sid=='02':
        d.text((105,210),'五类常见工况，一键载入参数',font=font(38),fill=NAVY)
        templates=[('高速跟驰','车速、制动与安全间距'),('弯道稳态','侧向加速度与转向需求'),('动态换道','横向位移与横摆响应'),('紧急避障','制动与侧向运动需求'),('城市路口','静态目标前的停车分析')]
        for j,(heading,body) in enumerate(templates):
            y=300+j*101
            active=(variant==0 and j<2) or (variant==1 and j in [2,3]) or (variant==2 and j==4)
            d.rounded_rectangle((105,y,1320,y+83),radius=13,fill='#dceeea' if active else '#edf4f7')
            d.text((130,y+18),f'{j+1:02}  '+heading,font=font(32),fill=TEAL if active else NAVY)
            d.text((520,y+23),body,font=font(28),fill=NAVY)
    elif sid=='07':
        flow(d,[('导入资料','PDF、DOCX、文本与Markdown'),('建立索引','按段落整理专业知识'),('匹配问题','联系当前工况与分析问题'),('保留依据','资料标题、段落与可用页码')],'让已有专业资料参与问题分析')
    elif sid=='08' and variant==2:
        entry=json.loads(LIVE.read_text(encoding='utf-8'))['highway']['structured']['observations'][0]
        d.text((105,215),'分析结论与引用',font=font(39),fill=NAVY)
        d.rounded_rectangle((105,290,380,345),radius=12,fill='#dceeea');d.text((128,298),'实际回答节选',font=font(30),fill=TEAL)
        end=text_block(d,105,388,entry['text'],35,1180,NAVY)
        d.text((105,end+42),'计算证据',font=font(29),fill=TEAL)
        end=text_block(d,105,end+92,' / '.join(entry['factIds']),27,1160,NAVY)
        d.text((105,end+30),'资料引用',font=font(29),fill=TEAL)
        text_block(d,105,end+80,' / '.join(entry['sourceIds']),30,1160,NAVY)
    elif sid=='08' and variant==1:
        flow(d,[('读取计算','了解当前工况与关键指标'),('比较日志','查看误差、缺失与覆盖范围'),('检索知识','寻找相关工程资料段落'),('重算候选','比较参数改变后的结果')],'围绕当前问题，按需连接工具与资料')
    elif sid=='09':
        data=json.loads(DATA.read_text(encoding='utf-8'))['productComparisons']['highway']
        if variant<2:
            gap=variant==1;field='increasedGap' if gap else 'lowerSpeed'
            d.text((105,215),'增加初始车距，观察跟驰结果' if gap else '比较车速改变后的停车距离',font=font(39),fill=NAVY)
            for j,(label,item) in enumerate([('当前计算基线',data['baseline']),('加距候选方案' if gap else '降速候选方案',data[field])]):
                x=110+j*610;d.rounded_rectangle((x,350,x+550,710),radius=18,fill='#edf4f7')
                condition=f'初始车距 {item["config"]["distance"]:g} m' if gap else f'初始车速 {item["config"]["speed"]:g} km/h'
                value=item['predictedMinimumFullBrakingGapM'] if gap else item['stoppingDistanceM']
                d.text((x+30,380),label,font=font(30),fill=MUTED);d.text((x+30,435),condition,font=font(31),fill=NAVY)
                d.text((x+30,510),f'{value:.2f} m',font=font(48),fill=TEAL if j==0 else ORANGE)
                d.text((x+30,588),'预测全程最小间距' if gap else '理论停车距离',font=font(27),fill=MUTED)
                d.text((x+30,647),'初始车速 100 km/h' if gap else '初始车距 80 m',font=font(26),fill=NAVY)
            d.text((110,759),'其余条件相同，候选与当前基线分别计算。',font=font(31),fill=NAVY)
        else:
            flow(d,[('查看候选','阅读参数变化与计算证据'),('对照基线','判断关键指标怎样变化'),('确认载入','由用户选择需要的方案'),('再次运行','用新参数继续下一轮比较')],'把可比较的建议带回工作台')
    elif sid=='04' and variant==2:
        data=json.loads(DATA.read_text(encoding='utf-8'))['productComparisons']['curve'];d.text((105,215),'改变弯道车速，观察侧向需求',font=font(38),fill=NAVY)
        for j,(label,item) in enumerate([('当前车速',data['baseline']),('降低车速',data['lowerSpeed'])]):
            y=360+j*210;value=item['maxLat'];d.text((110,y),f'{label} {item["config"]["speed"]:g} km/h',font=font(30),fill=NAVY);d.rounded_rectangle((110,y+65,110+value*800,y+115),radius=10,fill=TEAL if j==0 else ORANGE);d.text((1000,y+48),f'{value:.2f} m/s²',font=font(35),fill=NAVY)
    elif sid=='10':
        flow(d,[('保存工况','参数、日志配置与容差'),('恢复记录','继续查看已有工作条件'),('更新分析','条件变化后重新生成结论'),('比较方案','为不同方案保留独立记录')],'让一次分析能够继续使用')
    elif sid=='12' and variant>0:
        flow(d,[('设计工况','从模板和参数开始'),('连接数据','把采集日志带入分析'),('理解结果','联系计算证据与专业知识'),('交流方案','保存记录并导出报告')],'从一组参数，形成连贯的分析流程')
    else:
        shot=screenshot(scene,variant);fitted=ImageOps.contain(shot,(1296,684),Image.Resampling.LANCZOS);im.paste(fitted,(box[0]+(1316-fitted.width)//2,box[1]+(704-fitted.height)//2))
    d.rounded_rectangle((1410,180,1864,884),radius=18,fill=NAVY);text_block(d,1443,215,scene['chapter'],27,384,'#adc4d6')
    for j,point in enumerate(scene['points']):
        y=353+j*156
        if j==variant:d.rounded_rectangle((1430,y-20,1843,y+121),radius=13,fill='#2a4a60')
        d.text((1450,y),f'{j+1:02}',font=font(23),fill='#ff9c72');text_block(d,1500,y-2,point,31,320,'white')
    d.rounded_rectangle((56,930,1864,1044),radius=15,fill=NAVY)
    p=CACHE/sid/f'card-{variant}.png';im.save(p);return p

ASS_HEADER='''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Sans SC,42,&H00FFFFFF,&H00FFFFFF,&H00173147,&H00173147,0,0,0,0,100,100,0,0,1,1,0,2,95,95,53,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
def assemble_scene(scene,records):
    sid=scene['id'];directory=CACHE/sid;parts=[b'\0'*(PREFIX_FRAMES*SPF*2)];cursor=PREFIX_FRAMES;cues=[]
    for i,(sentence,record) in enumerate(zip(scene['sentences'],records)):
        audio,n=read_pcm(directory/f'sentence-{i+1:03}.wav');frames=(n+SPF-1)//SPF;pad=frames*SPF-n
        cues.append({'scene':sid,'sentenceIndex':i+1,'text':sentence,'ttsInput':record['ttsInput'],'audioFile':f'{sid}/sentence-{i+1:03}.wav','pcmSamples':n,'paddedSamples':frames*SPF,'actualAudioSeconds':n/SR,'paddingSamples':pad,'startFrame':cursor,'endFrame':cursor+frames,'startSeconds':cursor/FPS,'endSeconds':(cursor+frames)/FPS,'wavSha256':record['wavSha256']})
        parts.extend([audio,b'\0'*(pad*2)]);cursor+=frames
        if i<len(records)-1:parts.append(b'\0'*(GAP_FRAMES*SPF*2));cursor+=GAP_FRAMES
    parts.append(b'\0'*(TAIL_FRAMES*SPF*2));cursor+=TAIL_FRAMES
    write_pcm(directory/'scene.wav',parts)
    assert read_pcm(directory/'scene.wav')[1]==cursor*SPF
    rows=[ASS_HEADER]
    for c in cues:rows.append(f'Dialogue: 0,{clock(c["startFrame"],100)},{clock(c["endFrame"],100)},Default,,0,0,0,,{c["text"]}\n')
    (directory/'subtitles.ass').write_text(''.join(rows),encoding='utf-8');write_json(directory/'sentence-timeline.json',cues)
    return {'id':sid,'frames':cursor,'cues':cues}
def encode(scene,timeline):
    directory=CACHE/scene['id'];target=directory/'scene.mp4';duration=timeline['frames']/FPS
    segments=scene['visualSegments'];starts=[0]+[timeline['cues'][s['startSentence']-1]['startFrame'] for s in segments[1:]];ends=starts[1:]+[timeline['frames']]
    assert len(segments)==3 and all(a<b for a,b in zip(starts,ends))
    signature=hashlib.sha256((METHOD+json.dumps(segments)+str(starts)+str(timeline['frames'])+sha(directory/'subtitles.ass')+''.join(sha(directory/f'card-{i}.png') for i in range(3))).encode()).hexdigest();meta=directory/'encode.json'
    if target.exists() and meta.exists() and json.loads(meta.read_text())['signature']==signature:return
    listing=['ffconcat version 1.0']
    for segment,start,end in zip(segments,starts,ends):listing.extend([f"file 'card-{segment['variant']}.png'",f'option framerate {FPS}',f'duration {(end-start)/FPS:.8f}'])
    listing.extend(["file 'card-2.png'",f'option framerate {FPS}']);(directory/'images.ffconcat').write_text('\n'.join(listing)+'\n',encoding='utf-8')
    run([FFMPEG,'-hide_banner','-loglevel','warning','-y','-f','concat','-safe','0','-i','images.ffconcat','-vf',f'fps={FPS},ass=filename=subtitles.ass:fontsdir=../fonts','-frames:v',timeline['frames'],'-r',FPS,'-an','-c:v','libx264','-threads','3','-preset','veryfast','-tune','stillimage','-crf','20','-pix_fmt','yuv420p',target.name],cwd=directory,log=directory/'encode.log')
    actual=probe(target);assert(actual['width'],actual['height'])==(W,H)
    write_json(meta,{'signature':signature,'sha256':sha(target),'frames':timeline['frames'],'visualSegments':[{**s,'startFrame':a,'endFrame':b} for s,a,b in zip(segments,starts,ends)]});print('ENCODE '+scene['id']+' complete',flush=True)

def verify_boundary_frames(timelines):
    all_checks=[];contacts=[]
    for timeline in timelines:
        directory=CACHE/timeline['id'];cues=timeline['cues'];requests=[]
        for previous,following in zip(cues,cues[1:]):
            requests.extend([(previous['endFrame']-1,True,previous['text'],'前句末帧'),(previous['endFrame'],False,'','前句后首个空帧'),(following['startFrame']-1,False,'','后句前最后空帧'),(following['startFrame'],True,following['text'],'后句首帧')])
        frames=sorted(set(r[0] for r in requests));check_dir=directory/'boundary-frames';check_dir.mkdir(exist_ok=True)
        expression='+'.join(f'eq(n,{frame})' for frame in frames)
        run([FFMPEG,'-hide_banner','-loglevel','error','-y','-i','scene.mp4','-vf',f"select='{expression}',crop=1750:100:85:940",'-fps_mode','vfr',str(check_dir/'frame-%04d.png')],cwd=directory)
        files={frame:check_dir/f'frame-{i+1:04}.png' for i,frame in enumerate(frames)}
        for frame,present,expected,label in requests:
            crop=Image.open(files[frame]).convert('RGB');bright=sum(1 for r,g,b in crop.getdata() if r>165 and g>165 and b>165)
            if present and bright<200:raise RuntimeError(f'Missing full sentence subtitle {timeline["id"]} frame {frame}')
            if not present and bright>30:raise RuntimeError(f'Subtitle not cleared {timeline["id"]} frame {frame}')
            all_checks.append({'scene':timeline['id'],'frame':frame,'expectedText':expected,'expectedVisible':present,'brightPixels':bright,'file':str(files[frame].relative_to(CACHE))})
        contact=Image.new('RGB',(1750,640),'white');d=ImageDraw.Draw(contact)
        for i,(frame,present,expected,label) in enumerate(requests[:4]):
            d.text((20,i*160+10),label+'：'+(expected or '（应无字幕）'),font=font(25),fill=NAVY);contact.paste(Image.open(files[frame]),(0,i*160+57))
        contact.save(directory/'boundary-contact.jpg',quality=95);contacts.append(str((directory/'boundary-contact.jpg').relative_to(CACHE)))
    write_json(CACHE/'sentence-boundary-render-checks.json',all_checks)
    return {'sampledScenes':len(timelines),'sampledCaptionTimes':len(all_checks),'changingSubtitlePixels':True,'allSentenceBoundariesChecked':sum(len(t['cues'])-1 for t in timelines),'blankGapFramesPassed':True,'contacts':contacts}

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--render',action='store_true');parser.add_argument('--proxy',default='http://127.0.0.1:7897');args=parser.parse_args()
    if not(args.prepare or args.render):parser.error('Use --prepare or --render')
    CACHE.mkdir(parents=True,exist_ok=True);OUTPUTS.mkdir(parents=True,exist_ok=True);backup_v1()
    (CACHE/'fonts').mkdir(exist_ok=True);shutil.copyfile(FONT,CACHE/'fonts'/FONT.name)
    script=json.loads(SCRIPT.read_text(encoding='utf-8'));scenes=script['scenes'];voice=script['voice']['name'];rate=script['voice']['rate'];sentences=[s for scene in scenes for s in scene['sentences']]
    for name,digest in json.loads(DATA.read_text(encoding='utf-8'))['sourceSha256'].items():
        if sha(ROOT/name)!=digest:raise RuntimeError('Product demonstration data is stale; rebuild with node scripts/product-demo.mjs')
    for text in sentences:
        if len(re.findall(r'[。！？]',text))!=1 or text[-1] not in '。！？':raise RuntimeError('Each subtitle must be exactly one complete sentence: '+text)
    sem=asyncio.Semaphore(2);jobs=[sentence_audio(scene['id'],i,text,voice,rate,args.proxy,sem) for scene in scenes for i,text in enumerate(scene['sentences'])]
    records=await asyncio.gather(*jobs);timelines=[];index=0
    for scene in scenes:
        count=len(scene['sentences']);timelines.append(assemble_scene(scene,records[index:index+count]));index+=count
    total_frames=sum(t['frames'] for t in timelines);total=total_frames/FPS
    if not 300<=total<=480:raise RuntimeError(f'Natural product narration {total:.2f}s is outside 300–480 seconds; expand/revise content or rate, never pad blank minutes.')
    offset=0;global_cues=[];transcript=[];audio_parts=[]
    for scene,timeline in zip(scenes,timelines):
        for variant in range(3):product_card(scene,scenes.index(scene),variant)
        transcript.extend([scene['id']+'. '+scene['title'],*scene['sentences'],''])
        for cue in timeline['cues']:
            c=dict(cue);c['startFrame']+=offset;c['endFrame']+=offset;c['startSeconds']=c['startFrame']/FPS;c['endSeconds']=c['endFrame']/FPS;c['cueIndex']=len(global_cues)+1;global_cues.append(c)
        audio_parts.append(read_pcm(CACHE/scene['id']/'scene.wav')[0]);offset+=timeline['frames']
    assert [c['text'] for c in global_cues]==sentences
    assert all(a['endFrame']<b['startFrame'] for a,b in zip(global_cues,global_cues[1:]))
    assert all(a['endFrame']*100//FPS < b['startFrame']*100//FPS for a,b in zip(global_cues,global_cues[1:]))
    assert all(a['endFrame']*1000//FPS < b['startFrame']*1000//FPS for a,b in zip(global_cues,global_cues[1:]))
    write_pcm(CACHE/'narration.wav',audio_parts);assert read_pcm(CACHE/'narration.wav')[1]==total_frames*SPF
    srt='\n\n'.join(f'{i+1}\n{clock(c["startFrame"],1000)} --> {clock(c["endFrame"],1000)}\n{c["text"]}' for i,c in enumerate(global_cues))+'\n'
    (OUTPUTS/NAMES[1]).write_text(srt,encoding='utf-8');(OUTPUTS/NAMES[2]).write_text('DriveLab 产品演示逐字稿\n\n'+'\n'.join(transcript),encoding='utf-8')
    parsed=[block.split('\n',2)[2] for block in srt.strip().split('\n\n')];assert parsed==sentences
    checks={'method':METHOD,'schemaVersion':2,'sentenceCount':len(sentences),'oneToOne':True,'textExactMatch':True,'noCrossSentenceConcatenation':True,'noTimeOverlap':True,'quantizedNoTimeOverlap':True,'pcmSampleRate':SR,'samplesPerVideoFrame':SPF,'gapFrames':GAP_FRAMES,'perSentence':global_cues}
    metadata={'version':'product-demo-v2','preparedAt':datetime.now(ZONE).isoformat(),'mode':'prepared','productionMethodInternal':script['productionMethodInternal'],'scriptSha256':sha(SCRIPT),'voice':voice,'rate':rate,'plannedDurationSeconds':total,'resolution':[W,H],'fps':FPS,'sentenceSubtitleChecks':checks,'sourceScreenshotSha256':{p.name:sha(p) for p in SHOTS.glob('*.jpg')},'productDataSha256':sha(DATA),'liveModelQASha256':sha(LIVE),'narrationAudioEncoding':'Per-sentence MP3 decoded to integer PCM samples; all scenes joined as PCM; a single final AAC encode.'}
    write_json(CACHE/'video-metadata.json',metadata);write_json(CACHE/'timeline.json',timelines)
    print(f'PREPARED {len(sentences)} complete sentences; {total:.2f}s',flush=True)
    if not args.render:return
    for scene,timeline in zip(scenes,timelines):encode(scene,timeline)
    concat=CACHE/'clips.ffconcat';concat.write_text('ffconcat version 1.0\n'+'\n'.join(f"file '{s['id']}/scene.mp4'" for s in scenes)+'\n',encoding='utf-8')
    video=OUTPUTS/NAMES[0]
    run([FFMPEG,'-hide_banner','-loglevel','warning','-y','-f','concat','-safe','0','-i',concat,'-i',CACHE/'narration.wav','-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','96k','-ar',SR,'-ac','1','-t',f'{total:.8f}','-movflags','+faststart',video],log=CACHE/'final-encode.log')
    actual=probe(video);assert(actual['width'],actual['height'],actual['hasAudio'])==(W,H,True);assert 300<=actual['durationSeconds']<=480;assert abs(actual['durationSeconds']-total)<.15
    render_checks=verify_boundary_frames(timelines)
    checks['boundaryRenderChecks']={**render_checks,'detailFile':'.sites-runtime/competition-video-v2/sentence-boundary-render-checks.json'}
    decoded=run([FFMPEG,'-hide_banner','-loglevel','info','-xerror','-threads','3','-i',video.name,'-af','volumedetect','-f','null','NUL'],cwd=video.parent,log=CACHE/'full-decode.log')
    peak=re.search(r'max_volume: ([\-\d.]+) dB',decoded.stderr);mean=re.search(r'mean_volume: ([\-\d.]+) dB',decoded.stderr);assert peak and float(peak[1])<0
    metadata.update({'mode':'rendered-awaiting-independent-sentence-review','output':video.name,'outputSha256':sha(video),'fileSize':video.stat().st_size,'formatChecks':{k:actual[k] for k in ['durationSeconds','width','height','hasAudio']},'fullDecodeExitCode':decoded.returncode,'audioVolumeChecks':{'peakDb':float(peak[1]),'meanDb':float(mean[1]),'noDigitalPeakClipping':True},'subtitleRenderChecks':render_checks,'humanListeningAudit':'Not claimed; checks verify sentence source text, PCM timing, rendered boundaries and full media decode.'})
    write_json(CACHE/'video-metadata.json',metadata);write_json(OUTPUTS/NAMES[3],metadata)
    print('FINAL '+json.dumps(metadata['formatChecks'],ensure_ascii=False),flush=True)

if __name__=='__main__':asyncio.run(main())
