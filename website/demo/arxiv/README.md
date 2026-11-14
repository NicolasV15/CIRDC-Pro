# 离线真实数据 Demo

本目录供协作开发使用；无需 MySQL、生产站点、私有 provider、账户、密钥或外部论文下载。依赖安装和首次构建需要正常的软件包网络；完成后，Demo 运行及数据访问离线完成。

从仓库根运行：

```sh
# 已有此工作区的独立网站开发环境和前端依赖时可跳过 setup。
sh tools/web setup
sh tools/web build
sh tools/web demo --port 18090
```

打开 <http://127.0.0.1:18090/?source=arxiv>。端口已占用时更换 `--port`；不要停止现有服务。Ctrl+C 停止本次 Demo。无需启动任何采集、元数据初始化、同步或转换 worker。

`sh tools/web demo --prepare-only` 仅验证种子并生成 `work/arxiv-demo/demo.sqlite`。正常启动复用相同种子的现有数据库；种子改变后用 `sh tools/web demo --rebuild` 原子重建本 Demo 数据库。程序不会覆盖身份不匹配的数据库，不读取生产配置或运行状态。

## 样本与来源

- 基于协作源码 `9a99e210`，2026-11-14 从既有资料库只读抽样。`metadata.json` 包含 **43 篇真实 arXiv + 3 篇真实 IEEE 元数据**；保留题名、作者、摘要、分类、实际版本及可用附加字段，数据不是合成的。
- arXiv 取最近有限窗口内的电路相关分类及少量其他学科，再补充旧编号和多版本例子；覆盖 eess.SP / eess.SY、cs.AR / cs.ET、physics、cond-mat 等。该选择不是总体分布或完整收录声明；默认每页 25 条，可实际加载到 43 条。
- IEEE 只含 11741266、11126195、11717827 的元数据，用于同站样式对照；不包含 IEEE 正文、PDF、作者资料和关系数据库。
- `2611.14519v1` 带完整的已有缓存正文和原始 HTML。作者：Emre Kutlusan、Yongmin Li；题名：*Medical Image Segmentation: Foundation Model Adaptation versus Task-Specific Training*；[原论文](https://arxiv.org/abs/2611.14519v1)；许可为 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)，依据原记录的 license 字段。请保留作者、出处和许可归属。
- `files/2611.14519v1-original.html` 为原始 HTML，`files/2611.14519v1-body.html` 为现有阅读器适配层的派生正文；均按缓存字节复制，没有为 Demo 改写文章、公式或复制字段。API 外壳仅移除运行队列身份，并描述离线包的实际可用范围。各文件大小、SHA-256、固定版本、render ID、来源和许可记录在 `manifest.json`。
- 本次没有新的上游获取、解析或转换。这篇正文引用的 **4 张图片在捕获时未缓存**；其 PDF 正在获取、TeX 包在排队，因而均未打包。历史观察状态保留在 manifest；Demo 不连接或轮询这些真实任务。

## 直接打开的例子

以下路径均相对 Demo 地址：

| 目的 | 路径 |
| --- | --- |
| 真实列表、分页、多选、引用 | `/?source=arxiv` |
| 电路相关大类筛选 | `/?source=arxiv&category=eess` |
| 完整正文、目录、公式与 HTML 下载 | `/arxiv/papers/3300802?source=arxiv&v=1` |
| 两个真实版本、历史导航与元数据说明 | `/arxiv/papers/1?source=arxiv&v=2`（0704.0001，仅元数据） |
| 旧式编号及三个版本 | `/?source=arxiv&q=hep-th%2F9901001` |
| IEEE 对照 | `/`、`/papers/11741266` |
| 数据与缺项说明 API | `/api/demo` |

## 与生产接口的差异

1. arXiv 的检索、分类、年份、排序、Top-K、等价词、cursor 和总数计算复用本分支 `Catalog.search()`；详情用 SQLite 中导出的 API 元数据代替 MySQL。IEEE 检索同样复用现有索引实现；两者只查询样本，所有概览数量按样本计算。完整索引的性能、并发和真实 MySQL 契约仍需单独验证。
2. 本包不是正在运行的采集现场。未打包的资料返回 `not_packaged`；它不表示原站未提供、不表示访问受限，也不表示用户尚未请求过。当前生产前端会把这个 Demo 专用值直接显示为 `not_packaged`。不要为消除文字而改成 `unavailable`、零、空正文或假成功。
3. 正文返回 `partial` + `next_action=stop`：实际正文可读，但 4 张图片未缓存，离线时也不会继续补齐。HTML 中的版本/render 链接保持；缺失图片返回 404，正文会显示图片暂不可用。错误 render、未打包文件或版本不会串用其他资源。
4. 只支持已有 HTML 下载，原始字节可核对 SHA-256。**没有 PDF / TeX 文件，因此无法用本包验证共享 PDF 阅读、真实 ZIP 成功下载或 TeX 附件。** 下载弹窗可验证无可用 PDF 的真实离线状态；成功、失败、受限、排队和重试等交互继续使用明确的 fixture 回归。不要将两类证据混写。
5. 所有写请求返回 HTTP 409 / `demo_acquisition_disabled`；没有假任务、伪造队列或远端回源。未实现的 API 返回明确的 404 / `demo_route_not_packaged`。这包括 IEEE 正文/作者/引用关系、Agent API 和资源获取；对应控件可能显示未读取提示，这不是来源缺失证据。
6. 元数据来自当前对外 API。`Catalog.paper()` 已过滤的 `journal_ref` 等字段不会由 Demo 补造；真实数据库字段映射问题仍需在对应环境核对。冻结元数据不冒充历史版本快照。
7. Demo 顶部由启动器注入离线标识与样本数；没有修改生产页面的视觉代码。SQLite 建库、目录创建和静态构建均限于当前工作区；数据源配置和生产库不参与运行。

## 验证

```sh
website/.venv-dev/bin/python -m pytest website/tests/test_arxiv_demo.py -q
# 启动 Demo 后，使用已有 Playwright / Chromium；非默认安装按脚本支持的环境变量指定。
CIRDC_DEMO_ORIGIN=http://127.0.0.1:18090 node website/web/tests/arxivDemo.browser.cjs
```

浏览器脚本直接请求 Demo，不拦截伪造 API。它检查真实列表分页、引用、无缓存 PDF 弹窗、版本前进后退、完整正文/公式、原始 HTML 下载摘要、IEEE 对照，以及 1440 / 390 / 320px 下的溢出和浏览零写请求。真实缺图的 404 为已知限制；数据结构、下载字节、离线隔离和损坏种子保护由 Python 测试覆盖。它不替代生产 provider、完整库性能或线上验收。
