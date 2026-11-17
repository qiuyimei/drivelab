"""Build the editable technical document from shared native content blocks.

The formal PDF is exported from this DOCX by the authorized Word renderer.
ReportLab remains an explicitly named layout reference, never the formal PDF.
"""
from pathlib import Path
from xml.sax.saxutils import escape
import json
import re
import importlib.util
import argparse
import hashlib
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parents[1] / 'outputs'
OUT.mkdir(parents=True, exist_ok=True)
ENGINE=re.search(r"ENGINE_VERSION='([^']+)'",(ROOT/'lib/evidence.ts').read_text(encoding='utf-8')).group(1)
TEAM=json.loads((ROOT/'docs/competition/team.json').read_text(encoding='utf-8'))
VALIDATION=json.loads((ROOT/'docs/competition/FINAL-VALIDATION.json').read_text(encoding='utf-8'))
assert VALIDATION['engineVersion']==ENGINE and VALIDATION['softwareChecksPassed']
ENGINEERING_REVIEW_RECORD='docs/evidence/engineering-results-audit-20261117.json'
ENGINEERING_REVIEW=json.loads((ROOT/ENGINEERING_REVIEW_RECORD).read_text(encoding='utf-8'))
assert ENGINEERING_REVIEW['finalEngineVersion'] in {'1.1.4',ENGINE}
TASK_EVALUATION_RECORD='docs/evidence/ai-task-evaluation-20261117.json'
TASK_EVALUATION=json.loads((ROOT/TASK_EVALUATION_RECORD).read_text(encoding='utf-8'))
TASK_REVIEW=TASK_EVALUATION['independentReview']
assert TASK_REVIEW['sourceSetSha256']=='2c597a9c6878a46c48cb31accbdec2775bfbe9a9724e7092e050816609005f51'
assert TASK_REVIEW['summary']['fixedLiveTasks']==6 and TASK_REVIEW['summary']['modelRequests']==14
TASK_REGRESSION_RECORD='docs/evidence/AI-TASK-T06-REGRESSION-120.json'
TASK_REGRESSION=json.loads((ROOT/TASK_REGRESSION_RECORD).read_text(encoding='utf-8'))
assert TASK_REGRESSION['regression']['mode']=='llm' and TASK_REGRESSION['regression']['modelRequests']==3
REVIEW_DATE=VALIDATION['reviewedOn']
VIDEO=json.loads((ROOT/'docs/competition/VIDEO-FINAL-121.json').read_text(encoding='utf-8'))
VIDEO_TIMELINE=VIDEO['chapters']
APPLICATION_CASES=json.loads((ROOT/'docs/evidence/APPLICATION-CASES-121.json').read_text(encoding='utf-8'))
assert APPLICATION_CASES['engineVersion']==ENGINE
FIGURE_CONTENT=json.loads((ROOT/'docs/competition/implementation-results.json').read_text(encoding='utf-8'))
figure_spec=importlib.util.spec_from_file_location('implementation_figure_layout',ROOT/'scripts/create-implementation-results.py')
figure_layout=importlib.util.module_from_spec(figure_spec)
figure_spec.loader.exec_module(figure_layout)
HISTORICAL_MODEL_ENGINE='1.1.2'
pdfmetrics.registerFont(TTFont('NotoSC', str(ROOT / 'public/fonts/NotoSansSC-Regular.ttf')))
INK=colors.HexColor('#253846'); MUTED=colors.HexColor('#657887'); ORANGE=colors.HexColor('#df6939'); LINE=colors.HexColor('#dbe3e9')
styles={
 'title':ParagraphStyle('title',fontName='NotoSC',fontSize=31,leading=42,textColor=INK,spaceAfter=18),
 'heading':ParagraphStyle('heading',fontName='NotoSC',fontSize=20,leading=29,textColor=INK,spaceAfter=18),
 'sub':ParagraphStyle('sub',fontName='NotoSC',fontSize=12,leading=20,textColor=INK,spaceBefore=12,spaceAfter=7),
 'body':ParagraphStyle('body',fontName='NotoSC',fontSize=10,leading=17,textColor=INK,wordWrap='CJK',spaceAfter=10),
 'small':ParagraphStyle('small',fontName='NotoSC',fontSize=8.5,leading=14,textColor=MUTED,wordWrap='CJK',spaceAfter=8),
 'cell':ParagraphStyle('cell',fontName='NotoSC',fontSize=9,leading=14,textColor=INK,wordWrap='CJK'),
 'headcell':ParagraphStyle('headcell',fontName='NotoSC',fontSize=9,leading=14,textColor=colors.white,wordWrap='CJK'),
}
story=[]
content_blocks=[]
section_number=0
def p(text,kind='body'):
 return Paragraph(escape(str(text)).replace('\n','<br/>'),styles[kind])
def add(text,kind='body'):
 story.append(p(text,kind))
 content_blocks.append({'type':'paragraph','text':str(text),'style':kind})

def spacer(height):
 story.append(Spacer(1,height))
 content_blocks.append({'type':'spacer','height':height})
def table(headers,rows,widths):
 data=[[p(v,'headcell') for v in headers]]+[[p(v,'cell') for v in row] for row in rows]
 t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),INK),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f5f7f9')]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,-1),.4,LINE)]))
 story.append(t)
 content_blocks.append({'type':'table','headers':[str(v) for v in headers],'rows':[[str(v) for v in row] for row in rows],'widths':widths})
 spacer(12)
def page(number,title):
 global section_number
 if section_number==0:
  story.append(PageBreak());content_blocks.append({'type':'page_break'})
 section_number+=1
 add(title,'heading')
def image(name):
 file=ROOT/'docs/competition/screenshots'/name
 if file.exists():
  from PIL import Image as PILImage
  with PILImage.open(file) as im: w,h=im.size
  story.append(Image(str(file),width=510,height=510*h/w))
  content_blocks.append({'type':'image','data':file.read_bytes(),'width':510,'height':510*h/w,'source':str(file.relative_to(ROOT))})
  spacer(12)

