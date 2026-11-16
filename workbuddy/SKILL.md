---
name: smartedu-resources
description: 检索并下载国家中小学智慧教育平台（basic.smartedu.cn / 智慧中小学）的各类资源。当用户提到"国家中小学智慧教育平台""智慧中小学""basic.smartedu.cn""中小学电子教材"，或要求查找、预览、下载电子课本、某学科某版本某年级的教材 PDF，或查询课程教学课时、下载课件/教学设计/学习任务单/作业练习、查看名师课目录、实验教学、备课资源、课程标准对应资源时使用。需要登录时打开浏览器交给用户完成登录，之后继续取资源。
allowed-tools: Read, Write, Bash, Glob
---

# 国家中小学智慧教育平台资源（WorkBuddy / CodeBuddy 适配版）

本文件与 `smartedu-resources/SKILL.md` 内容等价，只改了三处：frontmatter 增加 `allowed-tools`（让脚本能执行）；第四节登录交接不依赖特定宿主工具名；第三节「文档转成可编辑 Word」改为**不依赖豆包插件**的可执行路径。安装方法见同目录 `安装说明.md`。

平台由教育部主办，覆盖德育、课程教学、体育、美育、劳动教育、课后服务、教师研修、家庭教育、教材等 15 个版块，资源全部免费。教材 PDF 与课时资源的详情、预览图都能通过公开接口拿到；只有视频需要登录后在线观看。

下文命令均在技能目录（`SKILL.md` 所在目录）下执行。

## 脚本一览

| 脚本 | 用途 | 登录 |
|---|---|---|
| `scripts/setup.py` | 检查并自动安装全部 Python 依赖（首次必跑） | 不需要 |
| `scripts/smartedu.py` | 教材目录检索、PDF 下载 | 不需要 |
| `scripts/fetch_resource.py` | 课时资源（课件/教学设计/任务单/作业）抓取并合成 PDF | 不需要 |
| `scripts/batch_download.py` | 按教材的某一章/某一节，把该章所有资源包批量落成 PDF | 不需要 |
| `scripts/to_pptx.py` | 把课件 PDF 转成 PPTX（每页铺满原图，可直接放映） | 不需要 |
| `scripts/pdf_to_md.py` | **把 PDF 解析成 markdown（文字 + 原位插图 + 真表格）**，文档转 Word 的第一步 | 不需要 |
| `scripts/md_to_docx.py` | 把 markdown 渲染成可编辑 Word（真表格 + 原位插图） | 不需要 |
| `scripts/build_docs.py` | 批量渲染整章/整节的 docx | 不需要 |
| `scripts/pdf_to_docx.py` | 【已废弃】纯 OCR 文字版，丢图，仅作对照 | 不需要 |
| `scripts/embed_page_images.py` | 【已废弃】整页原图嵌入版，已被验收否决 | 不需要 |

## 〇、首次使用：先让 setup.py 装依赖

第一次用、换了机器、或任何脚本报 `ModuleNotFoundError`，先跑这一条，不要手敲 pip：

```bash
python scripts/setup.py                          # 检查 + 缺什么装什么（带确认）
python scripts/setup.py --check                  # 只看状态，不动环境
python scripts/setup.py -y --mirror tsinghua     # 国内源静默装（-y 不询问）
python scripts/setup.py -y --self-test           # 装完逐个跑脚本 --help 自检
python scripts/setup.py -y --local-ocr           # 额外装本地 OCR 依赖（走离线兜底才需要）
```

- 必需依赖：`pillow`、`pymupdf`、`python-pptx`、`python-docx`、`requests`。
- 可选依赖组：`--local-ocr`（`rapidocr`、`rapid-layout`、`opencv-python-headless`、`numpy`，只有 `pdf_to_md.py --engine local` 需要）。
- setup.py 自身**不含第三方依赖**，只用标准库检测 import 并调 `python -m pip`；镜像默认官方，失败自动换清华源，也可 `--mirror aliyun/ustc/tencent/pypi`。
- 退出码 0 = 依赖齐全，1 = 仍有核心依赖缺失（此时不要继续跑下载，先解决环境）。
- 装完把版本信息告诉用户：Python 版本、装了哪几个包、`--self-test` 是否全过。

## 一、教材：检索与下载

