# doubao-skill-smartedu-resources

一个可直接安装使用的 **Agent Skill**：把国家中小学智慧教育平台（[basic.smartedu.cn](https://basic.smartedu.cn)，即“智慧中小学”）的公开资源检索并下载到本地。

平台所有资料都是免费的，但站点没有“下载”按钮：课件/教学设计/学习任务单/作业练习只有逐页转码图，视频只有在线流。本技能把能公开取到的全部拉下来，并额外提供「课件→PPTX」和「文档→可编辑 Word（保留原题插图与真表格）」两条后处理链路。

## 能做什么

| 能力 | 入口脚本 | 说明 |
|---|---|---|
| 电子教材检索与下载 | `scripts/smartedu.py` | 约 3500 本教材，按学段/学科/版本/年级/册次筛选，下载完整 PDF |
| 单份课时资源 | `scripts/fetch_resource.py` | 粘一个详情页链接或 resourceId，逐页取图合成 PDF |
| 整章 / 整节批量 | `scripts/batch_download.py` | 给定教材 id + 章名，一次拉完整章按节分目录，并写 `清单.md` |
| 课件 → PPTX | `scripts/to_pptx.py` | 每页原图铺满一页 16:9 幻灯片，视觉与原件一致 |
| 文档 → 可编辑 Word | `scripts/md_to_docx.py` + `scripts/build_docs.py` | 配合 TextIn xParse 解析结果，重建真表格 + 原位插图的可编辑 docx |

## 仓库结构

```
doubao-skill-smartedu-resources/
├── README.md
└── smartedu-resources/          ← 技能本体（整目录）
    ├── SKILL.md                 ← 入口与完整流程说明
    ├── references/api.md        ← 实测过的接口、主机行为、失效端点
    └── scripts/                 ← 6 个可运行脚本（见上表）
```

## 安装（3 步）

1. `git clone https://github.com/zynzlm/doubao-skill-smartedu-resources.git`
2. 把仓库里的 `smartedu-resources/` 整个目录复制到你所使用客户端的**用户技能目录**（user skills，各客户端位置不同，见对应客户端帮助；目录内必须直接是 `SKILL.md`）。若客户端要求目录名与技能名一致，把目录名保持为 `smartedu-resources` 即可。
3. 重启会话或重新加载技能，然后直接说“下人教版八年级上册物理第五章的全部资料”这类需求即可触发。

> 不装到客户端也可以当普通脚本用：直接 `python smartedu-resources/scripts/smartedu.py --help`。

## 依赖

Python 3.8+（推荐 3.10+）。

```bash
pip install requests pillow pymupdf python-pptx python-docx
```

| 依赖 | 用途 |
|---|---|
| `requests` | 可选，脚本本体用标准库 `urllib` |
| `pillow` | 页面图合成 PDF |
| `pymupdf` | 课件 PDF → PPTX、页图预览 |
| `python-pptx` | 写 PPTX |
| `python-docx` | 写 docx |
| `pywin32` | 可选，Windows 上docx→PDF 自查 |

## 快速上手

```bash
# 1) 看有哪些教材版本
python scripts/smartedu.py facets --module textbook

# 2) 检索并下载一本教材标注
python scripts/smartedu.py download --module textbook --subject 物理 --grade 八年级 --version 人教版 --volume 上册 --out "<目录>"

# 3) 下整章全部资料（章 id 来自备课页 URL 的 teachingmaterialId）
python scripts/batch_download.py --teachingmaterial 5370d999-5dd2-4c64-a9ed-089ec2694300 --chapter 第五章 --out "<输出目录>"

# 4) 课件 PDF 转 PPTX
python scripts/to_pptx.py --in "课件-第1节 透镜.pdf" --out "<输出目录>"
```

输出结构：`<输出目录>/第一节 透镜/课件-xxx.pdf`、`教学设计-xxx.pdf` …，并在根目录生成 `清单.md`（每份的页数与来源）。

## 文档转可编辑 Word

平台不提供教学设计/学习任务单/作业练习的原 docx。需要**可编辑文字 + 插图留在原题位置 + 真表格（含合并单元格）**时，走这条链路：

1. 用 TextIn xParse 解析源 PDF（`result_format=markdown`、`table_view=html`、`include_table_structure=true`），得到每份一个 md；
2. `python scripts/build_docs.py --work <work> --out <目录>` 批量渲染；`<work>/md/cXX.md` + `<work>/fileids.json`（`{"ok":{"c01":{"path":"<源PDF绝对路径>"}}}`）。

渲染器做的事：HTML 表格转真 Word 表格（支持 `colspan`/`rowspan`）；单元格内文字与 `<img>` 按文档顺序切段交替输出，连续多图同段并排；图片宽高双限缩放；剔除页眉残留与 LaTeX 碎片。

**必须人工校正的两处：**

- 表格单元格内的多张插图在解析结果里**只有顺序、没有坐标**，需要对照源 PDF 页图把 `<img>` 插回每道题之后；
- OCR 错字/公式碎片需按原图补齐。

## 合规与边界

- 平台声明资源免费，但**“任何单位及个人不得用于商业行为”**。本仓库只放代码与说明，**不包含任何下载的资源文件**。
- 请只按需取用户明确需要的少数几份，不做整库搬运。
- 视频是 m3u8 在线流，地址带签名，**不支持下载**；需要留存请由用户登录后在线观看或自行录屏。
- 登录：教材 PDF 与课时页面图都是公开接口。遇到需要登录的场景（视频、“我的资源库”），按 `SKILL.md` 第四节用浏览器打开登录页并交给用户完成登录，不要索取密码。

接口细节与已验证不可用的端点见 [`smartedu-resources/references/api.md`](smartedu-resources/references/api.md)。

## License

仅供学习与教学备课使用。平台资源版权归国家中小学智慧教育平台及原始提供方所有。
