"""Build the competition technical review draft with the bundled ReportLab runtime."""
from pathlib import Path
from xml.sax.saxutils import escape
import json
import re
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
def p(text,kind='body'):
 return Paragraph(escape(str(text)).replace('\n','<br/>'),styles[kind])
def add(text,kind='body'): story.append(p(text,kind))
def table(headers,rows,widths):
 data=[[p(v,'headcell') for v in headers]]+[[p(v,'cell') for v in row] for row in rows]
 t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),INK),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f5f7f9')]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,-1),.4,LINE)]))
 story.extend([t,Spacer(1,12)])
def page(number,title):
 story.append(PageBreak());add(f'{number:02d}  /  DRIVELAB','small');add(title,'heading')
def image(name):
 file=ROOT/'docs/competition/screenshots'/name
 if file.exists():
  from PIL import Image as PILImage
  with PILImage.open(file) as im: w,h=im.size
  story.extend([Image(str(file),width=510,height=510*h/w),Spacer(1,12)])
def footer(c,doc):
 c.setStrokeColor(LINE);c.line(42,801,553,801);c.line(42,39,553,39)
 c.setFont('NotoSC',8);c.setFillColor(MUTED)
 c.drawString(42,814,'DRIVELAB  /  ENGINEERING WITH EVIDENCE')
 c.drawString(42,25,'参赛技术文档 · 软件工程复核版 · 2026-11-16')
 c.drawRightString(553,25,str(doc.page))

add('AI WEB DEVELOPMENT  /  10037','small');story.append(Spacer(1,65))
add('DriveLab\n智能驾驶工况仿真\n与辅助分析平台','title')
add('以可复算的工程证据，连接工况设计、日志对标与 AI 解释。','sub')
story.append(Spacer(1,24))
table(['版本','状态'],[[f'产品 V1.0 / 计算引擎 {ENGINE}','软件复核与实际模型联调已完成'],['目标赛道','2026 传智杯 AI WEB 网页开发挑战赛'],['代码仓库','github.com/qiuyimei/drivelab（私有）']],[155,355])
add('当前结论','sub')
add('项目已形成工况设计、确定性计算、日志对标、免费模型工具分析、保存与中文报告的工作流。本轮复核修正低速横向模型、采样间尖峰、候选引用和报告时效问题。软件检查与可复算案例有明确记录；不把代码测试等同于实车标定或整车安全认证。')
if TEAM['confirmed']:
 add('团队：'+TEAM['teamName']+'；学校：'+TEAM['school']+'；组别：'+TEAM['group'],'small')
 add('成员：'+'；'.join(m['name']+'（'+m['role']+'）' for m in TEAM['members']),'small')
else:
 add('报名队伍名称、学校、组别、队长与实际分工尚待本人确认，统一登记于 README 与 team.json。本文不代填身份或人工签署。','small')

page(1,'问题、用户与功能闭环')
add('目标用户是参与智能驾驶前期工况设计、标定学习和数据复盘的学生团队。常见任务是反复改参数、比较数据、寻找依据并保留可追溯报告。')
table(['环节','实现行为','输出'],[
 ['工况设计','五类模板；行车、车辆、道路参数可编辑','带单位和范围的输入'],
 ['模型计算','服务端重算，显示曲线与约束检查','可复算数字和风险等级'],
 ['日志对标','清洗、换算、对齐、共同区间插值','四通道误差和缺失情况'],
 ['依据分析','资料检索；可选免费模型与受限工具','引用、执行步骤、候选重算'],
 ['记录与交付','账号隔离保存；证据 JSON；中文 PDF','参数、日志、阈值和分析快照'],
 ],[80,265,165])
add('产品定位','sub')
add('使用轻量模型快速筛查需求和约束，帮助团队解释“哪个参数导致哪个计算结果”。它不是完整自动驾驶系统，也不替代车型标定、动态车辆模型或整车安全认证。')
add('界面中的行车动画是运动学示意；紧急避障没有真实车辆外形碰撞几何、规划器或闭环跟踪器。')

page(2,'架构与数据流')
table(['层','职责','主要实现'],[
 ['浏览器','React 交互、SVG 曲线、文档正文提取、PDF 下载','app/workbench.tsx；app/ui/*'],
 ['Worker API','账号识别、输入校验、仿真、分析与 SSE','app/api/[...path]/route.ts'],
 ['确定性证据','计算时序、误差、候选参数、输入指纹','lib/simulation.ts；evidence.ts；fingerprint.ts'],
 ['检索与解释','持久化分块、混合词项检索、受限工具、引用校验','lib/rag.ts；retrieval.ts；analysis.ts'],
 ['存储与模型','D1 按 owner 隔离；免费模型通过服务端调用','Drizzle 迁移；lib/provider.ts'],
 ],[80,265,165])