def result_image(name,*,crop=None,max_height=195):
 from io import BytesIO
 from PIL import Image as PILImage
 file=ROOT/'docs/competition/screenshots'/name
 if not file.exists():raise FileNotFoundError(file)
 with PILImage.open(file) as original:
  result=original.crop(crop) if crop else original.copy()
  stream=BytesIO();result.save(stream,format='PNG');stream.seek(0)
  width=min(510,max_height*result.width/result.height)
  story.append(Image(stream,width=width,height=width*result.height/result.width))
  content_blocks.append({'type':'image','data':stream.getvalue(),'width':width,'height':width*result.height/result.width,'source':str(file.relative_to(ROOT))})
  spacer(10)

def result_asset(asset_id):
 result=figure_layout.render_figure_asset(FIGURE_CONTENT,asset_id)
 stream=BytesIO();result.save(stream,format='PNG');stream.seek(0)
 story.append(Image(stream,width=510,height=510*result.height/result.width))
 content_blocks.append({'type':'image','data':stream.getvalue(),'width':510,'height':510*result.height/result.width,'source':asset_id})
 spacer(12)
def footer(c,doc):
 c.setStrokeColor(LINE);c.line(42,801,553,801);c.line(42,39,553,39)
 c.setFont('NotoSC',8);c.setFillColor(MUTED)
 c.drawString(42,814,'DRIVELAB  /  ENGINEERING WITH EVIDENCE')
 c.drawString(42,25,'参赛技术文档 · 软件工程复核版 · '+REVIEW_DATE)
 c.drawRightString(553,25,str(doc.page))

spacer(12)
add('DriveLab\n智能驾驶工况仿真\n与辅助分析平台','title')
add('工况设计、日志对标、资料检索与 AI 辅助分析','sub')
spacer(24)
table(['版本','状态'],[[f'产品 V1.0 / 计算引擎 {ENGINE}','本轮软件复核；既有模型实测另标版本'],['目标赛道','2026 传智杯 AI WEB 网页开发挑战赛'],['代码仓库','github.com/qiuyimei/drivelab（私有）']],[155,355])
add('当前结论','sub')
add('项目形成了面向前期工况预评估与数据复盘的 Web 工作台，连接五类工况、参数计算、采集日志、专业资料、受限 AI 解释及中文报告。结果保留输入、处理口径和引用依据，便于工程人员比较方案与说明前提。软件验证与历史模型记录分开留证；尚无车型或企业标定验收。')
if TEAM.get('identityConfirmed'):
 add('学校：'+TEAM['school']+'；负责人：'+TEAM['captain']+'；成员：'+'、'.join(m['name'] for m in TEAM['members'])+'。','small')
 add('指导教师：无。','small')
else:
 add('队名：                 学校：                 组别：','small')

page(1,'问题、用户与功能闭环')
add('主要用户是车辆测试、底盘标定相关工程人员及小型测试团队，用于在详细仿真或受控测试前整理工况条件、比较需求和复盘已有采集文件。教学与跨专业学习是辅助使用场景；当前未声称获得企业或真实车型验收。')
table(['环节','实现行为','输出'],[
 ['工况设计','五类模板；行车、车辆、道路参数可编辑','带单位和范围的输入'],
 ['模型计算','服务端重算，显示曲线与约束检查','可复算数字和风险等级'],
 ['日志对标','清洗、换算、对齐、共同区间插值','四通道误差和缺失情况'],
 ['依据分析','资料检索；可选免费模型与受限工具','引用、执行步骤、候选重算'],
 ['记录与交付','账号隔离保存；证据 JSON；中文 PDF','参数、日志、阈值和分析快照'],
 ],[80,265,165])
add('产品定位','sub')
add('使用轻量模型快速筛查需求和约束，帮助使用者解释参数、计算结果和采集差异之间的关系，并保存可复盘的输入与报告。它不是完整自动驾驶系统，不替代车型标定、动态车辆模型或整车安全认证。')
add('界面中的行车动画是运动学示意；紧急避障没有真实车辆外形碰撞几何、规划器或闭环跟踪器。')

page(2,'架构与数据流')
table(['层','职责','主要实现'],[
 ['浏览器','四类任务、React交互、SVG曲线、文档提取与候选载入','app/workbench.tsx；app/ui/*'],
 ['Worker API','账号识别、输入校验、仿真、分析与 SSE','app/api/[...path]/route.ts'],
 ['确定性证据','计算时序、误差、候选参数、输入指纹','lib/simulation.ts；evidence.ts；fingerprint.ts'],
 ['检索与解释','持久化分块、混合词项检索、受限工具、引用校验','lib/rag.ts；retrieval.ts；analysis.ts'],
 ['存储与模型','D1 按 owner 隔离；免费模型通过服务端调用','Drizzle 迁移；lib/provider.ts'],
 ],[80,265,165])
add('一次分析的请求链','sub')
add('浏览器提交任务标识、原始问题、工况、日志与容差 → 服务端组装任务目标并重新计算证据 → 检索相关段落 → 可选模型调用受限工具 → 校验结构、引用登记与任务检查 → SSE返回步骤及结果。模型不直接执行SQL、访问任意URL或改写当前工况。')
add('持久化原则','sub')
add('列表只返回记录摘要；打开记录才读取本人完整快照。记录保留任务标识和原始问题，恢复时检查结构，并从实际工具产物重建任务状态。保存时校验引擎、工况、日志与容差指纹；输入变更或任务不匹配时，旧结果不冒充本次分析。该检查不是真实性签名。')
add('技术栈：React 19、TypeScript、Vinext、Vite、Cloudflare Worker、D1、Drizzle。前后端共享纯计算模块，但服务端独立校验与复算。','small')

