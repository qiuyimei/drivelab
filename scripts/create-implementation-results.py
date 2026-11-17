"""Build the detailed implementation/results DOCX with real, labelled images.

Use the bundled Python and --draft before release content is frozen. The source
development DOCX is retained unchanged; only the new output is written.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from io import BytesIO
import hashlib
import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from docx import Document
from docx.shared import Inches
from lxml import etree
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT/'scripts/create-project-explanation.py'
spec = importlib.util.spec_from_file_location('project_doc_components', HELPER)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
W, NS = base.W, base.NS
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG_R = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
DOCX_NAME = 'DriveLab 智能驾驶工况仿真与辅助分析 Web 平台 V1.0 软件实现与成果说明书.docx'


def paragraph(text, *, lead=None, style='Normal', before=0, after=100):
    return base.paragraph(text, style, before=before, after=after, bold_lead=lead)


def heading(text, *, new_page=False):
    return base.paragraph(text, 'Heading1', before=180, after=140, page_break=new_page)


def subheading(text):
    node = base.paragraph(text, 'Heading2', before=140, after=80)
    node.find('w:pPr', NS).append(base.element('keepNext'))
    return node


def table(columns, rows, widths):
    node = base.element('tbl')
    props = base.element('tblPr')
    props.append(base.element('tblW', w=sum(widths), type='dxa'))
    props.append(base.element('tblLayout', type='fixed'))
    borders = base.element('tblBorders')
    for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        borders.append(base.element(side, val='single', sz=4, color='D9D9D9'))
    props.append(borders)
    margins = base.element('tblCellMar')
    for side, size in [('top', 90), ('bottom', 90), ('left', 110), ('right', 110)]:
        margins.append(base.element(side, w=size, type='dxa'))
    props.append(margins)
    node.append(props)
    grid = base.element('tblGrid')
    for width in widths:
        grid.append(base.element('gridCol', w=width))
    node.append(grid)
    for index, values in enumerate([columns, *rows]):
        row = base.element('tr')
        rprops = base.element('trPr')
        rprops.append(base.element('cantSplit'))
        if index == 0:
            rprops.append(base.element('tblHeader'))
        row.append(rprops)
        for col, (width, value) in enumerate(zip(widths, values)):
            cell = base.element('tc')
            cprops = base.element('tcPr')
            cprops.append(base.element('tcW', w=width, type='dxa'))
            cprops.append(base.element('vAlign', val='center'))
            if index == 0:
                cprops.append(base.element('shd', fill='EDEDED'))
            cell.append(cprops)
            p = paragraph(str(value), after=0)
            for run in p.findall('w:r', NS):
                run.insert(0, base.font_properties(20, index == 0))
            if col == 0 or len(columns) == 5:
                p.find('w:pPr', NS).append(base.element('jc', val='center'))
            cell.append(p)
            row.append(cell)
        node.append(row)
    return node


class Builder:
    def __init__(self, content, reference, output, draft=False):
        self.content, self.reference, self.output = content, reference, output
        self.draft = draft
        with ZipFile(reference) as archive:
            self.parts = {item.filename: archive.read(item.filename) for item in archive.infolist()}
        self.document = etree.fromstring(self.parts['word/document.xml'])
        self.body = self.document.find('w:body', NS)
        self.section = deepcopy(self.body.find('w:sectPr', NS))
        for child in list(self.body):
            self.body.remove(child)
        self.relationships = etree.fromstring(self.parts['word/_rels/document.xml.rels'])
        self.types = etree.fromstring(self.parts['[Content_Types].xml'])
        self.figures = []

    def add(self, node):
        self.body.append(node)

    def text(self, value, **kwargs):
        self.add(paragraph(value, **kwargs))

    def page(self, title):
        self.add(heading(title, new_page=True))

    def figure(self, asset_id, *, max_height=3.2, crop=None, caption=None):
        asset = self.content['assets'][asset_id]
        max_height = asset.get('maxHeight', max_height)
        path = ROOT/asset['path']
        if not path.exists():
            if self.draft:
                return
            raise FileNotFoundError(path)
        original_bytes = path.read_bytes()
        image = Image.open(BytesIO(original_bytes)).convert('RGB')
        crop = crop or asset.get('crop')
        panels = asset.get('panels')
        if panels:
            pieces = [image.crop(tuple(rect)) for rect in panels]
            columns = asset.get('panelColumns', 2)
            cell_width = max(piece.width for piece in pieces)
            cell_height = max(piece.height for piece in pieces)
            gap = 12
            rows = (len(pieces) + columns - 1)//columns
            if columns == 1:
                image = Image.new('RGB', (cell_width,sum(piece.height for piece in pieces)+(len(pieces)-1)*gap), 'white')
                position = 0
                for piece in pieces:
                    image.paste(piece,(0,position))
                    position += piece.height + gap
            elif rows == 1:
                image = Image.new('RGB', (sum(piece.width for piece in pieces)+(len(pieces)-1)*gap,cell_height), 'white')
                position = 0
                for piece in pieces:
                    image.paste(piece,(position,0))
                    position += piece.width + gap
            else:
                image = Image.new('RGB', (columns*cell_width+(columns-1)*gap, rows*cell_height+(rows-1)*gap), 'white')
                for index, piece in enumerate(pieces):
                    image.paste(piece, ((index%columns)*(cell_width+gap), (index//columns)*(cell_height+gap)))
        elif crop:
            image = image.crop(tuple(crop))
        stream = BytesIO()
        image.save(stream, format='PNG')
        value = stream.getvalue()
        width = min(6.2, max_height*image.width/image.height)
        scratch = Document()
        shape = scratch.add_paragraph().add_run().add_picture(BytesIO(value), width=Inches(width))
        inline = deepcopy(shape._inline)
        number = len(self.figures) + 1
        rel_id = 'rIdImplementationImage' + str(number)
        media = f'implementation-results-{number}.png'
        for node in inline.iter():
            if node.tag == '{http://schemas.openxmlformats.org/drawingml/2006/main}blip':
                node.set('{' + R + '}embed', rel_id)
        docprops = inline.find('{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr')
        docprops.set('id', str(500 + number))
        docprops.set('name', 'DriveLab actual result ' + str(number))
        docprops.set('descr', caption or asset['caption'])
        p = paragraph('', before=70, after=70)
        p.find('w:pPr', NS).append(base.element('jc', val='center'))
        p.find('w:pPr', NS).append(base.element('keepNext'))
        drawing = base.element('drawing')
        drawing.append(inline)
        p.find('w:r', NS).append(drawing)
        self.add(p)
        self.add(paragraph(f'图{number} ' + (caption or asset['caption']), style='Caption', after=110))
        self.parts['word/media/' + media] = value
        rel = etree.SubElement(self.relationships, '{' + PKG_R + '}Relationship')
        rel.set('Id', rel_id)
        rel.set('Type', R + '/image')
        rel.set('Target', 'media/' + media)
        if self.types.find(f'{{{CT}}}Default[@Extension="png"]') is None:
            new_type = etree.SubElement(self.types, '{' + CT + '}Default')
            new_type.set('Extension', 'png')
            new_type.set('ContentType', 'image/png')
        self.figures.append({'number': number, 'assetId': asset_id, 'source': str(path.relative_to(ROOT)), 'sourceSha256': hashlib.sha256(original_bytes).hexdigest(), 'engineVersion': asset['engineVersion'], 'dataKind': asset['dataKind'], 'caption': caption or asset['caption'], 'crop': crop, 'panels': panels, 'displayWidthInches': width, 'displayHeightInches': width*image.height/image.width})

    def module(self, module, number):
        self.page(f'{number} {module["name"]}')
        self.add(subheading('原要求与当前实现'))
        self.text(module['originalRequirement'])
        self.text(module['implementation'])
        self.add(subheading('操作与输入输出'))
        for i, step in enumerate(module['steps'], 1):
            self.text(f'{i} {step}', after=65)
        self.text(module['input'], lead='输入  ', after=65)
        self.text(module['output'], lead='输出  ', after=75)
        self.add(subheading('实际界面与效果'))
        self.text(module['effect'], after=70)
        included = module['figureIds'][:1] if module.get('workedDetail') else module['figureIds']
        for asset_id in included:
            self.figure(asset_id, max_height=2.1 if len(module['figureIds']) > 1 else 3.0)
        if module.get('workedDetail'):
            detail = module['workedDetail']
            self.page(detail['title'])
            for text in detail['paragraphs']:
                self.text(text)
            for asset_id in module['figureIds'][1:]:
                self.figure(asset_id, max_height=2.8)

    def write(self):
        c = self.content
        self.add(paragraph(c['title'], style='Title', after=240))
        self.text('产品 V1.0  计算引擎 ' + c['engineVersion'], after=180)
        for text in c['overview']:
            self.text(text)
        self.add(subheading('说明书的阅读方式'))
        for text in c['readerGuide']:
            self.text(text)
        self.figure(c.get('overviewFigureId', 'lane'), max_height=2.65)

        self.page('一 使用对象与完整流程')
        for audience in c['audience']:
            self.add(subheading(audience['role']))
            self.text(audience['need'] + audience['use'])
        self.add(subheading('从问题到报告'))
        for i, step in enumerate(c['workflow'], 1):
            self.text(f'{i} {step}')

        self.page('二 系统架构与数据流')
        self.text(c['architecture']['intro'])
        self.add(table(['层次', '当前组成', '承担的工作'], c['architecture']['layers'], [1400, 2350, 5250]))
        self.add(subheading('主要数据流'))
        for text in c['architecture']['flows']:
            self.text(text)
        self.text(c['architecture']['implementationFiles'])

        numbers = ['三','四','五','六','八','九','十','十一','十二']
        for i, module in enumerate(c['modules']):
            self.module(module, numbers[i])
            if module['id'] == 'M4':
                self.page('七 AI 工具与候选比较')
                for text in c['aiDetail']['paragraphs']:
                    self.text(text)
                self.add(table(['工具作用', '返回内容'], c['aiDetail']['tools'], [2200, 6800]))
                self.add(subheading('模型结果的阅读方式'))
                self.text(c['aiDetail'].get('evidenceNote', c['aiDetail']['historyCaption']))
                self.figure(c['aiDetail'].get('figureId', 'ai112'), max_height=2.8)
                if c['aiDetail'].get('secondaryFigureId'):
                    detail = c['aiDetail']['workedDetail']
                    self.page(detail['title'])
                    for text in detail['paragraphs']:
                        self.text(text)
                    self.add(table(detail['columns'], detail['rows'], [3800,2600,2600]))
                    self.add(subheading('实际解释与引用'))
                    self.figure(c['aiDetail']['secondaryFigureId'], max_height=2.8)

        self.page('十三 ' + c['caseStudy']['title'])
        self.text(c['caseStudy']['intro'])
        self.add(table(c['caseStudy']['columns'], c['caseStudy']['rows'], [1400, 1750, 1650, 1900, 2300]))
        self.add(subheading('如何解释比较结果'))
        for text in c['caseStudy']['observations']:
            self.text(text)
        self.add(subheading('本流程形成的成果'))
        self.text(c['caseStudy']['deliverables'])
        if 'caseCurrent' in c['assets']:
            self.figure('caseCurrent', max_height=2.8)

        self.page('十四 当前范围与后续计划')
        self.text(c['scopeAndPlans']['current'])
        self.add(subheading('当前适用范围'))
        for title, text in c['scopeAndPlans']['boundaries']:
            self.text(text, lead=title + '  ')
        self.add(subheading('后续计划'))
        self.add(table(['方向', '计划内容'], c['scopeAndPlans']['plans'], [2000, 7000]))
        self.text(c['scopeAndPlans']['conclusion'], before=120)

        self.body.append(self.section)
        self.parts['word/document.xml'] = base.xml_bytes(self.document)
        self.parts['word/_rels/document.xml.rels'] = base.xml_bytes(self.relationships)
        self.parts['[Content_Types].xml'] = base.xml_bytes(self.types)
        styles = etree.fromstring(self.parts['word/styles.xml'])
        for identifier, name, size, bold in [('Normal','Normal',22,False),('Title','Title',36,True),('Heading1','heading 1',32,True),('Heading2','heading 2',24,True),('Caption','Caption',19,False)]:
            base.set_style(styles, identifier, name, size, bold)
        styles.find('w:style[@w:styleId="Heading2"]/w:pPr', NS).append(base.element('outlineLvl', val=1))
        self.parts['word/styles.xml'] = base.xml_bytes(styles)
        for name in ['word/footer1.xml','word/footer2.xml','word/footer3.xml']:
            footer = etree.fromstring(self.parts[name])
            for child in list(footer):
                footer.remove(child)
            p = paragraph('DriveLab 软件实现与成果说明书  ', style='Caption', after=0)
            p.find('w:pPr', NS).append(base.element('jc', val='right'))
            field = base.element('fldSimple', instr=' PAGE ')
            run = base.element('r')
            run.append(base.font_properties(18))
            text = base.element('t')
            text.text = '1'
            run.append(text)
            field.append(run)
            p.append(field)
            footer.append(p)
            self.parts[name] = base.xml_bytes(footer)
        core = etree.fromstring(self.parts['docProps/core.xml'])
        namespaces = {'dc': 'http://purl.org/dc/elements/1.1/', 'cp': 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties'}
        for tag, value in [('dc:title',c['title']),('dc:creator','DriveLab'),('cp:lastModifiedBy','DriveLab')]:
            node = core.find(tag, namespaces)
            if node is not None:
                node.text = value
        self.parts['docProps/core.xml'] = base.xml_bytes(core)
        app = etree.fromstring(self.parts['docProps/app.xml'])
        app_ns = {'ep':'http://schemas.openxmlformats.org/officeDocument/2006/extended-properties'}
        for child in list(app):
            if etree.QName(child).localname in ('Words','Characters','CharactersWithSpaces','Paragraphs','TotalTime','Pages'):
                app.remove(child)
        app.find('ep:Application', app_ns).text = 'DriveLab document builder'
        self.parts['docProps/app.xml'] = base.xml_bytes(app)
        custom = etree.fromstring(self.parts['docProps/custom.xml'])
        for child in list(custom):
            custom.remove(child)
        self.parts['docProps/custom.xml'] = base.xml_bytes(custom)
        self.output.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(self.output, 'w', compression=ZIP_DEFLATED) as archive:
            for name, value in self.parts.items():
                archive.writestr(name, value)
        if not self.draft:
            (ROOT/'docs/competition/DriveLab-软件实现与成果说明书.docx').write_bytes(self.output.read_bytes())
        return self.figures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--content', type=Path, default=ROOT/'docs/competition/implementation-results.json')
    parser.add_argument('--reference', type=Path, required=True, help='Retained original development DOCX; its source hash is checked.')
    parser.add_argument('--output', type=Path, default=ROOT.parents[1]/'outputs'/DOCX_NAME)
    parser.add_argument('--manifest', type=Path, default=ROOT/'.sites-runtime/implementation-results/build-manifest.json')
    parser.add_argument('--draft', action='store_true')
    args = parser.parse_args()
    original = args.reference.read_bytes()
    assert hashlib.sha256(original).hexdigest() == base.REFERENCE_SHA256
    content = json.loads(args.content.read_text(encoding='utf-8'))
    assert len(content['modules']) == 9
    if not args.draft and not content.get('finalized'):
        raise ValueError('Content/version/assets must be frozen before the final build; use --draft for preparation.')
    figures = Builder(content, args.reference, args.output, args.draft).write()
    assert args.reference.read_bytes() == original
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest = {'output':str(args.output),'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),'bytes':args.output.stat().st_size,'draft':args.draft,'engineVersion':content['engineVersion'],'referenceSha256':base.REFERENCE_SHA256,'referenceUnchanged':True,'figures':figures,'contentSha256':hashlib.sha256(args.content.read_bytes()).hexdigest()}
    args.manifest.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in manifest.items() if k!='figures'},ensure_ascii=False))


if __name__ == '__main__':
    main()
