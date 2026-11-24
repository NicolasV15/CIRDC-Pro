# 全站移动端体验优化交接

更新：2026-11-24。本文件是本轮 Claude 开发与交付入口。

## 目标、基线与职责

- 协作仓库：<https://github.com/Personal-collaborate/CIRDC-Pro>；交付分支：`codex/website-ui-collaboration`。
- 发出基线：`c7b64b97ea2a22d4b2ebe5ecee2875345d609e39`（当前已上线主线 `main`，含主题标签页图标同步与前端文案精简）。协作分支已从旧提交 `2098b45c` 快进至 `c7b64b97` 并附带本交接文档；接手时请直接拉取 `codex/website-ui-collaboration` 最新 HEAD。
- 职责边界：Claude 主导本轮前端移动端架构调整、视觉与交互实现、测试验证及分支交付；不修改后端/API、不合并 `main`、不部署生产、不重启服务。
- 阅读入口：先读仓库根 `AGENTS.md`、`website/AGENTS.md` 与 `docs/LOCAL_REMOTE_WORKFLOW.md`。旧 `ACCOUNT_FAVORITES_HANDOFF.md`、`ARXIV_FRONTEND_HANDOFF.md`、`UI_REDESIGN_DELIVERY.md` 与 `DEVELOPMENT_FOLLOWUPS.md` 仅为历史参考，旧轮次新增业务功能的授权不适用于本轮。

## 核心问题与实施范围（纯前端）

用户在手机端使用 CIRDC-Pro 时观察到：**按钮缺乏手机屏适配，窄屏下频繁折成两行、顶栏与筛选区占屏过多，尤其是首页非常影响观感。** 本轮定位为**全站移动端统一优化**（仅修改 `website/web/`），按优先级覆盖以下区域：

### 1. 顶栏与导航（最高优先级）

- 相关入口：`website/web/src/AppHeader.tsx`、`PaperSourceSwitch.tsx`、`ThemeControl.tsx`、`style.css`（当前 `<=760px` 允许 `.app-header-inner` 与 `.header-tools` 折行，品牌、来源切换、AI 接入、中英文、主题与登录/注册或账户菜单挤在一起会排成两行）。
- **硬要求**：手机端顶栏必须**严格单行、绝不换行、视觉清爽**，且无横向溢出。
- **设计自由度**：具体哪些入口留在顶栏外层、哪些收进汉堡/更多菜单或抽屉，由 Claude 自主决定。
- **演进预留**：保持 `PaperSourceSwitch` 与顶栏结构解耦，便于下一阶段独立规划“IEEE + arXiv 统一勾选检索”时平滑演进。

### 2. 读者端首页与论文列表（IEEE + arXiv，最高优先级）

- 相关入口：`website/web/src/ReaderPage.tsx`、`ArxivSearchPage.tsx`、`PaperSearchControls.tsx`、`ArxivCategoryFilter.tsx`、`VenueTags.tsx`、`PaperSelectionToolbar.tsx`、`PageSizeControl.tsx`、`style.css`、`arxiv.css`。
- 优化目标：
  - **检索与筛选区**：当前 `PaperSearchControls` 的检索字段、结果视图、排序与等价写法扩展默认全部展开，在手机端堆叠成多行挤占首屏。移动端允许结构性收拢（如默认折叠高级选项为紧凑展开条或抽屉，并清晰回显已生效的非默认筛选条件）。
  - **刊会/分类筛选与结果工具栏**：消除按钮无序折行与宽窄失衡，确保 `390px` 与 `320px` 下层次清晰、触控目标舒适。
  - **批量选择栏与论文列表卡片**：优化 `PaperSelectionToolbar` 及单条论文卡片的操作区（收藏、下载、引用、查看详情等）与元信息排版，避免按钮折两行或撑破宽度。

### 3. 论文详情与全文阅读页

- 相关入口：`website/web/src/PaperDetail.tsx`、`ArxivPage.tsx`、`DocumentReader.tsx`、`ArxivResources.tsx`、`PaperResourceLinks.tsx`、`ReaderLayoutControls.tsx`、`SelectionCopyToolbar.tsx`、`PaperReferences.tsx`、`PaperCitations.tsx`、`arxivReader.css`、`selectionCopy.css`。
- 优化目标：排查并修复顶部返回/操作工具栏、版本切换、资源下载/查看按钮组、目录抽屉、划词复制工具条以及长公式/表格/算法块/参考文献在 `390px` 和 `320px` 下的按钮折行、重叠与横向溢出。

### 4. 个人中心、认证页、弹窗与管理台

- 相关入口：`website/web/src/FavoritesPage.tsx`、`AccountPage.tsx`、`AuthPages.tsx`、`AuthorProfile.tsx`、`VenueGuide.tsx`、`ArxivCategoryGuide.tsx`、`CitationDialog.tsx`、`BatchDownloadDialog.tsx`、`FavoriteArchiveDialog.tsx`、`AgentAccessPage.tsx`、`AdminPage.tsx`、`ResourceSettings.tsx`、`MaintenanceStatus.tsx`、`Overview.tsx`、`personal.css`、`agentAccess.css`、`admin.css`。
- 优化目标：统一检查按钮组、标签页、弹窗头部/底部操作栏、筛选栏及管理台导航与表格在窄屏下的排版，消除按钮异常折行、挤压截断或视口溢出。