page(3,'物理模型、公式与适用条件')
table(['模型','公式 / 处理','适用条件'],[
 ['纵向停车','a = min(a请求, a底盘, mu*g)\ns = v0*tr + v0^2/(2a)\nt停止 = 0（v0=0）；否则 tr + v0/a','水平路面、恒减速，车速不反向'],
 ['完整跟驰','vc = max(v0-v前车, 0)\ngap最小 = d - vc*tr - vc^2/(2a)','前车恒速，不含前车制动'],
 ['稳态圆周','ay = v^2/R；r = v/R（v>0）\n方向盘角 = atan(L/R)*传动比（v>0）','静止时模型输出零；低侧偏运动学近似'],
 ['五次换道','y = W*(10u^3-15u^4+6u^5)\nay = W/T^2*(60u-180u^2+120u^3)','给定轨迹需求；u 按响应后时间归一化'],
 ['附着与压力','利用率 = sqrt(ax^2+ay^2)/(mu*g)\np = abs(ax)*质量/制动力增益','摩擦圆需求检查；压力为集总估算'],
 ],[80,265,165])
add('数值与边界处理','sub')
add('内部使用 m、s、m/s 和 m/s²；车速输入/输出 km/h，横摆 °/s，方向盘 °，压力 bar。时序按 0.1 s 输出并精确截止于窗口末端；纵向位移分段精确积分。给定五次轨迹在显示窗口内的活动时间上，侧向需求通过端点与驻点取连续极值；转向需求只在最低适用速度以上取端点与驻点极值。附着需求结合该轨迹与恒有效减速度计算，不扩展为任意车辆模型的连续最坏情况。')
add('公式中的角量使用 rad 与 rad/s；页面与日志协议的角度展示乘以 180/π 转为 ° 与 °/s。','small')
add('短显示窗口之外的完整制动间距另行解析预测。换道/避障初速低于 5 km/h 时明确拒绝；这是本软件的模型适用政策边界，不是车辆通用限值。避障降至低速且仍有横向需求时提示未完成评估，不能把未算出的转向需求当通过。变速换道仍是近似需求。')
add('短制动脉冲即使落在采样之间，也保留解析压力峰值 pmax = a*质量/制动力增益及纵向附着需求，并给出曲线覆盖提醒，不额外插入网格行。压力是模型估算，不是实际液压测量；不能把曲线零压力当作制动需求为零。','small')
add('默认侧向阈值、误差容差与制动增益是项目初始值，不是法规限值或经车型审核的标定值。','small')

page(4,'AI、RAG 与受限工具')
add('AI 负责解释已计算的证据、连接文档依据和提出可复算候选；确定性引擎负责数字和约束等级。未接通模型时明确显示规则分析，不用预写文本冒充联网模型。')
table(['工具','输入与行为','约束'],[
 ['inspect_simulation','读取服务端工况、风险和事实卡','不能覆盖风险等级'],
 ['compare_measurement','读取本次日志误差、偏差和覆盖范围','无日志时如实返回'],
 ['search_knowledge','根据问题检索资料分块','保留页码、段落和来源定位'],
 ['evaluate_parameters','独立重算速度/间距/响应/换道时间','白名单参数，不改附着条件，不修改基线'],
 ],[150,205,155])
add('检索实现','sub')
add('中文单字/双字与英文词项，BM25 结合 512 维稀疏词项哈希向量余弦相似度。约 700 字分块、560 字步进；索引保留 docId#cN、字符范围、PDF 页码或段落。该方法不是语义 embedding。')
add('生成校验与失败行为','sub')
add('模型最多请求3轮、每轮至多4个工具；最终输出结构化JSON。观察和建议须引用有效factId或chunkId。剩余请求内返回有界错误诊断与真实登记映射，要求模型自行纠正，不自动替换或填入引用。肯定式安全承诺仍拒绝。额度、网络或格式失败保留规则结果。编号有效不等于语义或引用支持已被证明。')
add('1.2.0新增固定任务对照，原六题真实结果保留5个被接收回答及1个降级，见后文有限评测。1.1.2/1.1.3/1.1.4模型案例另标历史，不充当当前版本重新运行证据。','small')
add('默认及工具重算候选使用独立CAND_n事实范围，保留patch、基线指纹和结果；界面均提供比较与确认载入。载入只填写参数，用户需单独运行，原日志随后解除绑定。检索只暴露已登记段落。编号校验不能证明文字与引用之间的全部支持关系。','small')
add('新资料导入在服务端核验段落位置字段，section仅接受不超过200字符的字符串；错误类型会被拒绝。PDF读取失败或被拒绝时释放解析任务，避免遗留解析资源。','small')
add('已有资料的兼容处理','sub')
add('读取旧索引时校验段落对象、页码和章节名称；非字符串章节改用真实页码或段落回退标签，异常分段跳过后使用可用正文。只做读取兼容，不迁移或改写已有数据库；原文、向量与有效定位不被替换。')

page(4,'四类任务与可操作结果')
table(['任务','前提与实际执行要求','完成检查的范围'],[
 ['工况风险复盘','已复算基线；日志可选','基线已给，无需为了凑流程重复调用读取仿真'],
 ['日志差异复盘','已绑定日志；实际compare_measurement','无日志阻止模型调用；误差不等于故障原因'],
 ['候选方案比较','实际evaluate_parameters生成有输入变化的候选','默认建议或未变参数不计本次工具流程完成'],
 ['资料依据问答','实际search_knowledge；核对返回的登记段落','零相关段落保留缺项，不伪装命中或车型知识'],
 ],[105,225,180])
add('任务状态由服务端按产物构建：complete为执行步骤齐全，partial为步骤不完整，非模型或降级为rules-only。原始问题随task保存，恢复时回到所选目标；切换任务不把旧结果当作新执行。检查仅记录流程，不保证自然语言语义或工程适用性。')
result_asset('taskHome120')
add('1.2.0本机四类任务卡局部拼排：按问题选择目标。无日志可做风险复盘，不能执行日志复盘。','small')

page(5,'日志协议与公开数据')
image('public-log.jpg')
add('历史 V1.0 界面：公开 comma2k19 导入样例，截图未显示引擎版本。它与仿真工况不同，图中差异不能用于评估模型精度。','small')
table(['处理','规则'],[
 ['字段','time_s；speed_kmh；yaw_rate_dps；brake_pressure_bar；steering_angle_deg'],
 ['清洗与对齐','去无效行；时间排序；重复时间保留最后一行；首时刻归零后应用偏移'],
 ['对标','在共同区间比较；单点可报告点误差，并警告不能代表持续工况。MAE/RMSE/偏差按原仿真网格等点权，最大误差/时刻按两网格并集；采样间隔提醒只计与共同区间正长度相交的间隔'],
 ['缺失','按有效通道值判断；有列名但全为空也标缺失。空值不补零，区间外不外推；先检查方向盘/前轮角定义'],
 ['曲线显示','浏览器与PDF共用共同窗口裁边插值；跨越窗口的线段保留窗口边界值，纵轴覆盖有效负值。该显示处理不改变误差统计口径'],
 ],[85,425])

