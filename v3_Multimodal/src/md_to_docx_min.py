#!/usr/bin/env python3
"""md_to_docx_min.py — 의존성 없는 최소 markdown → docx 변환기 (블록 M-4).

왜 이 스크립트인가
------------------
`docs/58` M-4 는 pandoc 사용을 지시하나, 본 머신에 **pandoc 이 설치돼 있지 않고**
지시서 절대금지 조항이 **네트워크를 금지**하므로 설치할 수 없다. 대신
① 스타일·numbering·rels 등 **패키지 뼈대는 v1 docx(pandoc 산출)에서 그대로 복사**하고
② `word/document.xml` 만 본 스크립트가 생성한다.
→ 결과물의 스타일명(`Heading1/2/3`·`BodyText`·`FirstParagraph`·`Compact`·`BlockText`·
  `VerbatimChar`·`Table`)과 표 마크업은 v1 과 동일하며, **모든 표는 실제 `w:tbl`** 로 렌더된다.

지원 문법(본 문서가 쓰는 부분집합만): `#`~`###` 제목 · 문단 · `- ` 불릿 · `> ` 인용 ·
`|` 표 · `---` 구분선 · 펜스 코드블록 · 인라인 `**굵게**`/`` `코드` ``.

실행: .venv/bin/python3 v3_Multimodal/src/md_to_docx_min.py <in.md> <out.docx> [skeleton.docx]
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import zipfile

DOC_HEAD = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:o="urn:schemas-microsoft-com:office:office" '
    'xmlns:v="urn:schemas-microsoft-com:vml" '
    'xmlns:w10="urn:schemas-microsoft-com:office:word" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
    "<w:body>"
)
DOC_TAIL = "<w:sectPr /></w:body></w:document>"
BULLET_NUMID = "1001"          # v1 numbering.xml 의 bullet abstractNum(991) 연결 numId


def esc(t):
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def runs(text):
    """인라인 마크업(**굵게**, `코드`) → w:r 시퀀스."""
    out = []
    for tok in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**") and len(tok) > 4:
            out.append('<w:r><w:rPr><w:bCs /><w:b /></w:rPr><w:t xml:space="preserve">'
                       f"{esc(tok[2:-2])}</w:t></w:r>")
        elif tok.startswith("`") and tok.endswith("`") and len(tok) > 2:
            out.append('<w:r><w:rPr><w:rStyle w:val="VerbatimChar" /></w:rPr>'
                       f'<w:t xml:space="preserve">{esc(tok[1:-1])}</w:t></w:r>')
        else:
            out.append(f'<w:r><w:t xml:space="preserve">{esc(tok)}</w:t></w:r>')
    return "".join(out)


def para(text, style="BodyText", numid=None):
    ppr = ""
    if numid:
        ppr += f'<w:numPr><w:ilvl w:val="0" /><w:numId w:val="{numid}" /></w:numPr>'
    ppr += f'<w:pStyle w:val="{style}" />'
    return f"<w:p><w:pPr>{ppr}</w:pPr>{runs(text)}</w:p>"


def cell(text, header=False):
    body = runs(text) if not header else (
        f'<w:r><w:rPr><w:bCs /><w:b /></w:rPr><w:t xml:space="preserve">{esc(text)}</w:t></w:r>'
        if "**" not in text and "`" not in text else runs(text))
    return ('<w:tc><w:tcPr /><w:p><w:pPr><w:pStyle w:val="Compact" />'
            f'<w:jc w:val="left" /></w:pPr>{body}</w:p></w:tc>')


def table(rows):
    ncol = max(len(r) for r in rows)
    width = 7920 // ncol
    grid = "".join(f'<w:gridCol w:w="{width}" />' for _ in range(ncol))
    trs = []
    for ri, row in enumerate(rows):
        cells = [cell(c, header=(ri == 0)) for c in row] + \
                [cell("") for _ in range(ncol - len(row))]
        trpr = '<w:trPr><w:tblHeader w:val="true" /></w:trPr>' if ri == 0 else ""
        trs.append(f"<w:tr>{trpr}{''.join(cells)}</w:tr>")
    return ('<w:tbl><w:tblPr><w:tblStyle w:val="Table" />'
            '<w:tblW w:type="pct" w:w="5000" />'
            '<w:tblLook w:firstRow="1" w:lastRow="0" w:firstColumn="0" w:lastColumn="0" '
            'w:noHBand="0" w:noVBand="0" w:val="0020" /><w:jc w:val="start" /></w:tblPr>'
            f"<w:tblGrid>{grid}</w:tblGrid>{''.join(trs)}</w:tbl>")


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def convert(md_text):
    lines = md_text.split("\n")
    out = []
    i = 0
    n_tables = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        if s.startswith("```"):                                  # 코드블록
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            for b in buf:
                out.append('<w:p><w:pPr><w:pStyle w:val="Compact" /></w:pPr>'
                           '<w:r><w:rPr><w:rStyle w:val="VerbatimChar" /></w:rPr>'
                           f'<w:t xml:space="preserve">{esc(b)}</w:t></w:r></w:p>')
            continue
        if re.match(r"^-{3,}$", s):                              # 구분선
            i += 1
            continue
        if s.startswith("#"):                                    # 제목
            lvl = len(s) - len(s.lstrip("#"))
            out.append(f'<w:p><w:pPr><w:pStyle w:val="Heading{min(lvl, 3)}" /></w:pPr>'
                       f"{runs(s[lvl:].strip())}</w:p>")
            i += 1
            continue
        if s.startswith("|"):                                    # 표
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                r = lines[i].strip()
                if not re.match(r"^\|[\s:\-|]+\|$", r):          # 구분행 제외
                    rows.append(split_row(r))
                i += 1
            out.append(table(rows))
            n_tables += 1
            continue
        if s.startswith(">"):                                    # 인용
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            chunk = []
            for b in buf:
                if not b:
                    if chunk:
                        out.append(para(" ".join(chunk), "BlockText"))
                        chunk = []
                else:
                    chunk.append(b)
            if chunk:
                out.append(para(" ".join(chunk), "BlockText"))
            continue
        if re.match(r"^[-*]\s+", s):                             # 불릿(연속행 병합)
            item = re.sub(r"^[-*]\s+", "", s)
            i += 1
            while i < len(lines) and lines[i].startswith("  ") and lines[i].strip() \
                    and not re.match(r"^\s*[-*]\s+", lines[i]):
                item += " " + lines[i].strip()
                i += 1
            out.append(para(item, "Compact", numid=BULLET_NUMID))
            continue
        if re.match(r"^\d+\.\s+", s):                            # 번호 항목(번호는 본문 그대로)
            item = s
            i += 1
            while i < len(lines) and lines[i].startswith("  ") and lines[i].strip() \
                    and not re.match(r"^\s*(\d+\.|[-*])\s+", lines[i]):
                item += " " + lines[i].strip()
                i += 1
            out.append(para(item, "Compact"))
            continue
        buf = [s]                                                # 문단(연속행 병합)
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].strip()[0] in "#|>-`" :
            buf.append(lines[i].strip())
            i += 1
        out.append(para(" ".join(buf), "BodyText"))
    return DOC_HEAD + "".join(out) + DOC_TAIL, n_tables


def main():
    src, dst = sys.argv[1], sys.argv[2]
    skel = sys.argv[3] if len(sys.argv) > 3 else \
        os.path.join(os.path.dirname(src), "55_rqint_external_statreview_package.docx")
    with open(src, encoding="utf-8") as f:
        md = f.read()
    xml, n_tables = convert(md)
    tmp = dst + ".tmp"
    with zipfile.ZipFile(skel) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                data = xml.encode("utf-8")
            zout.writestr(item.filename, data)
    shutil.move(tmp, dst)
    with zipfile.ZipFile(dst) as z:
        got = z.read("word/document.xml").decode("utf-8")
    assert got == xml, "docx roundtrip FAIL"
    print(f"[OK] {dst} · markdown 표 {n_tables}개 → w:tbl {got.count('<w:tbl>')}개 · "
          f"{os.path.getsize(dst)} bytes")


if __name__ == "__main__":
    main()