add('一次分析的请求链','sub')
add('浏览器提交工况 + 日志 + 容差 + 问题 → 服务端重新计算证据 → 检索工程段落 → 可选模型调用受限工具 → 校验结构和引用 → SSE 返回步骤及结果。模型不直接执行 SQL、访问任意 URL 或改写当前工况。')
add('持久化原则','sub')
add('列表只返回记录摘要；打开记录才读取本人完整快照。保存时校验输入指纹，包含引擎版本、工况、日志和容差。参数改变后，旧分析会被标记为过期，不作为当前证据保存。')
add('技术栈：React 19、TypeScript、Vinext、Vite、Cloudflare Worker、D1、Drizzle。前后端共享纯计算模块，但服务端独立校验与复算。','small')

page(3,'物理模型、公式与适用条件')
table(['模型','公式 / 处理','适用条件'],[
 ['纵向停车','a = min(a请求, a底盘, mu*g)\ns = v0*tr + v0^2/(2a)\nt停止 = tr + v0/a','水平路面、恒减速，车速不反向'],
 ['完整跟驰','vc = max(v0-v前车, 0)\ngap最小 = d - vc*tr - vc^2/(2a)','前车恒速，不含前车制动'],
 ['稳态圆周','ay = v^2/R；r = ay/v\n方向盘角 = atan(L*ay/v^2)*传动比','低侧偏运动学近似'],
 ['五次换道','y = W*(10u^3-15u^4+6u^5)\nay = W/T^2*(60u-180u^2+120u^3)','给定轨迹需求；u 按响应后时间归一化'],
 ['附着与压力','利用率 = sqrt(ax^2+ay^2)/(mu*g)\np = abs(ax)*质量/制动力增益','摩擦圆需求检查；压力为集总估算'],
 ],[80,265,165])
add('数值与边界处理','sub')
add('内部使用 m、s、m/s 和 m/s²；车速输入/输出 km/h，横摆 °/s，方向盘 °，压力 bar。按 0.1 s 采样，窗口末段精确截止；纵向位移分段精确积分。侧向、附着与方向盘峰值为采样需求峰值，不构成连续时间极值保证；贴近阈值时需加密验证。')
add('公式中的角量使用 rad 与 rad/s；页面与日志协议的角度展示乘以 180/π 转为 ° 与 °/s。','small')
add('短显示窗口之外的完整制动间距另行解析预测。换道/避障初速低于 5 km/h 时明确拒绝；这是本软件的模型适用政策边界，不是车辆通用限值。避障降至低速且仍有横向需求时提示未完成评估，不能把未算出的转向需求当通过。变速换道仍是近似需求。')
add('默认侧向阈值、误差容差与制动增益是项目初始值，不是法规限值或经车型审核的标定值。','small')

page(4,'AI、RAG 与受限工具')
add('AI 负责解释已计算的证据、连接文档依据和提出可复算候选；确定性引擎负责数字和约束等级。未接通模型时明确显示规则分析，不用预写文本冒充联网模型。')
table(['工具','输入与行为','约束'],[
 ['inspect_simulation','读取服务端工况、风险和事实卡','不能覆盖风险等级'],
 ['compare_measurement','读取本次日志误差、偏差和覆盖范围','无日志时如实返回'],
 ['search_knowledge','根据问题检索资料分块','保留页码、段落和来源定位'],
 ['evaluate_parameters','独立重算速度/间距/响应/换道时间','白名单参数，不改附着条件，不修改基线'],
 ],[125,230,155])
add('检索实现','sub')
add('中文单字/双字与英文词项，BM25 结合 512 维稀疏词项哈希向量余弦相似度。约 700 字分块、560 字步进；索引保留 docId#cN、字符范围、PDF 页码或段落。该方法不是语义 embedding。')
add('生成校验与失败行为','sub')
add('模型最多请求 3 轮、每轮至多 4 个工具；最终输出结构化 JSON。观察和建议必须引用有效 factId 或 chunkId；拒绝不存在的引用和绝对安全承诺。额度、网络或格式失败时保留规则结果。引用标识有效不等于文字语义已被完全证明，仍需人工复核。')
add('真实模型：ModelScope 免费 API-Inference 的 Qwen/Qwen3.5-27B。已完成账号准备、本机真实工具往返及一次线上 RAG 分析。实测发现 JSON 解码兼容问题后，仅对该服务商省略解码提示，保持本地严格校验；输出有误时在剩余三次请求预算内纠正，仍失败则降级。','small')
add('默认及工具重算候选使用独立 CAND_n 事实范围，保留参数、基线指纹与结果；基线事实不被候选覆盖。检索只暴露已登记的段落。校验仍不能自动证明所有自然语言语义，关键数值需对照事实字典复核。','small')

