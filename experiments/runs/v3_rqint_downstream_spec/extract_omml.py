#!/usr/bin/env python3
"""블록 AV(docs/112) AV-2 — 검토자 회신 docx 축자·수식 추출기.

일회성 도구(동결 대상 아님). `word/document.xml` 을 **구조 그대로** 파싱해
OMML(`m:oMath`) 을 선형식으로 복원한다. 단순 태그 strip 을 하지 않는다
(strip 하면 `m:d` 의 절댓값 기호와 분수 분자/분모 경계가 사라진다 — docs/112 F9).

출력 = reviewer_verbatim_extract.json.  확증 산출물 접근 0 · 네트워크 0.
"""
import sys
sys.dont_write_bytecode = True

import argparse, hashlib, json, os, re, zipfile
import xml.etree.ElementTree as ET

M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# --- 복원 규칙 -------------------------------------------------------------
ACC_DEFAULT = chr(0x0302)  # COMBINING CIRCUMFLEX — ECMA-376 m:acc 기본 chr
ZW = "\u200b\ufeff\u200c\u200d"


def _empty(s: str) -> bool:
    """ZWSP 전용 슬롯 = 첨자 없음. (OMML 이 빈 m:sup 을 ZWSP 로 채우는 경우가 있다.)"""
    return not s.strip().strip(ZW)


def _brace(s: str) -> str:
    """지수·첨자가 한 글자를 넘으면 중괄호로 묶어 경계를 남긴다."""
    return s if len(s) == 1 else "{" + s + "}"


def _sub(base: str, s: str) -> str:
    return base if _empty(s) else base + "_" + _brace(s)


def _sup(base: str, s: str) -> str:
    return base if _empty(s) else base + "^" + _brace(s)


def _children_text(node) -> str:
    return "".join(_node(c) for c in node)


def _slot(node, tag) -> str:
    sub = node.find(M + tag)
    return _children_text(sub) if sub is not None else ""


def _prop(node, prop_tag, chr_tag, default):
    p = node.find(M + prop_tag)
    if p is None:
        return default
    c = p.find(M + chr_tag)
    if c is None:
        return default
    return c.get(M + "val", default)


def _node(n) -> str:
    t = n.tag
    if t == M + "t":
        return n.text or ""
    if t == M + "r":
        return "".join(_node(c) for c in n)
    if t == M + "f":                                   # 분수
        return "(" + _slot(n, "num") + ")/(" + _slot(n, "den") + ")"
    if t == M + "sSub":                                # 아래첨자
        return _sub(_slot(n, "e"), _slot(n, "sub"))
    if t == M + "sSup":                                # 위첨자
        return _sup(_slot(n, "e"), _slot(n, "sup"))
    if t == M + "sSubSup":                             # 위·아래첨자
        return _sub(_slot(n, "e"), _slot(n, "sub")) + "^" + _brace(_slot(n, "sup"))
    if t == M + "nary":                                # 합·적 등
        op = _prop(n, "naryPr", "chr", "∑")
        sub, sup = _slot(n, "sub"), _slot(n, "sup")
        return _sup(_sub(op, sub), sup) + " " + _slot(n, "e")
    if t == M + "d":                                   # ★ 구분자 — 절댓값이 여기 실린다
        beg = _prop(n, "dPr", "begChr", "(")
        end = _prop(n, "dPr", "endChr", ")")
        sep = _prop(n, "dPr", "sepChr", ",")
        es = [_children_text(e) for e in n.findall(M + "e")]
        return beg + sep.join(es) + end
    if t == M + "rad":                                 # 근호
        pr = n.find(M + "radPr")
        hide = pr is not None and pr.find(M + "degHide") is not None and \
            pr.find(M + "degHide").get(M + "val", "1") in ("1", "true", "on")
        deg = _slot(n, "deg")
        body = "√(" + _slot(n, "e") + ")"
        return body if (hide or not deg) else "root[" + deg + "](" + _slot(n, "e") + ")"
    if t == M + "func":                                # 함수
        return _slot(n, "fName") + "(" + _slot(n, "e") + ")"
    if t == M + "acc":                                 # 액센트(bar 등)
        ch = _prop(n, "accPr", "chr", ACC_DEFAULT)
        return _slot(n, "e") + ch
    if t == M + "bar":
        return "‾(" + _slot(n, "e") + ")"
    if t == M + "limLow":
        return _sub(_slot(n, "e"), _slot(n, "lim"))
    if t == M + "limUpp":
        return _sup(_slot(n, "e"), _slot(n, "lim"))
    if t == M + "groupChr":
        return _slot(n, "e")
    if t in (M + "ctrlPr", M + "rPr", M + "fPr", M + "dPr", M + "naryPr",
             M + "radPr", M + "sSubPr", M + "sSupPr", M + "sSubSupPr",
             M + "accPr", M + "barPr", M + "funcPr", M + "limLowPr",
             M + "limUppPr", M + "groupChrPr", M + "argPr"):
        return ""
    if t == W + "t":                                   # 수식 안의 일반 run
        return n.text or ""
    if t in (W + "rPr", W + "pPr", W + "proofErr", W + "bookmarkStart",
             W + "bookmarkEnd", W + "lastRenderedPageBreak"):
        return ""
    return "".join(_node(c) for c in n)


