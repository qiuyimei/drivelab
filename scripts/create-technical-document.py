"""Build a plain student project report; export its formal PDF from this DOCX."""
from pathlib import Path
from io import BytesIO
import argparse
import hashlib
import importlib.util
import json
import re

from PIL import Image
from native_document import build_native_docx

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parents[1]/'outputs'
ENGINE=re.search(r"ENGINE_VERSION='([^']+)'",(ROOT/'lib/evidence.ts').read_text('utf-8')).group(1)
TEAM=json.loads((ROOT/'docs/competition/team.json').read_text('utf-8'))
VALIDATION=json.loads((ROOT/'docs/competition/FINAL-VALIDATION.json').read_text('utf-8'))
VIDEO=json.loads((ROOT/'docs/competition/VIDEO-FINAL-121.json').read_text('utf-8'))
assert VALIDATION['engineVersion']==ENGINE and VALIDATION['softwareChecksPassed']
FIGURES=json.loads((ROOT/'docs/competition/implementation-results.json').read_text('utf-8'))
spec=importlib.util.spec_from_file_location('report_figures',ROOT/'scripts/create-implementation-results.py')
figure_renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(figure_renderer)
blocks=[]


def add(text,style='body'):
    blocks.append({'type':'paragraph','text':text,'style':style})


def heading(text):
    add(text,'heading')


def sub(text):
    add(text,'sub')


def table(headers,rows,widths):
    blocks.append({'type':'table','headers':headers,'rows':rows,'widths':widths})


def picture(asset,caption):
    if asset.endswith('.jpg'):
        path=ROOT/'docs/competition/screenshots'/asset
        image=Image.open(path).convert('RGB')
    else:
        image=figure_renderer.render_figure_asset(FIGURES,asset)
    stream=BytesIO();image.save(stream,format='PNG')
    width=475
    blocks.append({'type':'image','data':stream.getvalue(),'width':width,'height':width*image.height/image.width,'source':asset})
    add(caption,'small')


add('DriveLab','title')
add('智能驾驶工况仿真与辅助分析平台','title')
add('项目说明与实现记录','sub')
add('学校：'+TEAM['school'])
add('成员：'+'、'.join(m['name'] for m in TEAM['members']))
add('负责人：'+TEAM['captain']+'    指导教师：无')
add('产品版本：V1.0    计算引擎：'+ENGINE)
add('2026年11月18日')
add('本项目把车辆工况计算、日志对比和AI辅助解释放在一个网页中。本文主要介绍做这个项目的原因、已经实现的功能、几个具体结果，以及目前还做不到的地方。')
blocks.append({'type':'page_break'})

heading('一、为什么做这个项目')
add('在整理车辆工况时，参数、计算表、采集文件和参考资料经常分散在不同地方。比如想比较“降低车速”和“增加车距”哪个更有帮助，除了算出结果，还要把前提说清楚。看日志时也一样：曲线有差异，可能先要检查单位和时间偏移，不能直接下结论。')
add('因此，我们做了DriveLab，希望把这几步放到同一套流程里：设置工况，运行计算，导入日志，结合资料分析，再保存或导出报告。主要面向车辆测试、底盘分析相关人员和小型测试团队，也可以用于车辆工程学习。')
add('项目目前是一个轻量的前期分析工具。它接收整理好的日志文件，没有直接连接车辆，也不代替专业整车仿真、车型标定或安全认证。')
sub('希望解决的三个具体问题')
add('1. 改参数以后，能够直接比较结果，而不是重新整理一遍计算表。\n2. 日志与仿真放在同一时间轴上，能看出误差、缺失通道和覆盖区间。\n3. AI解释能够对应到本次计算和资料段落，方便回头核对。')

heading('二、现在可以做什么')
add('系统提供紧急制动、跟驰制动、稳态圆周、换道和紧急避障五类模板。用户可以修改车速、响应时间、初始车距、附着条件、换道时长等参数，再查看曲线和需求检查。动画用于帮助理解运动过程，是运动学示意。')
add('首页的AI分析分成四个入口，分别对应不同问题。日志差异任务必须先导入日志；候选比较任务要实际调用参数重算工具。这样可以避免一个通用问答框把所有事情混在一起。')
picture('taskHome120','图1  四类分析任务。截图来自本机1.2.0版本；本轮1.2.1主要修复资料兼容和显示边界。')
add('常用流程是：选模板和参数 → 运行计算 → 需要时导入日志或资料 → 选择分析任务 → 核对结果 → 保存记录或导出报告。即使没有配置模型，也能使用计算、日志和规则检索功能。')