## 设计自由度与不可破坏约束

- **移动端自由度（`<=760px`）**：允许对导航、筛选区、工具栏和卡片操作区做结构性重排（如折叠菜单、抽屉、紧凑展开条、单行操作栏等），以简洁、克制、与 CIRDC-Pro 现有视觉语言一致为原则。
- **桌面端不可退化（`1440px` / `>=1024px`）**：桌面端视觉布局、控件结构与交互保持不变。
- **纯前端边界**：
  - 仅修改 `website/web/` 内的前端源码、样式与前端测试；**不改动** `website/src/` 后端代码、API 契约、数据库结构、采集脚本或新增第三方 npm/Python 依赖。
  - 浏览器浏览期间保持零外部来源请求。
- **既有能力完整保留**：
  - IEEE 与 arXiv 全文及公式（KaTeX）渲染、划词复制（含 IEEE 公式复制源值）、arXiv 三路径阅读适配；
  - arXiv 固定 UTC+8 日期格式与 13 类多选/分类指南；
  - 收藏、跨来源 ZIP 下载、账户设置同步与管理台全部功能操作（不得为适配移动端而删减已有操作）；
  - 6 套主题 + 跟随系统 + 标签页 favicon 同步；
  - 中英双语完整覆盖（`i18n.test.ts` 通过），遵守 `website/AGENTS.md` 文案规范：**不新增防御性免责声明或冗余说明文字**，靠布局、层级与留白传达结构。
- **明确不在本轮范围内**：
  - 不实现“IEEE + arXiv 合并为统一勾选检索”（已规划为下一阶段独立任务）。
  - 不新增业务功能或调整后端接口。

## 开发输入、运行与验证

复用现有离线 Demo 与前端命令，无需生产配置、数据库或凭据：

```sh
sh tools/web setup
sh tools/web demo --port 18090 --admin-port 18091 --state work/mobile-demo/state
```

说明：
- Demo 默认提供隔离读者端（IEEE 3 篇 + arXiv 43 篇样本、账号/收藏）与管理台（测试适配器，管理员凭据位于 `--state` 目录下的 `admin-credentials.txt`）。
- 如需查看真实 arXiv HTML 正文样本，可直接打开 `/arxiv/papers/3300802?source=arxiv&v=1`。

构建与测试命令：

```sh
npm --prefix website/web test
npm --prefix website/web run build
```

浏览器回归示例（按实际 Demo 端口运行）：

```sh
CIRDC_DEMO_ORIGIN=http://127.0.0.1:18090 node website/web/tests/accountFavorites.browser.cjs
CIRDC_DEMO_ORIGIN=http://127.0.0.1:18090 node website/web/tests/arxivReadingPaths.browser.cjs
CIRDC_DEMO_ADMIN_ORIGIN=http://127.0.0.1:18091 CIRDC_DEMO_ADMIN_CREDENTIALS=work/mobile-demo/state/admin-credentials.txt node website/web/tests/adminWorkspace.browser.cjs
python tools/check_release.py --component all
```

### 验收矩阵

1. **单测与构建**：`npm --prefix website/web test` 全部通过（含新增/更新的 `i18n` 与组件测试），`npm --prefix website/web run build` 无 TypeScript/Vite 错误。
2. **多视口 × 双语浏览器回归**：至少覆盖 `1440px`（桌面无回归）、`390px`（主流手机）、`320px`（窄屏手机） × **中文 / English**（英文标签更长，重点防按钮折行与溢出）：
   - **新增移动端自动化回归测试**（如 `website/web/tests/mobileLayout.browser.cjs`），显式断言：
     - 手机端顶栏单行不折行（控件不落到第二行）、高度受控、无横向溢出；
     - IEEE 与 arXiv 首页检索区、折叠/展开的高级筛选、刊会/分类筛选、批量选择栏与论文卡片操作按钮无异常折行与溢出；
     - 论文详情/阅读页、收藏/账户、登录/注册、常用弹窗及管理台在 `390px`/`320px` 下无横向溢出、无越界控件、无控制台/页面错误；
     - 桌面端 `1440px` 关键布局与现有浏览器回归保持通过。
3. **主题与可访问性**：抽检浅色/深色等 6 套主题对比度；移动端折叠菜单、抽屉与筛选开关支持键盘聚焦、`aria-expanded`、`Escape` 关闭与合理触控热区。
4. **发布脱敏门禁**：运行 `python tools/check_release.py --component all`（通用模式即可），确认无私有地址、本机绝对路径、凭据或意外 source map。

## 交付与当前停点

- 完成后请在本文件末尾追加「Claude 完成记录」，写明：交回 commit SHA、变更摘要、实际运行命令与测试证据、关键页面改前/改后截图本地路径（放进被忽略的 `artifacts/` 目录，不提交仓库）、已知限制与唯一下一步。
- 仅提交本轮改动并推送至 `Personal-collaborate/CIRDC-Pro` 的 `codex/website-ui-collaboration` 分支；不合并 `main`、不部署生产。

**当前停点**：交接基线已同步至 `c7b64b97`，等待 Claude 拉取 `codex/website-ui-collaboration` 开始实施。
