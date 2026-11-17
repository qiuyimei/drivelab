"""Verify native DOCX blocks and its exact-input Word PDF export.

Visual review is supplied explicitly after viewing all rendered pages. This
check does not infer image readability or semantic correctness from geometry.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
from zipfile import ZipFile

from docx import Document
import pdfplumber
from pypdf import PdfReader


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compact(text):
    return re.sub(r'\s+', '', text)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--docx',type=Path,required=True)
    parser.add_argument('--pdf',type=Path,required=True)
    parser.add_argument('--render-dir',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--visual-pages',default='')
    parser.add_argument('--max-pages',type=int,default=30)
    parser.add_argument('--docx-copy',type=Path)
    parser.add_argument('--pdf-copy',type=Path)
    parser.add_argument('--export-receipt',type=Path)
    args=parser.parse_args()
    manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
    doc=Document(args.docx)
    blocks=manifest['blocks']
    expected_paragraphs=[b['text'] for b in blocks if b['type']=='paragraph']
    expected_tables=[[b['headers'],*b['rows']] for b in blocks if b['type']=='table']
    actual_paragraphs=[p.text for p in doc.paragraphs if p.text]
    actual_tables=[[[cell.text for cell in row.cells] for row in table.rows] for table in doc.tables]
    assert expected_paragraphs==actual_paragraphs,'DOCX paragraphs differ from shared blocks'
    assert expected_tables==actual_tables,'Native table cells differ from shared blocks'
    assert sha(args.docx)==manifest['sha256'],'Rendered DOCX differs from built source'
    receipt=None
    if args.export_receipt:
        receipt=json.loads(args.export_receipt.read_text(encoding='utf-8-sig'))
        assert receipt['inputDocxSha256']==sha(args.docx) and receipt['outputPdfSha256']==sha(args.pdf),'PDF export receipt does not match final pair'
        assert receipt['readOnly'] and not receipt['addToRecentFiles'] and receipt['automationSecurity']==3
    with ZipFile(args.docx) as archive:
        body=archive.read('word/document.xml').decode('utf-8')
        media=[hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist() if name.startswith('word/media/')]
        metadata=archive.read('docProps/core.xml').decode('utf-8')
    figures=[b for b in blocks if b['type']=='image']
    assert body.count('<w:drawing>')==len(figures),'Native image count differs'
    assert all(b['sha256'] in media for b in figures),'Source image missing from DOCX'
    assert not re.search(r'Codex|ChatGPT|Claude|少量\s*AI|主要人工独立',body,re.I),'Unapproved assistant branding or ratio claim'
    assert doc.core_properties.author=='DriveLab' and doc.core_properties.last_modified_by=='DriveLab'
    geometry=[]
    with pdfplumber.open(args.pdf) as pdf:
        page_count=len(pdf.pages)
        assert 0<page_count<=args.max_pages
        for index,page in enumerate(pdf.pages,1):
            outside=[c for c in page.chars if c['x0'] < -0.5 or c['top'] < -0.5 or c['x1'] > page.width+0.5 or c['bottom'] > page.height+0.5]
            geometry.append({'page':index,'characters':len(page.chars),'outsidePageCount':len(outside),'replacementCount':sum(c['text']=='\ufffd' for c in page.chars)})
    # Word emits mixed Chinese/Latin runs whose visual-order clustering may
    # differ in pdfplumber; pypdf preserves the PDF text-operator sequence.
    pdf_text='\n'.join(page.extract_text() or '' for page in PdfReader(args.pdf).pages)
    normalized=compact(pdf_text)
    all_strings=expected_paragraphs+[cell for table in expected_tables for row in table for cell in row]
    missing=[value for value in all_strings if compact(value) not in normalized]
    assert not missing,'Shared source text absent from PDF: '+repr(missing[:3])
    assert all(not p['outsidePageCount'] and not p['replacementCount'] for p in geometry),'PDF character geometry failed'
    pngs=[args.render_dir/f'page-{index}.png' for index in range(1,page_count+1)]
    assert all(p.is_file() for p in pngs),'Rendered pages missing'
    reviewed=sorted({int(n) for n in args.visual_pages.split(',') if n.strip()})
    finalized=reviewed==list(range(1,page_count+1))
    for path,reference in [(args.docx_copy,args.docx),(args.pdf_copy,args.pdf)]:
        if path:assert sha(path)==sha(reference),'Repository copy differs'
    report={
        'engineVersion':manifest.get('engineVersion'),
        'pageCount':page_count,'pages':page_count,
        'sha256':sha(args.pdf),'latestPdfSha256':sha(args.pdf),'bytes':args.pdf.stat().st_size,
        'docxSha256':sha(args.docx),'docxBytes':args.docx.stat().st_size,
        'outputPdf':str(args.pdf.resolve()),'outputDocx':str(args.docx.resolve()),
        'contentSha256':manifest['contentSha256'],
        'sameContentSource':True,'nativeEditable':True,
        'nativeParagraphs':len(expected_paragraphs),'nativeTables':len(expected_tables),'actualFigureGroups':len(figures),
        'sourceParagraphAndTableEquality':True,'allSourceTextPresentInPdf':True,
        'textEqualityExtractor':'pypdf text-operator sequence, whitespace normalized; pdfplumber used independently for character geometry',
        'pdfExportInputDocxSha256':manifest['sha256'],
        'pdfExportReceipt':receipt,
        'renderer':'Independent hidden Microsoft Word 16 COM exact-input PDF export; bundled render_docx.py rasterizer and Poppler',
        'libreOfficeUsed':False,
        'renderDirectory':str(args.render_dir.resolve()),
        'renderedPngSha256':{p.name:sha(p) for p in pngs},
        'geometry':geometry,
        'visualReview':'pass' if finalized else 'pending',
        'visuallyReviewedPages':reviewed,'visualReviewAllPages':finalized,'finalized':finalized,
        'result':'passed_all_pages_rendered_and_visually_reviewed' if finalized else 'machine_checks_passed_visual_review_pending',
        'copiesByteIdentical':bool(args.docx_copy and args.pdf_copy),
        'limits':['Native structure and text equality do not establish engineering or natural-language semantic correctness.','Image readability is established by explicit page-image visual review, not by text or geometry checks.'],
    }
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({key:report[key] for key in ['engineVersion','pageCount','docxSha256','latestPdfSha256','nativeTables','sameContentSource','finalized']},ensure_ascii=False))


if __name__=='__main__':main()
