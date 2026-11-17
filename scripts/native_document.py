"""Write editable Word paragraphs, tables and figures from a shared block list."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import hashlib
import json

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor


def font(style, size, bold=False, color='000000'):
    style.font.name='Arial'
    style.font.size=Pt(size)
    style.font.bold=bold
    style.font.color.rgb=RGBColor.from_string(color)
    style.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),'等线')


def set_cell_borders(cell):
    props=cell._tc.get_or_add_tcPr()
    borders=OxmlElement('w:tcBorders')
    for name in ['top','left','bottom','right']:
        edge=OxmlElement('w:'+name)
        for key,value in [('val','single'),('sz','4'),('color','D9D9D9')]:edge.set(qn('w:'+key),value)
        borders.append(edge)
    props.append(borders)
    margins=OxmlElement('w:tcMar')
    for name,value in [('top','120'),('bottom','120'),('left','160'),('right','160')]:
        edge=OxmlElement('w:'+name);edge.set(qn('w:w'),value);edge.set(qn('w:type'),'dxa');margins.append(edge)
    props.append(margins)


def build_native_docx(blocks, output, *, title, reviewed_on, header='DRIVELAB  /  ENGINEERING WITH EVIDENCE',footer='参赛技术文档'):
    output=Path(output)
    document=Document()
    section=document.sections[0]
    section.page_width=Mm(210);section.page_height=Mm(297)
    section.left_margin=Pt(42);section.right_margin=Pt(42)
    section.top_margin=Pt(61);section.bottom_margin=Pt(57)
    section.header_distance=Pt(20);section.footer_distance=Pt(20)
    specs=[('Normal',10,17,False,10),('Title',31,42,False,18),('Heading 1',20,29,False,18),('Heading 2',12,20,False,7),('Caption',8.5,14,False,8)]
    for name,size,leading,bold,after in specs:
        style=document.styles[name];font(style,size,bold)
        style.paragraph_format.line_spacing=Pt(leading)
        style.paragraph_format.space_after=Pt(after)
        style.paragraph_format.space_before=Pt(12 if name=='Heading 2' else 0)
        style.paragraph_format.keep_with_next=name in ['Title','Heading 1','Heading 2']
    header_p=section.header.paragraphs[0];header_p.text=header
    header_p.style=document.styles['Caption']
    footer_p=section.footer.paragraphs[0];footer_p.style=document.styles['Caption']
    footer_p.paragraph_format.tab_stops.add_tab_stop(Pt(510),2)
    footer_p.add_run(footer+' · '+reviewed_on+'\t')
    field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),' PAGE ')
    run=OxmlElement('w:r');text=OxmlElement('w:t');text.text='1';run.append(text);field.append(run);footer_p._p.append(field)
    style_map={'title':'Title','heading':'Heading 1','sub':'Heading 2','small':'Caption','body':'Normal'}
    logical=[];counts={'paragraphs':0,'tables':0,'figures':0}
    for index,block in enumerate(blocks):
        kind=block['type']
        if kind=='paragraph':
            p=document.add_paragraph(block['text'],style_map.get(block.get('style','body'),'Normal'))
            if block.get('style')=='small':
                for run in p.runs:run.font.color.rgb=RGBColor.from_string('657887')
            counts['paragraphs']+=1;logical.append({'type':kind,'text':block['text'],'style':block.get('style','body')})
        elif kind=='page_break':
            document.add_page_break();logical.append({'type':kind})
        elif kind=='spacer':
            p=document.add_paragraph();p.paragraph_format.line_spacing=Pt(1)
            p.paragraph_format.space_before=Pt(0);p.paragraph_format.space_after=Pt(max(0,block['height']-1))
        elif kind=='table':
            rows=[block['headers'],*block['rows']]
            table=document.add_table(rows=0,cols=len(block['headers']))
            table.alignment=WD_TABLE_ALIGNMENT.LEFT;table.autofit=False
            for column,width in zip(table.columns,block['widths']):column.width=Pt(width)
            for row_index,values in enumerate(rows):
                row=table.add_row();props=row._tr.get_or_add_trPr()
                props.append(OxmlElement('w:cantSplit'))
                if row_index==0:props.append(OxmlElement('w:tblHeader'))
                for cell,width,value in zip(row.cells,block['widths'],values):
                    cell.width=Pt(width);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
                    set_cell_borders(cell)
                    fill='253846' if row_index==0 else 'F5F7F9' if row_index%2==0 else 'FFFFFF'
                    shading=OxmlElement('w:shd');shading.set(qn('w:fill'),fill);cell._tc.get_or_add_tcPr().append(shading)
                    p=cell.paragraphs[0];p.text=str(value)
                    p.paragraph_format.space_after=Pt(0);p.paragraph_format.space_before=Pt(0)
                    p.paragraph_format.line_spacing=Pt(14);p.paragraph_format.keep_with_next=row_index==0
                    for run in p.runs:
                        run.font.name='Arial';run.font.size=Pt(9)
                        run.font.color.rgb=RGBColor.from_string('FFFFFF' if row_index==0 else '253846')
                        run._element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),'等线')
            counts['tables']+=1
            logical.append({'type':kind,'headers':block['headers'],'rows':block['rows'],'widths':block['widths']})
        elif kind=='image':
            p=document.add_paragraph();p.paragraph_format.space_after=Pt(0)
            p.paragraph_format.line_spacing=1.0
            p.paragraph_format.keep_with_next=True
            p.add_run().add_picture(BytesIO(block['data']),width=Pt(block['width']))
            counts['figures']+=1
            logical.append({'type':kind,'sha256':hashlib.sha256(block['data']).hexdigest(),'width':block['width'],'height':block['height'],'source':block.get('source')})
        else:raise ValueError('Unknown document block: '+kind)
    for tree in [document.element,document.styles.element]:
        for border in tree.xpath('.//w:pBdr'):
            border.getparent().remove(border)
    core=document.core_properties;core.title=title;core.author='DriveLab';core.last_modified_by='DriveLab';core.comments='';core.subject=''
    output.parent.mkdir(parents=True,exist_ok=True);document.save(output)
    canonical=json.dumps(logical,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    return {'output':str(output),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'bytes':output.stat().st_size,'nativeEditable':True,**counts,'contentSha256':hashlib.sha256(canonical).hexdigest(),'blocks':logical}
