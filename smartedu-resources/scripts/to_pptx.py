#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把课时课件的 PDF（逐页图片）转成可直接放映/编辑版式的 PPTX。

平台只提供逐页转码图，合成出的 PDF 每页就是一张 1920x1080 的原图。
本脚本把这页图抽回，铺满一张幻灯片，得到与原件视觉一致的 .pptx：
文字是图片、不可再编辑文字，但版式、字号、图示与原件完全相同，可放映、可打印、可加动画。

用法：
    python to_pptx.py --in 课件-xxx.pdf --out <目录>
    python to_pptx.py --in <课件目录> --out <PPT目录>          # 批量转目录下所有 PDF
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

try:
    import pymupdf
except ImportError:
    try:
        import fitz as pymupdf
    except ImportError:
        raise SystemExit("需要 PyMuPDF：pip install pymupdf")

from pptx import Presentation
from pptx.util import Inches

EMU_PER_INCH = 914400
STD_16_9 = (13.333, 7.5)   # 英寸
STD_4_3 = (10.0, 7.5)


def pick_image(doc, page):
    """取页面上面积最大的那张图；返回图片字节与扩展名，取不到返回 (None, None)。"""
    best = None
    for info in page.get_images(full=True):
        xref = info[0]
        try:
            data = doc.extract_image(xref)
        except Exception:
            continue
        if not data or not data.get("image"):
            continue
        area = data.get("width", 0) * data.get("height", 0)
        if best is None or area > best[0]:
            best = (area, data)
    if best is None:
        return None, None
    return best[1]["image"], best[1]["ext"]


def render_page(doc, page, dpi=150):
    pix = page.get_pixmap(dpi=dpi)
    return pix.tobytes("png"), "png"


def page_bytes(doc, page, tmpdir):
    raw, ext = pick_image(doc, page)
    if raw is None:
        raw, ext = render_page(doc, page)
    fd, path = tempfile.mkstemp(suffix="." + ext, dir=tmpdir)
    with os.fdopen(fd, "wb") as f:
        f.write(raw)
    return path, ext


def convert(pdf_path, out_path, force=False):
    if out_path.exists() and not force:
        print(f"[跳过] 已存在：{out_path.name}")
        return None
    doc = pymupdf.open(str(pdf_path))
    if doc.page_count == 0:
        print(f"[跳过] 空文档：{pdf_path.name}")
        return None

    # 用首页原图定画幅比例
    with tempfile.TemporaryDirectory() as tmp:
        first, ext = page_bytes(doc, doc[0], tmp)
        from PIL import Image
        with Image.open(first) as im:
            ratio = im.width / im.height
        if abs(ratio - 16 / 9) < 0.08:
            w_in, h_in = STD_16_9
        elif abs(ratio - 4 / 3) < 0.08:
            w_in, h_in = STD_4_3
        else:
            w_in, h_in = STD_16_9[0], STD_16_9[0] / ratio

        prs = Presentation()
        prs.slide_width = Inches(w_in)
        prs.slide_height = Inches(h_in)
        blank = prs.slide_layouts[6]
        sw, sh = prs.slide_width, prs.slide_height

        for i, page in enumerate(doc, 1):
            p, _ = page_bytes(doc, page, tmp)
            slide = prs.slides.add_slide(blank)
            pic = slide.shapes.add_picture(p, 0, 0, width=sw)
            if pic.height > sh:                       # 比例不一致时按高度收缩居中
                slide.shapes._spTree.remove(pic._element)
                pic = slide.shapes.add_picture(p, 0, 0, height=sh)
                pic.left = int((sw - pic.width) / 2)
                pic.top = 0
            else:
                pic.top = int((sh - pic.height) / 2)
        prs.save(str(out_path))
    print(f"[OK] {pdf_path.name} -> {out_path.name}（{doc.page_count} 页，{out_path.stat().st_size / 1048576:.2f}MB）")
    return out_path


def main():
    ap = argparse.ArgumentParser(description="把课件 PDF 转成 PPTX")
    ap.add_argument("--in", dest="src", required=True, help="PDF 文件或目录")
    ap.add_argument("--out", dest="dst", required=True, help="输出目录")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的同名 pptx")
    args = ap.parse_args()

    src = Path(args.src)
    dst = Path(args.dst)
    dst.mkdir(parents=True, exist_ok=True)

    if src.is_dir():
        pdfs = sorted(src.glob("*.pdf"))
    else:
        pdfs = [src]
    if not pdfs:
        raise SystemExit("没找到 PDF")

    done = 0
    for pdf in pdfs:
        if convert(pdf, dst / (pdf.stem + ".pptx"), args.force):
            done += 1
    print(f"\n完成 {done}/{len(pdfs)} 份")


if __name__ == "__main__":
    main()