| 命令 | 用途 |
|---|---|
| `modules` | 列出可用模块、分片数、是否支持 PDF |
| `facets --module <模块>` | 查看该模块学段/学科/版本/年级/册次取值与数量 |
| `search --module <模块> ...` | 按条件检索，`--with-links` 附带详情页与 PDF 直链 |
| `download --module textbook ...` | 下载教材 PDF，`--out` 指定目录，`--dry-run` 只打印链接 |
| `link --module <模块> --id <id>` | 按 ID 输出详情页与 PDF 链接 |

筛选参数：`--keyword`（空格分隔表示同时包含）、`--stage`、`--subject`、`--version`、`--grade`、`--volume`、`--standard`、`--topic`、`--limit`、`--json`。

模块键名：`textbook` 电子教材（约 3500 本，唯一可下原版 PDF 的模块）、`course` 课程目录、`homework` 作业习题目录、`experiment` 实验教学、`lesson_plan` 备课目录。也可写中文：教材 / 课程 / 习题 / 实验 / 备课。

```bash
python scripts/smartedu.py facets --module textbook
python scripts/smartedu.py search --module textbook --subject 语文 --grade 一年级 --volume 上册 --version 统编版 --with-links
python scripts/smartedu.py download --module textbook --subject 数学 --grade 八年级 --version 北师大版 --volume 上册 --limit 1 --out "<项目目录>"
```

`--keyword` 含空格时必须整体加引号。首次检索某模块会抓取目录（教材约 40MB，10–40 秒），之后读本地缓存。

## 二、课时资源：找到并下载

站点没有"下载"按钮，但每份资料的逐页转码图是公开的。`fetch_resource.py` 把页面图按顺序取回并合成一个 PDF。

**定位资源**（在浏览器里操作，登录规则见第四节）：

1. 打开 `https://basic.smartedu.cn/syncClassroom/prepare`，选教材 → 展开章节。
2. 切换标签：`课程包`（整套课时资料）、`知识点微课`、`课件`、`教学设计`。
3. 点开一项，详情页 URL 形如 `.../syncClassroom/prepare/detail?resourceId=<id>&...`，`resourceId` 就是要的 ID；课程包页面的 `resourceId` 即课程包 ID。
4. 不想开浏览器时，也可以直接从章节树与资源分片的 JSON 里取 ID（见文末"关键事实"）。

```bash
python scripts/fetch_resource.py --id 594c23ae-... --out "<项目目录>"
python scripts/fetch_resource.py --id fb001691-... --out "<项目目录>"          # 整个课程包，视频自动跳过
python scripts/fetch_resource.py --url "https://basic.smartedu.cn/syncClassroom/prepare/detail?resourceId=..." --out "<目录>"
python scripts/fetch_resource.py --id <id> --out "<目录>" --images-only       # 只要页面图
```

输出：`{标题}.pdf` 与 `{标题}_页面图/001.jpg…`。完成后报告每份的页数、MB 与路径，并用宿主的文件交付能力交给用户。

## 三、按章节批量下载（整章 / 整节）

用户说"下某教材某单元/某章的全部资料"时用这个，不要逐页点。

```bash
python scripts/batch_download.py --teachingmaterial 5370d999-5dd2-4c64-a9ed-089ec2694300 --chapter 第五章 --out "<输出目录>"
python scripts/batch_download.py --teachingmaterial <教材id> --chapter 第五章 --section 第一节 --out "<目录>"
```

`--teachingmaterial` 就是备课页 URL 里的 `teachingmaterialId`；`--chapter` 用章标题关键词（如"第五章"），也可用 `--chapter-id` 精确匹配。

脚本做的事：抓章节树 → 抓该教材的资源分片 → 每章节点下挂的资源包 → 展开 `relations` 里的子文件 → 逐页取图合成 PDF。输出结构是 `输出目录/第一节 透镜/课件-xxx.pdf`，并写一份 `清单.md`。资源图片用 6 线程并发抓取，602 页的整章约 5 分钟。

三类资源包在 `relations` 里都带齐子文件与页面图。例外是两个 `coursewares` 记录（单份课件）没有 relations，脚本会自动回落单份详情接口。`micro_lesson_video` 一律跳过并记账。

### 课件转成 PPT

```bash
python scripts/to_pptx.py --in "<某个课件的 pdf>" --out "<输出目录>"
python scripts/to_pptx.py --in "<某节目录>" --out "<输出目录>"
```

