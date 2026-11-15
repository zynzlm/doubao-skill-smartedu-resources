---
name: smartedu-resources
description: 检索并下载国家中小学智慧教育平台（basic.smartedu.cn / 智慧中小学）的各类资源。当用户提到"国家中小学智慧教育平台""智慧中小学""basic.smartedu.cn""中小学电子教材"，或要求查找、预览、下载电子课本、某学科某版本某年级的教材 PDF，或查询课程教学课时、下载课件/教学设计/学习任务单/作业练习、查看名师课目录、实验教学、备课资源、课程标准对应资源时使用。需要登录时打开浏览器交给用户完成登录，之后继续取资源。
allowed-tools: Read, Write, Bash, Glob
---

# 国家中小学智慧教育平台资源（WorkBuddy / CodeBuddy 适配版）

本文件与 `smartedu-resources/SKILL.md` 内容等价，只改了两处：frontmatter 增加 `allowed-tools`（让脚本能执行），以及第四节登录交接不再依赖特定宿主的工具名。安装方法见同目录 `安装说明.md`。

平台由教育部主办，覆盖德育、课程教学、体育、美育、劳动教育、课后服务、教师研修、家庭教育、教材等 15 个版块，资源全部免费。教材 PDF 与课时资源的详情、预览图都能通过公开接口拿到；只有视频需要登录后在线观看。

下文中的 `<skill>` 指本技能目录（即 `SKILL.md` 所在目录，WorkBuddy 里的 `baseDirectory`）。命令行均在技能目录下执行。

## 脚本一览

| 脚本 | 用途 | 登录 |
|---|---|---|
| `scripts/smartedu.py` | 教材目录检索、PDF 下载 | 不需要 |
| `scripts/fetch_resource.py` | 课时资源（课件/教学设计/任务单/作业）抓取并合成 PDF | 不需要 |
| `scripts/batch_download.py` | 按教材的某一章/某一节，把该章所有资源包批量落成 PDF | 不需要 |
| `scripts/to_pptx.py` | 把课件 PDF 转成 PPTX（每页铺满原图，可直接放映） | 不需要 |
| `scripts/md_to_docx.py` | 把 xParse 解析出的 markdown 渲染成可编辑 Word（真表格 + 原位插图） | 不需要 |
| `scripts/build_docs.py` | 批量渲染整章/整节的 docx | 不需要 |
| `scripts/pdf_to_docx.py` | 【已废弃】纯 OCR 文字版，丢图，仅作对照 | 不需要 |
| `scripts/embed_page_images.py` | 【已废弃】整页原图嵌入版，已被验收否决 | 不需要 |

Python 3.8+；`fetch_resource.py` 合成 PDF 需要 Pillow（`pip install pillow`）。

```bash
python scripts/smartedu.py <子命令> [参数]
python scripts/fetch_resource.py --id <resourceId> --out <目录>
```

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
# 先看清有哪些版本与年级写法
python scripts/smartedu.py facets --module textbook

# 检索并给出链接
python scripts/smartedu.py search --module textbook --subject 语文 --grade 一年级 --volume 上册 --version 统编版 --with-links

# 下载到用户项目目录
python scripts/smartedu.py download --module textbook --subject 数学 --grade 八年级 --version 北师大版 --volume 上册 --limit 1 --out "<项目目录>"
```

`--keyword` 含空格时必须整体加引号。首次检索某模块会抓取目录（教材约 40MB，10–40 秒），之后读本地缓存。

## 二、课时资源：找到并下载

站点没有"下载"按钮，但每份资料的逐页转码图是公开的。`fetch_resource.py` 把页面图按顺序取回并合成一个 PDF。

**定位资源**（在浏览器里操作，登录规则见第四节）：

1. 打开 `https://basic.smartedu.cn/syncClassroom/prepare`，选教材 → 展开章节。
2. 切换标签：`课程包`（整套课时资料）、`知识点微课`、`课件`、`教学设计`。
3. 点开一项，详情页 URL 形如 `.../syncClassroom/prepare/detail?resourceId=<id>&...`，`resourceId` 就是要的 ID；课程包页面的 `resourceId` 即课程包 ID。
4. 不想开浏览器时，也可以直接从章节树与资源分片的 JSON 里取 ID（见第五节）。

**下载**：

```bash
# 单份课件
python scripts/fetch_resource.py --id 594c23ae-... --out "<项目目录>"

# 整个课程包（视频自动跳过，其余各出一份 PDF）
python scripts/fetch_resource.py --id fb001691-... --out "<项目目录>"

# 也可以直接粘详情页链接
python scripts/fetch_resource.py --url "https://basic.smartedu.cn/syncClassroom/prepare/detail?resourceId=..." --out "<项目目录>"

# 只要页面图，不合成 PDF
python scripts/fetch_resource.py --id <id> --out "<目录>" --images-only
```

输出：`{标题}.pdf` 与 `{标题}_页面图/001.jpg…`。完成后报告每份的页数、MB 与路径，PDF 用宿主提供的交付/文件上报能力交给用户。

## 三、按章节批量下载（整章 / 整节）

用户说"下某教材某单元/某章的全部资料"时用这个，不要逐页点。

```bash
# 整章
python scripts/batch_download.py --teachingmaterial 5370d999-5dd2-4c64-a9ed-089ec2694300 --chapter 第五章 --out "<输出目录>"

# 只某一节
python scripts/batch_download.py --teachingmaterial <教材id> --chapter 第五章 --section 第一节 --out "<目录>"
```