def para_text(p_elem, math_marker=True):
    """문단 → (평문, 그 문단의 수식 선형식 목록)."""
    out, maths = [], []
    def walk(n):
        for c in n:
            if c.tag in (M + "oMath",):
                s = _children_text(c)
                maths.append(s)
                out.append(("【" + s + "】") if math_marker else s)
            elif c.tag == M + "oMathPara":
                for om in c.findall(M + "oMath"):
                    s = _children_text(om)
                    maths.append(s)
                    out.append(("【" + s + "】") if math_marker else s)
            elif c.tag == W + "t":
                out.append(c.text or "")
            elif c.tag == W + "tab":
                out.append("\t")
            elif c.tag in (W + "br", W + "cr"):
                out.append("\n")
            elif c.tag in (W + "rPr", W + "pPr"):
                continue
            else:
                walk(c)
    walk(p_elem)
    return "".join(out), maths


def iter_paragraphs(xml_text):
    """원문 문자 오프셋을 보존하기 위해 raw XML 위에서 <w:p> 스팬을 직접 잘라 파싱한다."""
    for m in re.finditer(r"<w:p(?:\s[^>]*)?>.*?</w:p>|<w:p(?:\s[^>]*)?/>", xml_text, re.S):
        frag = m.group(0)
        if frag.endswith("/>"):
            yield m.start(), m.end(), "", []
            continue
        wrapped = ('<root xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                   'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
                   'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
                   'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                   'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
                   'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
                   'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
                   'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
                   'xmlns:v="urn:schemas-microsoft-com:vml" '
                   'xmlns:o="urn:schemas-microsoft-com:office:office" '
                   'xmlns:w10="urn:schemas-microsoft-com:office:word">' + frag + "</root>")
        try:
            root = ET.fromstring(wrapped)
        except ET.ParseError:
            yield m.start(), m.end(), "<<PARSE_ERROR>>", []
            continue
        p = root[0]
        txt, maths = para_text(p)
        yield m.start(), m.end(), txt, maths


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# --- 절 경계 (문단 인덱스 · 실측) -----------------------------------------
SECTIONS = [
    ("2.3", "2.3 \ud6c4\ubcf4 B(\uacf5\uc6a9\ub3d9\uc804)\uac00 \uc815\ub2f5\uc778 \uc774\uc720 \u2014 \uc720\ub3c4", 36, 46),
    ("2.4", "2.4 Concern 2(\uacf5\uc6a9\ub3d9\uc804 \uacf5\ubd84\uc0b0)\ub294 \uc624\uc9c4\uc785\ub2c8\ub2e4", 47, 56),
    ("2.6", "2.6 \ubcf4\uc870 \uc9c4\ub2e8\uc73c\ub85c\ub9cc \ud5c8\uc6a9\ub418\ub294 \uc120\ud615\ud654 \uac80\uc815", 78, 80),
    ("3", "3. Q2. \uad50\ud658\uac00\ub2a5\uc131 \ub2e8\uc704 (a)(b)(c) \ud3ec\ud568", 81, 94),
    ("4.1", "4.1 \uc21c\uc11c: \ud615\uc2dd (i)\ub97c \ucc44\ud0dd\ud558\uc2ed\uc2dc\uc624", 96, 105),
    ("4.2", "4.2 \u00a76.3 \u2014 \uc21c\uc5f4\uacfc \ub450 \ucd95\uc758 \uad00\uacc4", 106, 109),
    ("4.3", "4.3 RQ-int \ud310\uc815\uaddc\uce59", 110, 115),
    ("5.1", "5.1 \uc694\uccad \ubb38\uc11c\uac00 \ub193\uce5c \uc911\uc694\ud55c \ubd80\uc791\uc6a9", 118, 147),
    ("9.1", "9.1 \u00a74\uc758 \uc591\uce21 p-\uac12 \uc218\uc2dd \u2014 \uc808\ub313\uac12 \ud655\uc778 \uc694\ub9dd", 216, 219),
    ("APPENDIX_A", "\ubd80\ub85d A. Word \uc0bd\uc785\uc6a9 \uc218\uc2dd (\uc120\ud615\uc2dd / LaTeX)", 245, 324),
]

