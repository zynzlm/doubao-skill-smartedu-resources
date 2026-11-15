#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""国家中小学智慧教育平台（basic.smartedu.cn）资源检索与电子教材下载。

无需登录，只用平台公开的静态目录接口。用法见 SKILL.md。
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

FILE_HOST = "https://s-file-1.ykt.cbern.com.cn/zxx"
SITE = "https://basic.smartedu.cn"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Referer": SITE + "/"}

# ---------------------------------------------------------------- 模块定义

MODULES = {
    "textbook": {
        "entry": FILE_HOST + "/ndrs/resources/tch_material/version/data_version.json",
        "label": "电子教材",
        "pdf": True,
    },
    "course": {
        "entry": FILE_HOST + "/ndrs/national_lesson/teachingmaterials/version/data_version.json",
        "label": "课程教学目录",
        "pdf": False,
    },
    "homework": {
        "entry": FILE_HOST + "/ndrs/questions/teachingmaterials/version/data_version.json",
        "label": "作业习题目录",
        "pdf": False,
    },
    "experiment": {
        "entry": FILE_HOST + "/ndrs/experiment/teachingmaterials/version/data_version.json",
        "label": "实验教学",
        "pdf": False,
    },
    "lesson_plan": {
        "entry": FILE_HOST + "/ndrs/prepare_lesson/teachingmaterials/parts.json",
        "label": "备课资源",
        "pdf": False,
    },
}

ALIASES = {
    "教材": "textbook", "课本": "textbook", "电子教材": "textbook", "电子课本": "textbook",
    "textbook": "textbook", "tch_material": "textbook",
    "课程": "course", "国家课程": "course", "名师课": "course", "课程教学": "course",
    "course": "course", "national_lesson": "course",
    "作业": "homework", "习题": "homework", "练习": "homework",
    "homework": "homework", "questions": "homework",
    "实验": "experiment", "experiment": "experiment",
    "备课": "lesson_plan", "教案": "lesson_plan", "lesson_plan": "lesson_plan",
    "prepare_lesson": "lesson_plan",
}

# 标签维度 -> 我们的字段名
DIM_FIELDS = {
    "zxxxd": "stage",     # 学段
    "zxxk": "subject",    # 学科（部分模块用 zxxxk）
    "zxxxk": "subject",
    "zxxbb": "version",   # 版本/出版社
    "zxxnj": "grade",     # 年级
    "zxxcc": "volume",    # 册次
    "zxxkb": "standard",  # 课程标准
    "sykmk": "topic",     # 实验模块
}
FIELD_LABELS = {
    "stage": "学段", "subject": "学科", "version": "版本",
    "grade": "年级", "volume": "册次", "standard": "课标", "topic": "主题",
}


# ---------------------------------------------------------------- 基础工具

def cache_dir() -> Path:
    env = os.environ.get("SMARTEDU_CACHE")
    if env:
        return Path(env)
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / ".cache"
    return base / "smartedu-skill"


def http_json(url: str, timeout: int = 120):
    last = None
    for attempt in range(3):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"请求失败：{url}\n{last}")


def resolve_module(name: str) -> str:
    key = (name or "").strip()
    if key in MODULES:
        return key
    if key in ALIASES:
        return ALIASES[key]
    lowered = key.lower()
    if lowered in ALIASES:
        return ALIASES[lowered]
    raise SystemExit(f"未知模块：{name}\n可选：" + "、".join(f"{k}({v['label']})" for k, v in MODULES.items()))


def entry_parts(module: str):
    """返回 (module_version, [part_url, ...])"""
    info = http_json(MODULES[module]["entry"], timeout=60)
    if isinstance(info, list):                      # prepare_lesson/parts.json
        return "static", info
    urls = info.get("urls") or []
    if isinstance(urls, str):
        urls = [u.strip() for u in urls.split(",") if u.strip()]
    return str(info.get("module_version") or "0"), urls


