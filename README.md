# smartedu-resources

一个自建的 Skill：检索并下载**国家中小学智慧教育平台**（basic.smartedu.cn / 智慧中小学）的资源——电子教材 PDF、课时课件、教学设计、学习任务单、作业练习，以及把它们批量转成 PPTX 和可编辑 Word。

资源全部免费；仓库里**只有代码与说明**，不含任何从平台下载的文件。

## 能做什么

| 能力 | 脚本 | 产物 |
|---|---|---|
| 教材检索、下载原版 PDF | `scripts/smartedu.py` | `.pdf` |
| 单份课时资源抓取 | `scripts/fetch_resource.py` | `.pdf` + 页面图 |
| 整章 / 整节批量下载 | `scripts/batch_download.py` | 按节分目录 + `清单.md` |
| 课件转 PPT | `scripts/to_pptx.py` | `.pptx`（每页铺满原图，视觉同原件） |
| **PDF 解析成 markdown** | `scripts/pdf_to_md.py` | `.md` + 裁切插图（云端接口或本地 OCR） |
| **markdown 转可编辑 Word** | `scripts/md_to_docx.py` / `scripts/build_docs.py` | `.docx`（真表格 + 插图原位） |
| 依赖一键安装与自检 | `scripts/setup.py` | 环境就绪 / 未就绪 |

实测过整套流程：人教版八年级上册物理第五章（5 节）——54 份 PDF/602 页、20 个视频（只在线）、22 份课件转 PPTX，32 份教学设计/任务单/作业转成可编辑 Word（3.31MB）。

## 快速开始

```bash
# 1) 装依赖（首次必跑）
python scripts/setup.py -y --mirror tsinghua
python scripts/setup.py --check --self-test

# 2) 下载整章
python scripts/batch_download.py --teachingmaterial 5370d999-5dd2-4c64-a9ed-089ec2694300 --chapter 第五章 --out "<输出目录>"

# 3) 课件转 PPT
python scripts/to_pptx.py --in "<某课的课件.pdf>" --out "<输出目录>"

# 4) 文档转可编辑 Word（两步：先出 md，再出 docx）
python scripts/pdf_to_md.py --engine textin --in "第一节 透镜" --out-dir md      # 需 TEXTIN_APP_ID / TEXTIN_SECRET_CODE
python scripts/build_docs.py --md "md/作业练习-第1节  透镜.md" --out "<输出目录>" --name "作业练习-第1节 透镜.docx"
```

## 文档转成可编辑 Word（重点）

平台给的 PDF 是由逐页图片合成的，**没有文字层**（`pymupdf.get_text()` 返回 0 字符），所以“直接转 docx”的工具只能得到整页扫描图。合格产物必须走两步：**解析成 markdown（还原文字、表格、插图位置）→ 渲染成 docx**。

验收口径：①题目文字是可编辑段落，不是图片；②每张插图留在它所属的题目位置；③该保留的表格是真 Word 表格且合并单元格正确。

解析按环境选一档，质量从高到低：

- **A｜TextIn xParse HTTP 接口（推荐，任何宿主可用）**：`pdf_to_md.py --engine textin`。接口 `POST https://api.textin.com/api/v1/xparse/parse/sync`，请求头 `x-ti-app-id`/`x-ti-secret-code`，multipart 上传文件 + config（`table_view=html`、`include_table_structure=true`、`include_image_data=true`）。key 在 `https://www.textin.com` → 工作台 → 账号设置 → 开发者信息，有免费额度（每日 1000 页量级）。质量与豆包版一致。
- **B｜宿主自带版面解析 MCP**：装了就最省事，直接用插件产出 markdown 存到 `<work>/md/`，再跑 `build_docs.py`。
- **C｜本地 OCR 兜底（不联网、不要账号）**：`setup.py -y --local-ocr` 后 `pdf_to_md.py --engine local`。RapidOCR 出文字、RapidLayout 找图/表区域、自实现行聚类与裁切插回。**质量有限**：实测一页 7 张图能出 4~5 张、表格列数可能错、公式失真。只能应急，交付时需说明“对照源 PDF 复核”。

渲染器（`md_to_docx.py`）的能力：HTML 表格 → 真 Word 表格（含 `colspan`/`rowspan`）；markdown 管道表格自动转真表格；单元格内容按 `<br>`/`<img>` 文档顺序切段，文字与插图交替；插图支持 http(s) URL 与本地绝对路径，宽高双限缩放；连续多图并排；丢弃 LaTeX 碎片与页眉残留。

## WorkBuddy 上用

豆包 App 里可直接用 xParse 插件；WorkBuddy 没有这个插件，所以原版只写插件名的写法会“能下载、出不 docx”。已修正：`workbuddy/SKILL.md` 把转 Word 拆成上面 A/B/C 三档，插件不再是必需。

```bash
# 装到 WorkBuddy 后，首次先跑依赖
python scripts/setup.py -y --mirror tsinghua
# 再设云端解析凭证（Windows PowerShell）
$env:TEXTIN_APP_ID="xxx"; $env:TEXTIN_SECRET_CODE="yyy"
# 然后一条命令出 md + 一条命令出 docx
python scripts/pdf_to_md.py --engine textin --in "第一节 透镜" --out-dir md
python scripts/build_docs.py --work <md 所在工作目录> --out "<输出目录>"
```

详细安装步骤、常见问题与两个版本的差异，见 `workbuddy/安装说明.md`。

## 目录结构

```text
├─ README.md
├─ smartedu-resources/            # 主技能（豆包 App 直接可用）
│  ├─ SKILL.md
│  ├─ references/api.md           # 接口实测记录
│  └─ scripts/
│     ├─ setup.py
│     ├─ smartedu.py
│     ├─ fetch_resource.py
│     ├─ batch_download.py
│     ├─ to_pptx.py
│     ├─ pdf_to_md.py
│     ├─ md_to_docx.py
│     └─ build_docs.py
└─ workbuddy/                     # WorkBuddy 适配
   ├─ SKILL.md                    # 带 allowed-tools，不依赖插件
   └─ 安装说明.md
```

## 依赖

- 必需：`pillow`、`pymupdf`、`python-pptx`、`python-docx`、`requests`；Python 3.8+。
- 可选 `--local-ocr` 组：`rapidocr`、`rapid-layout`、`opencv-python-headless`、`numpy`。
- docx 交付前自检另需 `pywin32`（docx→PDF 出图核对，只在 Windows 需要）。

`setup.py` 会检测并安装，镜像默认官方、失败自动换清华源。

## 接口与边界

- 目录：`https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/...`；章节树 `https://s-file-2.ykt.cbern.com.cn/zxx/ndrs/prepare_lesson/trees/{teachingmaterialId}.json`；页面图主机 `r1/r2/r3-ndr.ykt.cbern.com.cn`。
- 教材 PDF：`https://cdncs.ykt.cbern.com.cn/v0.1/static/edu_product/esp/assets/{id}.pkg/pdf.pdf`，公开可下。
- 不可用：`r*-ndr-private` 上的 `transcode/pdf.pdf`（401）与 `m3u8`（401/403）需签名；视频只能登录后在线观看。
- 平台要求：资源免费，但“任何单位及个人不得用于商业行为”。仓库只含代码，不含资源文件；请勿把下载的教材/课件再分发。

接口细节见 `smartedu-resources/references/api.md`。

## License

仅供学习与教学使用。平台资源版权归原作者/出版方所有。
