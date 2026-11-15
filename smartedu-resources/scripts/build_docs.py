#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""把 xParse 解析出的 markdown 批量渲染成可编辑 Word。

输入约定（默认值可被命令行覆盖）：
  <work>/md/cXX.md        每份文档的 markdown（cXX 为自定义编号）
  <work>/fileids.json     {"ok": {"cXX": {"path": "<源 PDF 或原 docx 的绝对路径>"}}}
输出：
  <out>/<源文件所在目录名>/<源文件同名>.docx

用法：
  python build_docs.py                                   # 用 TEMP/smartedu_probe 与当前目录
  python build_docs.py --work D:\job --out "D:\输出"
  python build_docs.py --work D:\job --out E:\out --report D:\job\report.json

也可以用 --md 单份渲染：
  python build_docs.py --md c05.md --out E:\out\第一节 透镜 --name 教学设计-xxx.docx
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import md_to_docx as R


def default_work():
    return os.path.join(os.environ.get("TEMP") or os.getcwd(), "smartedu_probe")


def render_one(md_path, out_path):
    from docx import Document
    R.render(open(md_path, encoding="utf-8").read(), out_path)
    d = Document(out_path)
    return {
        "out": out_path,
        "tables": len(d.tables),
        "imgs": len(d.inline_shapes),
        "paras": sum(1 for p in d.paragraphs if p.text.strip())
        + sum(len(c.paragraphs) for t in d.tables for r in t.rows for c in r.cells),
    }


def main():
    ap = argparse.ArgumentParser(description="markdown → 可编辑 Word 批量渲染")
    ap.add_argument("--work", default=default_work(), help="含 md/ 与 fileids.json 的工作目录")
    ap.add_argument("--out", default=".", help="输出根目录（按源文件所在的节自动建子目录）")
    ap.add_argument("--report", default=None, help="渲染报告 json 路径")
    ap.add_argument("--md", default=None, help="只渲染单份：md 文件路径")
    ap.add_argument("--name", default=None, help="配合 --md 指定输出文件名")
    ap.add_argument("--ids", default=None, help="fileids.json 路径（默认 <work>/fileids.json）")
    args = ap.parse_args()

    if args.md:
        src = args.md
        name = args.name or (os.path.splitext(os.path.basename(src))[0] + ".docx")
        out = os.path.join(args.out, name)
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        info = render_one(src, out)
        print("OK", out, info)
        return

    ids_path = args.ids or os.path.join(args.work, "fileids.json")
    md_dir = os.path.join(args.work, "md")
    ids = json.load(open(ids_path, encoding="utf-8"))["ok"]

    done, missing = [], 0
    for ref, info in sorted(ids.items()):
        md = os.path.join(md_dir, ref + ".md")
        if not os.path.exists(md):
            missing += 1
            continue
        pdf = info["path"]
        sec = os.path.basename(os.path.dirname(pdf))
        stem = os.path.splitext(os.path.basename(pdf))[0]
        out_dir = os.path.join(args.out, sec)
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, stem + ".docx")
        try:
            got = render_one(md, out)
            done.append((ref, stem, got["tables"], got["imgs"]))
            print(f"OK {ref} {stem} tables={got['tables']} imgs={got['imgs']}")
        except Exception as e:
            print(f"FAIL {ref} {stem} {e}")

    print(f"完成 {len(done)} / {len(ids)}" + (f"（缺 md 跳过 {missing}）" if missing else ""))
    report = args.report or os.path.join(args.work, "render_report.json")
    json.dump(done, open(report, "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main()
