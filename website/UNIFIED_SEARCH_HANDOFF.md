# IEEE + arXiv 统一勾选检索前端交接（阶段 2B）

更新：2026-11-24。本文件是本轮 Claude 前端开发与交付入口。

## 目标、基线与职责

- 协作仓库：<https://github.com/Personal-collaborate/CIRDC-Pro>；交付分支：`codex/website-ui-collaboration`。
- 发出基线：基于已上线的移动端优化主线 `efab6775`，并已完成阶段 2A（统一检索后端 API、离线 Demo 适配、公开 Agent/MCP 入口与 `cirdc-research` Skill `1.3.0` 升级）。接手时请直接拉取 `codex/website-ui-collaboration` 最新 HEAD。
- 职责边界：Claude 主导阶段 2B 前端统一检索交互与视觉整合、测试验证及分支交付；**后端 API、Demo 适配与 Skill 已冻结，非必要不改 `website/src/`**，不合并 `main`、不部署生产、不重启服务。
- 阅读入口：先读仓库根 `AGENTS.md`、`website/AGENTS.md` 与 `docs/LOCAL_REMOTE_WORKFLOW.md`。旧 `MOBILE_UX_HANDOFF.md`、`ACCOUNT_FAVORITES_HANDOFF.md` 与 `ARXIV_FRONTEND_HANDOFF.md` 仅为历史参考。

## 已冻结的后端契约（阶段 2A 已实现并验证）

- **读者端接口**：`GET /api/search/unified`（正式站与 `sh tools/web demo` 均已接入）。
- **公开 Agent / MCP 入口**：`GET /api/agent/v1/search`、MCP 工具 `search_unified`、Skill `cirdc-research` `1.3.0`（均已更新并通过校验）。
- **查询参数**：
  - `sources`：逗号分隔来源集合，支持 `ieee,arxiv`（默认全选）、`ieee`、`arxiv`；非法或空值返回 `422 invalid_query`。
  - `q`：查询词（`field=body` 最长 600 字符，其余最长 200 字符）。
  - `field`：`all | title | authors | abstract | keywords | body | categories`（默认 `all`）。
  - `sort`：`relevance | year`（有关键词默认 `relevance`，空查询默认 `year`）。
  - `view`：`all | top`（默认 `all`）；`view=top` 时支持 `k=10|20|50|100`。
  - `terms`：`expand | exact`（默认 `expand`）。
  - `limit`：`1..100`（默认 `25`）；`cursor`：不透明游标；`totals`：`include | defer | only`；`include_dates`：`1 | 0`（默认 `1`，为 arXiv 补齐 UTC+8 `submitted_at`）。
  - 公共筛选：`year_from`、`year_to`。
  - IEEE 专属筛选（仅作用于 IEEE）：`venue`、`venue_any`、`venue_tags`、`kind`、`publication`、`author_id`、`author_source`。
  - arXiv 专属筛选（仅作用于 arXiv）：`category`（13 类多选逗号分隔）。
- **返回结构**：
  ```json
  {
    "items": [
      { "source": "ieee", "number": "...", "title": "...", "year": 2026, "...": "..." },
      { "source": "arxiv", "paper_id": 123, "arxiv_id": "2611.17337", "submitted_at": "...", "categories": ["eess.SY"], "...": "..." }
    ],
    "total": 46,
    "total_exact": true,
    "partial": false,
    "next_cursor": "...",
    "sort": "year",
    "field": "all",
    "view": "all",
    "selected_sources": ["ieee", "arxiv"],
    "sources": {
      "ieee": { "enabled": true, "selected": true, "status": "ok", "total": 3, "total_exact": true },
      "arxiv": { "enabled": true, "selected": true, "status": "ok", "total": 43, "total_exact": true }
    },
    "source_notes": []
  }
  ```
- **关键语义**：
  - 有关键词 + `sort=relevance` 采用跨库 RRF 融合排序；按时间或空查询按年份/日期从新到旧混排；跨页游标零重复、零遗漏。
  - 若选中单源专属字段（如 `keywords`/`body` 仅 IEEE 支持，`categories` 仅 arXiv 支持）且同时勾选了另一来源，后端跳过不支持来源并在 `source_notes` 返回 `{"source": "...", "code": "field_not_supported", "field": "..."}`。
  - 若某一来源繁忙/出错而另一来源正常，返回 `partial: true`、`total: null` 并在 `sources.<name>.status = "error"` 标出，前端需明确提示部分来源暂不可用，不可伪装成 0 条。
  - 既有 `/api/papers`、`/api/arxiv/papers`、详情、收藏、下载接口保持不变。