page(5,'日志协议与公开数据')
image('public-log.jpg')
add('页面实测截图：公开实测导入示例与仿真比较。两者工况不同，图中的差异不能用于评估模型精度。','small')
table(['处理','规则'],[
 ['字段','time_s；speed_kmh；yaw_rate_dps；brake_pressure_bar；steering_angle_deg'],
 ['清洗与对齐','去无效行；时间排序；重复时间保留最后一行；首时刻归零后应用偏移'],
 ['对标','MAE/RMSE/偏差按共同区间内仿真网格等点权计算；最大误差与峰值时间在仿真、采集两网格并集计算'],
 ['缺失','缺失通道和空值不补零，区间外不外推；先检查方向盘/前轮角定义'],
 ],[85,425])

page(6,'独立验证与结果')
bench=json.loads((ROOT/'public/validation/benchmark-results.json').read_text(encoding='utf-8-sig'))
table(['验证','结果','证明范围'],[
 ['核心回归',str(VALIDATION['coreTests'])+' 项通过','计算、低速边界、短时尖峰、单位与导入'],
 ['分析回归',str(VALIDATION['analysisTests'])+' 项通过','工具往返、候选事实、引用闭包、有界纠正与降级'],
 ['独立解析参考',f"{bench['summary']['passed']} / {bench['summary']['total']}",'公式与给定轨迹边界实现一致性'],
 ['固定检索回归','12/12 Hit@3；12/12 Top1','小样本回归，不代表泛化准确率'],
 ['公开 CAN 样例','4,973 行；约 59.98 s','哈希、单位、时间轴与缺失通道'],
 ['本地 API','六组验收通过','登录门禁、误差、SSE、快照、页码、夹具清理'],
 ['界面与保存工作流','实际界面操作及五组回归通过','小屏幕入口、CSV 导入、偏移/容差/分析恢复；视口模拟不等同另一台设备'],
 ['本地数据库','新库/重复初始化/旧库升级通过','保留旧记录，迁移不会重复建表'],
 ['中文 PDF','实际下载与渲染检查','中文、公式转写、图表、分页'],
 ],[115,170,225])
add('独立参考如何避免自证','sub')
add('参考生成器不调用应用计算模块。109 组停车参考由闭式解生成，9 组弯道参考从圆周几何生成，12 组换道参考通过六个边界条件的线性方程独立求解。最大绝对数值差约 9.095e-13。')
add('这些测试不证明真实车辆的模型精度、超限后的运动、安全性或所有大模型生成质量。真实免费模型流程已有实测，但不存在受控实车数据闭环标定或工程专家签署。','small')

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
add('本轮软件工程复核覆盖公式实现、单位、边界、对标采样与证据引用；发现项、复现和回归均有记录。默认参数和阈值没有特定车型标定或专家签署。公开课程与独立解析参考仅支撑假设内的实现，不被当作车型精度证明。')

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
 ['AI 深度 / 创新','计算证据 + 日志 + RAG + 工具重算 + 来源与输入指纹','已有真实联调；自然语言语义仍需人工核对'],
 ['前端 / 体验','完整工作台、对标曲线、执行步骤、报告下载','另一设备与评审账户端到端验收'],
 ['实用性 / 社会价值','车辆工程与软件工程交叉学习、前期复盘可追溯','实际使用反馈，不编造节省时间指标'],
 ],[110,245,155])
add('建议 6 分钟演示顺序','sub')
table(['时间','演示内容'],[
 ['0:00–0:40','说明用户问题、产品定位与适用边界'],
 ['0:40–1:50','从案例创建，修改附着/速度，展示确定性约束变化'],
 ['1:50–3:00','导入日志、单位与时间对齐、缺失通道与误差'],
 ['3:00–4:30','真实免费模型工具与来源、候选独立事实、有界纠正及规则降级'],
 ['4:30–5:25','候选重算、过期分析提醒、保存与恢复'],
 ['5:25–6:00','PDF 下载、独立验证结果、局限与后续计划'],
 ],[105,405])
