# 接口参考（实测于 2026-11-15）

## 目录接口

基址 `https://s-file-1.ykt.cbern.com.cn/zxx`，全部 GET、无需登录。

| 模块 | 入口 | 形态 |
|---|---|---|
| 电子教材 | `/ndrs/resources/tch_material/version/data_version.json` | `{module, module_version, urls}`，4 个分片，约 3565 条 |
| 课程教学 | `/ndrs/national_lesson/teachingmaterials/version/data_version.json` | 4 分片 |
| 作业习题 | `/ndrs/questions/teachingmaterials/version/data_version.json` | 4 分片 |
| 实验教学 | `/ndrs/experiment/teachingmaterials/version/data_version.json` | 1 分片，91 条 |
| 备课资源 | `/ndrs/prepare_lesson/teachingmaterials/parts.json` | 直接返回 URL 数组 |

`data_version.json` 的 `urls` 可能是逗号分隔字符串，也可能是数组，两种都要处理。分片内容为数组，每片 1000 条，元素含 `id`、`title`、`tag_list`、`custom_properties`、`provider_list`。

标签文件：`/ndrs/tags/k12.json`（仅学段）、`/ndrs/tags/tch_material_tag.json`、`national_lesson_tag.json`、`questions_tag.json`、`experiment_tag.json`。

## tag_list 维度

| tag_dimension_id | 含义 |
|---|---|
| `zxxxd` | 学段：小学 / 初中 / 高中 / 小学（五•四学制）/ 初中（五•四学制）/ 特殊教育 |
| `zxxxk`、`zxxk` | 学科 |
| `zxxbb` | 版本（出版社），如 人教版、北师大版 |
| `zxxnj` | 年级：一年级…高三，另有"高中年级""教师用书"等特殊值 |
| `zxxcc` | 册次：上册 / 下册 / 全一册 / 必修 第一册 |
| `zxxkb` | 课程标准（实验模块） |
| `sykmk` | 课标主题（实验模块） |

## 文件地址

教材 PDF（公开，可直接 GET/HEAD）：

```
https://cdncs.ykt.cbern.com.cn/v0.1/static/edu_product/esp/assets/{resource_id}.pkg/pdf.pdf
```

同一文件在 `https://r{1,2,3}-ndr-private.ykt.cbern.com.cn/edu_product/esp/assets/{id}.pkg/pdf.pdf` 也存在，但 GET 返回 401，`r{1,2,3}-ndr` 返回 403 —— 需登录态或 `x-nd-auth` 签名，不要作为主路径。

封面缩略图在 `custom_properties.thumbnails[0]`，主机为 `r1/r2/r3-ndr.ykt.cbern.com.cn`，可直接访问。

详情页：

```
https://basic.smartedu.cn/tchMaterial/detail?contentType=assets_document&contentId={id}&catalogType=tchMaterial&subCatalog=tchMaterial
```

## 已知不可用

- `/ndrs/online_judge/teachingmaterials/version/data_version.json` 与 `/ndrs/tags/online_judge_tag.json`：403，端点不存在。
- `/ndrv2/resources/tch_material/details/{id}`、`/ndrs/resources/tch_material/details/{id}`、`/basic.smartedu.cn/api/tchMaterial/details/{id}`：403，需登录态。课时级资源只能走浏览器。
- `api.ykt.cbern.com.cn/zxx/api_static/...`：403。

## 站内搜索

前端搜索走 `x-search.sdp.101.com` / `x-search.ykt.eduyun.cn`，带签名参数，未逆向。用户要搜具体课时内容时，直接用浏览器打开 `https://basic.smartedu.cn/search?keyword=<关键词>`。

## 数据规模

- 教材 3565 条，学段 6 种、学科 37 种、版本 114 种、年级 21 种、册次 180 种。
- `custom_properties.format` 全为 `pdf`，`size` 为平台登记的原始体积（与其转码后的实际 PDF 体积不同，后者以 cdncs 返回为准）。
