# IEEE 作者信息 API 调研

核对日期：2026-10-28（Asia/Shanghai）。本次只修改作者原页入口并查询官方文档，未批量采集作者主页，也未申请或使用 API key。

## 结论

IEEE 提供需要申请和审核 key 的官方 Metadata Search API。它可以补充论文层面的作者姓名、署名顺序、机构和作者主页 URL，但不能由此推断存在可直接批量下载完整作者主页资料的公开 API。当前公开 API 目录列出 Metadata Search、Open Access、Full-Text Access 和 DOI API，没有单独列出作者主页资料接口。[官方 API 目录](https://developer.ieee.org/docs/read/Home)

官方返回字段明确包含 `authors`、`full_name`、`author_order`、`affiliation` 和 `author_url`，并说明只返回已填充字段。`author_url` 是原始作者页的地址；该字段不是简介、照片或作者主页 JSON 的替代品。[返回字段](https://developer.ieee.org/docs/read/Metadata_API_responses)

作者姓名 `author` 和机构 `affiliation` 可用于论文检索，`d-au` 作者 facet 提供针对搜索结果的作者细化链接。当前参数列表没有独立记录 `author_id` 主页查询参数。不能用姓名搜索结果直接合并同名作者。[检索参数](https://developer.ieee.org/docs/read/Metadata_API_details)

## 能力边界

| 信息 | 官方文档支持的获取方式 | 建库时的含义 |
|---|---|---|
| 作者姓名、署名顺序 | 论文元数据 API | 属于某一篇论文的署名记录 |
| 机构 | 论文元数据 API 的 affiliation | 保留论文编号、年份和采样时间，不直接认定为作者当前单位 |
| IEEE 作者主页链接 | author_url | 校验原始链接中的来源 ID，与现有 `(source, author_id)` 关联 |
| 作者相关论文 | author 检索及 d-au 作者 facet 细化 | 必须按来源 ID 核对，不能仅按姓名归并 |
| 简介、照片、主页指标、主页 ORCID | 作者主页或作者管理门户中可见；当前公开 API 文档未列出对应独立资料接口 | 保持未知，不能声称 Metadata API 已返回这些资料 |

作者管理门户支持作者登录后修改姓名、照片、机构、研究主题和简介。这是作者管理自己的资料的入口，不能当作第三方作者资料读取 API。[官方作者资料管理说明](https://ieeexplore-custom.ieee.org/Xplorehelp/author-center/author-profile-management)

## 接入条件和后续步骤

1. 注册 IEEE API 账户，等待 key 审核。不要把 key 放进 Git、浏览器代码、日志或聊天内容。[Quick Start](https://developer.ieee.org/Quick_Start_Guide)
2. 如计划批量建立本地作者库，应向 IEEE 说明使用范围、数据保留方式和展示对象，确认许可和配额。公开条款对使用范围、批量内容和分发有约束，拥有 key 不等同于不受限制的批量收集许可。[官方条款](https://developer.ieee.org/API_Terms_of_Use2)
3. 先以已知论文编号取少量样本，核对作者链接、机构和缺失字段，再决定是否开发接入器。标准入口为 `https://ieeexploreapi.ieee.org/api/v1/search/articles`。[查询结构](https://developer.ieee.org/docs/read/Searching_the_IEEE_Xplore_Metadata_API)
4. 先复用现有来源 ID、名字变体和论文关系，新增机构观察记录应带论文来源和时间。由本库计算的论文数、合作者和关键词统计应标记为本库统计，不作为 IEEE 官方主页指标。
5. 若必须采集简介、照片、ORCID 或主页指标，向 IEEE API 支持确认作者资料 API 或数据服务。当前没有官方文档证据证明这些字段能通过上述 Metadata API 直接获取。[API 联系入口](https://developer.ieee.org/contact)

本次自动访问样例作者主页返回 HTTP 418，未读取到该主页内容。前端只在用户点击时打开原始网页，没有通过其他地址或身份规避访问限制。

## 已提供的网页入口

站内作者姓名链接继续按 ID 检索本库论文。选中作者和候选卡片另有“查看 IEEE Xplore 作者原始链接”；论文详情把各作者的原始链接放在默认折叠区域。原始页在新标签页打开，只有数值型 IEEE 来源 ID 才生成原页链接，其他来源或缺失 ID 不猜测。


## 同日复测补充：两台主机均成功

根据用户提供的访问环境重新测试，已补充确认作者丰富资料的实际获取方式。

| 方式 | 服务器环境 | 桌面环境 |
|---|---|---|
| 未建立站点会话，直接 GET 作者页 | 418 | 418 |
| 先访问搜索入口、复用站点下发的 Cookie，再 GET 作者 HTML | 200 | 200 |
| 正常会话下 GET `/rest/author/37086128853` | 200，JSON 可解析 | 首次遇到 502，有限重试后 200，JSON 可解析 |

这是网页实际使用的作者数据入口。当前官方应用脚本在 `api.authorProfile`
中定义 `/rest/author/`，`getAuthorProfile(id)` 使用 GET 请求该路径。
[网页应用脚本](https://ieeexplore.ieee.org/assets/dist/ng-new/main.js?cv=20261027_00000)

本次未使用 API key、未登录 IEEE 个人账号、未写数据库、未启动批量作者
采集。正常会话的请求方式复用了现有已验证的论文抓取客户端：先 GET
`/search/searchresult.jsp`，复用内存中的站点 Cookie，以 HTML Accept
访问页面、JSON Accept 访问数据接口。Cookie 值没有写入文档或仓库。

接口返回单元素 JSON 数组。样例来源 ID `37086128853` 对应 Yuefeng Cao，
两台机器返回的核心字段一致：

- `currentAffiliations`：中国科学技术大学相关院系的机构记录。这是 IEEE
  作者页当前返回值，本次不做独立任职核验。
- `bioParagraphs` 有简介内容，`photoUrl` 有照片地址。
- `orcid`：`0000-0003-1000-9079`。
- `articleCount`：19；`citations`：276；发表年份覆盖 2017–2026。
- 返回 19 条 `coAuthors` 和 50 条 `topics` 记录；不能由数组长度推断
  已取得网站上的全部合作者或所有主题。
- `idStr` 可作为字符串身份标识；`isHideProfile` 为 false。

因此，技术上已验证可通过网站作者 JSON 接口取得基础信息和丰富资料。
这补充了前文的实际访问结论；官方开发者 API 目录没有单独列出作者
资料接口的文档事实不变。网站内部接口的可读性也不代表已获得长期
接口支持或不受限制的批量收集许可。未来接入应保留来源 ID、采样时间、
缺失字段和请求失败状态，不能把 418、502 或解析失败当作空资料。

本次成功样本及状态对照保存在个人验证目录，原始网页、完整响应和
会话信息不放入公开仓库。