page(6,'独立验证与结果')
bench=json.loads((ROOT/'public/validation/benchmark-results.json').read_text(encoding='utf-8-sig'))
assert bench['engineVersion']==ENGINE
table(['验证','结果','证明范围'],[
 ['核心回归',str(VALIDATION['coreTests'])+' 项通过','给定轨迹连续极值、共同区间与单点边界、导入来源及既有计算/日志边界'],
 ['分析回归',str(VALIDATION['analysisTests'])+' 项通过','工具往返、候选事实、引用闭包、有界纠正与降级'],
 ['导入与曲线边界',str(VALIDATION['importPlotGroups'])+' 组通过','跨窗口线段、边界插值、有效负值与资料导入'],
 ['旧资料兼容',str(VALIDATION['legacyKnowledgeGroups'])+' 组通过','旧章节对象、异常页码/索引与有效定位保留'],
 ['独立解析参考',f"{bench['summary']['passed']} / {bench['summary']['total']}；另有1.1.4历史 {VALIDATION['continuousExtremaReview']['cases']} 组连续需求密扫",'当前公式实现与历史给定轨迹密扫分别留证；不冒充当前版本重新密扫'],
 ['既有1.1.3扩展交叉检查',f"{VALIDATION['independentExtendedReview']['longitudinalCases']} 组 / {VALIDATION['independentExtendedReview']['timeSamples']} 时序点；{VALIDATION['independentExtendedReview']['asynchronousLogCases']} 组异步日志",'历史检查保留；不冒充当前版本重新运行或实车精度'],
 ['固定检索回归',f"{bench['retrieval']['hitAt3']}/{bench['retrieval']['total']} Hit@3；{bench['retrieval']['top1']}/{bench['retrieval']['total']} Top1",'小样本回归，不代表泛化准确率'],
 ['公开 CAN 样例',f"{bench['publicSample']['rows']:,} 行；约 {bench['publicSample']['duration']:.2f} s",'哈希、单位、时间轴与缺失通道'],
 ['本地 API',str(VALIDATION['apiIntegrationChecks'])+' 项通过','独立数据库；登录/来源门禁、SSE、任务与快照、分段拒绝；夹具清理'],
 ['保存工作流',f"{VALIDATION['savedWorkflowGroups']} 组回归通过",'偏移、容差、任务和分析恢复；既有界面操作另按实际版本留证'],
 ['本地数据库','新库/重复启动/旧库升级通过','独立夹具确认迁移与既有记录保留；未操作用户数据库'],
 ['交付文档','同源 Word 导出 PDF 并逐页核验','原生文字和表格可编辑；中文、图表与分页'],
 ],[115,170,225])
add('独立参考如何避免自证','sub')
add('参考生成器不调用应用计算模块：停车参考由闭式解生成，弯道参考从圆周几何生成，换道参考通过六个边界条件的线性方程独立求解。最大绝对数值差约 '+format(bench['summary']['maxAbsoluteError'],'.4g')+'。')
add('测试只证明各自范围内的实现，不能作为实车精度或通用模型回答准确率。当前软件、任务模型评测与界面分别留证；旧模型与扩展工程检查保留实际版本。不曾进行受控实车闭环标定或专业安全签署。','small')

page(7,'数据来源、许可与复现')
add('公开数据来源为 comma.ai 官方 comma2k19 仓库中的示例 CAN 片段，MIT 许可。仅保留速度与方向盘转角，没有伪造横摆角速度或制动压力。')
add('固定源提交\n4c7f1a6e1957745beadc1def0e7225f559b09a2a','small')
add('CSV SHA-256\ne97ef42e65251f5ba0ca9fc2dec334b9870a27638be88710545ac5f1d17cd722','small')
add('成品 CSV 保留 speed_mps；应用导入时才换算为 km/h。生成样例时把方向盘角插值到共同区间的速度时间戳；不外推、不平滑。四个原始 NPY、Git blob 哈希、许可和转换脚本已补齐，并重建出相同 CSV 哈希。这个路段不是本项目停车/换道实验。')
table(['资料','位置'],[
 ['样例与许可','public/data/，含 CSV、metadata 和 MIT 许可'],
 ['参考基准','validation/independent-reference-cases.json 与生成脚本'],
 ['验证结果','public/validation/benchmark-results.json'],
 ['工程依据','docs/evidence/engineering-sources.json'],
 ['字体','Noto Sans SC，SIL OFL 1.1；来源、变体转换和哈希保留于 public/fonts/'],
 ],[110,400])
add('专业审核','sub')
add('软件验证覆盖公式实现、单位、边界、对标网格与证据引用，并保留可复算的测试记录。默认参数和阈值没有特定车型标定或专家签署。公开课程与独立解析参考仅支撑假设内的实现，不被当作车型精度证明。')

page(8,'运行环境与可靠性')
add('首次运行：Node.js 24；pnpm 11.25.0。执行下列命令后访问 127.0.0.1:5173。','body')
table(['命令','作用'],[
 ['pnpm install --frozen-lockfile','按锁文件安装依赖'],
 ['pnpm run db:local','创建或升级本地 D1；可重复执行'],
 ['pnpm run dev','准备文档解析资源并启动本地预览'],
 ['pnpm test / pnpm run typecheck','核心、分析、参考数据、检索、向导检查与类型检查'],
 ['pnpm run test:db / pnpm run test:api','独立数据库启动验收；服务启动后的 API 验收'],
 ['pnpm run build','生成生产 Worker 与浏览器资源'],
 ],[200,310])
