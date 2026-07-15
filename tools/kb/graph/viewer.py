from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .config import load_source_config, output_root


def render_graph_html(data: dict[str, Any]) -> str:
    embedded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    template = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>知识库关系图</title>
  <link rel="icon" href="data:," />
  <script src="https://unpkg.com/vis-network@9.1.6/standalone/umd/vis-network.min.js"
          integrity="sha384-Ux6phic9PEHJ38YtrijhkzyJ8yQlH8i/+buBR8s3mAZOJrP1gwyvAcIYl3GWtpX1"
          crossorigin="anonymous"></script>
  <style>
    :root{--bg:#0d0e18;--panel:#171827;--panel2:#10111d;--line:#2c2e45;--text:#ececf4;--muted:#9295aa;--accent:#6aa9e9}
    *{box-sizing:border-box}body{margin:0;height:100vh;overflow:hidden;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif}
    .app{display:grid;grid-template-columns:minmax(0,1fr) 350px;height:100vh}.stage{position:relative;min-width:0;min-height:0;height:100vh;overflow:hidden;background:#0d0e18}.side{background:linear-gradient(180deg,#191a2b,#141522);border-left:1px solid var(--line);overflow:hidden;display:flex;flex-direction:column}
    .side-head{padding:17px 18px 12px;border-bottom:1px solid var(--line)}h1{font-size:18px;margin:0 0 5px}.sub{font-size:11px;color:var(--muted);line-height:1.5}
    .controls{padding:12px 16px;border-bottom:1px solid var(--line);max-height:48vh;overflow:auto}.section{margin-top:12px}.section:first-child{margin-top:0}.section h2{font-size:11px;color:#9fa2b8;text-transform:uppercase;letter-spacing:.09em;margin:0 0 7px}
    .views{display:grid;grid-template-columns:1fr 1fr;gap:6px}button,select,input{font:inherit;color:var(--text);background:#0e0f1a;border:1px solid #343650;border-radius:6px;padding:7px 8px;outline:none}button{cursor:pointer}button.active{background:#285d91;border-color:#609bd2}.row{display:grid;grid-template-columns:1fr 1fr;gap:6px}.wide{grid-column:1/-1}
    label{display:block;color:var(--muted);font-size:10px;margin:7px 0 3px}select,input{width:100%;font-size:11px}.search-wrap{position:relative}.search-results{display:none;position:absolute;z-index:20;left:0;right:0;top:100%;max-height:180px;overflow:auto;background:#111321;border:1px solid #373a55;border-radius:0 0 6px 6px}.search-item{padding:7px 8px;font-size:11px;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.search-item:hover{background:#252840}
    .community-head{padding:12px 16px 8px;display:flex;align-items:center;justify-content:space-between}.community-head h2{font-size:13px;margin:0;letter-spacing:.08em}.select-all{display:flex;align-items:center;gap:6px;font-size:11px;color:#b3b6c8;cursor:pointer}.select-all input{width:auto}
    .communities{padding:0 12px 10px;overflow:auto;flex:1}.community-item{display:grid;grid-template-columns:18px 12px minmax(0,1fr) auto;align-items:center;gap:7px;padding:5px 4px;border-radius:5px;font-size:11px}.community-item:hover{background:#222438}.community-item input{width:auto}.community-dot{width:10px;height:10px;border-radius:50%}.community-name{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.community-count{color:#74778d}
    .detail{border-top:1px solid var(--line);padding:11px 16px;min-height:120px;max-height:30vh;overflow:auto;font-size:11px;line-height:1.55;color:#bfc1d0;word-break:break-word}.detail b{color:#fff}.source{display:inline-block;margin-top:6px;color:#88bde9;text-decoration:none}.source:hover{text-decoration:underline}.empty{color:#73768b;font-style:italic}
    #graph{position:absolute;inset:0}.topbar{position:absolute;left:14px;top:13px;z-index:4;background:rgba(17,18,31,.88);border:1px solid var(--line);border-radius:8px;padding:7px 10px;color:var(--muted);font-size:11px;backdrop-filter:blur(8px)}.pill{display:inline-block;border:1px solid #3d405c;border-radius:999px;padding:2px 7px;margin-right:5px;color:#c9d9e9}.loading{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#777b90;font-size:13px;pointer-events:none}.error{color:#f19a9a;text-align:center;max-width:420px;line-height:1.7}
    @media(max-width:820px){.app{grid-template-columns:1fr}.side{position:absolute;z-index:10;right:0;top:0;bottom:0;width:320px;box-shadow:-8px 0 25px #0008}}
  </style>
</head>
<body>
<div class="app">
  <main class="stage">
    <div id="stats" class="topbar"></div>
    <div id="graph"></div>
    <div id="loading" class="loading">正在形成社区网络…</div>
  </main>
  <aside class="side">
    <div class="side-head"><h1>知识库关系图</h1><div class="sub">Graphify 社区网络 · 五类知识视图 · 节点可回查来源</div></div>
    <div class="controls">
      <div class="section"><h2>看什么</h2><div id="views" class="views"></div></div>
      <div class="section"><h2>呈现方式</h2><div class="views"><button id="communityMode" class="active">社区网络</button><button id="layerMode">分层布局</button></div></div>
      <div class="section"><h2>查找与筛选</h2>
        <div class="search-wrap"><input id="search" placeholder="搜索并定位节点…" /><div id="searchResults" class="search-results"></div></div>
        <div class="row">
          <div><label>层级</label><select id="layer"><option value="">全部</option></select></div>
          <div><label>状态</label><select id="status"><option value="">全部</option></select></div>
          <div><label>领域</label><select id="domain"><option value="">全部</option></select></div>
          <div><label>关系来源</label><select id="relationSource"><option value="">全部</option><option value="deterministic">结构确定</option><option value="explicit">明确声明</option><option value="inferred">底层推断</option></select></div>
          <div class="wide"><label>最低可信度</label><select id="confidence"><option value="low">全部（推断关系淡显）</option><option value="medium">中及以上</option><option value="high">只看高可信</option></select></div>
        </div>
      </div>
    </div>
    <div class="community-head"><h2>社区</h2><label class="select-all"><input id="selectAll" type="checkbox" checked />全选</label></div>
    <div id="communities" class="communities"></div>
    <div id="detail" class="detail empty">点击网络中的节点查看层级、社区和原文件。</div>
  </aside>
</div>
<script id="graph-data" type="application/json">__GRAPH_DATA__</script>
<script>
const DATA=JSON.parse(document.getElementById('graph-data').textContent);
const RAW_NODES=(DATA.nodes||[]).map(n=>({...n,id:String(n.id)}));
const RAW_LINKS=(DATA.links||[]).map((e,i)=>({...e,_id:i,source:String(e.source),target:String(e.target)}));
const BY_ID=new Map(RAW_NODES.map(n=>[n.id,n]));
const VIEW_DEFS=(DATA.view_config&&DATA.view_config.views)||[];
const LAYER_COLORS=(DATA.view_config&&DATA.view_config.layers)||{};
const COMMUNITY_LABELS=DATA.community_labels||{};
const PALETTE=['#4E79A7','#F28E2B','#E15759','#76B7B2','#59A14F','#EDC948','#B07AA1','#FF9DA7','#9C755F','#BAB0AC','#6B9AC4','#E88C30','#D65F5F','#72C2C2','#65B95A','#F1C84B','#B783B5','#FF9DA7','#A67C64','#C7C1BD'];
const state={view:(DATA.view_config&&DATA.view_config.default_view)||'system',layout:'community',layer:'',status:'',domain:'',relationSource:'',confidence:'low',selected:'',hiddenCommunities:new Set()};
let network=null,nodesDS=null,edgesDS=null,currentNodes=[],currentLinks=[];
const confidenceRank=v=>({low:0,medium:1,high:2}[v]??0);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const communityId=n=>Number.isFinite(Number(n.community))?Number(n.community):0;
const communityColor=cid=>PALETTE[Math.abs(Number(cid)||0)%PALETTE.length];
const communityName=cid=>COMMUNITY_LABELS[String(cid)]||`社区 ${cid}`;

function baseNodeVisible(n){
  if(!(n.views||[]).includes(state.view))return false;
  if(state.layer&&n.layer!==state.layer)return false;
  if(state.status&&n.status!==state.status)return false;
  if(state.domain&&n.domain!==state.domain)return false;
  return true;
}
function baseNodes(){return RAW_NODES.filter(baseNodeVisible)}
function filteredData(){
  const nodes=baseNodes().filter(n=>!state.hiddenCommunities.has(communityId(n)));
  const ids=new Set(nodes.map(n=>n.id));
  const links=RAW_LINKS.filter(e=>ids.has(e.source)&&ids.has(e.target)&&(!state.relationSource||e.relation_source===state.relationSource)&&confidenceRank(e.confidence)>=confidenceRank(state.confidence));
  return {nodes,links};
}
function unique(field){return [...new Set(baseNodes().map(n=>String(n[field]||'')).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'zh-CN'))}
function fillSelect(id,values){const el=document.getElementById(id),current=el.value;el.innerHTML='<option value="">全部</option>'+values.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');if(values.includes(current))el.value=current}
function refreshFilters(){fillSelect('layer',unique('layer'));fillSelect('status',unique('status'));fillSelect('domain',unique('domain'))}

function visualNodes(nodes,links){
  const degree=new Map(nodes.map(n=>[n.id,0]));links.forEach(e=>{degree.set(e.source,(degree.get(e.source)||0)+1);degree.set(e.target,(degree.get(e.target)||0)+1)});
  const maxDegree=Math.max(1,...degree.values());
  return nodes.map(n=>{
    const cid=communityId(n),deg=degree.get(n.id)||0,color=communityColor(cid),important=deg>=maxDegree*.12||n.id===state.selected||n.node_kind==='route'||n.node_kind==='account'||n.node_kind==='workflow_stage';
    return {id:n.id,label:important?String(n.label||''):'',title:esc(String(n.label||'')),size:5+17*Math.sqrt(deg/maxDegree),color:{background:color,border:n.id===state.selected?'#ffffff':color,highlight:{background:'#ffffff',border:color}},borderWidth:n.id===state.selected?3:1.2,font:{size:important?11:0,color:'#f4f4fa',strokeWidth:2,strokeColor:'#0d0e18'},_label:String(n.label||''),_community:cid,_layer:n.layer,_source:n.source_file};
  })
}
function visualEdges(links){return links.map(e=>{const weak=e.confidence==='low'||e.relation_source==='inferred';return{id:e._id,from:e.source,to:e.target,title:esc(`${e.relation||'related'} · ${e.relation_source||''} · ${e.confidence||''}`),width:e.confidence==='high'?1.25:.7,dashes:e.relation_source==='inferred',color:{color:weak?'#596174':'#8d94a8',opacity:weak?.20:.42},arrows:{to:{enabled:true,scaleFactor:.35}}}})}
function layeredPositions(items){
  const groups=new Map();items.forEach(n=>{const raw=BY_ID.get(n.id),key=raw?.layer||'unknown';if(!groups.has(key))groups.set(key,[]);groups.get(key).push(n)});
  const keys=[...groups.keys()].sort();keys.forEach((key,gi)=>{const list=groups.get(key);const cols=Math.max(1,Math.ceil(Math.sqrt(list.length)));list.forEach((n,i)=>{n.x=gi*620+(i%cols)*24;n.y=Math.floor(i/cols)*24;n.fixed={x:true,y:true}})});
}
function networkOptions(){return{
  autoResize:true,
  physics:state.layout==='community'?{enabled:true,solver:'forceAtlas2Based',forceAtlas2Based:{gravitationalConstant:-52,centralGravity:.008,springLength:92,springConstant:.065,damping:.46,avoidOverlap:.55},stabilization:{enabled:true,iterations:260,updateInterval:25,fit:true}}:{enabled:false},
  interaction:{hover:true,tooltipDelay:100,hideEdgesOnDrag:true,hideEdgesOnZoom:true,multiselect:false,navigationButtons:false,keyboard:false},
  nodes:{shape:'dot'},edges:{smooth:{type:'continuous',roundness:.15},selectionWidth:2},layout:{improvedLayout:false}
}}
function ensureNetwork(){
  if(typeof vis==='undefined'){document.getElementById('loading').innerHTML='<div class="error">可视化引擎未加载。请确认网络可访问 unpkg.com，或使用本地 Web 后刷新。</div>';return false}
  if(network)return true;
  nodesDS=new vis.DataSet([]);edgesDS=new vis.DataSet([]);network=new vis.Network(document.getElementById('graph'),{nodes:nodesDS,edges:edgesDS},networkOptions());
  network.on('stabilizationProgress',p=>{document.getElementById('loading').textContent=`正在形成社区网络… ${Math.round(p.iterations/p.total*100)}%`});
  network.on('stabilizationIterationsDone',()=>{document.getElementById('loading').style.display='none';network.setOptions({physics:{enabled:false}})});
  network.on('click',params=>{if(params.nodes.length)showDetail(String(params.nodes[0]));else clearDetail()});
  return true;
}
function applyFilters({rerenderCommunities=true,refit=true}={}){
  if(!ensureNetwork())return;
  const data=filteredData();currentNodes=data.nodes;currentLinks=data.links;const vNodes=visualNodes(data.nodes,data.links);if(state.layout==='layered')layeredPositions(vNodes);
  nodesDS.clear();edgesDS.clear();nodesDS.add(vNodes);edgesDS.add(visualEdges(data.links));network.setOptions(networkOptions());
  if(state.layout==='community'){document.getElementById('loading').style.display='flex';network.stabilize(260)}else{document.getElementById('loading').style.display='none';setTimeout(()=>network.fit({animation:{duration:350}}),20)}
  if(rerenderCommunities)renderCommunities();if(refit&&state.layout==='community')setTimeout(()=>network.fit({animation:{duration:350}}),80);
  const viewName=VIEW_DEFS.find(v=>v.id===state.view)?.name||state.view;document.getElementById('stats').innerHTML=`<span class="pill">${esc(viewName)}</span><span class="pill">${state.layout==='community'?'社区网络':'分层布局'}</span>节点 ${data.nodes.length} · 关系 ${data.links.length}`;
}

function renderViews(){document.getElementById('views').innerHTML=VIEW_DEFS.map(v=>`<button data-view="${esc(v.id)}" class="${v.id===state.view?'active':''}" title="${esc(v.description)}">${esc(v.name)}</button>`).join('');document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{state.view=b.dataset.view;state.layer=state.status=state.domain=state.relationSource='';state.confidence='low';state.hiddenCommunities.clear();document.getElementById('relationSource').value='';document.getElementById('confidence').value='low';renderViews();refreshFilters();applyFilters()})}
function renderCommunities(){
  const counts=new Map();baseNodes().forEach(n=>counts.set(communityId(n),(counts.get(communityId(n))||0)+1));const rows=[...counts.entries()].sort((a,b)=>b[1]-a[1]||a[0]-b[0]);
  document.getElementById('communities').innerHTML=rows.map(([cid,count])=>`<label class="community-item"><input type="checkbox" data-community="${cid}" ${state.hiddenCommunities.has(cid)?'':'checked'} /><span class="community-dot" style="background:${communityColor(cid)}"></span><span class="community-name">${esc(communityName(cid))}</span><span class="community-count">${count}</span></label>`).join('');
  document.querySelectorAll('[data-community]').forEach(cb=>cb.onchange=()=>{const cid=Number(cb.dataset.community);cb.checked?state.hiddenCommunities.delete(cid):state.hiddenCommunities.add(cid);applyFilters({rerenderCommunities:false})});
  const all=document.getElementById('selectAll');all.checked=state.hiddenCommunities.size===0;all.indeterminate=state.hiddenCommunities.size>0&&state.hiddenCommunities.size<rows.length;
}
function setLayout(mode){state.layout=mode;document.getElementById('communityMode').classList.toggle('active',mode==='community');document.getElementById('layerMode').classList.toggle('active',mode==='layered');applyFilters({rerenderCommunities:false})}
function sourceHref(n){if(!n.source_file||String(n.source_file).endsWith('/'))return'';if(location.protocol==='file:')return encodeURI(`file://${DATA.root}/${n.source_file}`);return`/api/source?path=${encodeURIComponent(n.source_file)}`}
function showDetail(id){const n=BY_ID.get(id);if(!n)return;const previous=state.selected;state.selected=id;const href=sourceHref(n),source=href?`<a class="source" target="_blank" href="${href}">查看原文件 ${esc(n.source_location||'')}</a>`:'';const neighbors=network?network.getConnectedNodes(id).length:0;document.getElementById('detail').classList.remove('empty');document.getElementById('detail').innerHTML=`<b>${esc(n.label)}</b><br>社区：<span style="color:${communityColor(communityId(n))}">${esc(communityName(communityId(n)))}</span><br>层级：${esc(n.layer)} · 状态：${esc(n.status)}<br>领域：${esc(n.domain)} · 相邻节点：${neighbors}${n.account?`<br>账号：${esc(n.account)}`:''}${n.purpose?`<br>说明：${esc(n.purpose)}`:''}<br>来源：${esc(n.source_file||'派生节点')}${source}`;if(previous&&nodesDS.get(previous)){const old=BY_ID.get(previous),oldColor=communityColor(communityId(old));nodesDS.update({id:previous,borderWidth:1.2,color:{background:oldColor,border:oldColor,highlight:{background:'#ffffff',border:oldColor}}})}if(nodesDS.get(id)){const color=communityColor(communityId(n));nodesDS.update({id,label:String(n.label||''),borderWidth:3,color:{background:color,border:'#ffffff',highlight:{background:'#ffffff',border:color}}})}network.selectNodes([id]);network.focus(id,{scale:1.35,animation:true})}
function clearDetail(){state.selected='';document.getElementById('detail').className='detail empty';document.getElementById('detail').textContent='点击网络中的节点查看层级、社区和原文件。'}
function searchMatches(query){const q=query.toLowerCase().trim();if(!q)return[];return baseNodes().filter(n=>[n.label,n.source_file,n.domain,n.account,n.purpose].join(' ').toLowerCase().includes(q)).slice(0,20)}
function renderSearch(){const input=document.getElementById('search'),box=document.getElementById('searchResults'),matches=searchMatches(input.value);if(!matches.length){box.style.display='none';box.innerHTML='';return}box.innerHTML=matches.map(n=>`<div class="search-item" data-search-id="${esc(n.id)}" style="border-left:3px solid ${communityColor(communityId(n))}">${esc(n.label)} <span style="color:#707389">${esc(n.domain||'')}</span></div>`).join('');box.style.display='block';document.querySelectorAll('[data-search-id]').forEach(el=>el.onclick=()=>{const id=el.dataset.searchId,cid=communityId(BY_ID.get(id));state.hiddenCommunities.delete(cid);applyFilters();setTimeout(()=>showDetail(id),80);box.style.display='none';input.value=''})}

document.getElementById('communityMode').onclick=()=>setLayout('community');document.getElementById('layerMode').onclick=()=>setLayout('layered');
document.getElementById('selectAll').onchange=e=>{if(e.target.checked)state.hiddenCommunities.clear();else baseNodes().forEach(n=>state.hiddenCommunities.add(communityId(n)));applyFilters()};
['layer','status','domain','relationSource','confidence'].forEach(id=>document.getElementById(id).onchange=e=>{state[id]=e.target.value;state.hiddenCommunities.clear();applyFilters()});
document.getElementById('search').oninput=renderSearch;document.addEventListener('click',e=>{if(!e.target.closest('.search-wrap'))document.getElementById('searchResults').style.display='none'});
renderViews();refreshFilters();renderCommunities();applyFilters();
</script>
</body></html>"""
    return template.replace("__GRAPH_DATA__", embedded)


def serve_graph(root: Path, host: str = "127.0.0.1", port: int = 8790) -> int:
    root = root.resolve()
    out = output_root(root, load_source_config(root))
    graph_path, html_path, manifest_path = out / "graph.json", out / "index.html", out / "manifest.json"
    if not graph_path.exists() or not html_path.exists() or not manifest_path.exists():
        raise RuntimeError("graph_not_built: run tools.kb.cli graph build")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    allowed = {str(item) for item in manifest.get("allowed_sources") or []}

    class Handler(BaseHTTPRequestHandler):
        def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/index.html"}:
                self._send(html_path.read_bytes(), "text/html; charset=utf-8")
                return
            if parsed.path == "/graph.json":
                self._send(graph_path.read_bytes(), "application/json; charset=utf-8")
                return
            if parsed.path == "/api/source":
                relative = (parse_qs(parsed.query).get("path") or [""])[0]
                if relative not in allowed:
                    self._send("来源不在本次图谱白名单中。".encode(), "text/plain; charset=utf-8", 403)
                    return
                source = (root / relative).resolve()
                try:
                    source.relative_to(root)
                except ValueError:
                    self._send("非法来源路径。".encode(), "text/plain; charset=utf-8", 403)
                    return
                if not source.is_file():
                    self._send("来源文件不存在。".encode(), "text/plain; charset=utf-8", 404)
                    return
                self._send(source.read_bytes()[:500_000], "text/plain; charset=utf-8")
                return
            self._send(b"not found", "text/plain; charset=utf-8", 404)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Knowledge graph: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