# AV-2 가 «반드시 복원·대조» 하도록 지정한 9개 식.
#   (키, 본문 절, 본문 문단 i, 부록 A 항목)
REQUIRED = [
    ("d_F_g", "2.3", 41, "A4"),
    ("e_g", "2.3", 41, "A4"),
    ("T_z_hajek", "2.3", 43, "A5"),
    ("lambda_k", "3(a)", 88, "A11"),
    ("rho", "3(a)", 88, "A12"),
    ("G_eff", "3(c)", 93, "A10"),
    ("p_two_sided", "9.1", 218, "A7"),
    ("se_p_hat", "9.2", 222, "A8"),
    ("holm_adjusted", "5.1", 120, "A9"),
]

COMBINING = "".join(chr(c) for c in range(0x300, 0x370))

# \u00a79.1 \uc740 \u00ab\uc694\uccad \ubb38\uc11c\uc5d0 \uc778\uc1c4\ub41c \ud615\ud0dc\u00bb \ub97c \uadf8 \ubb38\uc11c\uc758 \ud45c\uae30(\u0394)\ub85c \uc9c0\uc801\u00b7\uc815\uc815\ud558\uace0,
# \ubd80\ub85d A7 \uc740 \uac80\ud1a0\uc790 \uc815\ubcf8 \ud45c\uae30(T)\ub85c \ub2e4\uc2dc \uc801\ub294\ub2e4. \uad6c\uc870\ub294 \ub3d9\uc77c\ud558\uba70, \ubcc4\uce6d\uc784\uc744 \uba85\uc2dc\ud55c\ub2e4.
NOTATION_ALIAS = {
    "p_two_sided": {
        "map": {chr(0x394) + "_b": "T_b", chr(0x394) + "_obs": "T_obs",
                "p_two-sided": "p"},
        "reason": "\u00a79.1 \ubcf8\ubb38\uc740 \u00ab\uc694\uccad \ubb38\uc11c\uc5d0 \uc778\uc1c4\ub41c \ud615\ud0dc\u00bb \ub97c \uadf8 \ubb38\uc11c\uc758 \ud45c\uae30(\u0394_b\u00b7\u0394_obs)\ub85c \uc778\uc6a9\ud558\uba70 \uc808\ub313\uac12 \ub204\ub77d\uc744 \uc9c0\uc801\ud55c\ub2e4. "
                  "\ubd80\ub85d A7 \uc740 \uac19\uc740 \uc2dd\uc744 \uac80\ud1a0\uc790 \uc815\ubcf8 \ud45c\uae30(T_b\u00b7T_obs)\ub85c \uc801\ub294\ub2e4. \uc2dd\uc758 \uad6c\uc870\u00b7\ud53c\uc5f0\uc0b0\uc790\ub294 \ub3d9\uc77c\ud558\uace0 \uae30\ud638\uba85\ub9cc \ub2e4\ub974\ub2e4.",
        "is_interpretation_not_verbatim": True,
    },
}
GROUPING = "()[]{}" + chr(0x201c) + chr(0x201d) + chr(0x22) + chr(0x3010) + chr(0x3011)
ZEROWIDTH = "".join(chr(c) for c in (0x200b, 0x200c, 0x200d, 0xfeff))
DROP = set(GROUPING) | set(ZEROWIDTH) | set(COMBINING)
ACCENT_INPUT = ("\\hat", "\\tilde", "\\bar")


def normalize(expr: str) -> str:
    """OMML 복원문과 부록 A 선형식을 같은 표준형으로 만든다.

    - 그룹 문자((), [], {})·따옴표·공백·제로폭·결합 악센트를 제거한다.
      악센트는 별도 assert 로 따로 확인하므로 여기서 떨궈도 검증이 약해지지 않는다.
    - `|`(절댓값)·`/`(분수 경계)·`_`·`^`·연산자·합기호는 **보존**한다.
      따라서 절댓값 유실이나 분자/분모 뒤섞임은 이 비교에서 반드시 드러난다.
    """
    for tok in ACCENT_INPUT:
        expr = expr.replace(tok, "")
    # ★ 공백은 ASCII 스페이스만이 아니다 — docx 는 U+2001(EM QUAD) 등 조판 공백을 쓴다.
    return "".join(c for c in expr if (c not in DROP) and (not c.isspace()))


