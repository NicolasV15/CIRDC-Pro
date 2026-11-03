export function agentExamples(origin:string){
 const site=new URL(origin).origin,base=site+'/api/agent/v1';
 const quote=(value:string)=>"'"+value.replace(/'/g,"'\"'\"'")+"'";
 const installUrl=base+'/skills/cirdc-research/scripts/install_skill.py';
 const install=(agent:string)=>`curl --fail --location --silent --show-error ${quote(installUrl)} --output cirdc-install-skill.py &&\npython3 cirdc-install-skill.py --base-url ${quote(site)} --agent ${agent}`;
 return {
  base,
  installUrl,
  sourceInstall:'sh tools/install-skill --agent all',
  installCodex:install('codex'),
  installClaudeCode:install('claude-code'),
  mcpUrl:base+'/mcp',
  skillUrl:base+'/skills/cirdc-research/SKILL.md',
  mcp:JSON.stringify({mcpServers:{'cirdc-research':{type:'http',url:base+'/mcp'}}},null,2),
  http:`curl '${base}/papers?q=ring%20amplifier&limit=20'\n\ncurl -X POST '${base}/papers/ARTICLE_NUMBER/ensure' \\\n  -H 'Content-Type: application/json' \\\n  -d '{"resources":["content","pdf"],"wait_seconds":10}'\n\ncurl '${base}/requests/REQUEST_ID'\n\ncurl '${base}/papers/ARTICLE_NUMBER/content?format=markdown'`,
  python:`import json\nfrom urllib.request import Request, urlopen\n\nbase = ${JSON.stringify(base)}\nrequest = Request(\n    base + "/papers/ARTICLE_NUMBER/ensure",\n    data=json.dumps({"resources": ["content"], "wait_seconds": 10}).encode(),\n    headers={"Content-Type": "application/json"},\n)\nwith urlopen(request, timeout=45) as response:\n    receipt = json.load(response)\nprint(receipt)  # Save request_id; inspect each resource state.`,
 };
}
