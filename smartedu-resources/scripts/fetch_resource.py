#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取国家中小学智慧教育平台课时资源并合成为 PDF。

站点不提供课件/教学设计的原文件下载，只给逐页转码图（公开可访问）；
本脚本把整份资料的页面图取回，按顺序合成一个 PDF，便于保存和打印。

用法：
    python fetch_resource.py --id <resourceId> --out <目录>
    python fetch_resource.py --url "<备课详情页URL>" --out <目录>
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SITE = "https://basic.smartedu.cn"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Referer": SITE + "/"}

SINGLE_URL = "https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/prepare_sub_type/resources/details/{}.json"
PACKAGE_URL = "https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/resources/{}.json"

DOC_TYPES = {
    "coursewares": "课件",
    "lesson_plandesign": "教学设计",
    "learning_task": "学习任务单",
    "after_class_exercise": "作业练习",
    "courseware": "课件",
    "lesson_plan": "教案",
}
VIDEO_TYPES = {"micro_lesson_video", "video", "lesson_video"}


def fetch_json(url: str, timeout: int = 60):
    last = None
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers=HEADERS), timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            time.sleep(1 + attempt)
    return None


def resolve(rid: str):
    """返回 ('single'|'package', data)"""
    d = fetch_json(SINGLE_URL.format(rid))
    if d and d.get("id"):
        return "single", d
    d = fetch_json(PACKAGE_URL.format(rid))
    if d and isinstance(d.get("relations"), dict):
        return "package", d
    return None, None


def preview_images(detail: dict):
    """按页序返回图片 URL 列表"""
    cp = detail.get("custom_properties") or {}
    preview = cp.get("preview") or {}
    if isinstance(preview, dict) and preview:
        pairs = []
        for k, v in preview.items():
            m = re.search(r"(\d+)", str(k))
            if m and isinstance(v, str):
                pairs.append((int(m.group(1)), v))
        if pairs:
            return [u for _, u in sorted(pairs)]

    # 退化：ti_items 里 image 模板，按 1..N 拼（N 取 size/resolution 无法得知，尽量从 preview 之外找）
    for it in detail.get("ti_items") or []:
        if it.get("ti_file_flag") == "image" and it.get("ti_storages"):
            base = it["ti_storages"][0]
            if base.endswith("/image"):
                return [f"{base}/{i}.jpg" for i in range(1, 200)]  # 由下载逻辑探测到 404 即止
    return []


def download_image(url: str, dest: Path, probe: bool = False):
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=45) as r:
            data = r.read()
        if not data or len(data) < 1024:
            return False
        dest.write_bytes(data)
        return True
    except HTTPError as e:
        if probe and e.code == 404:
            return None      # 探测式列表：到此为止
        return False
    except (URLError, TimeoutError, OSError):
        return False


def images_to_pdf(image_files, pdf_path: Path):
    try:
        from PIL import Image
    except ImportError:
        print("需要 Pillow：pip install pillow", file=sys.stderr)
        return False
    pages = []
    for f in image_files:
        try:
            img = Image.open(f)
            pages.append(img.convert("RGB"))
        except Exception:
            continue
    if not pages:
        return False
    first = pages[0]
    first.save(pdf_path, "PDF", resolution=150.0, save_all=True, append_images=pages[1:])
    return True


def safe_name(title: str, limit: int = 70) -> str:
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", str(title or "")).strip("_ ")
    name = re.sub(r"_+", "_", name)
    name = re.sub(r"\.(pptx|ppt|docx|doc|pdf|xlsx)$", "", name, flags=re.I)
    return name[:limit] or "resource"


def build_one(rid: str, title: str, out_dir: Path, images_only=False):
    d = fetch_json(SINGLE_URL.format(rid))
    if not d:
        print(f"[跳过] {title}：详情取不到（可能需要登录态）")
        return False
    title = title or d.get("title") or rid
    urls = preview_images(d)
    if not urls:
        print(f"[跳过] {title}：没有可用的页面图")
        return False

    stem = safe_name(title)
    img_dir = out_dir / f"{stem}_页面图"
    img_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    probing = urls and "/image/" in urls[0] and re.search(r"/image/\d+\.jpg$", urls[0]) is None
    for i, u in enumerate(urls, 1):
        dest = img_dir / f"{i:03d}.jpg"
        if dest.exists():
            saved.append(dest)
            continue
        ok = download_image(u, dest, probe=probing)
        if ok is None:
            break
        if ok:
            saved.append(dest)
    print(f"  {title}：{len(saved)}/{len(urls)} 页")

    if not saved:
        return False
    if images_only:
        return True
    pdf = out_dir / f"{stem}.pdf"
    if images_to_pdf(saved, pdf):
        print(f"  -> {pdf}")
        return True
    print(f"  [失败] 合成 PDF 失败：{title}")
    return False


def main():
    p = argparse.ArgumentParser(description="抓课时资源页面图并合成 PDF")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--id", help="资源 ID（备课详情页 URL 里的 resourceId）")
    g.add_argument("--url", help="备课详情页完整 URL")
    p.add_argument("--out", default=".", help="输出目录")
    p.add_argument("--images-only", action="store_true", help="只存页面图，不合成 PDF")
    args = p.parse_args()

    rid = args.id
    if args.url:
        m = re.search(r"resourceId=([0-9a-f\-]+)", args.url)
        if not m:
            raise SystemExit("URL 里没有 resourceId，请直接传 --id")
        rid = m.group(1)

    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)

    kind, data = resolve(rid)
    if kind is None:
        raise SystemExit(f"{rid}：接口取不到，可能需要在浏览器里登录后再试")

    if kind == "single":
        ok = build_one(rid, data.get("title"), out, args.images_only)
        print("\n完成" if ok else "\n未完成")
        return

    rel = (data.get("relations") or {}).get("course_resource") or []
    print(f"课程包：{data.get('title')}，含 {len(rel)} 项资源\n")
    done, skipped = 0, []
    for it in rel:
        t = (it.get("global_title") or {}).get("zh-CN") or it.get("title") or it.get("id")
        rtype = it.get("resource_type_code")
        if rtype in VIDEO_TYPES:
            skipped.append((t, "视频仅支持在线观看，站点不提供下载"))
            continue
        label = DOC_TYPES.get(rtype, rtype)
        print(f"- [{label}] {t}")
        if build_one(it.get("id"), t, out, args.images_only):
            done += 1
        else:
            skipped.append((t, "未能取得页面图"))

    print(f"\n完成 {done} 份")
    for t, why in skipped:
        print(f"  跳过：{t}（{why}）")


if __name__ == "__main__":
    main()