heading('三、系统是怎么实现的')
add('前端使用React和TypeScript，负责参数表单、曲线、任务入口、资料导入及结果展示。服务端在Worker中运行，负责登录检查、输入校验、重新计算、AI请求和记录读写。数据存放在D1中，不同账号的记录按owner隔离。')
table(['部分','主要工作','对应实现'],[
 ['页面','工况设置、SVG曲线、候选载入、报告下载','app/workbench.tsx、app/ui'],
 ['接口','校验请求、计算、分析和记录保存','app/api、lib/simulation.ts'],
 ['资料与AI','分块检索、工具调用、结果与引用检查','lib/rag.ts、lib/analysis.ts'],
 ['存储','工况快照、日志、资料及分析记录','D1、Drizzle迁移'],
],[70,220,185])
add('一次分析不是把屏幕上的数字直接发给模型。服务端会根据输入重新计算，整理本次事实，再检索相关资料；模型需要时调用限定工具，最后由服务端检查输出，分步返回页面。这样可以把计算结果和文字解释分开核对。')
add('保存记录时还会保存参数、日志、容差、任务及原问题。恢复后会检查分析是否仍对应这些输入。输入已经变化时，旧结果不会直接当作新的分析使用；这个检查只用于输入一致性，不是真实性签名。')

heading('四、计算模型和日志处理')
sub('1. 计算采用哪些简化')
add('纵向使用响应时间加恒减速模型；弯道使用稳态圆周关系；换道使用五次多项式轨迹。选择这些模型是为了把条件和结果讲清楚，计算量也适合在网页中运行。主要关系如下，内部统一使用米、秒及相应单位。')
table(['计算内容','采用的关系或方法'],[
 ['停车','s = v₀ × tr + v₀² / (2a)；有效减速度受请求、底盘和附着条件约束'],
 ['跟驰最小间距','前车恒速，用相对速度计算整个减速过程中的最小间距'],
 ['稳态弯道','侧向加速度 ay = v²/R；横摆角速度 r = v/R'],
 ['换道需求','给定五次轨迹，检查活动区间内的端点和驻点；低速域另作限制'],
 ['附着与压力','摩擦圆用于需求检查；制动压力是按质量和增益得到的集总估算'],
],[105,370])
add('曲线按0.1秒输出，末端精确截止。连续峰值和显示采样分开处理，避免只看网格点漏掉峰值。初始车速低于5 km/h时不接受换道或避障；这是本项目的适用范围。避障降到低速后仍有横向需求时会提醒评估不完整。')
add('模型没有包含真实轮胎非线性、坡度、载荷转移、闭环控制或真实车辆碰撞几何。默认阈值和制动增益也没有做特定车型标定。因此，页面中的需求和风险提示只能在这些前提下理解。')
sub('2. 日志怎样比较')
add('CSV至少包含时间和一个数值通道，支持速度、横摆角速度、制动压力和方向盘转角。导入时清理无效行、排序，并对重复时间保留最后一行；时间先归零，再应用偏移。空通道不会补零，区间外不外推。')
picture('public-log.jpg','图2  公开CAN样例的导入界面。它是历史界面素材，这一路段不对应图中的制动工况，差异不能作为模型精度。')
add('误差只在共同时间区间比较。MAE、RMSE和平均偏差沿用仿真网格等点权；最大误差还检查两套时间网格的并集。只有单点时也能给出点误差，但会提示不能代表持续工况。横向通道还要先确认方向盘角和前轮转角的定义。')
add('公开样例来自comma.ai官方comma2k19固定提交，共4,973行，约59.98秒，只包含速度和方向盘转角。原始数组、转换脚本、哈希与MIT许可均保留。文件名不能证明用户日志的来源，真实数据仍要单独确认。')