def normalize(item: dict, module: str) -> dict:
    tags = item.get("tag_list") or []
    dims = {"stage": "", "subject": "", "version": "", "grade": "",
            "volume": "", "standard": "", "topic": ""}
    for t in tags:
        field = DIM_FIELDS.get(t.get("tag_dimension_id"))
        if field and not dims.get(field):
            dims[field] = t.get("tag_name") or ""

    props = item.get("custom_properties") or {}
    thumbs = props.get("thumbnails") or []
    providers = item.get("provider_list") or []
    publisher = providers[0].get("name", "") if providers and isinstance(providers[0], dict) else ""

    rid = item.get("id") or item.get("version_id") or ""
    out = {
        "id": rid,
        "title": (item.get("title") or "").strip(),
        "module": module,
        "format": props.get("format") or "",
        "size_mb": round((props.get("size") or 0) / 1048576, 1),
        "thumb": thumbs[0] if thumbs else "",
        "publisher": publisher,
        "type": item.get("resource_type_code_name") or "",
    }
    out.update({k: v for k, v in dims.items() if v})
    return out


def build_index(module: str, refresh: bool = False) -> list:
    cdir = cache_dir()
    cdir.mkdir(parents=True, exist_ok=True)
    version, parts = entry_parts(module)
    cache_file = cdir / f"{module}.{version}.json"

    if cache_file.exists() and not refresh:
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

        # 版本未变时清理旧缓存
    for old in cdir.glob(f"{module}.*.json"):
        if old != cache_file:
            try:
                old.unlink()
            except OSError:
                pass

    items = []
    for url in parts:
        print(f"[抓取] {url.rsplit('/', 1)[-1]}", file=sys.stderr)
        data = http_json(url, timeout=180)
        for raw in data:
            try:
                items.append(normalize(raw, module))
            except Exception:
                continue

    cache_file.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    return items


# ---------------------------------------------------------------- 检索

def match(item: dict, args) -> bool:
    if args.keyword:
        hay = item.get("title", "").lower()
        if not all(tok.lower() in hay for tok in args.keyword.split()):
            return False
    for field in ("stage", "subject", "version", "grade", "volume", "standard", "topic"):
        wanted = getattr(args, field, None)
        if not wanted:
            continue
        have = item.get(field, "")
        if not have:
            return False
        w = wanted.strip()
        if w not in have and have not in w:
            return False
    return True


def detail_url(item: dict) -> str:
    if item.get("module") == "textbook":
        return (f"{SITE}/tchMaterial/detail?contentType=assets_document"
                f"&contentId={item['id']}&catalogType=tchMaterial&subCatalog=tchMaterial")
    return f"{SITE}/search?keyword={item.get('title', '')}"


def pdf_urls(rid: str):
    """公开静态镜像优先（无需登录），再退回 -private 主机。"""
    return [f"https://cdncs.ykt.cbern.com.cn/v0.1/static/edu_product/esp/assets/"
            f"{rid}.pkg/pdf.pdf"] + [
        f"https://r{h}-ndr-private.ykt.cbern.com.cn/edu_product/esp/assets/"
        f"{rid}.pkg/pdf.pdf" for h in (2, 1, 3)]


def safe_name(title: str, limit: int = 80) -> str:
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", title).strip("_ ")
    name = re.sub(r"_+", "_", name)
    return name[:limit] or "smartedu"


# ---------------------------------------------------------------- 命令

def cmd_modules(args):
    rows = []
    for key, meta in MODULES.items():
        try:
            version, parts = entry_parts(key)
            cached = list((cache_dir()).glob(f"{key}.*.json"))
            count = "已缓存" if cached else "未缓存"
            rows.append((key, meta["label"], len(parts), count, "支持" if meta["pdf"] else "仅目录"))
        except Exception as e:
            rows.append((key, meta["label"], "-", f"不可用({e.__class__.__name__})", "-"))
    print_table(["模块", "名称", "分片数", "状态", "PDF下载"], rows)


