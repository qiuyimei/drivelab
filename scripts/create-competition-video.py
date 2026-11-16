"""Reproducible narrated presentation from actual screenshots and app outputs.

Run with the bundled Python and retained video-tool package directory on PYTHONPATH.
--prepare synthesizes/cache narration and produces draft cards, subtitles and script.
--render requires the final AI/report screenshots, validates source hashes, and encodes.
No browser automation, secrets, paid API, fabricated UI or member impersonation.
"""
from __future__ import annotations
import argparse, asyncio, hashlib, html, json, math, re, shutil, subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

import edge_tts
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT.parent.parent
CACHE = ROOT / '.sites-runtime' / 'competition-video'
OUTPUTS = WORKSPACE / 'outputs'
SCRIPT = ROOT / 'docs/competition/video-script.json'
SHOTS = ROOT / 'docs/competition/screenshots'
ENGINEERING = ROOT / '.sites-runtime/engineering-demo.json'
LIVE_QA = ROOT / 'docs/competition/LIVE-ENGINE-112-QA.json'
FONT = ROOT / 'public/fonts/NotoSansSC-Regular.ttf'
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
VOICE, RATE = 'zh-CN-XiaoxiaoNeural', '+8%'
W, H, FPS = 1920, 1080, 24
NAVY, ORANGE, TEAL = '#173147', '#ee6a36', '#238e83'
BG, MUTED = '#f1f5f8', '#607489'
PREFIX, TAIL = .4, 1.1
CLIENT_ZONE = timezone(timedelta(hours=8))

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(command, log=None, check=True, cwd=None):
    result = subprocess.run([str(v) for v in command], cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if log:
        log.write_text(result.stdout+'\n'+result.stderr, encoding='utf-8')
    if check and result.returncode:
        raise RuntimeError(f'Command failed; inspect {log or "stderr"}: '+result.stderr[-700:])
    return result

def probe(path):
    path=Path(path)
    result = run([FFMPEG, '-hide_banner', '-i', path.name], check=False,cwd=path.parent)
    text = result.stderr
    match = re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)', text)
    if not match:
        raise RuntimeError(f'FFmpeg could not read duration: {path.name}')
    duration = int(match[1])*3600+int(match[2])*60+float(match[3])
    dimensions = re.search(r'Video: [^\n]*?\b(\d{3,5})x(\d{3,5})\b', text)
    return {'durationSeconds': duration, 'hasAudio': bool(re.search(r'Stream[^\n]*Audio:', text)),
            'width': int(dimensions[1]) if dimensions else None, 'height': int(dimensions[2]) if dimensions else None,
            'ffmpegInspection': text}

def font(size):
    return ImageFont.truetype(str(FONT), size)

def wrap(text, size, width):
    f = font(size)
    lines, current = [], ''
    for char in str(text):
        if char == '\n' or (current and f.getlength(current+char)>width):
            lines.append(current); current = '' if char=='\n' else char
        else:
            current += char
    if current: lines.append(current)
    return lines

def text_block(draw, xy, text, size=30, width=400, fill=NAVY, spacing=10):
    x,y = xy
    for line in wrap(text, size, width):
        draw.text((x,y),line,font=font(size),fill=fill)
        y += size+spacing
    return y

