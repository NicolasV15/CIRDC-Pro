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