每页原图铺满一张 16:9 幻灯片，视觉与原件一致（文字是图片，不可改字）。`--in` 传目录会把教学设计/任务单/作业一起转，只要课件时先按 `课件*.pdf` 筛。转换后核对 pptx 页数 = 源 PDF 页数。

### 文档转成可编辑 Word（验收口径：题目文字可编辑 + 插图留在原题位置 + 表格是真表格）

**先弄清为什么必须两步**：平台的 PDF 是把逐页转码图合成出来的，**没有文字层**（`pymupdf` 取 `get_text()` 结果为 0 字符），所以任何"直接转 docx"的工具都只能得到整页图片。必须先把 PDF 解析成 markdown（还原段落、表格、插图位置），再渲染成 docx。

解析有三种办法，按质量从高到低选。

#### 路径 A：TextIn xParse 的 HTTP 接口（推荐，任何宿主都能用，含 WorkBuddy）

豆包 App 里是 xParse **插件**，WorkBuddy 没有这个插件，但 TextIn 有公开 HTTP 接口，脚本已封装好，不需要任何 MCP：

```bash
# 取 key：https://www.textin.com → 工作台 → 账号设置 → 开发者信息
# macOS/Linux
export TEXTIN_APP_ID=xxxx; export TEXTIN_SECRET_CODE=yyyy
# Windows PowerShell
$env:TEXTIN_APP_ID="xxxx"; $env:TEXTIN_SECRET_CODE="yyyy"

python scripts/pdf_to_md.py --engine textin --pdf "作业练习-第1节  透镜.pdf" --out md/c02.md
python scripts/pdf_to_md.py --engine textin --in "第一节 透镜" --out-dir md      # 整节批量
```

- 接口：`POST https://api.textin.com/api/v1/xparse/parse/sync`，请求头 `x-ti-app-id` / `x-ti-secret-code`，multipart 上传 `file` + `config`（`table_view=html`、`include_table_structure=true`、`include_image_data=true`）。
- 有免费额度（每日 1000 页量级），一个章节够用。凭证缺失或错误时脚本直接给出注册指引。
- 质量与豆包版一致：真表格、插图是可直接下载的 URL，`md_to_docx.py` 会自己取回。

#### 路径 B：宿主自带版面解析 MCP（有就用，最省事）

若宿主里已经装了 xParse 一类 MCP，直接调用其工具解析每份 PDF，把返回的 markdown 存成 `<work>/md/cXX.md`，再走下面的渲染。豆包 App 里的流程就是：`prepare_file_upload` → `submit_parse_task` → `parse_document`，参数取 `result_format=markdown`、`table_view=html`、`include_table_structure=true`、`resource_mode=free_only`。

#### 路径 C：本地 OCR 兜底（不联网、不要账号，质量有限）

```bash
python scripts/setup.py -y --local-ocr        # 首次装 rapidocr / rapid-layout / opencv
python scripts/pdf_to_md.py --engine local --pdf "作业练习-第1节  透镜.pdf" --out md/c02.md
python scripts/pdf_to_md.py --engine local --in "第一节 透镜" --out-dir md --pattern "教学设计*.pdf,学习任务单*.pdf,作业练习*.pdf"
```

- 做法：逐页渲染 → RapidOCR 出文字框 → 自实现行聚类拼行 → RapidLayout 找 figure/table/header/footer → 裁切插图存 `<md名>_插图/` 并按 y 顺序插回 → 表格按横竖线重建 markdown 表格。
- **已知局限（必须告诉用户）**：版面模型会漏检部分插图（实测一页 7 张图能出 4~5 张）、表格列数与合并单元格可能错、公式与上下标会失真。
- 因此这条路径只能当应急，交付时**必须明确说明"插图/表格需对照源 PDF 复核"**，不要当成定稿直接交。

#### 渲染成 docx（三条路径共用）

```bash
python scripts/build_docs.py --md md/c02.md --out "<输出目录>" --name "作业练习-第1节 透镜.docx"
python scripts/build_docs.py --work <含 md/ 与 fileids.json 的目录> --out "<输出目录>"
```

`fileids.json` 形如 `{"ok": {"c02": {"path": "<源 PDF 绝对路径>"}}}`，配套 `<work>/md/c02.md`；不带 `--md` 时按 `fileids.json` 批量渲染并打印「完成 N / 总数」。

