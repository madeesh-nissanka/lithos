# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
Offline HTML screening dashboard for LITHOS.

Generates a single self-contained HTML file (no network, no CDN, no server):
records are embedded as JSON, decisions persist in browser localStorage, and
include/exclude buttons with reasons and tags update live PRISMA counts.
The exported decisions CSV is directly importable by
``lithos screen --import-decisions NAME=file.csv``.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from lithos._version import VERSION
from lithos.models import Record, ScreenState

logger = logging.getLogger(__name__)

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>LITHOS screening dashboard</title>
<style>
:root{--inc:#2e7d32;--exc:#c62828;--conf:#ef6c00;--line:#d7d7d7}
body{font-family:system-ui,Arial;margin:0;background:#f4f4f4;color:#212121}
header{background:#263238;color:#fff;padding:10px 16px;display:flex;flex-wrap:wrap;gap:12px;align-items:center}
header h1{font-size:18px;margin:0;font-weight:600}
.prisma{display:flex;gap:10px;flex-wrap:wrap;margin-left:auto}
.prisma span{background:#37474f;border-radius:4px;padding:4px 10px;font-size:13px}
.prisma b{margin-left:6px}
#bar{padding:10px 16px;background:#fff;border-bottom:1px solid var(--line);display:flex;gap:10px;flex-wrap:wrap;align-items:center}
#bar input[type=search]{padding:6px;border:1px solid var(--line);border-radius:4px;min-width:240px}
select,button{padding:6px 10px;border:1px solid var(--line);border-radius:4px;background:#fff;cursor:pointer}
button.primary{background:#1565c0;color:#fff;border-color:#1565c0}
main{padding:14px 16px;max-width:1100px;margin:0 auto}
article{background:#fff;border:1px solid var(--line);border-left:6px solid #90a4ae;border-radius:6px;margin:0 0 10px;padding:10px 14px}
article.inc{border-left-color:var(--inc)}article.exc{border-left-color:var(--exc)}article.conf{border-left-color:var(--conf)}
.meta{font-size:12.5px;color:#555;margin:2px 0 6px}
.abstract{font-size:13px;color:#333;margin:6px 0;display:none;white-space:pre-wrap}
.abstract.open{display:block}
.ctl{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:6px}
.ctl .state{font-size:12px;font-weight:700;width:74px}
.inc .state{color:var(--inc)}.exc .state{color:var(--exc)}.conf .state{color:var(--conf)}
progress{width:160px;height:14px}
.tag{background:#e3f2fd;border-radius:3px;padding:1px 6px;font-size:11px;margin-left:4px}
#status{font-size:12px;color:#555;margin-left:8px}
h2{margin:0 0 10px;font-size:15px;color:#37474f}
</style>
</head>
<body>
<header>
  <h1>LITHOS screening dashboard <small>v__VERSION__</small></h1>
  <div class="prisma">
    <span>identified<b id="p_id">0</b></span>
    <span>screened<b id="p_s">0</b></span>
    <span>included<b id="p_i">0</b></span>
    <span>excluded<b id="p_e">0</b></span>
    <span>conflicts<b id="p_c">0</b></span>
  </div>
</header>
<div id="bar">
  <input type="search" id="q" placeholder="Filter title/author/venue...">
  <select id="fstate">
    <option value="">All states</option><option value="UNSCREENED">Unscreened</option>
    <option value="INCLUDE">Include</option><option value="EXCLUDE">Exclude</option>
    <option value="CONFLICT">Conflict</option>
  </select>
  <select id="fsort"><option value="rank">Rank (as given)</option><option value="year_desc">Year desc</option><option value="year_asc">Year asc</option><option value="title">Title A-Z</option></select>
  <label><input type="checkbox" id="abs"> show abstracts</label>
  <span style="margin-left:auto">reviewer <input type="text" id="reviewer" size="10"></span>
  <progress id="prog" max="1" value="0"></progress><span id="status"></span>
  <button class="primary" onclick="exportCSV()">Export decisions CSV</button>
  <button class="primary" onclick="exportJSON()">Export decisions JSON</button>
  <button onclick="clearAll()">Reset decisions</button>
</div>
<main id="list"><h2>Records</h2></main>
<script>
"use strict";
const DATA=__PAYLOAD__;
const KEY="lithos_dash_"+DATA.dataset_id;
let decisions=JSON.parse(localStorage.getItem(KEY)||"{}");
const RULE_REASONS=(DATA.rules&&DATA.rules.reasons)||["wrong population","wrong outcome","wrong intervention","not primary research","wrong study design","full text unavailable","duplicate"];
function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}
function setDec(id,st,reason,tags){
  const prev=decisions[id]||{};
  if(!st){delete decisions[id];}
  else{decisions[id]={decision:st,reason:reason!==undefined?reason:(prev.reason||""),tags:tags!==undefined?tags:(prev.tags||[]),reviewer:document.getElementById("reviewer").value||prev.reviewer||""};}
  localStorage.setItem(KEY,JSON.stringify(decisions));render();
}
function addTag(ev,id){const t=prompt("tag:");if(t){const d=decisions[id]||{decision:"UNSCREENED",tags:[]};d.tags=(d.tags||[]).concat([t]);decisions[id]=d;localStorage.setItem(KEY,JSON.stringify(decisions));render();}}
function toggleAbs(ev,id){const a=document.getElementById("abs_"+id.replace(/[^a-zA-Z0-9]/g,"_"));a.classList.toggle("open")}
function stateOf(r){const d=decisions[r.id];return (d&&d.decision)||r.screen_state||"UNSCREENED"}
function render(){
  const q=document.getElementById("q").value.toLowerCase();
  const fs=document.getElementById("fstate").value;
  const sort=document.getElementById("fsort").value;
  let recs=DATA.records.map((r,i)=>({...r,_i:i}));
  if(fs)recs=recs.filter(r=>stateOf(r)===fs);
  if(q)recs=recs.filter(r=>(r.title+" "+(r.authors||[]).join(" ")+" "+(r.venue||"")).toLowerCase().includes(q));
  if(sort==="year_desc")recs.sort((a,b)=>(b.year||0)-(a.year||0));
  if(sort==="year_asc")recs.sort((a,b)=>(a.year||9999)-(b.year||9999));
  if(sort==="title")recs.sort((a,b)=>a.title.localeCompare(b.title));
  let n=0,ni=0,ne=0,nc=0;
  const rows=recs.map(r=>{
    const d=decisions[r.id];
    const st=stateOf(r);
    if(st!=="UNSCREENED"){n++;}
    if(st==="INCLUDE")ni++;else if(st==="EXCLUDE")ne++;else if(st==="CONFLICT")nc++;
    const rid=r.id.replace(/[^a-zA-Z0-9]/g,"_");
    const cls=st==="INCLUDE"?"inc":st==="EXCLUDE"?"exc":st==="CONFLICT"?"conf":"";
    const opts=['|— decision pending —',"INCLUDE|Include","EXCLUDE|Exclude","CONFLICT|Conflict / third review"];
    const sel=opts.map(o=>{const v=o.split("|");return `<option value="${v[0]}"${v[0]===st?" selected":""}>${v[1]}</option>`}).join("");
    const rsel=['|no reason'].concat(RULE_REASONS.map(x=>`${x}|${x}`)).map(o=>{const v=o.split("|");return `<option value="${v[0]}"${(d&&d.reason)===v[0]?" selected":""}>${v[1]}</option>`}).join("");
    const tags=((d&&d.tags)||[]).map(t=>`<span class="tag">${esc(t)}</span>`).join("");
    return `<article class="${cls}">
    <b>${esc(r.title)}</b>
    <div class="meta">${esc((r.authors||[]).slice(0,3).join("; ")).concat(r.authors&&r.authors.length>3?" …":"")} · ${r.year||"—"} · <i>${esc(r.venue||"")}</i> · ${esc(r.source||"")}${r.doi?" · "+esc(r.doi):""} · #${r._i+1}</div>
    <div class="abstract" id="abs_${rid}">${esc(r.abstract||"(no abstract)")}</div>
    <div class="ctl"><span class="state">${st}</span>
    <select onchange="setDec('${esc(r.id)}',this.value)">${sel}</select>
    <select onchange="setDec('${esc(r.id)}',undefined,this.value||'')" title="reason">${rsel}</select>
    <button onclick="addTag(event,'${esc(r.id)}')">+tag</button>${tags}
    <a href="#" style="font-size:12px;margin-left:auto" onclick="toggleAbs(event,'${r.id}');return false">abstract</a>
    </div></article>`;
  }).join("");
  document.getElementById("list").innerHTML="<h2>Records ("+recs.length+" shown)</h2>"+rows;
  document.getElementById("p_id").textContent=DATA.records.length;
  document.getElementById("p_s").textContent=n;
  document.getElementById("p_i").textContent=ni;
  document.getElementById("p_e").textContent=ne;
  document.getElementById("p_c").textContent=nc;
  const tot=DATA.records.length;
  document.getElementById("prog").value=tot?n/tot:0;
  document.getElementById("status").textContent=n+"/"+tot+" screened";
}
function download(name,text,type){const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click();URL.revokeObjectURL(a.href)}
function csvCell(s){s=String(s==null?"":s);return /[",\\n]/.test(s)?'"'+s.replace(/"/g,'""')+'"':s}
function exportCSV(){
  const byId={};DATA.records.forEach(r=>byId[r.id]=r);
  const rows=["record_id,reviewer,title,year,first_author,venue,doi,decision,reason"];
  for(const [id,d] of Object.entries(decisions)){
    if(!d.decision||d.decision==="UNSCREENED")continue;
    const r=byId[id]||{};
    rows.push([csvCell(id),csvCell(d.reviewer||""),csvCell(r.title||""),r.year||"",csvCell((r.authors&&r.authors[0])||""),csvCell(r.venue||""),csvCell(r.doi||""),csvCell(d.decision),csvCell([d.reason].concat(d.tags||[]).filter(Boolean).join("; "))].join(","));
  }
  download("decisions.csv",rows.join("\\n"),"text/csv");
}
function exportJSON(){download("decisions.json",JSON.stringify({dataset_id:DATA.dataset_id,decisions},null,2),"application/json")}
function clearAll(){if(confirm("Clear all local decisions for this dataset?")){localStorage.removeItem(KEY);decisions={};render()}}
["q","fstate","fsort","abs","reviewer"].forEach(id=>document.getElementById(id).addEventListener("input",render));
render();
</script>
</body>
</html>
"""


def build_dashboard(
    records: list[Record],
    out_path: Path,
    rules: Optional[dict] = None,
    dataset_id: str = "lithos",
    reviewer: str = "",
) -> Path:
    """Write a single self-contained offline HTML screening dashboard."""
    payload = {
        "dataset_id": dataset_id,
        "version": VERSION,
        "reviewer": reviewer,
        "rules": rules or {},
        "records": [
            {
                "id": r.id,
                "title": r.title,
                "authors": r.authors,
                "year": r.year,
                "venue": r.venue,
                "doi": r.doi,
                "abstract": r.abstract,
                "source": r.source,
                "keywords": r.keywords,
                "screen_state": (r.screen_state or ScreenState.UNSCREENED).value
                if not isinstance(r.screen_state, str)
                else r.screen_state,
            }
            for r in records
        ],
    }
    reason_terms = sorted({
        rule.get("description") or rule.get("pattern", "")
        for rule in (rules or {}).get("rules", [])
        if (rule.get("description") or rule.get("pattern", "")) and len(rule.get("pattern", "")) < 60
    })[:20]
    payload["rules"]["reasons"] = reason_terms

    json_payload = json.dumps(payload, ensure_ascii=True).replace("</", "<\\/")
    html = _TEMPLATE.replace("__VERSION__", VERSION).replace("__PAYLOAD__", json_payload)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    logger.info(f"Dashboard written: {out_path} ({len(html)} bytes, {len(records)} records)")
    return out_path
