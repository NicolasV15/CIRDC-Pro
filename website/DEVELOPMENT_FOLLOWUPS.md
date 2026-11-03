# Website 后续开发事项

> 基于协作分支 `codex/website-ui-collaboration` 的提交 `5b3f75a`（2026-11-03）。
> 已完成的内容与验证见 [UI_REDESIGN_DELIVERY.md](UI_REDESIGN_DELIVERY.md)；检索接口与正文索引的现行说明见 [docs/web.md](docs/web.md#result-views-and-full-text-passages)。
> 本文件只记录尚未完成的事项。完成一项后删除或改写对应条目，并在提交说明中注明。

## 1. 在部署端启用正文检索（优先）

**现状**：正文检索的代码、索引与界面已完成，但本仓库不含私有资源提供方，实际站点的正文索引仍为空。界面目前显示"正文检索尚未启用"，不返回正文结果。

**要做**：

1. 在私有资源提供方中实现只读钩子 `agent_document_catalog(cursor=None, limit=100)`，约定见 [docs/agent-api.md](docs/agent-api.md)。状态为 `ready`/`partial` 的正文会被索引，其他状态会删除已有段落；用上次返回的游标再次调用时，应返回新增或变化的文档。
2. 在部署端运行 `cirdc web fulltext-index`：
   - 不带参数时常驻运行，同步到目录末尾后每 30 秒检查一次新增或变化的正文；
   - `--once` 完成一轮后退出，适合定时任务；
   - `--max-rows N` 处理满 N 篇后在当前目录页结束时退出，适合首次分批建立。

   同一时间只能运行一个索引进程（`fulltext.lock`）。索引器只读取已缓存的正文，不会触发获取、转换或采集。
3. 采用常驻还是定时运行属于部署配置，记录在私有部署资料中，不写入仓库。

**验收**：`GET /api/fulltext/status` 返回的已索引篇数、目录总数和待索引数与提供方一致，界面显示的正文检索范围与之相符。

## 2. 用真实数据复核

目前所有验证都使用合成数据。正文启用后需要复核以下三项：

- **段落对齐**：服务端按阅读器的块结构切分段落，阅读器按段落序号和首部词语定位。合成正文和测试 fixture 都能逐段对应，但真实 IEEE 正文的结构可能更多样。应抽样若干篇真实正文，比较服务端段落与阅读器 DOM 是否逐段对应。若频繁出现"当前显示的正文中未找到该段落"或"已按段落文字重新定位"提示，需要同时调整 `src/cirdc/web/fulltext.py` 的 `passages()` 和 `web/src/passageLocate.ts`，并重新生成 `web/tests/fixtures/fulltextPassages.json`。
- **性能**：合成基准为 10 万篇元数据加 5,000 篇正文（约 40 万段），正文常见词检索约 140 ms。正文篇数增加后要在真实规模下重测，重点关注常见词的总数统计和 Top-K。
- **检索质量**：用真实检索词（术语、作者、标题、DOI、英文原句）整理一份小型标准答案集，用于比较 Top-K 排序和召回，并作为后续调整的回归基线。

## 3. 检索质量改进

### 3.1 作者名的缩写与顺序

以下问题已在合成索引上确认：

- `B. Razavi`、`Razavi B` 这类首字母缩写查不到结果，因为作者字段中没有 `b` 这个词。
- `Razavi, Behzad` 能查到论文，但 Top-K 的"作者姓名一致"只识别"名 姓"顺序，所以排序不会提升。
- 选择"作者"字段时，Top-K 没有文本得分，按年份排序，也不显示匹配原因（`ranking.py` 中的现有设计）。

**可考虑**：识别"首字母 + 姓"、"姓, 名"、带中间名缩写等写法，改写为作者字段内的"姓氏 + 首字母"匹配，并让 `explain()` 的作者匹配兼容这些写法。不要放宽为只按姓氏匹配，以免混入同姓作者。

### 3.2 含行内公式的原句

正文索引把公式替换为占位符 `⋯`。原句中含公式文本（如 `g_m`）时，通常无法逐字命中，只能得到"近似匹配"。

**可考虑**：为简单的行内公式生成可检索的纯文本，或在原句匹配时允许跳过占位符位置。无论采用哪种方式，"原句"标签都只能用于逐字一致的段落。

### 3.3 术语表

等价写法与相关概念维护在 `src/cirdc/web/query.py` 的 `CONCEPTS` 中，目前有 32 个电路领域概念，表外的缩写按普通词匹配。

**可以**：

- 根据真实检索词或作者关键词补充术语；
- 把术语表移到单独的数据文件，并配套测试；
- 新增缩写时检查歧义。例如单独检索 `SAR` 也会匹配合成孔径雷达论文；而 `SAR ADC` 作为整体概念匹配，不受影响。

### 3.4 词形变化

目前没有做通用的词干还原，普通词的单复数和其他词形不会互相匹配（如 `comparator` 与 `comparators`）。术语表中的术语会自动加上 `-s` 复数形式，但仅限 `PLURAL` 列出的中心词。

**如要支持**：为词干还原另建一列或一个索引（例如使用 FTS5 的 `porter` 分词器），保留现有索引用于精确匹配。不要直接修改现有 `search.sqlite` 的分词方式。

### 3.5 近似匹配与 Top-K 的候选上限

- **近似匹配**：先用查询中最少见的 2–4 个实义词召回最多 5,000 个候选段落，再要求同一段落覆盖至少 60% 的实义词（`fulltext.py` 的 `APPROXIMATE_LIMIT`、`COVERAGE`）。因此近似匹配的总数是下限（界面已注明），主要由常见词组成的句子可能召回不足。
- **Top-K**：只对 BM25 排名前 300 的候选（`ranking.py` 的 `CANDIDATES`、`fulltext.py` 的 `TOP_CANDIDATES`）以及标题、作者短语候选重新打分，候选集之外的论文不会进入 Top-K；"全部匹配"视图不受影响。

以上参数应根据真实数据调整。

## 4. 不在当前范围

- **PDF 页码检索**：按本阶段需求未做。如需支持，需要 PDF 文本层与页码的对应关系，应作为单独的功能另行规划。

## 5. 测试与工具

- **浏览器回归的运行方式**：`web/tests/*.browser.cjs` 不包含在 `npm test` 中。先运行 `npm --prefix website/web run build`（测试读取构建后的 `src/cirdc/web/static`），再运行 `PLAYWRIGHT_MODULE=<playwright 或 playwright-core 的路径> node website/web/tests/<名称>.browser.cjs`。
  - `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 可指定浏览器，`CIRDC_BROWSER_OUTPUT` 可指定输出目录；部分测试还需要文件头注释中说明的 fixture 变量。
  - 所有请求均由 fixture 提供，不写入数据。
- **`selectionCopy.browser.cjs` 在 macOS 上失败**：原生复制步骤使用 `Control+c`，而 macOS 需要 `Meta+c`，可改为按平台选择快捷键。该问题在改版前已存在。
- **溢出与键盘检查**：交付时的全主题溢出扫描和键盘焦点检查使用的是临时脚本，未提交到仓库。如需长期回归，可改写为 `*.browser.cjs`。

## 代码位置

路径相对于 `website/`。

| 内容 | 位置 |
|---|---|
| 查询理解、术语表、DOI 规范化 | `src/cirdc/web/query.py` |
| 元数据检索与筛选 | `src/cirdc/web/index.py` |
| Top-K 排序与匹配原因 | `src/cirdc/web/ranking.py` |
| 正文段落索引、正文检索、单篇命中 | `src/cirdc/web/fulltext.py` |
| 接口路由 | `src/cirdc/web/app.py` |
| 检索说明、匹配原因、段落命中 | `web/src/SearchInsights.tsx` |
| 阅读器段落定位 | `web/src/passageLocate.ts`、`web/src/DocumentReader.tsx`、`web/src/PaperDetail.tsx` |
| 测试 | `tests/test_web_search_quality.py`、`tests/test_web_fulltext.py`、`web/tests/passageLocate.test.ts`、`web/tests/fulltextSearch.browser.cjs` |
