#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按教材章节批量下载国家中小学智慧教育平台的全部课时资料。

数据全部来自公开目录接口：章节树 + 该教材的资源分片。每个资源的
relations 里已经带齐子文件（课件/教学设计/任务单/作业练习）及其逐页图地址，
逐页取图后在本地合成 PDF，按「节」分目录存放。视频只有在线流，跳过。

用法：
    python batch_download.py --teachingmaterial <教材id> --chapter 第五章 --out <目录>
    python batch_download.py --teachingmaterial <id> --chapter 第五章 --section 第一节 --out <目录>
"""

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_resource import (  # noqa: E402
    DOC_TYPES,
    VIDEO_TYPES,
    SINGLE_URL,
    download_image,
    fetch_json,
    images_to_pdf,
    preview_images,
    safe_name,
)

BASE = "https://s-file-2.ykt.cbern.com.cn/zxx/ndrs/prepare_lesson"
TREE_URL = BASE + "/trees/{}.json"
PARTS_URL = BASE + "/teachingmaterials/{}/resources/parts.json"
WORKERS = 6


def load_catalog(tid):
    tree = fetch_json(TREE_URL.format(tid))
    if not isinstance(tree, list):
        raise SystemExit(f"章节树取不到：{tid}（教材 id 是否正确？）")
    parts = fetch_json(PARTS_URL.format(tid)) or []
    if isinstance(parts, str):
        parts = [parts]
    records = []
    for pu in parts:
        d = fetch_json(pu)
        if isinstance(d, list):
            records.extend(d)
    if not records:
        raise SystemExit("资源分片取不到，换 --refresh 或检查网络")
    return tree, records


def find_chapter(tree, keyword, chapter_id=None):
    for node in tree:
        if chapter_id and node.get("id") == chapter_id:
            return node
        if keyword and keyword in (node.get("title") or ""):
            return node
    return None


def section_nodes(chapter):
    return chapter.get("child_nodes") or []


def collect_docs(record):
    """返回 [(子文件标题, 类型, preview urls)]，跳过视频。"""
    docs = []
    rel = record.get("relations") or {}
    for value in rel.values():
        if not isinstance(value, list):
            continue
        for item in value:
            rtype = item.get("resource_type_code")
            if rtype in VIDEO_TYPES:
                continue
            title = (item.get("global_title") or {}).get("zh-CN") or item.get("title") or item.get("id")
            urls = preview_images(item)
            if urls:
                docs.append((title, rtype, urls))
    return docs


def collect_videos(record):
    vids = []
    for value in (record.get("relations") or {}).values():
        if isinstance(value, list):
            for item in value:
                if item.get("resource_type_code") in VIDEO_TYPES:
                    t = (item.get("global_title") or {}).get("zh-CN") or item.get("title")
                    vids.append(t)
    return vids


def grab_images(urls, img_dir, workers=WORKERS):
    img_dir.mkdir(parents=True, exist_ok=True)
    todo = []
    for i, u in enumerate(urls, 1):
        dest = img_dir / f"{i:03d}.jpg"
        if not dest.exists() or dest.stat().st_size < 1024:
            todo.append((u, dest))

    def task(pair):
        u, dest = pair
        return u, download_image(u, dest)

    if todo:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(task, todo))

    present = sorted(p for p in img_dir.glob("*.jpg") if p.stat().st_size >= 1024)
    return present


def build_doc(title, rtype, urls, out_dir, label_override=None):
    label = label_override or DOC_TYPES.get(rtype, rtype)
    stem = f"{label}-{safe_name(title)}"
    img_dir = out_dir / f"{stem}_页面图"
    files = grab_images(urls, img_dir)
    if not files:
        print(f"    [失败] {title}：页面图一张也没取到")
        return None
    pdf = out_dir / f"{stem}.pdf"
    if images_to_pdf(files, pdf):
        mb = pdf.stat().st_size / 1048576
        print(f"    [OK] {label} {title}：{len(files)}/{len(urls)} 页 -> {pdf.name}（{mb:.2f}MB）")
        return (pdf, len(files))
    print(f"    [失败] 合成 PDF 失败：{title}")
    return None


def main():
    p = argparse.ArgumentParser(description="按章节批量下载课时资料")
    p.add_argument("--teachingmaterial", required=True, help="教材 id（备课页 teachingmaterialId）")
    p.add_argument("--chapter", help="章名关键词，如 第五章")
    p.add_argument("--chapter-id", help="章节点 id（更精确）")
    p.add_argument("--section", help="只下某一节，如 第一节")
    p.add_argument("--out", default=".", help="输出根目录")
    p.add_argument("--images-only", action="store_true", help="保留页面图，不删（默认保留）")
    args = p.parse_args()

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    tree, records = load_catalog(args.teachingmaterial)
    chapter = find_chapter(tree, args.chapter, args.chapter_id)
    if not chapter:
        titles = [n.get("title") for n in tree]
        raise SystemExit(f"没找到章。可用章节：{titles}")
    sections = section_nodes(chapter)
    if args.section:
        sections = [s for s in sections if args.section in (s.get("title") or "")]
        if not sections:
            raise SystemExit(f"章内没有节匹配 {args.section}")

    print(f"教材：{args.teachingmaterial}")
    print(f"章节：{chapter.get('title')}，{len(sections)} 节")
    print(f"输出：{out_root.resolve()}\n")

    chapter_ids = [chapter.get("id")] + [s.get("id") for s in sections]
    rows = [r for r in records if set(r.get("chapter_ids") or []) & set(chapter_ids)]
    print(f"本章资源 {len(rows)} 个\n")

    report = []
    total_pdf = 0
    for sec in sections:
        sec_title = sec.get("title") or sec.get("id")
        sec_dir = out_root / safe_name(sec_title, 80)
        sec_dir.mkdir(parents=True, exist_ok=True)
        print(f"== {sec_title}")
        sec_rows = [r for r in rows if sec.get("id") in (r.get("chapter_ids") or [])]
        seen_names = {}
        for rec in sec_rows:
            rtype = rec.get("resource_type_code")
            pkg_title = rec.get("title") or ""
            docs = collect_docs(rec)
            vids = collect_videos(rec)
            if not docs:
                # 单份资源（如课件 coursewares）：走单份详情接口
                d = fetch_json(SINGLE_URL.format(rec.get("id")))
                urls = preview_images(d) if d else []
                docs = [(pkg_title, rtype, urls)] if urls else []
            print(f"  [{rtype}] {pkg_title} -> {len(docs)} 份文档")
            for title, utype, urls in docs:
                label = DOC_TYPES.get(utype, utype)
                key = f"{label}-{safe_name(title)}"
                n = seen_names.get(key, 0)
                seen_names[key] = n + 1
                override = label if n == 0 else f"{label}({n + 1})"
                res = build_doc(title, utype, urls, sec_dir, label_override=override)
                if res:
                    total_pdf += 1
                    report.append((sec_title, pkg_title, res[0].name, res[1]))
            for v in vids:
                print(f"    [视频] {v}：仅在线观看")

    lines = ["# 下载清单", "", f"章节：{chapter.get('title')}", ""]
    for sec_title, pkg, name, pages in report:
        lines.append(f"- {sec_title}｜{pkg}｜{name}（{pages} 页）")
    lines.append("")
    lines.append("视频类资源站点只提供在线播放，未包含在本目录。")
    (out_root / "清单.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"\n合计 {total_pdf} 份 PDF，清单：{out_root / '清单.md'}")


if __name__ == "__main__":
    main()
