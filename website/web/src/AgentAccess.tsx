import {useEffect,useRef,useState} from 'react';
import {t} from './i18n';
import {agentExamples} from './agentAccess';
import './agentAccess.css';

function CopyExample({title,value}:{title:string;value:string}){
 const [notice,setNotice]=useState(''),field=useRef<HTMLTextAreaElement>(null);
 async function copy(){
  try{await navigator.clipboard.writeText(value);setNotice(t('已复制'));}
  catch{field.current?.focus();field.current?.select();setNotice(t('已选中文本，请手动复制。'));}
 }
 return <section className="agent-example"><div className="agent-example-heading"><h3>{title}</h3><button type="button" onClick={()=>void copy()}>{t('复制')}</button></div><textarea ref={field} className={value.includes('\n')?'':'agent-single-value'} readOnly value={value} aria-label={title} spellCheck={false}/><span role="status">{notice}</span></section>;
}

export default function AgentAccess(){
 const [capabilities,setCapabilities]=useState<any>(),[error,setError]=useState('');
 const examples=agentExamples(window.location.origin);
 useEffect(()=>{const controller=new AbortController();void fetch('/api/agent/v1/capabilities',{credentials:'omit',signal:controller.signal}).then(async r=>{if(!r.ok)throw Error();setCapabilities(await r.json());}).catch(e=>{if(e.name!=='AbortError')setError(t('暂时无法读取接入能力。'));});return()=>controller.abort();},[]);
 return <main className="workspace agent-access">
  <div className="page-heading"><div><span className="eyebrow">DEVELOPER ACCESS</span><h1>{t('AI 接入')}</h1><p className="muted">{t('让你的 AI 和项目直接检索论文、读取正文并获取 PDF。')}</p></div><a className="text-button" href="/">{t('返回论文检索')}</a></div>
  <section className="panel agent-intro"><h2>{t('一个站点地址，按需选择接入方式')}</h2><p>{t('公开访问，无需账号或 API Key。已有资料直接返回，缺失资源按需获取。')}</p><code className="agent-base">{examples.base}</code>
   <div className="agent-capabilities" aria-live="polite">{error?<span role="alert">{error}</span>:capabilities?['content','pdf'].map(kind=><span className="badge" key={kind}>{kind==='content'?t('正文'):'PDF'} · {capabilities.resources[kind]?.enabled?t('可用'):t('未配置')}</span>):<span>{t('正在检查可用能力…')}</span>}</div>
   <div className="agent-links"><a href={examples.skillUrl}>{t('在线 Skill')}</a><a href="/api/agent/v1/openapi.json">OpenAPI</a><a href="/llms.txt">{t('机器可读说明')}</a></div>
  </section>
  <div className="agent-grid">
   <section className="panel"><h2>{t('在 AI 中使用')}</h2><p>{t('在支持远程 MCP 的 AI 工具中填写服务地址，即可直接使用。无需下载压缩包或启动本地适配器。')}</p><CopyExample title={t('MCP 服务地址')} value={examples.mcpUrl}/><p>{t('连接类型选择 Streamable HTTP。使用 JSON 配置的工具可参考以下示例。')}</p><CopyExample title={t('MCP 配置')} value={examples.mcp}/><p>{t('也可以把在线 Skill 地址交给 AI，让它读取调用流程并直接使用 HTTP API。')}</p><CopyExample title={t('在线 Skill 地址')} value={examples.skillUrl}/></section>
   <section className="panel"><h2>{t('在项目中调用')}</h2><p>{t('HTTP API 可直接用于脚本和应用，不需要安装 MCP 或数据库环境。')}</p><CopyExample title={t('HTTP 调用示例')} value={examples.http}/></section>
  </div>
  <section className="panel"><h2>{t('安装到 Codex / Claude Code')}</h2><p>{t('将一份 Skill 保存到本机，再软链接到所选工具的技能目录，即可在各项目中使用。')}</p><p className="hint">{t('在本机终端运行，需要 macOS / Linux、Python 3.10+；从站点下载时还需要 curl。')}</p><p>{t('已有仓库源码时，在仓库根目录运行以下命令即可直接安装。安装可离线执行，站点地址可在首次使用时提供。')}</p><CopyExample title={t('从仓库源码安装')} value={examples.sourceInstall}/><p>{t('通过站点下载安装：')}</p><div className="agent-grid"><CopyExample title={t('安装到 Codex')} value={examples.installCodex}/><CopyExample title={t('安装到 Claude Code')} value={examples.installClaudeCode}/></div><p>{t('安装后在 Codex 新会话中使用 $cirdc-research；Claude Code 运行 /reload-skills 后使用 /cirdc-research。')}</p><p>{t('重新运行安装命令即可更新。站点地址会保存在本机；原生 Skill 安装与 MCP 连接分别配置。')}</p><div className="agent-links"><a href={examples.base+'/skills/cirdc-research/references/api.md#native-skill-installation'}>{t('软链接、源码安装与卸载说明')}</a></div></section>
  <section className="panel"><h2>{t('从检索到可用资源')}</h2><ol className="agent-workflow"><li>{t('检索并确认论文编号、标题及 DOI。')}</li><li>{t('请求所需正文或 PDF，默认最多等待 10 秒。')}</li><li>{t('若返回 202，保存 request_id，按提示间隔查询 status_url。查询不会重新启动任务。')}</li><li>{t('正文按 next_cursor 继续读取，并保持同一版本；PDF 使用返回的下载链接。')}</li></ol><p>{t('正文、图片和 PDF 分别报告状态。部分可用或已排队不代表全部完成；失败后仅在明确需要时重试。')}</p><p className="hint">{t('示例中的 ARTICLE_NUMBER 与 REQUEST_ID 需要替换为实际返回值。接入页面本身不会触发资源获取。')}</p><CopyExample title={t('Python 调用示例')} value={examples.python}/></section>
 </main>;
}