add('密钥与故障处理','sub')
add('本机连接向导运行在回环地址 5174，采用密码输入框、来源校验与请求令牌。密钥写入忽略的 .dev.vars；服务商原始错误不能原样返回，避免回显凭证。公开目录查询与真实鉴权测试分开。')
add('ModelScope 免费入口需要本人按官方页面完成账号准备；未认证、鉴权失败、额度和服务错误分别提示。免费保护不选择提供方付费后缀，也不自动切换付费。线上仅使用服务端 secret。')
add('数据库初始化先检查旧结构，再接入迁移记录；不删除或重建现有用户表。桌面启动器自动准备解析资源和数据库，开发工具与安装包继续保留。')

page(9,'竞赛展示与团队复核')
table(['评价方向','可展示内容','仍需补齐'],[
 ['AI 深度 / 创新','任务目标 + 计算证据 + 日志 + RAG + 工具候选 + 执行检查','固定合成题有限对照；泛化语义与引用支持仍需复核'],
 ['前端 / 体验','完整工作台、对标曲线、执行步骤、报告下载','另一设备与评审账户端到端验收'],
 ['实用性 / 社会价值','工程方案比较、测试任务复盘与输入可追溯；教学为辅助','实际使用反馈，不编造节省时间指标'],
 ],[110,245,155])
add('本轮产品演示','sub')
def timestamp(seconds):
 seconds=int(seconds);return f'{seconds//60}:{seconds%60:02}'
table(['时间','演示内容'],[
 [timestamp(c['startSeconds'])+'–'+timestamp(c['endSeconds']),c['title']] for c in VIDEO_TIMELINE
 ],[105,405])
add('本轮视频 '+format(VIDEO['format']['durationSeconds'],'.2f')+' s、1920×1080，采用本机离线普通话合成解说、逐句字幕、实际界面截图与结果剪辑。新增四任务、工具候选、事实与任务报告画面。真实模型材料保留1.2.0版本和初次降级，基础日志/资料素材另标历史版本；不是连续操作录屏或新一轮联网模型测试。制作与核验见VIDEO-FINAL-121.json。','small')

page(9,'项目成员与职责分配')
add('学校：'+TEAM['school']+'。负责人：'+TEAM['captain']+'。指导教师：无。')
table(['成员','学院与专业','项目职责'],[[m['name'],m['college']+'\n'+m['discipline'],m['role'].replace('API接入、','API接入、\n',1)] for m in TEAM['members']],[65,175,270])
add('软件架构、功能开发与系统集成由两名软件工程成员分工负责；车辆工况、模型依据、参数含义及适用条件由车辆工程成员负责梳理与核对。开发过程与成果由版本记录、测试及交付材料追溯。')
add('开发过程中使用AI辅助，相关内容纳入版本管理、测试与复核。团队负责说明系统架构、关键代码及模型假设；产品内推理服务使用魔搭API接入Qwen模型。')

page(10,'版本与交付证据')
table(['证据','本轮交付','适用范围'],[
 ['软件引擎',ENGINE+'；回归、接口与构建通过','曲线、资料字段、解析清理和旧索引兼容修复；未增加3D或硬件'],
 ['真实模型','六题14请求；另有T06定向回归','保留实际1.2.0版本、初次降级及引用局限；未整批重跑'],
 ['技术文档','可编辑Word与同源PDF','正式PDF不超过30页；原生文字/表格，截图保留真实版本'],
 ['演示视频','普通话、1080p、5–8分钟','画面与数据来自已留证素材；本机合成配音'],
 ['正式压缩包','技术PDF、MP4、仓库链接TXT','仅三项；技术Word与个人修改核对单单独交付'],
 ],[105,140,265])
add('可追溯的修改范围','sub')
add('保留完整Git历史及真实模型记录。源码中的产品接口、登录路径与部署配置保留必要技术标识；面向评审的开发辅助表述统一为AI。曲线显示修复不改变误差统计网格或物理方程。')
add('使用与复核','sub')
add('应用为前期需求评估与数据复盘原型，尚无实车标定或企业任务验收。后续实测与用户反馈列入展望，不计为本轮成果。视频采用实际截图与合成解说，不伪装连续操作、成员录音或实车实验。')

page(11,'关键计算与证据口径')
table(['能力','当前实现','证明范围'],[
 ['连续轨迹需求','给定五次轨迹在显示活动时间内检查端点与驻点；转向限定于适用速度域；附着结合恒减速需求','不是任意轨迹或真实轮胎模型的最坏情况'],
 ['时序与误差','0.1 s 时序与连续需求指标分开；MAE/RMSE/偏差仍按原仿真网格等点权；日志最大误差用两网格并集','不把采集插值点当成新增独立测量'],
 ['共同时间区间','在共同区间比较；单点也可报告点误差，并警告不能代表持续工况；采样间隔提醒只计正长度相交','只证明所给分段线性数据与有效点的比较'],
 ['数据来源','文件名不证明来源；导入数据统一提示出处未核验，公开/合成样例不充当车型标定','人工确认数据授权、工况、采样与通道定义'],
 ['压力与低速边界','短制动保留解析压力需求和曲线覆盖提示；静止单独处理；低速横向不完整评估时明确告警','简化需求模型，不是执行器或车辆安全认证'],
 ],[105,270,135])
add('连续需求工程复核见'+ENGINEERING_REVIEW_RECORD+'（原记录版本'+ENGINEERING_REVIEW['finalEngineVersion']+'）；当前软件检查见FINAL-VALIDATION.json。旧工程和模型记录不被改写为本轮重新运行证明。','small')