## 阶段 2B 前端实施范围（`website/web/`）

### 1. 移除顶栏双板块切换，改为首页来源勾选

- 移除顶栏中的 `IEEE / arXiv` 分栏切换（`AppHeader.tsx` 中的 `PaperSourceSwitch`），进一步精简桌面与移动端顶栏。
- 首页统一入口为 `/`（**无需保留旧 `?source=ieee` / `?source=arxiv` 分栏模式**），来源选择改为常规检索/筛选参数（如 `sources=ieee,arxiv`，默认全选）。
- 在检索栏或筛选区提供清晰直观的来源勾选控件（`[✓] IEEE`、`[✓] arXiv`），默认同时勾选，至少保留 1 项不可全取消；取消或勾选来源后刷新结果并同步 URL 参数。

### 2. 智能联动筛选区与检索字段

- **只勾 IEEE**：显示 IEEE 刊会筛选、精选刊会指南入口及 IEEE 支持的检索字段。
- **只勾 arXiv**：显示 arXiv 13 类学科筛选、分类指南入口及 arXiv 支持的检索字段。
- **同时勾选 IEEE + arXiv**：
  - 公共筛选（年份区间、排序、结果视图、等价写法扩展）直接作用于联合检索；
  - IEEE 刊会筛选与 arXiv 分类筛选分组清晰展示（桌面与移动端均避免堆叠冗长），各自独立过滤对应来源，互不清空；
  - 若用户选择了仅单一来源支持的字段（如 `关键词`/`正文` 或 `分类`），根据 `source_notes` 给出一句简洁直观的提示（例如“当前字段仅匹配 IEEE 论文”），遵守文案规范，不写防御性免责声明。

### 3. 混排结果列表与操作适配

- 单列表混排展示 `/api/search/unified` 返回的 `items`，每条卡片带清晰的 `IEEE` / `arXiv` 来源徽标。
- IEEE 卡片保留既有刊会、年份、作者、摘要与 `/papers/{number}` 详情链接；arXiv 卡片保留 UTC+8 首次投稿日期 `YYYY-MM-DD`、分类标签、arXiv 编号与 `/arxiv/papers/{paper_id}` 详情链接。
- 顶部结果统计区清晰呈现总命中数及分来源计数（`sources.ieee.total` / `sources.arxiv.total`），遇到 `partial: true` 或单源 `status: "error"` 时明确提示受限来源并允许重试。
- 收藏、批量引用与批量选择工具栏适配单源与混排列表：确保 IEEE 与 arXiv 混选时收藏、引用导出和批量下载行为清晰、无报错或错配身份。

### 4. 保持既有移动端与桌面端体验不退化

- 完整保留刚刚上线的移动端（`390px` / `320px`）单行顶栏（高度 `<= 60px`、零折行）、紧凑折叠检索选项、无按钮折行与零横向溢出；
- 保留 6 套主题 + 系统主题 + 标签页 favicon 同步、中英双语（`i18n.test.ts` 全覆盖）、IEEE/arXiv 详情页与全文/公式渲染及划词复制、收藏/账户与管理台全部既有功能。

## 开发输入、运行与验证

复用现有离线 Demo（已内置 `/api/search/unified`，包含 3 篇 IEEE + 43 篇 arXiv 样本）：

```sh
sh tools/web demo --port 18090 --admin-port 18091 --state work/unified-demo/state
npm --prefix website/web test
npm --prefix website/web run build
```

浏览器回归建议：
- 新增统一检索自动化回归（如 `website/web/tests/unifiedSearch.browser.cjs`），覆盖：默认双源混排、单源勾选切换、刊会/分类智能联动、单源专属字段提示、翻页去重、详情跳转，以及 `1440px` / `390px` / `320px` × 中英文。
- 同步更新受顶栏移除 `PaperSourceSwitch` 或首页统一入口影响的既有浏览器测试（如 `mobileLayout.browser.cjs`、`arxivSearch.browser.cjs`、`arxivCategories.browser.cjs`、`accountFavorites.browser.cjs`、`agentAccess.browser.cjs`），保持核心回归全部通过。
- 运行 `python3 tools/check_release.py --component all` 确认无泄露。

