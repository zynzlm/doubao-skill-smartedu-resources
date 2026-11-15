#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 xParse 输出的 markdown（表格为 HTML、图片为 URL/HTML）渲染成可编辑 Word。

特点：题目文字是普通段落；表格转成真正的 Word 表格（保留合并单元格）；
图片从 URL 下载后原样插入到它原来的位置；公式的 LaTeX 碎片做轻量降噪。

用法:
    python md_to_docx.py --md a.md --out a.docx
    python md_to_docx.py --dir <md目录> --out-dir <docx目录>
"""

import argparse
import os
import re
import ssl
import sys
import urllib.request

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0 Safari/537.36"
IMG_DIR = os.path.join(os.environ.get("TEMP", "."), "xparse_imgs")


# ---------------------------------------------------------------- 公式清洗
def clean_latex(s: str) -> str:
    s = s.replace("$$", "").replace("$", "")
    for _ in range(3):
        s = re.sub(r"\\(?:text|mathrm|mathbf)\{([^{}]*)\}", r"\1", s)
        s = re.sub(r"\\(?:overset|underset|stackrel)\{[^{}]*\}\{([^{}]*)\}", r"\1", s)
        s = re.sub(r"\\frac(\{[^{}]*\})(\{[^{}]*\})", r"\1/\2", s)
    s = s.replace("\\prime", "′").replace("\\cdot", "·").replace("\\times", "×")
    s = s.replace("\\left", "").replace("\\right", "").replace("\\ ", " ").replace("\\\\", "")
    s = re.sub(r"\\[a-zA-Z]+", "", s)
    s = s.replace("{", "").replace("}", "")
    return re.sub(r"[ \t]{2,}", " ", s).strip()


def fmt_text(s: str) -> str:
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"`(.+?)`", r"\1", s)
    # 复杂 LaTeX（含反斜杠）在 OCR 下只会变乱码，整段丢弃；简单 $F$ 保留内文
    s = re.sub(r"\$[^$]*\\[^$]*\$", " ", s)
    s = re.sub(r"\$([^$]*)\$", r"\1", s)
    s = (s.replace("&#39;", "'" ).replace("&amp;", "&")
          .replace("&lt;", "<").replace("&gt;", ">").replace("\u00ad", ""))
    s = re.sub(r"\s{2,}", " ", s).strip()
    if len(re.sub(r"[^\w\u4e00-\u9fff]", "", s)) <= 1:
        return ""
    # 图注散落的单字符噪声（如 "F F F F F"、"AB C D"）整行丢弃
    if not re.search(r"[\u4e00-\u9fff]", s):
        toks = s.split()
        if len(toks) >= 3 and all(len(t) <= 2 for t in toks):
            return ""
    return s


# ---------------------------------------------------------------- 图片下载
def download(url: str) -> str:
    os.makedirs(IMG_DIR, exist_ok=True)
    name = re.sub(r"[^0-9a-zA-Z_.]", "_", url.split("/")[-1])[:80] or "img.jpg"
    path = os.path.join(IMG_DIR, name)
    if os.path.exists(path) and os.path.getsize(path) > 512:
        return path
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=40, context=ctx) as r:
            data = r.read()
        if len(data) < 512:
            return ""
        with open(path, "wb") as f:
            f.write(data)
        return path
    except Exception:
        return ""


def img_width_cm(path: str, max_cm: float = 11.0, max_h_cm: float = 9.0) -> float:
    try:
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
        if w >= 480:
            width = max_cm
        else:
            width = max(3.0, round(max_cm * w / 480.0, 2))
        if w > 0:
            height = width * h / w
            if height > max_h_cm:
                width = round(width * max_h_cm / height, 2)
        return round(width, 2)
    except Exception:
        return 8.0


# ---------------------------------------------------------------- 文档样式
def setup_doc(doc: Document):
    st = doc.styles["Normal"]
    st.font.name = "宋体"
    st.font.size = Pt(12)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    pf = st.paragraph_format
    pf.line_spacing = 1.5
    pf.space_after = Pt(4)
    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Cm(2.6)
    sec.top_margin = sec.bottom_margin = Cm(2.2)


def add_para(doc_or_cell, text: str, style=None, bold=False, size=None, align=None, indent=False):
    p = doc_or_cell.add_paragraph(style=style) if style else doc_or_cell.add_paragraph()
    if text:
        run = p.add_run(text)
        run.bold = bold
        if size:
            run.font.size = Pt(size)
        run.font.name = "宋体"
        run.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    if align is not None:
        p.alignment = align
    if indent:
        p.paragraph_format.first_line_indent = Pt(24)
    return p


def add_pic(container, path: str, max_cm=11.0, center=True):
    p = container.add_paragraph()
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(3)
    try:
        p.add_run().add_picture(path, width=Cm(img_width_cm(path, max_cm)))
    except Exception:
        pass
    return p


# ---------------------------------------------------------------- 表格解析
TD_RE = re.compile(r"<td(?P<attrs>[^>]*)>(?P<body>.*?)</td>", re.I | re.S)
TR_RE = re.compile(r"<tr[^>]*>(?P<body>.*?)</tr>", re.I | re.S)
IMG_RE = re.compile(r'<img[^>]+src="([^"]+)"', re.I)
SPAN_RE = re.compile(r'(colspan|rowspan)\s*=\s*"(\d+)"', re.I)


def parse_table(html: str):
    rows = []
    for tr in TR_RE.finditer(html):
        cells = []
        for td in TD_RE.finditer(tr.group("body")):
            attrs = td.group("attrs") or ""
            col = row = 1
            for k, v in SPAN_RE.findall(attrs):
                if k.lower() == "colspan":
                    col = int(v)
                else:
                    row = int(v)
            cells.append({"html": td.group("body"), "colspan": col, "rowspan": row})
        if cells:
            rows.append(cells)
    return rows


CELL_TOKEN = re.compile(r'<br\s*/?>|<img[^>]*src="([^"]+)"[^>]*>', re.I)


def cell_segments(html: str):
    """按文档顺序把单元格内容切成 ('t', 文本) / ('i', 图片URL) 序列，
    让单元格内的插图落在它原来那一段之后，而不是统统堆到单元格末尾。"""
    segs = []
    buf = []

    def flush():
        if buf:
            t = fmt_text("".join(buf))
            if t:
                segs.append(("t", t))
            buf.clear()

    pos = 0
    for m in CELL_TOKEN.finditer(html):
        buf.append(html[pos:m.start()])
        tok = m.group(0).lower()
        if tok.startswith("<img"):
            flush()
            segs.append(("i", m.group(1)))
        else:
            flush()
        pos = m.end()
    buf.append(html[pos:])
    flush()
    return segs


def fill_cell(cell, html: str, is_header=False):
    segs = cell_segments(html)
    first = True
    i = 0
    n = len(segs)
    while i < n:
        kind, val = segs[i]
        p = cell.paragraphs[0] if first else cell.add_paragraph()
        p.paragraph_format.line_spacing = 1.15
        p.paragraph_format.space_after = Pt(0)
        if kind == "t":
            run = p.add_run(val)
            run.font.name = "宋体"
            run.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
            run.font.size = Pt(10.5)
            if is_header:
                run.bold = True
            first = False
            i += 1
            continue
        # 连续的多张图放进同一段，模拟原版一行并排的选项图
        j = i
        while j < n and segs[j][0] == "i":
            j += 1
        group = [u for k, u in segs[i:j] if k == "i"]
        width = min(9.5, round(15.0 / max(len(group), 1), 2))
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        drew = False
        for u in group:
            path = download(u)
            if not path:
                continue
            try:
                p.add_run().add_picture(path, width=Cm(img_width_cm(path, width, 4.6)))
                drew = True
            except Exception:
                pass
        if drew:
            first = False
        elif first:
            p._element.getparent().remove(p._element)
        i = j


def add_table(doc: Document, rows):
    ncols = max(sum(c["colspan"] for c in r) for r in rows)
    tbl = doc.add_table(rows=len(rows), cols=ncols)
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = True
    occupied = {}
    for ri, row in enumerate(rows):
        ci = 0
        for c in row:
            while occupied.get((ri, ci)):
                ci += 1
            if ci >= ncols:
                break
            cell = tbl.cell(ri, ci)
            span_c = min(c["colspan"], ncols - ci)
            span_r = min(c["rowspan"], len(rows) - ri)
            if span_c > 1 or span_r > 1:
                cell = cell.merge(tbl.cell(ri + span_r - 1, ci + span_c - 1))
            for r2 in range(ri, ri + span_r):
                for c2 in range(ci, ci + span_c):
                    occupied[(r2, c2)] = True
            fill_cell(cell, c["html"], is_header=(ri == 0))
            ci += span_c
    doc.add_paragraph()
    return tbl


# ---------------------------------------------------------------- 主渲染
BLOCK_TABLE = re.compile(r"<table[^>]*>.*?</table>", re.I | re.S)
BLOCK_IMG = re.compile(r"!\[[^\]]*\]\((https?://[^)\s]+)\)")
MD_SEP = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def split_md_row(line: str):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", line)]


def md_cell_html(text: str) -> str:
    # 单元格里的 markdown 图片转成 <img>，交给 cell_segments 按原位切段
    return re.sub(r"!\[[^\]]*\]\((https?://[^)\s]+)\)", r'<img src="\1">', text)


def convert_md_tables(md: str) -> str:
    """把 markdown 管道表格（| a | b | 配合 |---|---| 分隔行）转成 <table> HTML，
    这样后面的表格渲染只需处理一种输入；HTML 表格与正文里的竖线不受影响。"""
    lines = md.split("\n")
    out, i = [], 0
    while i < len(lines):
        cur = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if "|" in cur and MD_SEP.match(nxt.strip()):
            rows = [split_md_row(cur)]
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                rows.append(split_md_row(lines[j]))
                j += 1
            parts = ["<table>"]
            for r in rows:
                parts.append("<tr>" + "".join(f"<td>{md_cell_html(c)}</td>" for c in r) + "</tr>")
            parts.append("</table>")
            out.append("\n".join(parts))
            i = j
        else:
            out.append(cur)
            i += 1
    return "\n".join(out)


def render(md: str, out_path: str):
    doc = Document()
    setup_doc(doc)
    # xParse 有时会把整页内容包在 HTML 注释里，注释符要去掉，内容必须保留
    md = re.sub(r"<!--", "", md).replace("-->", "")
    md = convert_md_tables(md)
    pos = 0
    for m in re.finditer(f"{BLOCK_TABLE.pattern}|{BLOCK_IMG.pattern}", md, re.I | re.S):
        head = md[pos:m.start()]
        emit_text(doc, head)
        token = m.group(0)
        if token.lower().startswith("<table"):
            rows = parse_table(token)
            if rows:
                add_table(doc, rows)
        else:
            url = BLOCK_IMG.match(token).group(1) if BLOCK_IMG.match(token) else m.group(1)
            path = download(url)
            if path:
                add_pic(doc, path)
        pos = m.end()
    emit_text(doc, md[pos:])
    doc.save(out_path)
    return out_path


def emit_text(doc: Document, text: str):
    text = text.replace("\u00ad", "")
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if re.fullmatch(r"-{3,}", line) or re.fullmatch(r"<!--.*-->", line, re.S):
            continue
        hm = re.match(r"^(#{1,6})\s*(.*)$", line)
        if hm:
            lvl = len(hm.group(1))
            t = fmt_text(hm.group(2))
            if t:
                add_para(doc, t, bold=True, size=16 if lvl <= 2 else 14,
                         align=WD_ALIGN_PARAGRAPH.CENTER if lvl <= 1 else None)
            continue
        if line.startswith("**") and line.endswith("**") and len(line) < 40:
            t = fmt_text(line)
            if t == "基础教育精品课":
                continue
            add_para(doc, t, bold=True, size=16, align=WD_ALIGN_PARAGRAPH.CENTER)
            continue
        t = fmt_text(line)
        if t == "基础教育精品课":
            continue
        if t:
            add_para(doc, t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md")
    ap.add_argument("--out")
    ap.add_argument("--dir")
    ap.add_argument("--out-dir")
    a = ap.parse_args()
    if a.md:
        print(render(open(a.md, encoding="utf-8").read(), a.out))
    else:
        os.makedirs(a.out_dir, exist_ok=True)
        for f in sorted(os.listdir(a.dir)):
            if not f.lower().endswith(".md"):
                continue
            src = os.path.join(a.dir, f)
            dst = os.path.join(a.out_dir, os.path.splitext(f)[0] + ".docx")
            try:
                render(open(src, encoding="utf-8").read(), dst)
                print("OK", dst)
            except Exception as e:
                print("FAIL", f, e)


if __name__ == "__main__":
    main()