heading('五、AI是怎么接入的')
add('产品推理使用ModelScope免费入口上的Qwen/Qwen3.5-27B。选择它主要考虑当时可用的免费入口、中文解释需求和兼容的接口。项目没有做多个模型的横向比较，不据此声称它比其他模型更准确。')
add('AI主要负责组织解释、联系资料和提出候选。数值由计算引擎给出，模型不能直接改风险等级、执行SQL、访问任意网址或修改当前参数。可以调用的工具只有四类：')
table(['工具','在项目里做什么'],[
 ['inspect_simulation','读取本次工况和已计算事实'],
 ['compare_measurement','读取日志误差和覆盖情况'],
 ['search_knowledge','查找资料中登记的段落'],
 ['evaluate_parameters','只修改允许的参数，独立重算候选'],
],[165,310])
sub('资料检索与输出检查')
add('PDF、Word或文本导入后，大约每700字分块，步进560字，并保留页码或段落位置。检索采用BM25和512维稀疏词项向量，属于词项检索，不是语义embedding。它把与当前问题相关的段落交给分析流程，避免把整份资料都塞进上下文。')
add('模型最多请求3轮，每轮最多4个工具。最终返回结构化JSON，观察和建议必须关联已登记的计算事实或资料段落。格式或引用出错时，在剩余次数内给出限长诊断；连续失败则显示规则结果。引用编号存在、步骤执行完，并不表示每句话的意思都已经正确。')
add('候选会保留修改项、基线和计算结果。点击“载入候选”只是填写参数，仍需单独运行，原日志随后解除绑定。这样用户可以先比较，再决定是否采用。')

heading('六、两个具体例子')
sub('例子1：停车距离大于初始车距，就一定追尾吗')
add('设自车100 km/h、前车60 km/h且保持恒速，初始间距80 m，响应时间0.8 s，请求减速度5 m/s²。本模型计算的停车距离为99.3827 m，停车时间6.3556 s，全过程最小间距58.7654 m。')
add('停车距离虽然大于80 m，也不能直接判断追尾，因为前车还在向前运动。这个例子用来说明“停车距离”和“最小相对间距”的区别，不是实车测试结果。如果前车也制动，需要换用相应模型。')
sub('例子2：把换道时间从5秒延长到6.25秒')
picture('toolCandidate120','图3  实际工具生成的候选卡。1.2.0初次T06记录中的候选被保留，文字回答随后因引用问题降级。')
add('该候选只把换道时长从5 s改为6.25 s，车速90 km/h、响应时间0.8 s及其余输入保持。侧向需求从约0.81降到0.52 m/s²，方向盘需求从约3.11降到1.99°。这些是给定轨迹下的需求比较，不代表真实车辆的最终表现。')
add('初次记录实际调用了工具，但3次请求后因引用错误转为规则结果。之后另一次同题定向回归用3次请求得到接收回答，主要数值和修改项核对一致；局部文字的引用支持仍有限。这一次成功没有替换原来的失败，也没有当作整批评测重新运行。')

heading('七、做过哪些测试和修改')
add('本轮软件引擎为'+ENGINE+'。计算和分析用自动回归检查；接口测试在独立本机数据库中使用临时夹具，检查结束后清理。主要结果如下：')
table(['检查内容','本轮结果'],[
 ['功能与边界','41项核心、40项分析；8组保存恢复、7组导入/曲线、4组旧资料兼容通过'],
 ['数值与检索','130项独立解析参考通过，最大绝对差约9.095×10⁻¹³；12条固定检索回归通过'],
 ['接口与数据库','14项接口通过；新库、重复启动、旧库升级及记录保留通过'],
 ['工程检查','类型检查、零警告代码检查、官方生产构建通过；大分块和图标优化提示保留'],
],[105,370])
add('独立参考没有直接调用应用计算模块：停车用闭式解，弯道用圆周几何，换道从边界条件另行求解。它检查的是这些公式的实现，不是实车精度。12条检索题也只是固定小样本，不能称为通用准确率。')
add('本轮主要补了几类问题：跨窗口线段没有端点落在窗口内时仍要显示；新资料的章节名称必须是限长字符串；旧资料的异常标签在读取时兼容；PDF失败或被拒绝后也要释放解析资源。读取兼容没有迁移用户数据库，曲线显示修复也没有改变误差统计方法。')
sub('真实模型试用的结果')
add('已有1.2.0记录中，预选6个固定任务实际调用模型14次，5个回答被接收、1个降级。另有8个离线任务，在3种软件变体上核对24项参考，共72次断言；这些不是72道独立问题，也不是模型准确率。原始失败、源码版本和单题回归都保留在仓库中。')
add('目前没有真实用户节省时间的对照数据，也没有车型标定或企业验收结论。测试数量、回答被接收和工具步骤齐全，都不能代替这些验证。')