## 交付与当前停点

- 完成后请在本文件末尾追加「Claude 完成记录」，写明：交回 commit SHA、变更摘要、实际运行命令与测试证据、关键页面截图本地路径（放进被忽略的 `artifacts/` 目录，不提交仓库）、已知限制与唯一下一步。
- 仅提交本轮改动并推送至 `Personal-collaborate/CIRDC-Pro` 的 `codex/website-ui-collaboration` 分支；不合并 `main`、不部署生产。

**当前停点**：阶段 2A（后端统一检索 API、Demo 适配、Skill `1.3.0` 与单测）已完成并推送，等待 Claude 拉取 `codex/website-ui-collaboration` 实施阶段 2B 前端。

## Claude 完成记录（2026-11-24）

**交回提交**：`23e3e60`（实现与测试），基于 `3173d40`；本记录在其后的提交中。只推送到 `codex/website-ui-collaboration`，没有合并 `main`、部署或重启服务。

### 变更摘要

- **顶栏**：移除 `PaperSourceSwitch`（文件已删除）。桌面与手机顶栏只剩品牌、登录/账户与站点工具；手机仍为单行。
- **首页统一入口 `/`**：`ReaderPage.tsx` 改为统一检索页，调用 `/api/search/unified`，原 IEEE 列表页与 `ArxivSearchPage.tsx`（已删除）合并为一页。URL 参数 `sources=ieee,arxiv`（默认）/ `ieee` / `arxiv`；旧 `?source=arxiv` 链接按“只勾 arXiv”打开。IEEE 详情仍在 `/papers/{number}` 页内打开，arXiv 详情 `/arxiv/papers/{paper_id}` 返回时恢复原列表与滚动位置。
- **来源勾选**：检索框内 `[✓] IEEE` `[✓] arXiv` 两个复选框（手机在输入框下方单独一行，不随“检索选项”折叠）；最后一个已勾来源标记为不可取消；勾选变化立即刷新结果与 URL。
- **字段与筛选联动**：
  - 检索字段随来源变化：只勾 IEEE 有关键词、正文，只勾 arXiv 有学科分类，双选时全部可选。切换来源后，当前字段若不再适用，回到“全部”。
  - 双选且字段仅单源支持时，按 `source_notes` 显示一句“当前字段仅匹配 IEEE / arXiv 论文”。
  - 筛选区分为 IEEE 组（精选刊会与指南、出版物类型、期刊/会议系列、摘要/关键词状态）、arXiv 组（13 类分类与分类指南、分类代码）和公共年份。双选时两个分类面板默认折叠，有选中项时展开。
  - 各组只过滤自己的来源。取消某来源后其条件保留在页面状态里，但不进入 URL 与请求；重新勾选后恢复。条件标签带来源徽标。
- **混排结果**：每条卡片带 `IEEE` / `arXiv` 徽标，其余信息与原两页一致（IEEE：刊会、年份、作者、摘要与资源；arXiv：UTC+8 首次投稿日期、分类标签、arXiv 编号）。
  - 统计区显示总数与分来源计数（`IEEE n · arXiv m`）。
  - `partial` 或单源 `status: "error"` 时显示“{来源} 暂时无法检索，当前结果不含该来源。”并提供“重试”，不显示伪造的 0 或总数。
  - 无关键词默认按时间从新到旧，有关键词默认相关度；排序作为显式参数发送。
- **批量操作**：选中项以 `ieee:{number}` / `arxiv:{paper_id}` 区分，混选时引用与批量下载按各自来源读取。`CitationDialog` / `BatchDownloadDialog` 显示与提交的仍是原编号；各归档接口只收到自己来源的编号。收藏状态按来源与版本读取。
- **后端（两处小改，均为保留既有功能）**：
  - `unified_search.py` 的 IEEE 专属参数增加 `abstract_state`、`keywords_state`、`author_unidentified`（原 IEEE 页的状态筛选与“未提供作者 ID”视图）。
  - 统一结果透传 IEEE 的 `fulltext` 状态（正文检索提示）。
  - `tests/test_unified_search.py` 新增 2 项。
  - `tests/test_agent_clients.py` 的 MCP 工具集合补上 2A 新增的 `search_unified`。该项在 `3173d40` 上已失败。
