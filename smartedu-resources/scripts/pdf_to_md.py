#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把平台的 PDF（逐页图片）在本地解析成 markdown：文字成段 + 插图回到原位。

这是**离线兜底方案**，不依赖任何云端解析服务或 MCP 插件，供没有 xParse 的
宿主（WorkBuddy / CodeBuddy / 纯命令行）跑通「PDF → md → 可编辑 Word」。
链路：pdf_to_md.py 出 md → build_docs.py 或 md_to_docx.py 渲染 docx。

质量说明（务必如实告知用户）：
  - 文字：OCR 识别，正文字准确率较高，公式/上下标/希腊字母会失真；
  - 插图：按版面分析裁切原图插回原位置，不会丢图；
  - 表格：优先用横竖线重建真表格；重建失败时该区域退化为按行文本。

用法：
    python pdf_to_md.py --pdf "作业练习-第1节 透镜.pdf" --out md/c02.md
    python pdf_to_md.py --in "第一节 透镜" --out-dir md --pattern "作业练习*.pdf,学习任务单*.pdf"
    python pdf_to_md.py --pdf a.pdf --out a.md --no-figures      # 只要文字
"""

import argparse
import glob
import json
import os
import re
import sys

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import pymupdf
except ImportError:
    try:
        import fitz as pymupdf
    except ImportError:
        raise SystemExit("需要 PyMuPDF：python scripts/setup.py")

DPI = 150
TEXTIN_URL = "https://api.textin.com/api/v1/xparse/parse/sync"
TEXTIN_HINT = (
    "TextIn 凭证无效或缺失。请到 https://www.textin.com 注册（有免费额度），"
    "在「工作台 - 账号设置 - 开发者信息」取 x-ti-app-id 与 x-ti-secret-code，"
    "然后设置环境变量 TEXTIN_APP_ID / TEXTIN_SECRET_CODE，或传 --app-id / --secret-code。"
)
MIN_IMG_SIDE = 24          # 太小的裁切块当噪声丢掉
GAP_RATIO = 2.2            # 同一行两段文字间距超过 2.2 倍字高才加分隔
FIG_CLASSES = {"figure", "table"}
DROP_CLASSES = {"header", "footer"}


def textin_parse(pdf_path, app_id, secret_code, timeout=600):
    """调 TextIn xParse 同步接口，返回 markdown（表格为 HTML，插图是可下载的 URL）。"""
    try:
        import requests
    except ImportError:
        raise SystemExit("需要 requests：python scripts/setup.py --optional")
    cfg = {
        "capabilities": {
            "include_table_structure": True,
            "table_view": "html",
            "include_image_data": True,
            "title_tree": True,
            "pages": True,
        },
        "config": {"force_engine": "textin", "engine_params": {"parse_mode": "auto"}},
    }
    with open(pdf_path, "rb") as f:
        r = requests.post(
            TEXTIN_URL,
            headers={"x-ti-app-id": app_id, "x-ti-secret-code": secret_code},
            files={"file": (os.path.basename(str(pdf_path)), f, "application/pdf")},
            data={"config": json.dumps(cfg)},
            timeout=timeout,
        )
    try:
        d = r.json()
    except ValueError:
        raise SystemExit(f"TextIn 返回不是 JSON（HTTP {r.status_code}）：{r.text[:200]}")
    code = d.get("code")
    if code in (40101, 40102, 40103):
        raise RuntimeError(TEXTIN_HINT)
    if code != 200:
        raise RuntimeError(f"TextIn 解析失败 code={code} message={d.get('message')}")
    md = (d.get("data") or {}).get("markdown") or ""
    if not md.strip():
        raise RuntimeError("TextIn 返回的 markdown 为空，检查源文件是否正常")
    return md


def write_text(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def convert(pdf_path, out_md, engine, app_id, secret_code, dpi, want_figures):
    if engine == "textin":
        return write_text(out_md, textin_parse(pdf_path, app_id, secret_code))
    return pdf_to_md(pdf_path, out_md, dpi, want_figures)


def _engines():
    from rapidocr import RapidOCR
    from rapid_layout import RapidLayout
    return RapidOCR(), RapidLayout()


def page_array(page, dpi=DPI):
    pix = page.get_pixmap(dpi=dpi)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n >= 3:
        arr = arr[:, :, :3]
    return np.ascontiguousarray(arr), pix.width, pix.height


def boxes_of(ocr_res):
    items = []
    if ocr_res is None:
        return items
    if getattr(ocr_res, "boxes", None) is None or len(ocr_res.boxes) == 0:
        return items
    for box, txt, score in zip(ocr_res.boxes, ocr_res.txts, ocr_res.scores):
        pts = box.tolist() if hasattr(box, "tolist") else box
        xs = [float(p[0]) for p in pts]
        ys = [float(p[1]) for p in pts]
        t = (txt or "").strip()
        if not t:
            continue
        items.append({"x0": min(xs), "x1": max(xs), "y0": min(ys), "y1": max(ys),
                      "t": t, "s": float(score)})
    return items


def group_lines(items):
    """把 OCR 框按纵向聚成行，同一行内的框按 x 拼接。"""
    items.sort(key=lambda d: (d["y0"] + d["y1"]) / 2)
    groups = []
    for d in items:
        yc = (d["y0"] + d["y1"]) / 2
        h = max(1.0, d["y1"] - d["y0"])
        if groups and abs(yc - groups[-1]["yc"]) <= max(6.0, 0.45 * h):
            groups[-1]["items"].append(d)
            groups[-1]["yc"] = (groups[-1]["yc"] * (len(groups[-1]["items"]) - 1) + yc) / len(groups[-1]["items"])
        else:
            groups.append({"yc": yc, "items": [d]})

    lines = []
    for g in groups:
        row = sorted(g["items"], key=lambda d: d["x0"])
        h = max(d["y1"] - d["y0"] for d in row)
        text, prev_x1 = "", None
        for it in row:
            if prev_x1 is not None and (it["x0"] - prev_x1) > GAP_RATIO * h:
                text += "  "
            text += it["t"]
            prev_x1 = it["x1"]
        lines.append({"yc": g["yc"], "h": h, "t": re.sub(r"[ \t]{3,}", "  ", text).strip(),
                      "x0": min(d["x0"] for d in row), "x1": max(d["x1"] for d in row)})
    return lines


def inside(box, x0, y0, x1, y1, tol=2.0):
    cx, cy = (box["x0"] + box["x1"]) / 2, box["yc"]
    return x0 - tol <= cx <= x1 + tol and y0 - tol <= cy <= y1 + tol


def layout_regions(lay, width, height):
    """返回 (figures, drops)：figure/table 区域与页眉页脚区域。"""
    figs, drops = [], []
    if lay is None:
        return figs, drops
    if getattr(lay, "boxes", None) is None or len(lay.boxes) == 0:
        return figs, drops
    for b, c, s in zip(lay.boxes, lay.class_names, lay.scores):
        bt = b.tolist() if hasattr(b, "tolist") else b
        x0, y0, x1, y1 = [float(v) for v in bt[:4]]
        x0, y0 = max(0.0, x0), max(0.0, y0)
        x1, y1 = min(width, x1), min(height, y1)
        if x1 - x0 < MIN_IMG_SIDE or y1 - y0 < MIN_IMG_SIDE:
            continue
        if c in DROP_CLASSES:
            drops.append((x0, y0, x1, y1))
            figs.append((c, x0, y0, x1, y1))     # 同类区域也要遮掉里面的文字
        elif c in FIG_CLASSES:
            figs.append((c, x0, y0, x1, y1))
    return figs, drops


def crop_save(arr, x0, y0, x1, y1, out_path):
    from PIL import Image
    sub = arr[int(y0):int(y1), int(x0):int(x1)]
    if sub.size == 0:
        return ""
    if sub.shape[0] > 1 and sub.shape[1] > 1:
        if int(sub.min()) > 230:      # 整块几乎没有深色像素，是误检的空白块
            return ""
    Image.fromarray(np.ascontiguousarray(sub)).save(out_path)
    return out_path


def table_to_markdown(arr, x0, y0, x1, y1):
    """在给定区域里找横竖线，重建简单 markdown 表格；失败返回空串。"""
    try:
        import cv2
    except ImportError:
        return ""
    sub = arr[int(y0):int(y1), int(x0):int(x1)]
    if sub.size == 0:
        return ""
    gray = cv2.cvtColor(sub, cv2.COLOR_RGB2GRAY)
    bw = cv2.adaptiveThreshold(~gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                               cv2.THRESH_BINARY, 15, -2)
    h, w = bw.shape
    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(10, w // 12), 1)))
    vert = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(10, h // 4))))
    cols = int(round((vert.sum(axis=0) > 0).sum() / max(1, h) * 0))
    # 用线的位置直接推行列
    xs = [i for i, v in enumerate((vert > 0).sum(axis=0)) if v > h * 0.30]
    ys = [i for i, v in enumerate((horiz > 0).sum(axis=1)) if v > w * 0.25]
    xs = _cluster(xs)
    ys = _cluster(ys)
    if len(xs) < 2 or len(ys) < 2:
        return ""
    return {"xs": [x0 + v for v in xs], "ys": [y0 + v for v in ys]}


def _cluster(vals, tol=6):
    out = []
    for v in vals:
        if out and v - out[-1] <= tol:
            out[-1] = (out[-1] + v) // 2
        else:
            out.append(v)
    return out


def grid_text(grid, lines):
    """把某区域的 OCR 行按网格归位，拼成 markdown 表格文本。"""
    xs, ys = grid["xs"], grid["ys"]
    ncol, nrow = len(xs) - 1, len(ys) - 1
    if ncol < 2 or nrow < 1:
        return ""
    cells = [["" for _ in range(ncol)] for _ in range(nrow)]
    for ln in lines:
        cx, cy = (ln["x0"] + ln["x1"]) / 2, ln["yc"]
        ci = ri = -1
        for i in range(ncol):
            if xs[i] <= cx <= xs[i + 1]:
                ci = i
                break
        for i in range(nrow):
            if ys[i] <= cy <= ys[i + 1]:
                ri = i
                break
        if ci < 0 or ri < 0:
            continue
        cells[ri][ci] = (cells[ri][ci] + " " + ln["t"]).strip() if cells[ri][ci] else ln["t"]
    if not any(c.strip() for row in cells for c in row):
        return ""
    md = []
    for ri, row in enumerate(cells):
        md.append("| " + " | ".join(c.replace("|", "｜") for c in row) + " |")
        if ri == 0:
            md.append("|" + "|".join(["---"] * ncol) + "|")
    return "\n".join(md)


def pdf_to_md(pdf_path, out_md, dpi=DPI, want_figures=True):
    from PIL import Image  # noqa: F401  (确保 schema 可用)
    ocr, lay = _engines()
    doc = pymupdf.open(str(pdf_path))
    stem = os.path.splitext(os.path.basename(str(pdf_path)))[0]
    img_dir = os.path.join(os.path.dirname(os.path.abspath(out_md)), stem + "_插图")
    os.makedirs(img_dir, exist_ok=True)

    out = []
    for pno, page in enumerate(doc, 1):
        arr, w, h = page_array(page, dpi)
        res = ocr(arr)
        lines = group_lines(boxes_of(res))
        lay_res = lay(arr) if (want_figures and hasattr(lay, "__call__")) else None
        figs, _ = layout_regions(lay_res, w, h) if lay_res is not None else ([], [])

        print(f"  第 {pno} 页：文字 {len(lines)} 行，图形 {len(figs)} 块")

        # 图区内文字太多，说明是文字块被误检成图形：不裁图，也不遮文字
        good_figs = []
        for cls, x0, y0, x1, y1 in figs:
            inked = [ln for ln in lines if inside(ln, x0, y0, x1, y1)]
            if cls == "figure" and sum(len(ln["t"]) for ln in inked) > 60:
                continue
            good_figs.append((cls, x0, y0, x1, y1))

        # 表格：能按线条重建的走真表格，该区文字交给表格承载（避免重复输出）
        tables, drop_tables = [], []
        for cls, x0, y0, x1, y1 in good_figs:
            if cls != "table":
                continue
            grid = table_to_markdown(arr, x0, y0, x1, y1)
            text = grid_text(grid, lines) if grid else ""
            if text:
                tables.append((y0, text))
                drop_tables.append((x0, y0, x1, y1))

        # 遮掉页眉页脚、图区内标注、以及已被表格接管的文字
        drop_boxes = [(x0, y0, x1, y1) for c, x0, y0, x1, y1 in good_figs if c != "table"] + drop_tables
        kept = [ln for ln in lines if not any(inside(ln, *b) for b in drop_boxes)]

        elements = [{"k": "t", "y": ln["yc"], "h": ln["h"], "t": ln["t"]} for ln in kept]
        elements += [{"k": "tbl", "y": y0, "h": 10, "t": text} for y0, text in tables]
        for i, (cls, x0, y0, x1, y1) in enumerate(good_figs, 1):
            if cls in ("table", "header", "footer"):
                continue
            if not want_figures:
                continue
            fp = os.path.join(img_dir, f"p{pno}_{i}.png")
            got = crop_save(arr, x0, y0, x1, y1, fp)
            if got:
                elements.append({"k": "f", "y": y0, "h": y1 - y0, "p": got})

        elements.sort(key=lambda d: (round(d["y"] / 3.0), d.get("x0", 0) if "x0" in d else 0))

        med_h = np.median([ln["h"] for ln in kept]) if kept else 0
        for el in elements:
            if el["k"] == "f":
                out.append("![](" + el["p"].replace("\\", "/") + ")")
                continue
            t = el["t"].strip()
            if not t:
                continue
            if med_h and el.get("h", 0) > med_h * 1.35 and len(t) <= 30 and not re.match(r"^[\d（(]", t):
                out.append("## " + t)
            else:
                out.append(t)
        out.append("")

    md = "\n\n".join(out)
    os.makedirs(os.path.dirname(os.path.abspath(out_md)), exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md)
    return out_md


def main():
    ap = argparse.ArgumentParser(description="离线把平台 PDF 解析成 markdown（文字 + 原位插图）")
    ap.add_argument("--pdf", help="单个 PDF")
    ap.add_argument("--out", help="输出 md 路径（配 --pdf）")
    ap.add_argument("--in", dest="src", help="PDF 所在目录（批量）")
    ap.add_argument("--out-dir", help="批量输出 md 目录")
    ap.add_argument("--pattern", default="教学设计*.pdf,学习任务单*.pdf,作业练习*.pdf",
                    help="批量时的文件名通配，逗号分隔")
    ap.add_argument("--engine", choices=["auto", "textin", "local"], default="auto",
                    help="textin=云端高质量（需凭证）；local=本地 OCR 兜底；auto=有凭证用 textin")
    ap.add_argument("--app-id", default=None, help="TextIn x-ti-app-id（默认读环境变量 TEXTIN_APP_ID）")
    ap.add_argument("--secret-code", default=None, help="TextIn x-ti-secret-code（默认读 TEXTIN_SECRET_CODE）")
    ap.add_argument("--dpi", type=int, default=DPI)
    ap.add_argument("--no-figures", action="store_true", help="本地模式只出文字，不裁插图")
    a = ap.parse_args()

    app_id = a.app_id or os.environ.get("TEXTIN_APP_ID", "")
    secret = a.secret_code or os.environ.get("TEXTIN_SECRET_CODE", "")
    engine = a.engine
    if engine == "auto":
        engine = "textin" if (app_id and secret) else "local"
    if engine == "textin" and not (app_id and secret):
        raise SystemExit(TEXTIN_HINT)
    if engine == "local":
        print("[引擎] 本地 OCR（无云端凭证）：文字可编辑、插图按版面插回原位，"
              "但表格结构与公式会走样，交付前需对照源 PDF 校正。")
        print("       要与豆包版一致的质量：设 TEXTIN_APP_ID / TEXTIN_SECRET_CODE 再加 --engine textin")
    else:
        print("[引擎] TextIn xParse 云端解析")

    def one(pdf_path, out_md):
        print(f"[解析] {os.path.basename(pdf_path)} -> {out_md}")
        convert(pdf_path, out_md, engine, app_id, secret, a.dpi, not a.no_figures)
        print(f"[完成] {out_md}（{os.path.getsize(out_md)} 字节）")

    if a.pdf:
        try:
            one(a.pdf, a.out or (os.path.splitext(a.pdf)[0] + ".md"))
        except RuntimeError as e:
            raise SystemExit(str(e))
        return

    if not (a.src and a.out_dir):
        raise SystemExit("用 --pdf/--out 单份，或 --in/--out-dir 批量")
    os.makedirs(a.out_dir, exist_ok=True)
    files = []
    for pat in a.pattern.split(","):
        files.extend(sorted(glob.glob(os.path.join(a.src, pat.strip()))))
    files = list(dict.fromkeys(files))
    if not files:
        raise SystemExit("没匹配到 PDF：" + a.pattern)
    ok = 0
    for f in files:
        stem = os.path.splitext(os.path.basename(f))[0]
        try:
            one(f, os.path.join(a.out_dir, stem + ".md"))
            ok += 1
        except Exception as e:
            print(f"[失败] {stem}: {type(e).__name__} {e}")
    print(f"\n完成 {ok}/{len(files)} 份")


if __name__ == "__main__":
    main()