page(12,'真实工具产物与报告交付')
result_asset('toolCandidate120')
add('1.2.0本机初次T06工具候选三列与载入按钮局部拼排：换道时长5→6.25 s，侧向需求0.81→0.52 m/s²、方向盘需求3.11→1.99°。三请求后正文因引用失败降级，工具产物保留；不是成功模型回答。','small')
add('固定案例核对','sub')
add('100 km/h 自车、60 km/h 恒速前车、80 m 间距、0.8 s 响应、5 m/s² 减速：解析停车距离 99.3827 m，停车时间 6.3556 s，全过程最小间距 58.7654 m。停车距离大于初始间距并不直接判碰撞，因为前车持续运动。实际回答需明确未绑定测量日志。')
page(12,'任务报告与执行检查')
add('任务报告加入目标、原始问题、状态与逐项执行检查，并保留参数、时序、日志口径、事实字典、候选登记与资料锚点。旧分析与当前参数、日志、阈值或引擎不一致时不采用；任务检查不代表语义正确或认证完成。')
result_asset('taskReport120')
add('另一次唯一授权T06定向回归的成功PDF任务表：三请求、实际CAND_3和执行检查齐全。初次降级保留；完整成功报告已全6页检查，不代表通用语义可靠。','small')
add('AI 辅助开发披露','sub')
add('开发过程中使用AI辅助，相关内容纳入版本管理、测试与复核。团队负责说明系统架构、关键代码及模型假设；产品内推理服务使用魔搭API接入Qwen模型。')

page(12,'有限任务对照及失败记录')
add('固定问题对照无检索规则、规则加RAG和完整工具流程。离线8题中预选6题实际调用ModelScope Qwen/Qwen3.5-27B，共14次请求：5个模型回答被接收、1个降级。这个结果不是83.3%语义准确率。')
table(['固定问题','实际观察','限制'],[
 ['偏差与已知时移','误差和覆盖符合参考，模型组织时移校正行动','T01/T02部分具体断言所附资料只支持通用流程'],
 ['自定义90 km/h与110 m','两个实际工具候选匹配独立公式','最终叙述缺引用，3请求后降级；不是模型答题成功'],
 ['弯道降速20%','实际重算1.00→0.64 m/s²并解释平方关系','默认候选也可给相同数值；不是AI独有计算能力'],
 ['项目资料问答','回答步骤、版本和页节位置','人工项目夹具，不是厂家PDF或真实车型规范'],
 ['未知厂家标定','承认未知，不把默认540°当厂家值','合理未知不等于已获得车型参数'],
 ],[115,205,190])
add('原六题绑定源码集合SHA-256：\n'+TASK_REVIEW['sourceSetSha256'],'small')
add('记录：'+TASK_EVALUATION_RECORD+'。评测使用合成日志和项目资料，单模型、单次小样本，实际API语料未严格隔离。主要任务人工核对不能证明全部引用蕴含、通用语义或实车适用性。未测真实用户耗时或节省比例。','small')
add('初次T06界面验收另有1案例3请求降级及正确工具候选，未并入上述6题。补充有界诊断与登记映射后，唯一授权的同输入定向回归用3请求接收模型回答；不是重新运行整批评测。','small')
add('定向回归的主要数值、patch和本例关系人工核对通过，但“reaction未变”的所附峰值/通用资料不直接编码该配置；交通流效率也未量化。两次结果不是随机重复对照，不能把改善完全归因于提示变化；见'+TASK_REGRESSION_RECORD+'。','small')

page(13,'AI 选型、创新与总结展望')
add('模型选型理由','sub')
add('此前选用 ModelScope 提供的 Qwen/Qwen3.5-27B，基于当时可用的免费入口、中文解释需求，以及 OpenAI 兼容接口和工具协议的集成条件。既有联调证明它能完成所记录的案例；应用仍以本地 JSON、引用校验和有界纠正管理输出。未做模型横向基准，不声称其准确率、速度或中文能力优于其他模型。')
add('集成与优化','sub')
add('用约700字分块与混合词项检索缩小上下文，先组装确定性事实，再按任务开放受限工具。总请求限制为3次；错误诊断、事实登记映射和输出长度均有边界，持续失败回退规则结果。候选独立重算后经用户确认载入，减少解释、计算与当前输入混用。优化作用由固定回归和单题记录说明，不声称未经测量的速度或成本收益。')
add('技术创新点：证据与工具的工程组合','sub')
add('将服务端任务目标、确定性计算、日志误差、段落检索与受限工具串成同一证据链，用独立候选事实、执行检查、输入指纹和明确降级减少混用。这是面向具体流程的工程组合与交付设计，不是新的物理或语义嵌入算法。')
add('应用创新点：面向工程复盘的完整工作台','sub')
add('把工况设计、日志复盘、专业资料与候选比较连接到保存和报告，帮助车辆测试与底盘标定相关工程人员、小型团队说明条件、结果和依据；也可辅助教学。没有真实用户规模或效率对照试验，不虚构时间节省比例、商业收益或实车精度。')
add('总结与展望','sub')
add('当前原型已完成五类轻量工况、文件日志对标、四类AI任务、可操作候选、保存恢复和报告交付。固定小样本对照显示有针对性的解释与资料问答，也保留引用局限和降级。后续计划如下，均不是已完成成果。')
table(['后续方向','计划与验收方式'],[
 ['车型参数','由实际工程成员核对参数、阈值和增益，记录适用条件与审核结论'],
 ['受控实测','在授权、同工况数据基础上核对采样、单位和时间，再评价模型差异'],
 ['真实用户','开展跨设备与任务流程试用，收集可追查的问题和反馈，不预设收益比例'],
 ['检索与解释评测','扩展问题集、引用相关性和人工生成质量复核，保留失败案例与版本'],
 ],[105,405])

page(14,'应用场景与完整操作流程')
add('项目主要用于前期工况预评估和已有文件的数据复盘。应用价值不只是在页面上算出一个数，而是把输入条件、曲线、资料、候选与报告串在一起，方便使用者说明结果是怎么得到的。以下按实际使用过程展开，不把原型描述为已经完成企业落地。')
table(['场景','先看什么','适合继续做的事'],[
 ['高速跟驰','自车/前车速度、初始间距、响应与减速条件','比较降速、增加间距或改变响应条件后的停车距离和最小相对间距'],
 ['弯道稳态','车速、半径、附着与转向约束','查看侧向、横摆与转向需求，比较不同车速；不把稳态模型外推为瞬态控制'],
 ['动态换道','车速、换道宽度/时长、响应与显示窗口','比较横向需求；确认窗口覆盖轨迹，再查看独立工具候选'],
 ['紧急避障','纵向制动与横向轨迹同时存在的条件','检查附着需求、停车与低速提示；不把需求示意当可执行规划路径'],
 ['城市路口','纵向制动条件、时序与压力估算','观察参数变化和制动结果；不推定已经包含信号灯识别或完整交通交互'],
 ],[85,165,260])