- **其他**：作者链接带 `sources=ieee`；收藏页的 arXiv 链接不再带旧 `source` 参数；`docs/web.md` 新增“Unified IEEE and arXiv search”并更新手机顶栏说明；`docs/arxiv-reading.md` 更新 URL 说明；i18n 新增 17 条。

### 实际运行命令

```sh
sh tools/web demo --port 18090 --admin-port 18091 --state work/unified-demo/state3
npm --prefix website/web test
npm --prefix website/web run build
(cd website && .venv-dev/bin/python -m pytest -q)
# 浏览器回归：PLAYWRIGHT_MODULE / PLAYWRIGHT_CHROMIUM_EXECUTABLE 指向本机 Playwright 与 headless shell
CIRDC_DEMO_ORIGIN=http://127.0.0.1:18090 node website/web/tests/unifiedSearch.browser.cjs
(cd website && .venv-dev/bin/python -m build --outdir dist .)   # 本机没有 uv
python3 tools/check_release.py --component all
```

### 测试证据

| 项目 | 结果 |
| --- | --- |
| `npm test`（含新增 `unifiedSearch.test.ts` 5 项） | 192 / 192 通过 |
| `npm run build`、`tsc --noEmit` | 通过 |
| website `pytest` | 401 通过，41 跳过 |
| 新增 `unifiedSearch.browser.cjs`（1440 / 390 / 320 × 中英文） | 6 / 6 组通过：双源混排、单源切换与最后一项不可取消、刊会/分类联动与互不清空、单源字段提示、单源失败提示与重试、翻页 46 条零重复零遗漏、混选引用与下载、IEEE/arXiv 详情往返 |
| 既有浏览器回归 | 31 个文件中 27 个通过（`arxivCategories` 在全量运行中受本机一次临时 `git stash` 干扰，单独重跑通过）；4 个失败（`abstractRendering`、`patentCitations`、`resourceDiagnostics`、`selectionCopy`），断言与基线完全相同，属既有问题，本轮未处理；`resourceApiLinked` 需要真实站点地址，未运行 |
| 新控件对比度（6 套主题 × 1440/390） | 180 处均 ≥ 4.5:1 |
| `check_release --component all`（重新打包后） | passed；发行包无 source map |

受影响的既有浏览器测试已同步：
- 顶栏不再有来源切换：`mobileLayout` 焦点顺序改为品牌 → 登录 → 菜单。
- 首页统一入口：`accountFavorites`、`arxivDemo`、`arxivSearch`、`arxivCategories`、`mobileLayout` 改用 `sources=`。
- `.venue-family-filter` 同时匹配 arXiv 分类面板：相关定位改为 `:not(.arxiv-category-filter)`。
- 双源统计格少一格：`resourceCoverage` 的格数与下标随之调整。
- 原 IEEE 页的夹具测试通过新增的 `tests/unifiedFixture.cjs` 把 `/api/search/unified` 转给夹具自己的 `/api/papers`；两个 arXiv 夹具直接响应统一接口。

### 截图（本地，已被 git 忽略）

`artifacts/unified-search/after/`：`unified-home-*`、`unified-ieee-*`、`unified-arxiv-*`、`unified-filters-*`、`unified-field-note-*`、`unified-partial-*`，每类 6 组（中英文 × 1440/390/320），以及其他浏览器测试的页面截图。

### 已知限制

- 只在 headless Chromium 中验证，未在真机 iOS Safari / Android Chrome 上检查。
- Demo 不含 IEEE 正文索引（`field=body` 返回 409），正文检索在统一页中的效果由夹具测试 `fulltextSearch` 覆盖。
- 双源时 arXiv 的年份下限仍由后端按 1991 处理；年份下拉沿用 IEEE 的范围。
- 原 IEEE 检索返回的“索引覆盖或同步尚未完成”（`partial`）提示在统一接口中没有对应字段，首页不再显示；统一接口的 `partial` 只表示某一来源失败。
- 夹具测试中的 IEEE 页面以“双源、arXiv 0 篇”的形式运行，只覆盖 IEEE 行为；双源真实数据由 `unifiedSearch.browser.cjs` 在 Demo 上覆盖。

### 唯一下一步

在真实 iOS Safari 与 Android Chrome 上按 390 / 320 抽查首页来源勾选、筛选分组和混排列表。确认后，由维护者决定是否合并 `main` 并部署。