def cmd_facets(args):
    module = resolve_module(args.module)
    items = build_index(module, args.refresh)
    print(f"模块 {module}（{MODULES[module]['label']}）共 {len(items)} 条\n")
    for field in ("stage", "subject", "version", "grade", "volume", "standard", "topic"):
        counter = {}
        for it in items:
            v = it.get(field)
            if v:
                counter[v] = counter.get(v, 0) + 1
        if not counter:
            continue
        ordered = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
        print(f"【{FIELD_LABELS[field]}】共 {len(ordered)} 种")
        print("  " + "；".join(f"{k}({v})" for k, v in ordered[:40]) + (" …" if len(ordered) > 40 else ""))
        print()


def cmd_search(args):
    module = resolve_module(args.module)
    items = build_index(module, args.refresh)
    hits = [it for it in items if match(it, args)]

    if args.keyword:
        # 标题完全包含关键词优先
        hits.sort(key=lambda it: (args.keyword not in it["title"], len(it["title"])))

    total = len(hits)
    shown = hits[: args.limit]

    if args.json:
        print(json.dumps({"total": total, "items": shown}, ensure_ascii=False, indent=1))
        return

    print(f"命中 {total} 条，显示前 {len(shown)} 条（模块：{module}）\n")
    rows = []
    for it in shown:
        meta = "/".join(x for x in (it.get("stage"), it.get("subject"),
                                    it.get("version"), it.get("grade"), it.get("volume")) if x)
        rows.append((it["title"], meta, f"{it.get('size_mb', 0)}M" if it.get("size_mb") else "-", it["id"]))
    print_table(["标题", "学段/学科/版本/年级/册次", "大小", "ID"], rows)

    if args.with_links:
        print("\n详情页：")
        for it in shown:
            print("  " + detail_url(it))
        if MODULES[module]["pdf"]:
            print("\nPDF 直链：")
            for it in shown:
                print("  " + pdf_urls(it["id"])[0])


def cmd_link(args):
    module = resolve_module(args.module)
    items = build_index(module, args.refresh)
    by_id = {it["id"]: it for it in items}
    for rid in args.id:
        it = by_id.get(rid)
        if not it:
            print(f"{rid}  不在 {module} 目录中")
            continue
        print(f"{it['title']}\n  详情页：{detail_url(it)}")
        if MODULES[module]["pdf"]:
            print(f"  PDF：{pdf_urls(rid)[0]}")


def download_one(item: dict, out_dir: Path, dry: bool) -> bool:
    rid = item["id"]
    name = safe_name(item["title"])
    target = out_dir / f"{name}.pdf"
    if target.exists() and target.stat().st_size > 1024 * 1024:
        print(f"[跳过] 已存在 {target.name}")
        return True

    for url in pdf_urls(rid):
        if dry:
            print(f"[dry-run] {url}\n        -> {target}")
            return True
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=60) as r:
                ctype = r.headers.get("Content-Type", "")
                if "pdf" not in ctype:
                    continue
                tmp = target.with_suffix(".pdf.part")
                got = 0
                with open(tmp, "wb") as f:
                    while True:
                        chunk = r.read(1024 * 512)
                        if not chunk:
                            break
                        f.write(chunk)
                        got += len(chunk)
                tmp.replace(target)
                print(f"[完成] {target.name}  {got / 1048576:.1f} MB")
                return True
        except (HTTPError, URLError, TimeoutError, OSError) as e:
            print(f"[重试] {url.rsplit('/', 2)[-2][:8]}… {e}")
            continue
    print(f"[失败] {item['title']}")
    return False


