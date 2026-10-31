# CIRDC-Pro 网站

[English](README.md) | [简体中文](README_CN.md) | [项目总览](../README_CN.md)

网站将 CIRDC 元数据集合组织为可检索的科研文献库。本目录包含 React 前端和 Python API，
由父目录的 Git 仓库统一管理。长期采集使用[根目录元数据引擎](../README_CN.md#元数据后端)，
网站包保留既有管理功能需要的兼容模块。

## 读者端与管理端

| 界面 | 功能 |
| --- | --- |
| 论文检索 | 检索标题、作者、关键词、摘要，按 DOI／论文编号查找，按年份、出版物、预设刊会系列筛选，自定义每页条数 |
| 论文详情 | 保留顺序的作者链接、精确来源 ID 检索、摘要、分类关键词和原始来源链接 |
| 引用导出 | BibTeX、IEEE、GB/T 7714 格式，复制或下载，逐篇或按选中结果导出 |
| 显示体验 | 中英文界面，六套外观预设与跟随系统，响应式布局，KaTeX 标题公式 |
| 管理功能 | 账户管理、更新计划／任务／日志、索引状态与预检、可选资源配置 |
| 可选阅读资源 | 资源插件提供的缓存正文、章节导航、本地 PDF 和经可用性检查的批量打包 |

公开安装提供元数据浏览；阅读资源需要显式配置插件，并具备相应文件或正文数据。
资源缺失会单独显示。作者身份浏览使用已有索引，可选作者资料采集则需要明确指定单个作者。

## 网站内部结构

| 源码 | 职责 |
| --- | --- |
| [web/src/](web/src/) | React + TypeScript 读者页和管理员页 |
| [src/cirdc/web/app.py](src/cirdc/web/app.py) | Starlette API、读者／管理员路由与静态资源 |
| [src/cirdc/web/index.py](src/cirdc/web/index.py) | SQLite FTS5 搜索投影、历史回填与增量同步 |
| [src/cirdc/web/auth.py](src/cirdc/web/auth.py) | Argon2 密码散列、会话和账户审计 |
| [tests/](tests/)／[web/tests/](web/tests/) | Python/API 与前端测试 |
| [deploy/](deploy/)／[tools/deploy_web.sh](tools/deploy_web.sh) | 服务模板及发布回滚流程 |

论文详情直接读取 MySQL/MariaDB，搜索读取派生的 SQLite 索引。
索引器先回填历史记录，再消费带版本的数据库变更；提交搜索投影后才确认对应事件。
账户和索引状态保存在源码目录之外，由 `CIRDC_WEB_STATE` 选择。

读者端和管理员端使用独立路由表与会话。管理端仅监听本机回环地址，
写操作需要管理员认证、同源检查和绑定会话的 CSRF token。

## 本机安装与运行

除特别说明外，以下命令均在**仓库根目录**运行。
需要 Python 3.12、uv、Node.js 22.12+ 和 npm，元数据数据库先由根目录包完成初始化与验证。
网站使用独立环境，与根目录 `.venv` 分开，两套包的导入名都是 `cirdc`。

### 1. 安装并构建

```sh
sh tools/web setup
sh tools/web build
uv pip install --python website/.venv-dev/bin/python \
  --reinstall-package cirdc-pro --no-deps ./website
```

安装脚本将网站 `dev,web` 依赖装入 `website/.venv-dev`，并安装前端依赖。
构建执行 TypeScript 检查与 Vite 打包，在 `website/dist/` 生成 wheel 和源码包。
最后一条命令刷新网站开发环境中的常规安装包，使本机服务能够使用刚构建的前端资源。
源码或资源变化后重新刷新；也可以明确配置可编辑的开发安装。

### 2. 配置数据库与私有状态

以 [config.example.json](config.example.json) 为模板建立私有配置，填写网站主机可连接的
MySQL 地址、可访问的数据目录与运行路径。网站配置加载器不会自动转换根目录维护包的
SSH 目标配置；应显式提供可达端点或既有隧道。

```sh
export CIRDC_CONFIG=/path/to/private/website.json
export CIRDC_WEB_STATE="$HOME/.local/state/cirdc-web-dev"
```

后续各终端使用相同的变量值。状态目录使用本机存储，保存账户／会话数据库、
搜索索引与索引器检查点。首次搜索回填要求索引卷至少有 20 GiB 可用空间。

### 3. 初始化账户并运行索引器

仅在**全新**网站状态目录初始化账户：

```sh
website/.venv-dev/bin/python -m cirdc.cli web init-users --username admin
```

该命令交互读取初始密码，创建显式指定的管理员。
也可省略 `--username`，在私有配置的 `web.bootstrap_users` 中填写
`{"username": "admin", "role": "admin"}` 及 reader 条目的列表，至少包含一名管理员。
实际服务器账户名单保留在私有配置中，后续账户由已认证的管理员维护。
既有账户会保留；网站账户独立于系统账户，首次登录需要修改密码。

单独打开终端运行索引器：

```sh
website/.venv-dev/bin/python -m cirdc.cli web index
```

索引器构建或恢复索引，然后持续消费变更。`--max-rows N` 限制初始回填数量；
`--once` 在完成必要的初始回填及一轮增量／作者关系回填后退出。
有限数量或尚未完成的索引不代表全库搜索覆盖。索引会安装所需的数据库变更捕获与队列，
不会启动 IEEE 采集。

### 4. 启动读者端与管理端

在使用相同私有配置与状态目录的不同终端分别运行：

```sh
sh tools/web serve --interface reader --host 127.0.0.1 --port 18090
```

```sh
sh tools/web serve --interface admin --host 127.0.0.1 --port 18091
```

打开[读者端](http://127.0.0.1:18090/)和[管理端](http://127.0.0.1:18091/admin/)。
以上为本机开发端口。

读者端默认需要登录；设置 `CIRDC_WEB_READER_AUTH=public` 可启用匿名只读访问，
管理端始终需要认证。管理端保持回环监听，远程访问沿用已配置并获授权的隧道。

## 测试与打包

在仓库根目录：

```sh
sh tools/web test
sh tools/web build
```

网站 Python 集成测试在网站目录中运行：

```sh
cd website
CIRDC_INTEGRATION=1 CIRDC_CONFIG=/path/to/private/website-test-profile.json \
  .venv-dev/bin/python -m pytest
```

集成测试使用连接内临时表与隔离路径，应选择已验证的独立测试配置。
网站 wheel 包含构建后的前端资源，根目录元数据分发包单独构建和检查。
Node.js 用于前端开发与构建，运行已构建的网站 wheel 使用 Python 环境。

## 部署与详细文档

面向**已有且已配置的部署目标**，从根目录执行：

```sh
CIRDC_WEB_ROOT=/path/to/existing/deployment sh tools/web deploy RELEASE_ID
```

这是独立于本机安装的发布操作，需要已有私有状态、服务及回滚 wheel。
流程在停止服务前构建源码快照，离线安装 wheel，保留依赖和资源插件版本；
激活检查失败时恢复上一版。网站部署不会启动或恢复元数据采集。

- [项目总览与元数据后端](../README_CN.md)
- [统一开发与运行流程](../docs/LOCAL_REMOTE_WORKFLOW.md)
- [网站行为、搜索一致性与部署](docs/web.md)
- [显式单作者资料库](docs/authors.md)
- [CC BY 4.0 许可](LICENSE)与[上游署名](../README_CN.md#来源与许可)

凭据、部署配置、账户状态、索引和文献存储保留在 Git 之外。