add('一次完整操作可以分为六步。第一，选模板并核对单位、前车运动假设、车速和响应时间。第二，运行计算，先看约束与覆盖提示，再读曲线。第三，需要对标时导入日志，核对通道定义、单位、偏移与共同区间。第四，有相关资料时导入并确认提取出的正文。第五，选择风险、日志、候选或资料任务，核对计算事实与引用。第六，将确认过的条件保存，导出报告用于复盘。')
add('四个任务入口并不要求每次全部执行。只想了解工况可以先做风险复盘；有日志再做差异复盘；想比较修改才选候选任务；查资料时才要求实际检索。缺少必要输入时保留缺项，不能为了让流程看起来完整而伪造资料或日志。')

page(14,'应用案例一：比较降速和增加车距')
add('假设前车保持60 km/h，自车响应时间0.8 s，请求减速度5 m/s²，其他车辆、道路参数沿用默认值。下面三组由本轮1.2.1确定性引擎直接复算，不占模型额度，也不是新做的实车或联网模型试验。')
application_rows=[]
for label,item in zip(['原方案','降低自车速度','增加初始间距'],APPLICATION_CASES['highway']):
 application_rows.append([label,str(item['config']['speed']),str(item['config']['distance']),format(item['stoppingDistance'],'.4f'),format(item['predictedMinGap'],'.4f')])
table(['方案','车速 km/h','初始间距 m','停车距离 m','全过程最小间距 m'],application_rows,[110,80,80,115,125])
add('原方案的停车距离约99.38 m，大于80 m初始间距，但预测最小相对间距仍约58.77 m。原因是前车在响应和制动期间继续向前运动。不能只比较“停车距离”和“初始间距”来判断是否碰撞。这里仍以恒速前车和恒减速为前提，前车制动需另设模型。')
add('降速方案同时减少自身停车距离和相对接近量；增加间距方案不改变自身停车距离，但增加了相对间距余量。两种改动解决的问题不同。本节三组由引擎逐组复算后汇总到本报告；当前软件仍以当前基线、候选和个人记录查看，没有新增多方案表格模块。比较时要同时保留输入与多个指标，默认阈值没有车型审核，不能只凭一个变小的数宣布方案最好。')
result_asset('parameters114')
add('参数设置与运行入口的既有1.1.4本机截图；用于说明操作位置。上表是1.2.1重新计算的三组示例，截图不充当新版本操作记录。','small')
add('在界面中，可先保存原方案，再修改一个条件并运行。若使用AI候选比较，要核对CAND编号下的修改项和结果，确认没有同时改动附着条件等比较前提。载入候选只填写参数，运行后才得到新的当前基线；原来的日志随之解除绑定。')

page(14,'应用案例二：把日志差异变成可核对的问题')
add('日志复盘先判断“文件是否能正确比较”，再讨论差异。以接口验收使用的合成夹具为例：弯道稳态基线速度36 km/h、窗口5 s；日志在0–5 s每0.1 s记录一次，共51点，速度恒为38 km/h，仅有速度通道。这个夹具用于检查固定偏差，不是采集到的真实车辆数据。')
table(['项目','本例应看到的结果','怎样理解'],[
 ['共同区间','0–5 s','只比较两边都有有效数值的部分'],
 ['速度误差','MAE=2 km/h；RMSE=2 km/h；最大误差=2 km/h','该合成例每个共同点均高2 km/h，不表示已找出真实故障'],
 ['缺失通道','横摆、压力、转向缺失','不补零，也不能据此判断这些系统没有动作'],
 ['其他容差/偏移','随本次输入保留','修改后原分析需要重新核对，不沿用旧结论'],
 ],[95,185,230])
add('实际工作中，先检查速度是否把m/s误作km/h、时间是秒还是毫秒、方向盘角是否被当成前轮转角。再核对时间归零和偏移方向，查看共同区间及采样间隙。只有这些前提合理，误差数字才有解释价值。')
add('模型模式完成日志差异任务时，要求实际读取本次compare_measurement产物。本节固定夹具在规则模式下验收，规则结果不冒充模型工具调用。模型可以组织误差、覆盖和待检查条件，但不能仅凭一条偏差断言传感器、控制器或车辆发生故障。若怀疑时延，应先用已知工况和事件对齐；若怀疑参数，应确认文件对应相同运行条件，再重新比较。')
add('误差表、曲线和质量提醒需要一起看：单个采样点的误差不能代表持续过程；长采样间隔中的插值不等于新测量；公开comma2k19路段不对应本项目任意选中的制动或换道模板，不能用它直接证明模型精度。')

page(14,'应用案例三：让资料回答对应到页码和事实')
add('专业资料的作用是帮助说明条件和方法，而不是给任意模型结论补一个看似权威的出处。操作时先导入PDF、DOCX或文本，核对标题和提取正文，再保存资料。PDF提取不到可读正文时，需要先提供可读取的文本版本；上传成功不等于资料正确或已经完成专业审核。')
result_asset('knowledgeFlow114')
add('既有1.1.4资料导入与保存界面；图中是项目编写的示例资料，保留待审核状态，不是厂家原始标定文件。','small')
add('问“本次应该怎样检查日志偏差”时，模型模式的资料任务要求实际检索；命中时返回已登记文档与可用的页码或段落位置，零命中时保留资料不足。页面中一般方法和本次计算事实分别展示。若只检索到通用对齐流程，不能把它写成已经证明本次偏差的具体原因。')
add('问“某厂家车型的方向盘极限是不是540°”时，如果资料里没有该车型信息，就应保留未知；项目默认值不能自动成为厂家参数。此前固定任务已保留这类未知问题的结果，但这不等于项目已经获得该车型的数据。')
result_asset('factClaim120')
add('1.2.0定向回归的实际事实展开界面。可以回看事实编号、值与单位；编号存在仍不等于它充分支持文字中的每个意思。','small')
add('核对时可以顺着三条线阅读：本次输入是什么，引用的SIM或CAND事实算了什么，资料段落支持的是一般方法还是特定条件。若三者对不上，先改问题、补资料或重新运行，不把“引用有效”直接当作工程结论成立。')