def cmd_download(args):
    module = resolve_module(args.module)
    if not MODULES[module]["pdf"]:
        raise SystemExit(f"模块 {module} 不提供 PDF 下载，改用 search --with-links 拿详情页链接。")

    items = build_index(module, args.refresh)
    by_id = {it["id"]: it for it in items}

    todo = []
    for rid in args.id or []:
        if rid in by_id:
            todo.append(by_id[rid])
        else:
            print(f"[未匹配] {rid}")

    if not todo:
        hits = [it for it in items if match(it, args)]
        if args.keyword:
            hits.sort(key=lambda it: (args.keyword not in it["title"], len(it["title"])))
        todo = hits[: args.limit]
        if len(hits) > args.limit:
            print(f"共 {len(hits)} 条符合，仅处理前 {args.limit} 条；扩大范围请调 --limit")
    if not todo:
        raise SystemExit("没有匹配到教材。先用 search 看一下条件。")

    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"输出目录：{out_dir}\n待下载 {len(todo)} 本\n")

    ok = 0
    for it in todo:
        print(f"→ {it['title']}")
        if download_one(it, out_dir, args.dry_run):
            ok += 1
    print(f"\n完成 {ok}/{len(todo)}")


# ---------------------------------------------------------------- 输出

def width(s: str) -> int:
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in s)


def pad(s: str, n: int) -> str:
    return s + " " * max(0, n - width(s))


def print_table(headers, rows):
    cols = len(headers)
    widths = [width(h) for h in headers]
    for row in rows:
        for i in range(cols):
            widths[i] = min(72, max(widths[i], width(str(row[i]))))
    line = "  ".join(pad(h, widths[i]) for i, h in enumerate(headers))
    print(line)
    print("-" * width(line))
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            text = str(cell)
            if width(text) > widths[i]:
                cut, acc = "", 0
                for ch in text:
                    if acc + (2 if ord(ch) > 0x2E80 else 1) > widths[i] - 1:
                        break
                    cut += ch
                    acc += 2 if ord(ch) > 0x2E80 else 1
                text = cut + "…"
            cells.append(pad(text, widths[i]))
        print("  ".join(cells))


# ---------------------------------------------------------------- 入口

def main():
    p = argparse.ArgumentParser(
        description="国家中小学智慧教育平台资源检索 / 电子教材下载",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--refresh", action="store_true", help="强制重建本地索引")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("modules", help="列出可用模块").set_defaults(func=cmd_modules)

    f = sub.add_parser("facets", help="查看某模块的学段/学科/版本/年级取值")
    f.add_argument("--module", required=True)
    f.set_defaults(func=cmd_facets, args_for_match=None)

    def add_filters(sp):
        sp.add_argument("--module", required=True, help="textbook/course/homework/experiment/lesson_plan 或中文名")
        sp.add_argument("--keyword", help="标题关键词，空格分隔表示同时包含")
        sp.add_argument("--stage", help="学段：小学/初中/高中/小学（五•四学制）…")
        sp.add_argument("--subject", help="学科：语文/数学/英语…")
        sp.add_argument("--version", help="版本：人教版/北师大版…")
        sp.add_argument("--grade", help="年级：一年级…高三")
        sp.add_argument("--volume", help="册次：上册/下册")
        sp.add_argument("--standard", help="课程标准（部分模块）")
        sp.add_argument("--topic", help="主题（实验模块）")

    s = sub.add_parser("search", help="按条件检索资源")
    add_filters(s)
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--with-links", action="store_true", help="同时输出详情页与 PDF 直链")
    s.set_defaults(func=cmd_search)

    l = sub.add_parser("link", help="按 ID 输出详情页与 PDF 链接")
    l.add_argument("--module", required=True)
    l.add_argument("--id", nargs="+", required=True)
    l.set_defaults(func=cmd_link)

    d = sub.add_parser("download", help="下载电子教材 PDF")
    add_filters(d)
    d.add_argument("--id", nargs="+", help="直接指定教材 ID")
    d.add_argument("--limit", type=int, default=3, help="按条件批量下载时的上限")
    d.add_argument("--out", default=".", help="输出目录")
    d.add_argument("--dry-run", action="store_true", help="只打印将下载的链接")
    d.set_defaults(func=cmd_download)

    args = p.parse_args()
    if getattr(args, "keyword", None) is None and args.cmd in ("search", "download"):
        pass
    args.func(args)


if __name__ == "__main__":
    main()