heading('八、怎样运行和查看结果')
add('运行需要Node.js 24和pnpm 11.25.0。在有权限的情况下克隆仓库后，先安装依赖并初始化本地数据库，再启动页面：')
add('git clone https://github.com/qiuyimei/drivelab.git\ncd drivelab\npnpm install --frozen-lockfile\npnpm run db:local\npnpm run dev','small')
add('本机地址为127.0.0.1:5173。可以先选工况运行，再导入样例，使用规则与检索模式，检查保存、恢复和PDF。真实模型需要合法配置的服务端凭证；密钥不放在源码或材料里，也不会自动切到付费模型。')
picture('taskReport120','图4  另一次T06成功记录导出的任务表。显示步骤和结果，不能把“已具备”理解为实车或文字语义验收。')
add('保存和报告保留任务、原问题、参数、时序、日志口径及引用。用户可以据此说明分析是基于哪些条件得到的，而不只是拿到一段结论。')
add('本轮演示视频为7分43.833秒、1920×1080，采用实际界面截图、结果和96句本机离线普通话配音剪辑。四任务与模型案例保留1.2.0版本，基础流程另标历史素材；它不是连续操作录屏，也不是本轮新增模型调用。')

heading('九、项目分工、特点和下一步')
table(['成员','专业','主要分工'],[
 [m['name'],m['discipline'],m['role']] for m in TEAM['members']
],[65,85,325])
add('开发中使用AI辅助，相关代码和材料通过测试、核对后纳入版本记录。团队需要能够说明系统架构、关键代码和模型假设。')
sub('这个项目的特点')
add('技术上，项目把服务端计算、资料检索、受限工具和候选重算连在一起，尽量让解释能够回到具体输入与依据。应用上，把工况设计、日志复盘和报告整理放到一个工作台，减少在多个文件之间切换。这些是面向具体流程的实现改进，不是新的物理算法。')
sub('目前不足和后续计划')
add('目前的物理模型还比较简化，默认参数没有特定车型标定；资料检索题和真实模型试用题都不多，引用与文字也需要继续人工核对。下一步应先补车型参数依据、同工况实测数据和更多问题，再做真实用户试用。3D和车辆硬件接入暂不纳入本轮。')

heading('参考资料与项目记录')
add('以下资料用于理解公式、模型假设和第三方数据。课程资料不是车型审核结论；公开样例和字体许可随仓库保留。','small')
references=[
 ('UIUC：停车距离课程','https://courses.grainger.illinois.edu/ece101/fa2025/lectures/101-024-autonomous-driving.pdf'),
 ('UCSD：车辆动力学与摩擦圆资料','https://cseweb.ucsd.edu/classes/sp19/cse291-d/Files/CSE291_14_VehicleDynamics.pdf'),
 ('CMU Snider：车辆路径跟踪方法','https://publications.ri.cmu.edu/storage/publications/pub_files/2009/2/Automatic_Steering_Methods_for_Autonomous_Automobile_Path_Tracking.pdf'),
 ('PythonRobotics：五次轨迹实现','https://github.com/AtsushiSakai/PythonRobotics/tree/master/PathPlanning/QuinticPolynomialsPlanner'),
 ('comma.ai：comma2k19数据与MIT许可','https://github.com/commaai/comma2k19'),
 ('ModelScope：API-Inference文档','https://modelscope.cn/docs/model-service/API-Inference/intro'),
]
for name,url in references:add(name+'\n'+url,'small')
add('项目仓库：https://github.com/qiuyimei/drivelab（保持私有）。软件检查、原始模型记录和T06回归说明保留在仓库的docs目录。','small')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUT/'DriveLab-参赛技术文档.docx')
    parser.add_argument('--manifest',type=Path,default=ROOT/'.sites-runtime/technical-native/build-manifest.json')
    args=parser.parse_args()
    manifest=build_native_docx(blocks,args.output,title='DriveLab 智能驾驶工况仿真与辅助分析平台',reviewed_on=VALIDATION['reviewedOn'],report_style='student')
    manifest.update({'engineVersion':ENGINE,'builderSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'sameContentSource':True,'editorialStyle':'plain student project report; no English branding or audit-style page panels','pdfPolicy':'Formal PDF exported from this exact editable DOCX.'})
    args.manifest.parent.mkdir(parents=True,exist_ok=True)
    args.manifest.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf-8',newline='\n')
    print(json.dumps({k:v for k,v in manifest.items() if k!='blocks'},ensure_ascii=False))


if __name__=='__main__':main()
