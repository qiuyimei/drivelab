"""Create the product explanation DOCX from the retained development reference.

Run with the bundled Python. Rendering is a separate QA step; no Office or
network process is started by this builder.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_SHA256 = '201e1b05c744aebb00ebea950e3a43c60d3d2f8973b128e153a8e190fc88df79'
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}


def element(name: str, **attrs):
    node = etree.Element(f'{{{W}}}{name}')
    for key, value in attrs.items():
        node.set(f'{{{W}}}{key}', str(value))
    return node


def font_properties(size=22, bold=False):
    props = element('rPr')
    props.append(element('rFonts', ascii='Arial', hAnsi='Arial', eastAsia='等线', cs='Arial'))
    if bold:
        props.append(element('b'))
    props.append(element('color', val='000000'))
    props.append(element('sz', val=size))
    return props


def paragraph(text: str, style='Normal', *, before=0, after=100, bold_lead=None, page_break=False):
    p = element('p')
    props = element('pPr')
    props.append(element('pStyle', val=style))
    props.append(element('spacing', before=before, after=after, line=288, lineRule='auto'))
    props.append(element('widowControl'))
    if style in ('Title', 'Heading1'):
        props.append(element('keepNext'))
    if page_break:
        props.append(element('pageBreakBefore'))
    p.append(props)
    parts = [(text, False)] if not bold_lead else [(bold_lead, True), (text, False)]
    for value, bold in parts:
        run = element('r')
        if bold:
            run.append(font_properties(bold=True))
        t = element('t')
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        t.text = value
        run.append(t)
        p.append(run)
    return p


def heading(text: str, *, page_break=False):
    return paragraph(text, 'Heading1', before=180, after=120, page_break=page_break)


def numeric_table(columns, rows):
    table = element('tbl')
    props = element('tblPr')
    props.append(element('tblW', w=9000, type='dxa'))
    props.append(element('tblLayout', type='fixed'))
    borders = element('tblBorders')
    for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        borders.append(element(side, val='single', sz=4, color='D9D9D9'))
    props.append(borders)
    margins = element('tblCellMar')
    for side, width in [('top', 100), ('bottom', 100), ('left', 100), ('right', 100)]:
        margins.append(element(side, w=width, type='dxa'))
    props.append(margins)
    table.append(props)
    widths = [1540, 1720, 1620, 1880, 2240]
    grid = element('tblGrid')
    for width in widths:
        grid.append(element('gridCol', w=width))
    table.append(grid)
    for row_index, values in enumerate([columns, *rows]):
        row = element('tr')
        row_props = element('trPr')
        row_props.append(element('cantSplit'))
        if row_index == 0:
            row_props.append(element('tblHeader'))
        row.append(row_props)
        for width, text in zip(widths, values):
            cell = element('tc')
            cell_props = element('tcPr')
            cell_props.append(element('tcW', w=width, type='dxa'))
            cell_props.append(element('vAlign', val='center'))
            if row_index == 0:
                cell_props.append(element('shd', fill='EDEDED'))
            cell.append(cell_props)
            p = paragraph(text, after=0)
            p.find('w:pPr', NS).append(element('jc', val='center'))
            for run in p.findall('w:r', NS):
                run.insert(0, font_properties(size=20, bold=row_index == 0))
            cell.append(p)
            row.append(cell)
        table.append(row)
    return table


def set_style(styles, identifier, name, size, bold=False):
    existing = styles.find(f'w:style[@w:styleId="{identifier}"]', NS)
    if existing is not None:
        styles.remove(existing)
    style = element('style', type='paragraph', styleId=identifier)
    style.append(element('name', val=name))
    if identifier != 'Normal':
        style.append(element('basedOn', val='Normal'))
        style.append(element('next', val='Normal'))
    style.append(element('qFormat'))
    props = element('pPr')
    props.append(element('spacing', line=288, lineRule='auto'))
    if identifier in ('Title', 'Heading1'):
        props.append(element('keepNext'))
        if identifier == 'Heading1':
            props.append(element('outlineLvl', val=0))
    style.append(props)
    style.append(font_properties(size=size, bold=bold))
    styles.append(style)


def xml_bytes(root):
    return etree.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)


def build(reference: Path, content_file: Path, output: Path):
    reference_bytes = reference.read_bytes()
    if hashlib.sha256(reference_bytes).hexdigest() != REFERENCE_SHA256:
        raise ValueError('Reference changed; inspect and distill it before authoring.')
    content = json.loads(content_file.read_text(encoding='utf-8'))
    assert len(content['functions']) == 9 and len(content['boundaries']) == 3
    with ZipFile(reference) as archive:
        parts = {item.filename: archive.read(item.filename) for item in archive.infolist()}
    document = etree.fromstring(parts['word/document.xml'])
    body = document.find('w:body', NS)
    section = deepcopy(body.find('w:sectPr', NS))
    for child in list(body):
        body.remove(child)
    body.append(paragraph(content['title'], 'Title', after=240))
    body.append(heading('一 项目全称'))
    body.append(paragraph(content['projectName'] + '  V1.0'))
    body.append(heading('二 项目简介'))
    for text in content['introduction']:
        body.append(paragraph(text))
    body.append(heading('三 面向对象与需求'))
    for text in content['audienceAndNeeds']:
        body.append(paragraph(text))
    body.append(heading('四 设计思路'))
    for text in content['designApproach']:
        body.append(paragraph(text))
    body.append(heading('五 主要功能', page_break=True))
    for index, feature in enumerate(content['functions'], 1):
        body.append(paragraph(feature['description'], before=60, after=150, bold_lead=f'{index} {feature["name"]}  '))
    body.append(heading('六 典型使用流程', page_break=True))
    for index, text in enumerate(content['workflow'], 1):
        body.append(paragraph(f'{index} {text}', after=90))
    example = content['example']
    body.append(paragraph(example['assumptions'], before=60, after=110))
    body.append(numeric_table(example['columns'], example['rows']))
    body.append(paragraph(example['interpretation'], before=110, after=100))
    body.append(heading('七 当前实现与边界'))
    body.append(paragraph(content['currentImplementation']))
    for boundary in content['boundaries']:
        body.append(paragraph(boundary['description'], bold_lead=boundary['name'] + '  ', after=100))
    body.append(section)
    parts['word/document.xml'] = xml_bytes(document)
    styles = etree.fromstring(parts['word/styles.xml'])
    set_style(styles, 'Normal', 'Normal', 22)
    set_style(styles, 'Title', 'Title', 36, True)
    set_style(styles, 'Heading1', 'heading 1', 32, True)
    parts['word/styles.xml'] = xml_bytes(styles)
    core = etree.fromstring(parts['docProps/core.xml'])
    namespaces = {'dc': 'http://purl.org/dc/elements/1.1/', 'cp': 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties'}
    for tag, value in [('dc:title', content['title']), ('dc:creator', 'DriveLab'), ('cp:lastModifiedBy', 'DriveLab')]:
        node = core.find(tag, namespaces)
        if node is None:
            prefix, local = tag.split(':')
            node = etree.SubElement(core, f'{{{namespaces[prefix]}}}{local}')
        node.text = value
    parts['docProps/core.xml'] = xml_bytes(core)
    # Do not carry the reference's document-generation identity into this work.
    app = etree.fromstring(parts['docProps/app.xml'])
    app_ns = {'ep': 'http://schemas.openxmlformats.org/officeDocument/2006/extended-properties'}
    for tag, value in [('Application', 'DriveLab document builder'), ('Pages', '3')]:
        node = app.find('ep:' + tag, app_ns)
        if node is not None:
            node.text = value
    for tag in ['Words', 'Characters', 'CharactersWithSpaces', 'Paragraphs', 'TotalTime']:
        node = app.find('ep:' + tag, app_ns)
        if node is not None:
            app.remove(node)
    parts['docProps/app.xml'] = xml_bytes(app)
    custom = etree.fromstring(parts['docProps/custom.xml'])
    for child in list(custom):
        custom.remove(child)
    parts['docProps/custom.xml'] = xml_bytes(custom)
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
        for name, value in parts.items():
            archive.writestr(name, value)
    assert reference.read_bytes() == reference_bytes
    print(json.dumps({'output': str(output), 'bytes': output.stat().st_size, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'referenceUnchanged': True}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True, help='Path to the retained original development DOCX')
    parser.add_argument('--content', type=Path, default=ROOT/'docs/competition/project-explanation.json')
    parser.add_argument('--output', type=Path, default=ROOT.parents[1]/'outputs/DriveLab-项目说明书.docx')
    args = parser.parse_args()
    build(args.reference, args.content, args.output)
