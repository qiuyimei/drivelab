"""Create a private editable checklist, excluded from the submission ZIP."""
from pathlib import Path
import argparse
import hashlib
import json
import re

from native_document import build_native_docx

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parents[1]/'outputs'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUT/'DriveLab-最终修改核对单.docx')
    parser.add_argument('--manifest',type=Path,default=ROOT/'.sites-runtime/final-checklist/build-manifest.json')
    args=parser.parse_args()
    validation=json.loads((ROOT/'docs/competition/FINAL-VALIDATION.json').read_text(encoding='utf-8'))
    engine=re.search(r"ENGINE_VERSION='([^']+)'",(ROOT/'lib/evidence.ts').read_text(encoding='utf-8')).group(1)
    assert validation['engineVersion']==engine and validation['softwareChecksPassed'],'Final current-engine software validation is required'
    technical=json.loads((ROOT/f"docs/competition/TECHNICAL-PDF-QA-{engine.replace('.','')}.json").read_text(encoding='utf-8'))
    assert technical['finalized'] and technical['sameContentSource'] and technical['nativeEditable']
    video=json.loads((ROOT/'docs/competition/VIDEO-FINAL-121.json').read_text('utf-8'))
    blocks=[]
    def add(text,style='body'):blocks.append({'type':'paragraph','text':text,'style':style})
    add('DriveLab 最终修改核对单','title')
    add('个人核对用  不放入提交 ZIP','sub')
    add('本单记录本轮实际修改和最终交付范围。技术 Word 与 PDF 为同一内容；正式ZIP仅含PDF、MP4和仓库链接TXT。报名、缴费及评审账号设置按要求未处理；3D与硬件未纳入。个人核对项保持未勾选。')
    add('这次修改了什么','heading')
    add('跨窗口日志曲线','sub')
    add('浏览器图与报告 PDF 共用窗口裁边插值：日志线段即使两个原始点都在窗口外，跨越窗口的部分仍可显示；有效负值纳入纵轴。裁边仅影响显示，不改变 MAE、RMSE、最大误差或采样口径。')
    add('资料分段输入与解析清理','sub')
    add('新导入拒绝非字符串或超过200字符的章节名称。旧索引读取时规范异常页码/章节标签，跳过无效分段并保留可用正文；不迁移数据库或改写原文、向量及有效定位。PDF成功、失败或拒绝均释放解析资源。')
    add('报告内容与分工','sub')
    add('正文统一使用中性的 AI辅助开发表述，不替换为未用过的工具，不写少量、百分比或人工独立完成比例。保留负责人独立身份字段与三人职责分配，删除职责末尾的负责人主责括注。技术 Word 使用原生文字、表格和实际截图，PDF由同一份 Word 导出。')
    add('根据最新意见，仅将报告版式改得朴素自然。原有117段技术内容、17张表和4组原图完整保留；另加应用流程、降速与增距比较、日志偏差、资料核对和报告复盘细节。去掉英文页眉口号和深色表头，不扩展软件功能。')
    add('验证依据与范围','sub')
    add(f"引擎 {engine}：{validation['coreTests']} 项核心、{validation['analysisTests']} 项分析、8组保存恢复、7组导入/曲线、4组旧资料兼容、130项独立参考及14项独立接口验收通过；类型、零警告代码检查、独立数据库与生产构建通过。完整范围见 FINAL-VALIDATION.json；不构成实车精度、车辆安全认证或通用AI语义准确率。")
    add('视频核验','sub')
    seconds=video['format']['durationSeconds']
    add(f'本轮视频1920×1080、{int(seconds//60)}分{seconds%60:.3f}秒，加入四任务、工具候选、事实与任务报告；96句本机离线普通话配音及逐句字幕。历史1.2.0模型成功与降级均保留，不冒充新调用或连续录屏。')
    blocks.append({'type':'page_break'})
    add('本人最终检查','heading')
    add('请逐项查看后自行勾选；需修改时先编辑技术 Word，再重新导出 PDF。以下空白项不属于软件测试结果。')
    checks=[
        ('两张要求图片','[ ] 已逐项对照本人提供的两张要求图片，确认交付材料、名称和提交方式符合实际要求。'),
        ('身份与职责','[ ] 学校、三位成员、专业、负责人身份与职责分配准确。'),
        ('可编辑与内容一致','[ ] 已在 Word 中试选正文和表格进行编辑；PDF 与该 Word 同内容。手工修改后已重新导出并检查页数、图片和分页。'),
        ('视频观看','[ ] 已完整播放新版视频，检查声音、字幕与画面；理解历史素材与真实模型结果的范围。'),
        ('提交文件','[ ] 已确认最终提交 ZIP 的三项内容与报名要求一致；本核对单和技术 Word 单独留存，不装入提交 ZIP。'),
        ('产品边界','[ ] 已理解这是简化需求计算与文件日志复盘原型，没有直接控制车辆、完整仿真替代或实车标定验收结论；AI引用有效不等于全部语义正确。'),
    ]
    for title,text in checks:add(title,'sub');add(text)
    add('核对人：________________     日期：________________','sub')
    output=args.output
    manifest=build_native_docx(blocks,output,title='DriveLab 最终修改核对单',reviewed_on=validation['reviewedOn'],report_style='student')
    manifest.update({'engineVersion':validation['engineVersion'],'excludedFromSubmissionZip':True,'builderSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    target=args.manifest
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in manifest.items() if k!='blocks'},ensure_ascii=False))


if __name__=='__main__':main()