add('车辆工程角色审核公式、单位、参数、数据与边界；软件工程角色解释前后端、检索、工具约束、存储与测试。实际成员、学校、组别、指导教师、开发过程和分工由团队如实填写。')

page(10,'最终提交前的验收门槛')
table(['门槛','当前状态','完成条件'],[
 ['真实免费模型','已实测，有边界','实际工具/RAG 请求与来源有记录；不将单次通过等同所有问题稳定'],
 ['工程软件复核','已完成本轮检查','复现缺陷已修复并增加回归；车型参数与实车精度不在本次验收范围'],
 ['访问与运行','本地已验收；评审未验收','另一台电脑复现；安排指定评审只读权限；验证链接可访问'],
 ['提交材料','本轮制作与逐项校核','PDF ≤30 页；普通话 5–8 分钟 1080p MP4；源码与完整 Git 历史；补真实报名信息'],
 ['报名规则','待团队核对','按学校、报名后台及组委会最新要求确认资格和截止时间'],
 ],[105,140,265])
add('私有协作','sub')
add('GitHub 仓库继续 Private。所有者在 Settings → Collaborators → Add people 输入共创伙伴用户名，对方接受后协作；推荐独立分支与 Pull Request。没有自动邀请任何人，也没有将仓库或网站改为公开。')
add('交付态度','sub')
add('视频采用真实界面截图、实际计算结果与普通话合成解说剪辑，明确披露素材和配音来源；不伪装连续操作、成员亲自配音或实车实验。用户仍需能解释代码逻辑，按报名后台核准身份、评审访问和提交阶段。')

page(11,'工程复核与修复记录')
table(['复现问题','修复与针对性验证','证据范围'],[
 ['极低速横向评估','拒绝低于 5 km/h 的横向场景，低速剩余横向需求明确警告；非法候选跳过','软件适用边界，非车辆法规阈值'],
 ['采样间瞬态漏峰','36 km/h 平稳基线中，0.05 s 采集尖峰 +100 km/h；并集最大误差应为 100，不能报告全零通过','只证明对输入分段线性数据的峰值处理'],
 ['稀疏日志过度解释','报告原始采样数量、最大采样间隔；超过 1 s 时提醒；不足两个点或无共同区间不给虚构统计','1 s 为提醒政策，不是传感器合格标准'],
 ['候选和基线同名引用','独立 CAND_n 事实登记；保存候选参数和重算值；模型不能将候选值写入基线','标识闭包与可复算性，不是自动语义证明'],
 ['PDF 旧分析及证据缺失','导出时核对输入指纹；不匹配不采用旧分析；附基线事实与候选字典','报告对应本次输入，避免错配'],
 ],[105,270,135])
add('记录路径：docs/competition/FINAL-VALIDATION.json；docs/evidence/engineering-review-20261116.json；docs/evidence/analysis-review-20261116.json。','small')

page(12,'真实模型与报告交付证据')
image('final-ai.jpg')
add('真实界面与执行记录截图；模型只能基于服务端计算、日志和登记段落进行解释。截图的引擎版本与日期见画面，历史测试不会被当作新引擎实车验证。','small')
add('固定案例核对','sub')
add('100 km/h 自车、60 km/h 恒速前车、80 m 间距、0.8 s 响应、5 m/s² 减速：解析停车距离 99.3827 m，停车时间 6.3556 s，全过程最小间距 58.7654 m。停车距离大于初始间距并不直接判碰撞，因为前车持续运动。实际回答需明确未绑定测量日志。')
add('报告包含参数、时序、约束、日志口径、事实字典、候选登记、资料锚点与执行步骤；旧分析因输入或引擎版本变化失效。完整样张随材料包提供。')
add('AI 辅助开发披露','sub')
add('项目使用 Codex 辅助代码、回归、材料和配音脚本制作，并使用公开软件与数据。实际成员须对选题、代码逻辑与交付承担解释责任；拟定分工不作为已完成贡献，原创性或资格声明由本人核实后提交。')

page(13,'主要来源与工程许可')
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

file=OUT/'DriveLab-参赛技术文档.pdf'
doc=SimpleDocTemplate(str(file),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=61,bottomMargin=57,title='DriveLab 智能驾驶工况仿真与辅助分析平台参赛技术文档',author='DriveLab')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
from pypdf import PdfReader
reader=PdfReader(file)
assert len(reader.pages)<=30
assert all(len(page.extract_text().strip())>60 for page in reader.pages)
print(json.dumps({'file':str(file),'pages':len(reader.pages)},ensure_ascii=False))
