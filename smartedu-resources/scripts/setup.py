#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键检查并安装 smartedu-resources 的全部 Python 依赖。

首次使用、换机器、或报 ModuleNotFoundError 时先跑这个：

    python scripts/setup.py                  # 缺什么装什么（带确认）
    python scripts/setup.py --check          # 只看状态，不动环境
    python scripts/setup.py -y               # 缺什么直接装，不询问
    python scripts/setup.py --mirror tsinghua  # 走国内镜像
    python scripts/setup.py --self-test      # 装完顺手验一遍 6 个脚本能不能跑

退出码：0 表示依赖齐全（或已装好）；1 表示仍有核心依赖缺失。
"""

import argparse
import importlib.util
import os
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# (import 名, pip 包名, 用途, 是否核心)
DEPS = [
    ("PIL", "pillow", "页面图合成 PDF（fetch_resource / batch_download）", True),
    ("fitz", "pymupdf", "课件 PDF→PPTX、页图渲染（to_pptx / md_to_docx）", True),
    ("pptx", "python-pptx", "写 .pptx（to_pptx）", True),
    ("docx", "python-docx", "写 .docx（md_to_docx / build_docs）", True),
    ("requests", "requests", "可选：HTTP 客户端（脚本本体用标准库 urllib）", False),
]

MIRRORS = {
    "tsinghua": "https://pypi.tuna.tsinghua.edu.cn/simple",
    "aliyun": "https://mirrors.aliyun.com/pypi/simple",
    "ustc": "https://mirrors.ustc.edu.cn/pypi/simple",
    "tencent": "https://mirrors.cloud.tencent.com/pypi/simple",
    "pypi": "https://pypi.org/simple",
}

# 依赖检查通过后，顺带确认这几个脚本能被解释器加载（--help 即退出）
SELF_TEST = [
    "smartedu.py", "fetch_resource.py", "batch_download.py",
    "to_pptx.py", "md_to_docx.py", "build_docs.py",
]

HERE = os.path.dirname(os.path.abspath(__file__))


def installed(module_name):
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError, AttributeError):
        return False


def pip_install(pkgs, index_url=None, quiet=True):
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check"]
    if quiet:
        cmd.append("-q")
    if index_url:
        cmd += ["-i", index_url, "--trusted-host", index_url.split("//")[-1].split("/")[0]]
    cmd += pkgs
    return subprocess.call(cmd)


def try_install(pkgs, mirror=None, keep_going=True):
    """先按指定镜像（或官方）装，失败再换国内镜像重试一次。"""
    order = []
    if mirror:
        order.append(mirror)
    order.append(MIRRORS["pypi"])
    if mirror != MIRRORS["tsinghua"]:
        order.append(MIRRORS["tsinghua"])

    for i, idx in enumerate(order):
        print(f"  pip install {' '.join(pkgs)}  ← {idx}")
        rc = pip_install(pkgs, idx)
        if rc == 0:
            return True
        if not keep_going:
            return False
        if i == len(order) - 1:
            print("  [失败] 三个源都没装成，可手动执行：")
            print(f"         {sys.executable} -m pip install {' '.join(pkgs)}")
    return False


def report(verbose=True):
    rows, missing_core, missing_opt = [], [], []
    for mod, pkg, why, core in DEPS:
        ok = installed(mod)
        rows.append((pkg, mod, "已安装" if ok else "缺失", "必需" if core else "可选", why))
        if not ok:
            (missing_core if core else missing_opt).append(pkg)
    if verbose and rows:
        print("依赖状态：\n")
        for pkg, mod, state, need, why in rows:
            print(f"  [{state:4s}] {pkg:12s} (import {mod:8s}) {need}  {why}")
    return missing_core, missing_opt


def python_ok():
    v = sys.version_info
    print(f"Python {v.major}.{v.minor}.{v.micro}  ({sys.executable})")
    if v < (3, 8):
        print("  [警告] 需要 Python 3.8 及以上，当前版本过低。")
        return False
    return True


def self_test():
    print("\n脚本自检（只跑 --help，不联网、不下载）：")
    bad = []
    for name in SELF_TEST:
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            print(f"  [缺失] {name} 不在 {HERE}")
            bad.append(name)
            continue
        try:
            r = subprocess.run([sys.executable, path, "--help"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        except Exception as e:
            print(f"  [失败] {name}  {e}")
            bad.append(name)
            continue
        if r.returncode == 0:
            print(f"  [OK]   {name}")
        else:
            tail = (r.stderr or b"").decode("utf-8", "replace").strip().splitlines()
            print(f"  [失败] {name}  {tail[-1] if tail else r.returncode}")
            bad.append(name)
    return bad


def main():
    ap = argparse.ArgumentParser(description="检查/安装 smartedu-resources 的 Python 依赖")
    ap.add_argument("--check", action="store_true", help="只检查，不安装")
    ap.add_argument("-y", "--yes", action="store_true", help="缺依赖时直接安装，不再确认")
    ap.add_argument("--mirror", choices=list(MIRRORS), default=None, help="pip 镜像（默认官方，失败自动换清华源）")
    ap.add_argument("--optional", action="store_true", help="连可选依赖 requests 一起装")
    ap.add_argument("--self-test", action="store_true", help="装完逐个跑脚本 --help 验证")
    args = ap.parse_args()

    python_ok()
    missing_core, missing_opt = report()

    todo = list(missing_core)
    if args.optional:
        todo += missing_opt

    if args.check:
        print(f"\n检查完毕：缺核心依赖 {len(missing_core)} 个"
              + (f"（{'、'.join(missing_core)}）" if missing_core else "")
              + f"，缺可选依赖 {len(missing_opt)} 个")
        if args.self_test:
            self_test()
        return 0 if not missing_core else 1

    if not todo:
        print("\n依赖齐全，无需安装。")
    else:
        print(f"\n待安装 {len(todo)} 个：{'、'.join(todo)}")
        if not args.yes:
            try:
                ans = input("现在安装？(Y/n) ").strip().lower()
            except EOFError:
                ans = "y"
            if ans and ans[0] == "n":
                print("已跳过安装。缺依赖时脚本会报 ModuleNotFoundError。")
                return 1 if missing_core else 0
        t0 = time.time()
        ok = try_install(todo, MIRRORS.get(args.mirror) if args.mirror else None)
        print(f"\n安装{'成功' if ok else '未完成'}，耗时 {time.time() - t0:.0f}s")
        print()
        still_core, still_opt = report()
        if still_core:
            print(f"\n[未解决] 仍有核心依赖缺失：{'、'.join(still_core)}")
            print("可尝试：换 --mirror tsinghua / 关掉代理 / 升级 pip：python -m pip install -U pip")
            return 1

    if args.self_test:
        bad = self_test()
        if bad:
            print("\n[异常] 上述脚本未通过自检，先看报错再往下用。")
            return 1
        print("\n全部脚本自检通过。")

    print("\n环境就绪。用法示例：")
    print(f"  {sys.executable} {os.path.join(HERE, 'smartedu.py')} modules")
    return 0


if __name__ == "__main__":
    sys.exit(main())
