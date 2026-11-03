export const CIRDC_REPOSITORY='https://github.com/NicolasV15/CIRDC-Pro.git';

export function agentPrompts(origin:string,language:'zh'|'en'='zh'){
 const site=new URL(origin).origin;
 const skill=site+'/api/agent/v1/skills/cirdc-research/SKILL.md';
 const installer=site+'/api/agent/v1/skills/cirdc-research/scripts/install_skill.py';
 const remote=language==='zh'?`请在当前 AI 工具实际发现技能的本机环境中，为我安装 cirdc-research Skill，并连接以下 CIRDC-Pro 站点。
目标站点：${site}
在线 Skill：${skill}
官方安装程序：${installer}

先读取在线 Skill 及其安装说明，识别当前 AI 工具，使用官方安装程序完成原生 Skill 安装。安装时明确设置参数 --base-url ${site}
验证连接并保存站点配置。复用或安全更新匹配的安装，保留已有文件和其他配置；如果工作区经过 SSH，区分源码所在机器与技能实际安装的机器。

安装完成后，从任意项目目录，在不传 URL 的情况下调用已安装的 Skill HTTP helper 的 capabilities，核对调用实际使用的地址就是上述站点。请直接执行并返回 Skill 安装位置、已绑定站点和验证结果，后续使用时不要再向我询问站点地址。`:
`Install the cirdc-research Skill in the local environment where my current AI host actually discovers skills, and connect it to the CIRDC-Pro site below.
Target site: ${site}
Online Skill: ${skill}
Official installer: ${installer}

Read the online Skill and its installation reference. Identify the current AI host and complete its native Skill installation with the official installer. Set this installer argument explicitly: --base-url ${site}
Verify connectivity and persist the site configuration. Reuse or safely update a matching installation while preserving existing files and other settings. If the workspace uses SSH, distinguish the source machine from the machine where skills are installed.

From an arbitrary project directory, call capabilities through the installed Skill's HTTP helper without providing a URL, and verify that the helper actually uses the target site above. Execute the installation and report the Skill location, bound site, and verification result. Do not ask me for a site address during later research use.`;
 const local=language==='zh'?`请在当前对话的工作目录下，一条龙完成 CIRDC-Pro 源码克隆、本地网页部署和 cirdc-research Skill 安装。先用 pwd 或等效命令确认当前工作目录，将它作为部署根目录，无需再让我指定路径。
源码仓库：${CIRDC_REPOSITORY}

1. 检查当前工作目录和运行环境，将仓库克隆到其中的 CIRDC-Pro 子目录；如果当前目录本身或该子目录已是同仓副本，则直接复用。阅读根目录和 website/ 的 AGENTS.md、README 及部署说明，保护已有文件、数据和服务。
2. 使用仓库官方入口准备依赖，分别维护元数据后端与网站的 Python 环境，完成首次部署所需的数据库、私有配置、账户/访问模式、搜索索引和前端构建。我明确提供的数据目标经校验后可使用；否则为本次部署新建独立空库和状态目录，配置保存在源码之外，并如实记录数据与正文/PDF provider 的状态。
3. 启动并验证网页和 API，配置退出本轮会话后仍能运行的后台服务。默认尝试本机 18088；若端口被占用，保留原服务并选择空闲端口，确定从 Skill 执行环境可达的实际站点 URL。
4. 从刚克隆的源码为当前 AI 工具安装 cirdc-research Skill，将上述实际 URL 通过安装器的 --base-url 明确写入本机配置。Skill 必须指向这次部署的实例；站点配置在安装阶段完成。
5. 验证网页、/healthz、/api/agent/v1/capabilities、检索 API，以及已安装 helper 在不传 URL 时实际使用的地址与本次部署 URL 一致。区分服务可用、数据覆盖和资源可用性，不把部署完成当作全库同步完成。

请直接完成这些步骤，返回源码位置、网页地址、Skill 安装位置、保存的站点地址、验证结果及后台服务的启动/停止方法。仅在缺少必要权限或无法继续所需的信息时询问。`:
`Complete the entire CIRDC-Pro workflow in this conversation's current working directory: clone the source, deploy the website locally, and install the cirdc-research Skill. Confirm the current directory with pwd or the platform equivalent and use it as the deployment root without asking me to supply a path.
Source repository: ${CIRDC_REPOSITORY}

1. Inspect the current directory and runtime environment, then clone into its CIRDC-Pro subdirectory. If the current directory itself or that subdirectory is already a matching checkout, reuse it. Read AGENTS.md, README, and deployment guidance at the root and under website/. Preserve existing files, data, and services.
2. Use the official repository entrypoints to prepare dependencies, keeping the metadata and website Python environments separate. Complete first-deployment database initialization, private configuration, accounts/access mode, search indexing, and the frontend build. Validate and use a data target I explicitly supplied; otherwise create an isolated empty database and state directory for this deployment, keep configuration outside the source tree, and accurately record data and full-text/PDF provider availability.
3. Start and verify the website and API, with a background service that survives the end of this session. Try local port 18088 by default; if occupied, preserve the existing service and choose an available port. Determine the actual site URL reachable from the Skill's execution environment.
4. Install cirdc-research from this checkout for the current AI host, passing that actual URL explicitly through the installer's --base-url option and saving it locally. The Skill must point to the instance deployed by this task. Complete site configuration during installation.
5. Verify the website, /healthz, /api/agent/v1/capabilities, the search API, and that the installed helper without a URL argument actually uses this deployment URL. Distinguish service readiness, data coverage, and resource availability; deployment does not establish complete corpus synchronization.

Execute the workflow and return the checkout location, website URL, Skill location, saved site address, verification results, and service start/stop instructions. Ask only when a required permission or missing fact prevents further progress.`;
 return {remote,local};
}