def srt_time(seconds):
    ms = max(0,round(seconds*1000)); h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); s,ms=divmod(ms,1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

def ass_time(seconds):
    cs=max(0,round(seconds*100)); h,cs=divmod(cs,360000); m,cs=divmod(cs,6000); s,cs=divmod(cs,100)
    return f'{h}:{m:02}:{s:02}.{cs:02}'

def make_cues(events):
    cues, words, length = [], [], 0
    def flush():
        nonlocal words,length
        if words:
            combined=''.join(html.unescape(w['text']) for w in words)
            cues.append({'start':words[0]['offset']/1e7,'end':(words[-1]['offset']+words[-1]['duration'])/1e7,'text':combined})
        words=[];length=0
    for event in events:
        text=html.unescape(event['text'])
        if not text.strip(): continue
        if words and (length+len(text)>28 or event['offset']/1e7-(words[-1]['offset']+words[-1]['duration'])/1e7>.6): flush()
        words.append(event);length+=len(text)
    flush()
    if not cues: raise RuntimeError('TTS returned no timing events; subtitles cannot be verified.')
    return cues

async def synthesize(scene, semaphore, proxy):
    directory=CACHE/scene['id'];directory.mkdir(parents=True,exist_ok=True)
    audio, metadata=directory/'narration.mp3',directory/'narration.json'
    signature=hashlib.sha256((VOICE+RATE+scene['narration']).encode()).hexdigest()
    if audio.exists() and metadata.exists():
        old=json.loads(metadata.read_text(encoding='utf-8'))
        if old.get('signature')==signature and audio.stat().st_size>1000:
            print(f'VOICE {scene["id"]} cached {old["durationSeconds"]:.2f}s',flush=True);return old
    async with semaphore:
        for attempt in range(2):
            events=[]
            try:
                speaker=edge_tts.Communicate(scene['narration'],VOICE,rate=RATE,boundary='WordBoundary',proxy=proxy,receive_timeout=90)
                temporary=directory/'narration.mp3.part'
                with temporary.open('wb') as output:
                    async for chunk in speaker.stream():
                        if chunk['type']=='audio': output.write(chunk['data'])
                        elif chunk['type']=='WordBoundary': events.append({k:chunk[k] for k in ['offset','duration','text']})
                temporary.replace(audio)
                duration=probe(audio)['durationSeconds']
                result={'signature':signature,'voice':VOICE,'rate':RATE,'durationSeconds':duration,'cues':make_cues(events),'wordEvents':events,'synthesizedAt':datetime.now(CLIENT_ZONE).isoformat()}
                write_json(metadata,result)
                print(f'VOICE {scene["id"]} ready {duration:.2f}s',flush=True);return result
            except Exception:
                if attempt: raise
                print(f'VOICE {scene["id"]} transient failure; one bounded retry',flush=True)

def engineering_data(required=False):
    if not ENGINEERING.exists():
        if required: raise RuntimeError('Missing engineering-demo.json')
        return None
    data=json.loads(ENGINEERING.read_text(encoding='utf-8'))
    for name,digest in data['sourceSha256'].items():
        if sha(ROOT/name)!=digest: raise RuntimeError(f'Engineering demonstration is stale: {name}; rebuild with node scripts/engineering-demo.mjs')
    spike=next(v for v in data['subgridSpike']['comparison'] if v['key']=='speed')
    if not (spike['max']==100 and spike['peakTime']==.05 and spike['pass'] is False and spike['mae']==0 and spike['rmse']==0):
        raise RuntimeError('Expected synthetic spike checks not satisfied')
    return data

def source_shot(scene, variant):
    sid=scene['id']
    if sid in ['08','09']: return SHOTS/'final-ai.jpg'
    if sid=='10' and variant>0: return SHOTS/'final-report.jpg'
    if sid=='02' and variant==2: return SHOTS/'mobile-menu.jpg'
    if sid in ['05','07']: return SHOTS/'public-log.jpg'
    if sid=='11': return SHOTS/'validation.jpg'
    return SHOTS/'lane-workbench.jpg'

def draw_shot(image, scene, variant, draft):
    path=source_shot(scene,variant)
    draw=ImageDraw.Draw(image)
    box=(56,172,1372,876)
    draw.rounded_rectangle(box,radius=18,fill='white',outline='#d9e2eb',width=2)
    if not path.exists():
        if not draft: raise RuntimeError(f'Missing final source screenshot: {path.name}')
        text_block(draw,(110,420),'素材待补：'+path.name,40,1120)
        draw.text((110,495),'制作预览，不能作为最终演示画面',font=font(28),fill=ORANGE)
        return '素材未就绪，仅制作预览'
    shot=Image.open(path).convert('RGB')
    if variant and path.name=='lane-workbench.jpg':
        shot=shot.crop((220,90 if variant==1 else 330,shot.width-18,min(shot.height,790 if variant==1 else 890)))
    elif variant and path.name in ['public-log.jpg','validation.jpg']:
        top=140 if variant==1 else 385
        shot=shot.crop((240,top,shot.width-20,min(shot.height,790 if variant==1 else shot.height)))
    elif path.name=='final-report.jpg' and variant==2:
        shot=shot.crop((round(shot.width*.05),round(shot.height*.1),round(shot.width*.96),round(shot.height*.54)))
    elif path.name=='final-ai.jpg' and scene['id']=='09':
        # Preserve the visible engine/request-count tag near the middle of this
        # actual screenshot. These are the default online two-request results.
        top=.14 if variant<2 else .40
        shot=shot.crop((round(shot.width*.45),round(shot.height*top),round(shot.width*.985),round(shot.height*.99)))
    fitted=ImageOps.contain(shot,(box[2]-box[0]-20,box[3]-box[1]-20),Image.Resampling.LANCZOS)
    image.paste(fitted,(box[0]+(box[2]-box[0]-fitted.width)//2,box[1]+(box[3]-box[1]-fitted.height)//2))
    old=path.name not in ['final-ai.jpg','final-report.jpg']
    date='2026-11-15（历史界面）' if old else datetime.fromtimestamp(path.stat().st_mtime,CLIENT_ZONE).strftime('%Y-%m-%d')
    example='（不同工况功能示例）' if scene['id']=='10' else '（线上默认问题：2次请求；工具案例另见验收记录）' if scene['id'] in ['08','09'] else ''
    return f'实际界面/报告截图：{date} {example} · '+('局部放大' if variant else '全景')+' · 剪辑展示，不代表实时操作耗时'

def plot(draw, box, lines, xlim, ylim, xlabel, ylabel):
    x0,y0,x1,y1=box
    draw.line((x0,y0,x0,y1,x1,y1),fill='#8395a8',width=2)
    for i in range(6):
        y=y1-(y1-y0)*i/5;draw.line((x0,y,x1,y),fill='#e6ecf1',width=1)
        draw.text((x0-60,y-12),f'{ylim[0]+(ylim[1]-ylim[0])*i/5:g}',font=font(19),fill=MUTED)
    for i in range(4):
        x=x0+(x1-x0)*i/3;draw.text((x-18,y1+12),f'{xlim[0]+(xlim[1]-xlim[0])*i/3:.2f}',font=font(19),fill=MUTED)
    def map_point(p): return (x0+(p[0]-xlim[0])/(xlim[1]-xlim[0])*(x1-x0),y1-(p[1]-ylim[0])/(ylim[1]-ylim[0])*(y1-y0))
    for points,color in lines:
        original=sorted(points)
        points=list(original)
        for boundary in xlim:
            for before,after in zip(original,original[1:]):
                if before[0]<boundary<after[0]:
                    ratio=(boundary-before[0])/(after[0]-before[0]);points.append((boundary,before[1]+ratio*(after[1]-before[1])));break
        points.sort()
        points=[map_point(p) for p in points if xlim[0]<=p[0]<=xlim[1]]
        if len(points)>1: draw.line(points,fill=color,width=5)
        for x,y in points:
            draw.ellipse((x-5,y-5,x+5,y+5),fill=color)
    draw.text((x0,y0-42),ylabel,font=font(24),fill=NAVY)
    draw.text((x1-120,y1+45),xlabel,font=font(23),fill=MUTED)

def draw_engineering(image, scene, variant, data):
    draw=ImageDraw.Draw(image);draw.rounded_rectangle((56,172,1372,876),radius=18,fill='white',outline='#d9e2eb',width=2)
    if scene['id']=='06':
        spike=data['subgridSpike'];comparison=next(x for x in spike['comparison'] if x['key']=='speed')
        draw.text((100,205),'0.05 s 合成尖峰回归夹具',font=font(38),fill=NAVY)
        draw.text((100,264),'基线 36 km/h；日志单点升至 136 km/h',font=font(27),fill=MUTED)
        log=[(r['time'],r['speed']) for r in spike['log']['rows']]
        simulation=[(r[0],r[1]) for r in spike['simulation']['curves']]
        plot(draw,(170,365,1290,655),[(simulation,'#3681bf'),(log,ORANGE)],(0,.15),(0,150),'时间 / s','车速 / km/h（局部时间窗）')
        draw.text((120,748),f'MAE {comparison["mae"]:.0f}    RMSE {comparison["rmse"]:.0f}    最大误差 {comparison["max"]:.0f} km/h',font=font(35),fill=NAVY)
        draw.text((120,806),'原网格平均仍为零；并集峰值触发超差',font=font(28),fill=ORANGE)
    elif variant==1:
        pair=data['lowAdhesionComparison'];b=pair['baseline']['metrics'];c=pair['lowAdhesion']['metrics']
        draw.text((100,205),'改变附着条件，重算同一跟驰工况',font=font(37),fill=NAVY)
        for index,(label,mu,m) in enumerate([('基线',pair['baselineMu'],b),('低附着',pair['changedMu'],c)]):
            y=330+index*205
            draw.text((110,y),f'{label}  μ = {mu}',font=font(31),fill=NAVY)
            draw.rounded_rectangle((110,y+65,110+m['stoppingDistanceM']*4,y+115),radius=10,fill=TEAL if index==0 else ORANGE)
            draw.text((1000,y+40),f'{m["stoppingDistanceM"]:.1f} m',font=font(43),fill=NAVY)
        draw.text((110,793),'理论停车距离；同一恒减速与水平路面假设',font=font(27),fill=MUTED)
    else:
        pair=data['acceptedLaneComparison']
        draw.text((100,205),'低速换道：输入被接受 ≠ 约束通过',font=font(36),fill=NAVY)
        draw.text((105,275),'0.1 km/h：拒绝计算，超出当前软件适用范围',font=font(30),fill=ORANGE)
        for x,label in [(110,'初始车速'),(420,'采样方向盘需求峰值'),(855,'模型判断')]:draw.text((x,347),label,font=font(24),fill=MUTED)
        for index,key in enumerate(['at5Kmh','at60Kmh']):
            item=pair[key];y=395+index*165
            draw.text((110,y),f'{item["config"]["speed"]:g} km/h',font=font(40),fill=NAVY)
            draw.text((420,y),f'{item["metrics"]["maximumSampledSteeringDeg"]:.2f}°',font=font(40),fill=ORANGE if index==0 else TEAL)
            draw.text((855,y+6),item['risk'],font=font(32),fill=ORANGE if index==0 else TEAL)
        text_block(draw,(110,773),'5 km/h 是当前软件模型的输入边界，不是法规或通用安全下限。',27,1160,fill=MUTED)
    return '由当前应用输出 JSON 重绘 · 简化模型 / 合成夹具，非实车实验 · '+data['generatedAt'][:10]

def draw_model_case(image,variant):
    if not LIVE_QA.exists():raise RuntimeError('Missing actual model-tool QA record')
    records=json.loads(LIVE_QA.read_text(encoding='utf-8'))
    draw=ImageDraw.Draw(image);draw.rounded_rectangle((56,172,1372,876),radius=18,fill='white',outline='#d9e2eb',width=2)
    if variant==1:
        record=records['highway']
        if record['mode']!='llm' or record['fallbackReason'] is not None:raise RuntimeError('Live highway tool record not passed')
        names=[t['label'].split('：',1)[1] for t in record['trace'] if t['label'].startswith('执行工具：')]
        if 'inspect_simulation' not in names or 'search_knowledge' not in names:raise RuntimeError('Expected real tools absent')
        draw.text((105,210),'独立真实联网工具案例',font=font(39),fill=NAVY)
        draw.text((105,275),f'本机正式分析引擎 · {record["evidence"]["engineVersion"]} · {record["modelCalls"]} 次请求',font=font(29),fill=MUTED)
        for index,(name,label) in enumerate([('inspect_simulation','读取本次服务端计算证据'),('search_knowledge','检索工程资料并返回段落依据')]):
            y=390+index*160
            draw.rounded_rectangle((105,y-15,1300,y+112),radius=16,fill='#f0f6f7')
            draw.text((135,y),name,font=font(36),fill=TEAL)
            draw.text((135,y+61),label+' · 已完成',font=font(27),fill=NAVY)
        text_block(draw,(110,760),'这是另一组真实请求的验收记录，不是线上默认问题截图中的步骤。',28,1160,fill=MUTED)
    else:
        record=records['candidate']
        if not record['passed'] or record['mode']!='llm':raise RuntimeError('Candidate live QA not passed')
        candidate=next(c for c in record['candidates'] if c['kind']=='tool')
        baseline=next(f for f in record['factRegistry'] if f['id']=='SIM_LATERAL')
        alternate=next(f for f in record['factRegistry'] if f['id']==candidate['id']+'__SIM_LATERAL')
        draw.text((105,210),'候选事实与基线独立编号',font=font(39),fill=NAVY)
        draw.text((105,280),'真实联网候选案例 · 合成固定偏差日志 · 非实车标定',font=font(27),fill=MUTED)
        for index,(label,fact) in enumerate([('当前基线侧向需求',baseline),(f'工具候选：{candidate["patch"]["speed"]:g} km/h',alternate)]):
            x=110+index*610
            draw.rounded_rectangle((x,380,x+550,680),radius=16,fill='#f1f6f8')
            draw.text((x+30,409),label,font=font(30),fill=MUTED)
            draw.text((x+30,465),f'{fact["value"]:.3f} m/s²',font=font(49),fill=NAVY)
            draw.text((x+30,548),'各自引用对应的计算事实',font=font(29),fill=NAVY)
            text_block(draw,(x+30,610),fact['id'],24,490,fill=TEAL if index==0 else ORANGE)
        draw.text((110,759),'候选未自动应用；原基线保持不变。',font=font(32),fill=NAVY)
        draw.text((110,816),'编号区分证据来源，文字语义仍需工程复核。',font=font(27),fill=MUTED)
    return '真实联网验收 JSON 重绘，非页面截图 · LIVE-ENGINE-112-QA.json · 与默认线上2次请求案例分开'

def make_card(scene,index,variant,data,draft):
    image=Image.new('RGB',(W,H),BG);draw=ImageDraw.Draw(image)
    draw.rectangle((0,0,W,12),fill=ORANGE)
    draw.text((56,34),'DriveLab',font=font(38),fill=NAVY)
    draw.text((300,46),'AI WEB · 实际界面剪辑 · AI合成解说',font=font(23),fill=MUTED)
    draw.text((1730,43),f'{index+1:02} / 12',font=font(28),fill=ORANGE)
    draw.text((56,94),scene['title'],font=font(35),fill=NAVY)
    draw.rounded_rectangle((56,146,1864,152),radius=3,fill='#dbe4ec')
    draw.rounded_rectangle((56,146,56+1808*(index+1)/12,152),radius=3,fill=ORANGE)
    if scene['id']=='08' and variant>0 and LIVE_QA.exists():
        source=draw_model_case(image,variant)
    elif data and (scene['id']=='06' or (scene['id']=='04' and variant>0)):
        source=draw_engineering(image,scene,variant,data)
    else: source=draw_shot(image,scene,variant,draft)
    draw.rounded_rectangle((1410,172,1864,876),radius=18,fill=NAVY)
    text_block(draw,(1443,203),scene['chapter'],25,384,fill='#adc4d6')
    for i,point in enumerate(scene['points']):
        y=335+i*143
        if i==variant: draw.rounded_rectangle((1430,y-16,1843,y+118),radius=13,fill='#2a4a60')
        draw.text((1450,y),str(i+1).zfill(2),font=font(22),fill='#ff9c72')
        text_block(draw,(1500,y-2),point,29,320,fill='white',spacing=10)
    text_block(draw,(1443,804),'前期辅助评估，需工程复核',20,380,fill='#adc4d6')
    draw.text((60,891),source,font=font(19),fill=MUTED)
    draw.rounded_rectangle((56,929,1864,1040),radius=15,fill=NAVY)
    draw.text((60,1052),'源码、数据口径与完整限制见最终技术文档和验收记录',font=font(17),fill=MUTED)
    target=CACHE/scene['id']/f'card-{variant}.png';image.save(target)
    return target

ASS_HEADER='''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Sans SC,35,&H00FFFFFF,&H00FFFFFF,&H00173147,&H00173147,0,0,0,0,100,100,0,0,1,1,0,2,110,110,60,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''

def write_ass(path,cues):
    rows=[ASS_HEADER]
    for cue in cues:
        text=cue['text'].replace('{','').replace('}','').replace('\\','')
        rows.append(f'Dialogue: 0,{ass_time(cue["start"]+PREFIX)},{ass_time(cue["end"]+PREFIX)},Default,,0,0,0,,{text}\n')
    path.write_text(''.join(rows),encoding='utf-8')

def encode_scene(scene,duration):
    directory=CACHE/scene['id'];target=directory/'scene.mp4'
    signature=hashlib.sha256(('|'.join(sha(directory/f'card-{i}.png') for i in range(3))+sha(directory/'narration.mp3')+sha(directory/'subtitles.ass')+f'{duration}:{FPS}:x264-veryfast-crf20-fps-before-ass-v2').encode()).hexdigest()
    encode_metadata=directory/'scene-encode.json'
    if target.exists() and encode_metadata.exists():
        previous=json.loads(encode_metadata.read_text(encoding='utf-8'))
        if previous.get('signature')==signature:
            actual=probe(target)
            if actual['width']==W and actual['height']==H and actual['hasAudio']:
                print(f'ENCODE {scene["id"]} cached {actual["durationSeconds"]:.2f}s',flush=True);return target
    inputs=directory/'images.ffconcat'
    lines=['ffconcat version 1.0']
    for i in range(3): lines += [f"file 'card-{i}.png'",f'duration {duration/3:.6f}']
    lines += ["file 'card-2.png'"]
    inputs.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    command=[FFMPEG,'-hide_banner','-loglevel','warning','-y','-f','concat','-safe','0','-i',inputs.name,'-i','narration.mp3',
             '-vf',f'fps={FPS},ass=filename=subtitles.ass:fontsdir=../fonts','-af',f'adelay=400,apad,atrim=duration={duration:.6f}',
             '-t',f'{duration:.6f}','-r',str(FPS),'-c:v','libx264','-threads','3','-preset','veryfast','-tune','stillimage','-crf','20','-pix_fmt','yuv420p',
             '-c:a','aac','-b:a','96k','-ar','24000','-ac','1','-movflags','+faststart',target.name]
    run(command,log=directory/'ffmpeg-encode.log',cwd=directory)
    actual=probe(target)
    if actual['width']!=W or actual['height']!=H or not actual['hasAudio']: raise RuntimeError('Invalid encoded scene format')
    write_json(encode_metadata,{'signature':signature,'durationSeconds':actual['durationSeconds'],'sha256':sha(target)})
    print(f'ENCODE {scene["id"]} ready {actual["durationSeconds"]:.2f}s',flush=True)
    return target

def verify_rendered_subtitles(scenes,audio):
    """Inspect real encoded pixels at two different caption times per scene.

    This catches a still-image VFR bug where subtitles were rendered before
    output-only frame duplication and froze for an entire image interval.
    It is a sampled rendering check, not speech recognition or human listening.
    """
    records=[]
    for scene,meta in zip(scenes,audio):
        directory=CACHE/scene['id'];samples=[]
        for index,cue in enumerate(meta['cues'][:2]):
            timestamp=PREFIX+(cue['start']+cue['end'])/2
            frame=directory/f'qa-caption-{index+1}.png'
            run([FFMPEG,'-hide_banner','-loglevel','error','-y','-ss',f'{timestamp:.4f}','-i',directory/'scene.mp4','-frames:v','1','-update','1',frame])
            crop=Image.open(frame).convert('RGB').crop((90,938,1830,1035))
            bright=sum(1 for r,g,b in crop.getdata() if r>165 and g>165 and b>165)
            if bright<200:raise RuntimeError('No readable burned subtitle pixels: '+scene['id'])
            samples.append({'seconds':timestamp,'brightTextPixels':bright,'subtitleCropSha256':hashlib.sha256(crop.tobytes()).hexdigest()})
        if len(samples)>1 and samples[0]['subtitleCropSha256']==samples[1]['subtitleCropSha256']:raise RuntimeError('Subtitles appear frozen: '+scene['id'])
        records.append({'scene':scene['id'],'captionSamples':samples,'changingSubtitlePixels':True})
    write_json(CACHE/'subtitle-render-qa.json',records)
    return records

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--render',action='store_true');parser.add_argument('--encode-ready',action='store_true');parser.add_argument('--proxy',default='http://127.0.0.1:7897')
    args=parser.parse_args()
    if not args.prepare and not args.render and not args.encode_ready: parser.error('Use --prepare, --encode-ready or --render')
    CACHE.mkdir(parents=True,exist_ok=True);OUTPUTS.mkdir(parents=True,exist_ok=True)
    (CACHE/'fonts').mkdir(exist_ok=True)
    cached_font=CACHE/'fonts'/FONT.name
    if not cached_font.exists() or sha(cached_font)!=sha(FONT):shutil.copyfile(FONT,cached_font)
    shutil.copyfile(ROOT/'public/fonts/OFL-NotoSansSC.txt',CACHE/'OFL-NotoSansSC.txt')
    script=json.loads(SCRIPT.read_text(encoding='utf-8'));scenes=script['scenes']
    if len(scenes)!=12: raise RuntimeError('Expected twelve editorial scenes')
    data=engineering_data(required=args.render)
    if args.render:
        for name in ['final-ai.jpg','final-report.jpg']:
            if not (SHOTS/name).exists(): raise RuntimeError(f'Final source not ready: {name}')
    semaphore=asyncio.Semaphore(2)
    audio=await asyncio.gather(*(synthesize(scene,semaphore,args.proxy) for scene in scenes))
    normalize=lambda value: ''.join(re.findall(r'[\w]',value)).casefold()
    for scene,meta in zip(scenes,audio):
        if normalize(scene['narration'])!=normalize(''.join(w['text'] for w in meta['wordEvents'])):raise RuntimeError('TTS timing words do not match narration: '+scene['id'])
        if meta['cues'][-1]['end']>meta['durationSeconds']+.1:raise RuntimeError('Subtitle extends beyond audio: '+scene['id'])
    durations=[math.ceil((meta['durationSeconds']+PREFIX+TAIL)*FPS)/FPS for meta in audio]
    total=sum(durations)
    if not 300<=total<=480: raise RuntimeError(f'Natural narrated duration {total:.1f}s is outside official range; adjust RATE and resynthesize, do not pad blank minutes.')
    transcript=[];global_cues=[];offset=0
    for index,(scene,meta,duration) in enumerate(zip(scenes,audio,durations)):
        transcript += [f'{index+1:02}. {scene["title"]}  [{srt_time(offset)} – {srt_time(offset+duration)}]',scene['narration'],'']
        for cue in meta['cues']: global_cues.append({'start':offset+PREFIX+cue['start'],'end':offset+PREFIX+cue['end'],'text':cue['text']})
        write_ass(CACHE/scene['id']/'subtitles.ass',meta['cues'])
        for variant in range(3): make_card(scene,index,variant,data,draft=not args.render)
        offset+=duration
    (OUTPUTS/'DriveLab-参赛演示.srt').write_text('\n\n'.join(f'{i+1}\n{srt_time(c["start"])} --> {srt_time(c["end"])}\n{c["text"]}' for i,c in enumerate(global_cues))+'\n',encoding='utf-8')
    (OUTPUTS/'DriveLab-参赛演示-逐字稿.txt').write_text('DriveLab 普通话合成解说逐字稿\n'+script['narrationDisclosure']+'\n\n'+'\n'.join(transcript),encoding='utf-8')
    metadata={'preparedAt':datetime.now(CLIENT_ZONE).isoformat(),'mode':'render' if args.render else 'draft-prepare','scriptSha256':sha(SCRIPT),'voice':VOICE,'rate':RATE,'plannedDurationSeconds':total,'resolution':[W,H],'fps':FPS,'narrationDisclosure':script['narrationDisclosure'],'sceneDurations':dict(zip([s['id'] for s in scenes],durations)),'audioSeconds':sum(m['durationSeconds'] for m in audio),'subtitleCues':len(global_cues),'narrationWordsMatchTimingEvents':True,'sourceScreenshotSha256':{p.name:sha(p) for p in SHOTS.glob('*.jpg')},'engineeringDataSha256':sha(ENGINEERING) if data else None,'liveModelQASha256':sha(LIVE_QA) if LIVE_QA.exists() else None,'limitations':['界面截图按日期标注；局部放大与图表属于剪辑展示，非连续操作或真实耗时。','线上默认2次请求与本机联网工具3次请求是不同测试案例，图表明确区分。','工程图来自当前应用输出和合成回归夹具，不是实车实验。','普通话为AI合成解说；不模拟成员本人声音。']}
    write_json(CACHE/'video-metadata.json',metadata)
    print(f'PREPARED {total:.2f}s; {len(global_cues)} subtitle cues',flush=True)
    if args.encode_ready and not args.render:
        for scene,duration in zip(scenes,durations):
            if scene['id']=='06' and not data:continue
            if all(source_shot(scene,variant).exists() for variant in range(3)):
                for variant in range(3):make_card(scene,scenes.index(scene),variant,data,draft=False)
                encode_scene(scene,duration)
            else:print(f'ENCODE {scene["id"]} waiting for final source screenshot',flush=True)
        return
    if not args.render: return
    for scene,duration in zip(scenes,durations): encode_scene(scene,duration)
    concat=CACHE/'video.ffconcat'
    concat.write_text('ffconcat version 1.0\n'+'\n'.join(f"file '{s['id']}/scene.mp4'" for s in scenes)+'\n',encoding='utf-8')
    video=OUTPUTS/'DriveLab-参赛演示.mp4'
    run([FFMPEG,'-hide_banner','-loglevel','warning','-y','-f','concat','-safe','0','-i',concat,'-c','copy','-movflags','+faststart',video],log=CACHE/'ffmpeg-final.log')
    actual=probe(video)
    if not(actual['width']==W and actual['height']==H and actual['hasAudio'] and 300<=actual['durationSeconds']<=480): raise RuntimeError('Final MP4 format acceptance failed')
    if abs(actual['durationSeconds']-total)>1: raise RuntimeError('Final timing drift exceeds one second')
    subtitle_checks=verify_rendered_subtitles(scenes,audio)
    decoded=run([FFMPEG,'-hide_banner','-loglevel','info','-xerror','-threads','3','-i',video.name,'-af','volumedetect','-f','null','NUL'],log=CACHE/'ffmpeg-full-decode.log',cwd=video.parent)
    peak=re.search(r'max_volume: ([\-\d.]+) dB',decoded.stderr)
    mean=re.search(r'mean_volume: ([\-\d.]+) dB',decoded.stderr)
    if not peak or float(peak[1])>=0:raise RuntimeError('Audio peak check failed or clipping needs review')
    metadata.update({'mode':'rendered-awaiting-visual-audio-review','output':video.name,'fileSize':video.stat().st_size,'outputSha256':sha(video),'formatChecks':{k:actual[k] for k in ['durationSeconds','width','height','hasAudio']},'subtitleRenderChecks':{'sampledScenes':len(subtitle_checks),'sampledCaptionTimes':sum(len(r['captionSamples']) for r in subtitle_checks),'changingSubtitlePixels':True},'fullDecodeExitCode':decoded.returncode,'audioVolumeChecks':{'peakDb':float(peak[1]),'meanDb':float(mean[1]) if mean else None,'noDigitalPeakClipping':True},'ffmpegInspection':actual['ffmpegInspection']})
    write_json(CACHE/'video-metadata.json',metadata);write_json(OUTPUTS/'DriveLab-参赛演示-制作与格式验收.json',metadata)
    print('FINAL '+json.dumps(metadata['formatChecks'],ensure_ascii=False),flush=True)

if __name__=='__main__': asyncio.run(main())