page(14,'记录、报告与后续复盘怎么衔接')
add('比较方案时，可以把记录名称写成“工况＋主要输入差异”，例如高速跟驰基准、降速方案、增大间距方案。保存的是当时参数、日志、容差及分析快照。以后打开记录，应先核对恢复后的参数与任务，再决定是否继续分析。')
result_asset('records114')
add('既有1.1.4个人工况记录列表的实际局部，用于说明保存与打开入口；图中记录是合成演示条件。','small')
table(['报告中保留的内容','复盘时要回答的问题'],[
 ['输入、模型与版本','这次用的车速、间距、响应、道路和引擎是否一致'],
 ['时序、连续需求与约束','曲线展示到了哪里，峰值按什么范围检查，哪些提示仍未解决'],
 ['日志、单位、偏移和误差','文件与工况是否对应，哪些通道缺失，误差比较区间是什么'],
 ['任务、原问题与步骤','本次到底做了风险、日志、候选还是资料分析，缺了什么'],
 ['事实、候选和资料锚点','数字来自基线还是候选，引用支持到哪一步，报告中的候选修改了哪些输入'],
 ],[165,345])
add('这些信息用于让同伴能看懂结果的前提，而不只是拿到一句结论。当前记录按个人账号隔离，不包含跨团队共享审批、车型专家签署或企业协同管理。报告内容与参数、日志、容差或引擎不匹配时，应重新运行；输入指纹只检查一致性，不证明外部日志真实。')
add('候选报告保留的是独立、未应用的重算结果，不追踪它之后是否被载入和执行。若用户载入候选再运行，旧分析会清除，应另查看新一轮计算或保存记录，不能用原候选报告证明后续操作已经完成。')
add('在学习场景，也可以围绕同一工况组织比较：先解释降速与增加间距的差别，再比较换道5 s与6.25 s下的横向需求，最后导入明确标记的合成偏差日志。这样的演示用于理解模型与数据处理，不将课程实验包装成车辆安全试验。')

page(14,'主要来源与工程许可')
refs=[
 ('赛事方发布页','https://m.saikr.com/vse/2026AIWEBKF'),
 ('传智杯官网','https://www.boxuegu.com/match/'),
 ('UIUC 制动距离课程，PDF 23–26 页','https://courses.grainger.illinois.edu/ece101/fa2025/lectures/101-024-autonomous-driving.pdf'),
 ('UCSD Vehicle Dynamics，摩擦圆课程资料','https://cseweb.ucsd.edu/classes/sp19/cse291-d/Files/CSE291_14_VehicleDynamics.pdf'),
 ('CMU Snider，运动学单轨，正文 18–20 页','https://publications.ri.cmu.edu/storage/publications/pub_files/2009/2/Automatic_Steering_Methods_for_Autonomous_Automobile_Path_Tracking.pdf'),
 ('PythonRobotics，五次轨迹实现，MIT','https://github.com/AtsushiSakai/PythonRobotics/tree/master/PathPlanning/QuinticPolynomialsPlanner'),
 ('comma.ai 数据集和 MIT 许可','https://github.com/commaai/comma2k19'),
 ('Google Fonts Noto Sans SC，SIL OFL 1.1','https://github.com/google/fonts/tree/main/ofl/notosanssc'),
 ('ModelScope API-Inference 官方文档','https://modelscope.cn/docs/model-service/API-Inference/intro'),
 ]
for title,url in refs: add(title,'sub');add(url,'small')
add('赛事信息还对照了用户提供的参赛资料汇编第 2.2 节；最终提交应以学校和报名后台要求为准。页面截图来自本机实际运行，规则分析不被描述为真实大模型联网结果。','small')

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--format',choices=['docx','reportlab-preview'],default='docx')
 parser.add_argument('--output',type=Path)
 parser.add_argument('--manifest',type=Path,default=ROOT/'.sites-runtime/technical-native/build-manifest.json')
 args=parser.parse_args()
 if args.format=='reportlab-preview':
  file=args.output or OUT/'DriveLab-参赛技术文档-排版参考.pdf'
  if file.resolve()==(OUT/'DriveLab-参赛技术文档.pdf').resolve():
   raise ValueError('The formal PDF must be exported from the editable DOCX, not ReportLab.')
  doc=SimpleDocTemplate(str(file),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=61,bottomMargin=57,title='DriveLab 技术文档排版参考',author='DriveLab')
  doc.build(story,onFirstPage=footer,onLaterPages=footer)
  print(json.dumps({'file':str(file),'referenceOnly':True},ensure_ascii=False));return
 from native_document import build_native_docx
 file=args.output or OUT/'DriveLab-参赛技术文档.docx'
 for block in content_blocks:
  if block['type']=='table':
   scale=475/sum(block['widths']);block['widths']=[width*scale for width in block['widths']]
  elif block['type']=='image' and block['width']>475:
   scale=475/block['width'];block['width']=475;block['height']*=scale
 manifest=build_native_docx(content_blocks,file,title='DriveLab 智能驾驶工况仿真与辅助分析平台参赛技术文档',reviewed_on=REVIEW_DATE,report_style='student')
 manifest.update({'engineVersion':ENGINE,'builderSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'pdfPolicy':'The formal PDF is a native Word export of this exact DOCX input.','sameContentSource':True})
 manifest['editorialStyle']='plain layout with all original technical content retained and expanded application detail'
 args.manifest.parent.mkdir(parents=True,exist_ok=True)
 args.manifest.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
 if file.resolve()==(OUT/'DriveLab-参赛技术文档.docx').resolve():
  (ROOT/'docs/competition/DriveLab-参赛技术文档.docx').write_bytes(file.read_bytes())
 print(json.dumps({key:value for key,value in manifest.items() if key!='blocks'},ensure_ascii=False))


if __name__=='__main__':main()