`--teachingmaterial` 就是备课页 URL 里的 `teachingmaterialId`；`--chapter` 用章标题关键词（如"第五章"），也可用 `--chapter-id` 精确匹配。

脚本做的事：抓章节树 → 抓该教材的资源分片 → 每章节点下挂的资源包（国课/精品课/微课包/课件）→ 展开 `relations` 里的子文件 → 逐页取图合成 PDF。输出结构是 `输出目录/第一节 透镜/课件-xxx.pdf`，并写一份 `清单.md` 记录每份的页数与来源。资源图片用 6 线程并发抓取，602 页的整章约 5 分钟。

三类资源包在 `relations` 里都带齐子文件与页面图。例外是两个 `coursewares` 记录（单份课件）没有 relations，脚本会自动回落单份详情接口。`micro_lesson_video` 一律跳过并记账。

### 课件转成 PPT

用户要"课件做成 PPT"时，用 `to_pptx.py`。源 PDF 每页就是一张 1920×1080 原图，脚本把这页图抽回铺满一张 16:9 幻灯片，视觉与原件完全一致（文字是图片，不可改字）：

```bash
python scripts/to_pptx.py --in "<某个课件的 pdf>" --out "<输出目录>"
python scripts/to_pptx.py --in "<某节目录>" --out "<输出目录>"     # 转该目录下所有 PDF
```

注意 `--in` 传目录会把教学设计/任务单/作业一起转，只要课件时先按文件名筛出 `课件*.pdf` 再逐个转，或转完清掉非课件产物。转换后核对每份 pptx 的页数是否等于源 PDF 页数。

### 文档转成可编辑 Word（验收口径：题目文字可编辑 + 插图留在原题位置 + 表格是真表格）

教学设计、学习任务单、作业练习的原文件（docx）平台不提供，只有逐页图片。**不要用整页扫描图冒充可编辑文档**，也不要交纯文字稿（丢图同样不合格）。可靠路径是「云端版面解析 + 本地渲染」：

1. **云端解析**：用支持版面还原的文档解析服务（芸互/TextIn xParse 一类；WorkBuddy 里可以接对应 MCP 或 REST）解析源 PDF，参数取
   `result_format=markdown`、`table_view=html`、`include_table_structure=true`，一张 PDF 得到一份 markdown。
2. **本地渲染**：`scripts/md_to_docx.py`，批量入口 `scripts/build_docs.py`
   - HTML 表格 → 真 Word 表格，支持 `colspan`/`rowspan` 合并
   - 单元格内容按 `<br>` 与 `<img>` 的文档顺序切段，文字与插图交替输出；**连续多图放进同一段并排**（选项图 A/B/C/D 不会叠成竖排）
   - 插图按宽高双限缩放（单图 9cm 宽、并行图按张数均分、高度上限 4.6cm）
   - 丢弃 LaTeX 碎片行、纯符号行，以及页眉残留的「基础教育精品课」

```bash
python scripts/build_docs.py --work <含 md/ 与 fileids.json 的目录> --out "<输出目录>"
```

`fileids.json` 形如 `{"ok": {"c01": {"path": "<源 PDF 绝对路径>"}}}`，配套 `<work>/md/c01.md`。也可以用 `--md c01.md --out <目录> --name xxx.docx` 单份渲染。

3. **必须人工校正的三处**（不校正会被退回）：
   - **表格单元格内的多张插图**：解析结果里格内图只有 `image_datas` 列表（顺序即阅读顺序）、**没有坐标**，markdown 会把整批图堆到单元格末尾。必须按题号插回每题之后——先渲染源 PDF 页看图（`pymupdf`，115dpi），再改 md 里 `<img>` 的位置。表格**外**的图是独立元素，自带坐标，解析顺序已正确，不用动。
   - **OCR 错字与公式**：LaTeX 碎片被丢弃后个别选项文字会缺，按源图补齐（如 `CC′`、`甲/乙`、`凸透镜/凹透镜`）。
   - **未识别成表格的整页表格**：按页图手工重建成 4~6 列真表格（近视/远视对比表、实验记录表等）。
4. **验收自检**：docx→PDF 出图看页，核对①题目是普通可编辑段落而非图片②每张插图紧跟所属的题③课程基本信息表/教学过程表是真表格且合并单元格正确。

依赖：`python-docx`、`Pillow`、`pymupdf`。

> 旧方案已废弃，不要再用：`pdf_to_docx.py` 纯 OCR 文字（丢图）、`embed_page_images.py` 每页插整页原图（验收明确否决）。

## 四、需要登录时：交给用户自己登录

登录只对**视频播放**和**我的资源库**需要；教材 PDF 与课时页面图都是公开接口，上面所有脚本路径都不需要登录。

遇到被登录墙挡住时（页面正文为空、只有页头页脚，或播放/资源库入口打不开）：

1. 打开登录页 `https://auth.smartedu.cn`（点站内"登录"会跳到这里）。WorkBuddy 可以用内置浏览器/网页工具打开，也可以直接让用户在自己浏览器里打开。
2. 明确告诉用户需要完成哪一步（扫码 / 手机验证码 / 密码），然后**停下等待**。不要自己尝试输入账号密码或验证码，也不要索取这类信息。
3. 用户确认完成后，重新读取页面确认已登录，再继续取资源。
4. 同一网站只需交接一次；用户拒绝或登录失败时停在这个步骤并如实说明，不要绕过登录墙或假装页面已读到。

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