渲染器做的事：
- HTML 表格 → 真 Word 表格，支持 `colspan`/`rowspan`；markdown 管道表格（`| a | b |` + `|---|---|`）自动转真表格；
- 单元格内容按 `<br>` 与 `<img>` 的文档顺序切段，文字与插图交替输出，连续多图同段并排；
- 插图支持 **http(s) URL 与本地绝对路径**两种来源，按宽高双限缩放（单图 9cm 宽、并行图均分、高度上限 4.6cm）；
- 丢弃 LaTeX 碎片行、纯符号行、页眉残留的「基础教育精品课」。

#### 交付前必须自检

1. docx 转 PDF 出图逐页看：①题目是普通可编辑段落而非图片 ②每张插图紧跟所属的题 ③课程基本信息表/教学过程表是真表格且合并单元格正确；
2. 走路径 C 时额外核对插图张数是否与源 PDF 一致，缺的要么补裁、要么如实向用户说明。

> 旧方案已废弃，不要再用：`pdf_to_docx.py` 纯 OCR 文字（丢图）、`embed_page_images.py` 每页插整页原图（已明确否决）。

## 四、需要登录时：交给用户自己登录

登录只对**视频播放**和**我的资源库**需要；教材 PDF 与课时页面图都是公开接口，上面所有脚本路径都不需要登录。

遇到被登录墙挡住时（页面正文为空、只有页头页脚，或播放/资源库入口打不开）：

1. 打开登录页 `https://auth.smartedu.cn`（点站内"登录"会跳到这里）。可以用宿主内置浏览器打开，也可以直接让用户在自己浏览器里打开。
2. 明确告诉用户需要完成哪一步（扫码 / 手机验证码 / 密码），然后**停下等待**。不要自己尝试输入账号密码或验证码，也不要索取这类信息。
3. 用户确认完成后，重新读取页面确认已登录，再继续取资源。
4. 同一网站只需交接一次；用户拒绝或登录失败时停在这个步骤并如实说明，不要绕过登录墙。

登录态留在用户浏览器里，之后可以在同一窗口自己浏览、播放、下载，不需要重复登录。

## 五、视频怎么处理

课时视频是 m3u8 流，地址在 `-private` 主机上需要签名，站点不提供下载。做法是：告诉用户可以登录后在线观看，需要留存就用录屏工具；不要承诺下载或直接给出 m3u8。

## 关键事实（已实测）

- 教材 PDF：`https://cdncs.ykt.cbern.com.cn/v0.1/static/edu_product/esp/assets/{id}.pkg/pdf.pdf`，公开、无需登录，完整 PDF。
- 课时资源详情 JSON（公开）：`https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/prepare_sub_type/resources/details/{id}.json`。
- 课程包 JSON（公开）：`https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/resources/{packageId}.json`，`relations.course_resource` 列出整套资源。
- 章节树与资源分片（公开）：`https://s-file-2.ykt.cbern.com.cn/zxx/ndrs/prepare_lesson/trees/{teachingmaterialId}.json`、`.../teachingmaterials/{teachingmaterialId}/resources/parts.json` → `part_100.json`。分片里每条资源记录**自带** `relations`，子文件及其 `custom_properties.preview` 页图都在里面，不必再逐个请求详情。
- 页面图在 `r1/r2/r3-ndr.ykt.cbern.com.cn`，公开；课件 31 页就是 31 张图。
- 转码 `pdf.pdf` 与 `m3u8` 在 `r*-ndr-private` 主机，需 `x-nd-auth` 签名，直连 401/403，不要浪费时间尝试。
- 目录数据的 `tag_list` 已结构化给出学段(zxxxd)、学科(zxxxk)、版本(zxxbb)、年级(zxxnj)、册次(zxxcc)，按字段筛选，别用标题猜。
- 教材详情页：`https://basic.smartedu.cn/tchMaterial/detail?contentType=assets_document&contentId={id}&catalogType=tchMaterial&subCatalog=tchMaterial`

## 边界

- 只取用户明确需要的少数几份，不做整库搬运；一个课程包一次即可。
- 平台声明资源免费但"任何单位及个人不得用于商业行为"。遇到商业用途、对外分发、批量转存，明确提示限制，只给链接不下载。
- 目录会更新、教材会换版本。用户反馈"找不到/对不上"时先加 `--refresh` 重建索引再查。

接口细节、主机行为与已知失效端点见 `references/api.md`。
