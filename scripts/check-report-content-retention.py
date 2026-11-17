"""Verify that a layout revision retains the original detailed report content."""
from pathlib import Path
from io import BytesIO
from collections import Counter
import argparse,hashlib,json,re,subprocess
from zipfile import ZipFile
from docx import Document

ROOT=Path(__file__).resolve().parents[1]
BASELINE='591b895d4b514eb75421d84e92e9a8a6dbadf12a'
BASELINE_FILE='docs/competition/DriveLab-参赛技术文档.docx'


def compact(text):return re.sub(r'\s+','',text)


def media_hashes(data):
    with ZipFile(BytesIO(data)) as archive:
        return {hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist() if name.startswith('word/media/')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--docx',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    baseline_bytes=subprocess.check_output(['git','show',BASELINE+':'+BASELINE_FILE],cwd=ROOT)
    current_bytes=args.docx.read_bytes()
    baseline=Document(BytesIO(baseline_bytes));current=Document(BytesIO(current_bytes))
    original=[p.text for p in baseline.paragraphs if p.text]
    decorative=[text for text in original if re.fullmatch(r'\d+/DRIVELAB|AIWEBDEVELOPMENT/10037',compact(text))]
    expected=[text for text in original if text not in decorative]
    actual=[p.text for p in current.paragraphs if p.text]
    expected_counts=Counter(map(compact,expected));actual_counts=Counter(map(compact,actual))
    missing=expected_counts-actual_counts
    assert not missing,'Original technical paragraphs missing: '+repr(list(missing)[:3])
    rows=lambda doc:[[[cell.text for cell in row.cells] for row in table.rows] for table in doc.tables]
    expected_tables=rows(baseline);actual_tables=rows(current)
    assert actual_tables[:len(expected_tables)]==expected_tables,'Original table text or order changed'
    original_media=media_hashes(baseline_bytes);actual_media=media_hashes(current_bytes)
    assert original_media<=actual_media,'Original source images were removed or changed'
    result={'status':'passed','baselineCommit':BASELINE,'baselineDocxSha256':hashlib.sha256(baseline_bytes).hexdigest(),'currentDocxSha256':hashlib.sha256(current_bytes).hexdigest(),'originalNonemptyParagraphs':len(original),'decorativePageBadgesRemoved':decorative,'originalTechnicalParagraphsRetained':len(expected),'originalTablesRetained':len(expected_tables),'originalDistinctImagesRetained':len(original_media),'currentNonemptyParagraphs':len(actual),'currentTables':len(actual_tables),'currentDistinctImages':len(actual_media),'scope':'Exact original technical paragraph, table and image retention; layout badges excluded. Additional application material is checked separately and does not replace the original.'}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8',newline='\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['decorativePageBadgesRemoved','scope']},ensure_ascii=False))


if __name__=='__main__':main()