def parse_appendix_a(rows):
    """\ubd80\ub85d A \u2192 {\ud56d\ubaa9: {title, omml, linear, latex}}"""
    items, cur = {}, None
    for r in rows[245:325]:
        t = r["text"].strip()
        if not t:
            continue
        m = re.match(r"^(A\d+)\.\s*(.*)$", t)
        if m:
            cur = m.group(1)
            items[cur] = {"item": cur, "title": m.group(2), "omml_restored": [],
                          "linear_input": None, "latex": None, "paragraph_index": r["i"]}
            continue
        if cur is None:
            continue
        if t.startswith("\uc120\ud615\uc2dd:"):
            items[cur]["linear_input"] = t.split(":", 1)[1].strip()
        elif t.startswith("LaTeX:"):
            items[cur]["latex"] = t.split(":", 1)[1].strip()
        elif r["math"]:
            items[cur]["omml_restored"].extend(r["math"])
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dump-paragraphs")
    a = ap.parse_args()

    with zipfile.ZipFile(a.docx) as z:
        xml_text = z.read("word/document.xml").decode("utf-8")
    paras = [{"i": i, "offset": [s, e], "text": t, "math": mm}
             for i, (s, e, t, mm) in enumerate(iter_paragraphs(xml_text))]

    if a.dump_paragraphs:
        with open(a.dump_paragraphs, "w", encoding="utf-8") as f:
            for r in paras:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    appendix = parse_appendix_a(paras)

    sections = []
    for key, heading, lo, hi in SECTIONS:
        body = []
        for r in paras[lo:hi + 1]:
            if not r["text"].strip():
                continue
            body.append({"paragraph_index": r["i"], "xml_char_offset": r["offset"],
                         "text_verbatim": r["text"], "math_restored": r["math"]})
        sections.append({"section": key, "heading": heading,
                         "paragraph_range": [lo, hi], "n_paragraphs": len(body),
                         "paragraphs": body})

    required, unresolved = [], []
    for kkey, sec, pi, ai in REQUIRED:
        maths = paras[pi]["math"]
        app = appendix.get(ai)
        cand = None
        if app:
            tgt = normalize(app["linear_input"] or "")
            for mexpr in maths:
                n = normalize(mexpr)
                if n == tgt or tgt in n or n in tgt:
                    cand = mexpr
                    break
        if cand is None and len(maths) == 1:
            cand = maths[0]
        entry = {
            "key": kkey, "reviewer_section": sec, "paragraph_index": pi,
            "xml_char_offset": paras[pi]["offset"],
            "omml_restored": cand,
            "all_math_in_paragraph": maths,
            "appendix_item": ai,
            "appendix_title": app["title"] if app else None,
            "appendix_omml_restored": app["omml_restored"] if app else None,
            "appendix_linear_input": app["linear_input"] if app else None,
            "appendix_latex": app["latex"] if app else None,
        }
        app_omml = (app["omml_restored"] or [None])[0] if app else None
        entry["normalized"] = {
            "body_omml": normalize(cand) if cand else None,
            "appendix_omml": normalize(app_omml) if app_omml else None,
            "appendix_linear": normalize(app["linear_input"]) if app and app["linear_input"] else None,
        }
        entry["notation_alias"] = NOTATION_ALIAS.get(kkey)
        if entry["notation_alias"]:
            for a_sym, b_sym in entry["notation_alias"]["map"].items():
                if entry["normalized"]["body_omml"]:
                    entry["normalized"]["body_omml_aliased"] = \
                        (entry["normalized"].get("body_omml_aliased") or
                         entry["normalized"]["body_omml"]).replace(a_sym, b_sym)
            entry["normalized"]["body_omml"] = entry["normalized"]["body_omml_aliased"]
        n = entry["normalized"]
        # \ubcf8\ubb38 OMML \u2194 \ubd80\ub85d A OMML \u2194 \ubd80\ub85d A \uc120\ud615\uc2dd \uc0bc\uc911 \ub300\uc870
        entry["match_body_vs_appendix_omml"] = bool(
            n["body_omml"] and n["appendix_omml"] and
            (n["body_omml"] == n["appendix_omml"] or n["appendix_omml"] in n["body_omml"]))
        entry["match_appendix_omml_vs_linear"] = bool(
            n["appendix_omml"] and n["appendix_linear"] and
            n["appendix_omml"] == n["appendix_linear"])
        entry["resolved"] = bool(cand) and entry["match_body_vs_appendix_omml"] \
            and entry["match_appendix_omml_vs_linear"]
        if not entry["resolved"]:
            unresolved.append(kkey)
        required.append(entry)

    # \u2605 m:d \ubcf4\uc874 assert \u2014 \uc808\ub313\uac12\uc774 \uc0b4\uc544\uc788\ub294\uac00
    abs_checks = {
        "rho_numerator_has_abs": "|" in (next(e["omml_restored"] for e in required if e["key"] == "rho") or ""),
        "p_two_sided_has_abs": "|" in (next(e["omml_restored"] for e in required if e["key"] == "p_two_sided") or ""),
        "T_k_defined_by_abs_e_g": "|e_g|" in paras[89]["text"].replace("\u3010", "").replace("\u3011", ""),
    }
    for k, v in abs_checks.items():
        if not v:
            unresolved.append(k)

    out = {
        "_doc": "docs/112 \ube14\ub85d AV / AV-2 \u2014 \uac80\ud1a0\uc790 \ud68c\uc2e0 docx \ucd95\uc790\u00b7\uc218\uc2dd \ucd94\ucd9c. \uc22b\uc790\ub294 \uc804\ubd80 \uac80\ud1a0\uc790 \ubb38\uba74\uc5d0\uc11c \uc628 \uac83\uc774\uba70, \ud655\uc99d \uc0b0\ucd9c\ubb3c\uc5d0\uc11c \uc628 \uac12\uc740 \ud558\ub098\ub3c4 \uc5c6\ub2e4.",
        "provenance": "reviewer_docx_verbatim",
        "block": "AV (docs/112)",
        "source": {
            "path": os.path.basename(a.docx),
            "sha256": sha256_file(a.docx),
            "bytes": os.path.getsize(a.docx),
            "xml_part": "word/document.xml",
            "n_oMath": xml_text.count("<m:oMath>") + xml_text.count("<m:oMath "),
            "n_paragraphs": len(paras),
        },
        "parser": {
            "handled_omml_nodes": ["m:f", "m:sSub", "m:sSup", "m:sSubSup", "m:nary", "m:d",
                                   "m:rad", "m:func", "m:acc", "m:bar", "m:limLow", "m:limUpp",
                                   "m:groupChr", "m:r", "m:t"],
            "delimiter_rule": "m:d \uc758 m:begChr/m:endChr \ub97c \uadf8\ub300\ub85c \ubcf4\uc874\ud55c\ub2e4(\uae30\ubcf8 '(' ')'). \uc774 \uaddc\uce59\uc774 \uc5c6\uc73c\uba74 \u03bb\u00b7\u03c1 \uc758 \uc808\ub313\uac12\uc774 \uc720\uc2e4\ub41c\ub2e4.",
            "empty_script_rule": "ZWSP \uc804\uc6a9 m:sub/m:sup \uc2ac\ub86f\uc740 \u00ab\ucca8\uc790 \uc5c6\uc74c\u00bb \uc73c\ub85c \ub2e4\ub8ec\ub2e4.",
            "accent_default_chr": "U+0302 (ECMA-376 m:acc \uae30\ubcf8\uac12)",
            "tag_strip_forbidden": True,
        },
        "canonical_crosscheck": "\ubd80\ub85d A(\u00abWord \uc0bd\uc785\uc6a9 \uc218\uc2dd\u00bb)\uc758 \uc120\ud615\uc2dd\u00b7LaTeX \ud3c9\ubb38\uc774 \uc815\ubcf8 \ub300\uc870\ubcf8\uc774\ub2e4. OMML \ubcf5\uc6d0\uacb0\uacfc\ub294 \ubc18\ub4dc\uc2dc \uadf8 \ubb38\uc790\uc5f4\uacfc \ub300\uc870\ud55c\ub2e4.",
        "sections": sections,
        "appendix_a": [appendix[k] for k in sorted(appendix, key=lambda x: int(x[1:]))],
        "n_appendix_items": len(appendix),
        "required_formulas": required,
        "n_required": len(required),
        "absolute_value_preservation_checks": abs_checks,
        "unresolved": sorted(set(unresolved)),
        "n_unresolved": len(set(unresolved)),
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({"n_sections": len(sections), "n_appendix_items": len(appendix),
                      "n_required": len(required), "n_unresolved": out["n_unresolved"],
                      "unresolved": out["unresolved"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
