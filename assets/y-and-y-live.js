(() => {
  "use strict";
  const BASE = "/data/";
  const path = (window.location.pathname || "/").toLowerCase();
  const endpointForPath = () => path.includes("/threshold") ? "threshold-live.json" : path.includes("/wwt") ? "wwt-live.json" : path.includes("/trfk") ? "trfk-live.json" : path.includes("/infrawatch") ? "infrawatch-live.json" : path.includes("/atlas") ? "atlas-live.json" : path.includes("/brief") ? "brief-live.json" : "worldwatch-live.json";
  const labelForPath = () => path.includes("/threshold") ? "THRESHOLD" : path.includes("/wwt") ? "WWT" : path.includes("/trfk") ? "TRFK" : path.includes("/infrawatch") ? "INFRAWATCH" : path.includes("/atlas") ? "ATLAS" : path.includes("/brief") ? "BRIEF" : path.includes("/worldwatch") ? "WORLDWATCH" : "Y&Y";
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined && text !== null) n.textContent = String(text); return n; };
  const formatTime = (v) => { if (!v) return "—"; const d = new Date(v); return Number.isNaN(d.getTime()) ? v : d.toLocaleString([], {year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"}); };
  const ageMinutes = (v) => { const d=new Date(v); if(Number.isNaN(d.getTime())) return null; return Math.max(0,Math.round((Date.now()-d.getTime())/60000)); };
  function addStyle(){
    if(document.getElementById("yy-live-style")) return;
    const s=document.createElement("style"); s.id="yy-live-style";
    s.textContent=`#yy-live-panel{position:fixed;right:14px;bottom:14px;z-index:2147483000;width:min(450px,calc(100vw - 28px));max-height:min(76vh,700px);overflow:auto;color:#f2f2f2;background:rgba(5,5,5,.98);border:1px solid #9d1010;box-shadow:0 0 24px rgba(140,0,0,.28);font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;font-size:12px;line-height:1.42}#yy-live-panel summary{cursor:pointer;list-style:none;padding:10px 12px;user-select:none;color:#ff3a3a;background:#0b0b0b;border-bottom:1px solid #431010;font-weight:800;letter-spacing:.08em}#yy-live-panel summary::-webkit-details-marker{display:none}#yy-live-panel .yy-body{padding:10px 12px 12px}#yy-live-panel .yy-row{display:flex;justify-content:space-between;gap:12px;padding:3px 0;border-bottom:1px dotted #262626}#yy-live-panel .yy-key{color:#a8a8a8}#yy-live-panel .yy-val{color:#f0f0f0;text-align:right}#yy-live-panel .yy-good{color:#69d769}#yy-live-panel .yy-warn{color:#ffb347}#yy-live-panel .yy-bad{color:#ff5656}#yy-live-panel .yy-head{margin:10px 0 6px;color:#ff3a3a;letter-spacing:.08em;font-weight:800}#yy-live-panel .yy-event{padding:8px 0;border-top:1px solid #222}#yy-live-panel .yy-event a{color:#f5f5f5;text-decoration:none}#yy-live-panel .yy-event a:hover{color:#ff5555;text-decoration:underline}#yy-live-panel .yy-meta{color:#888;font-size:11px;margin-top:2px}#yy-live-panel .yy-note{color:#8d8d8d;margin-top:8px;font-size:11px}#yy-live-panel .yy-score{font-size:25px;font-weight:900;color:#ff3a3a;line-height:1;padding:6px 0 2px}#yy-live-panel .yy-errors{color:#ff8b8b;margin-top:6px}#yy-live-panel .yy-corro{color:#69d769}#yy-live-panel .yy-pill{display:inline-block;border:1px solid #333;padding:1px 5px;margin-left:5px;font-size:10px;color:#aaa}#yy-live-panel .yy-stale{color:#ffb347}@media(max-width:650px){#yy-live-panel{right:8px;bottom:8px;width:calc(100vw - 16px);max-height:66vh}}@media print{#yy-live-panel{display:none!important}}`;
    document.head.appendChild(s);
  }
  function addRow(parent,key,value,valueClass){ const r=el("div","yy-row"); r.appendChild(el("span","yy-key",key)); r.appendChild(el("span","yy-val "+(valueClass||""),value)); parent.appendChild(r); }
  function renderEvents(parent,events){
    if(!Array.isArray(events)||events.length===0){ parent.appendChild(el("div","yy-note","No qualifying live-source events in this window.")); return; }
    parent.appendChild(el("div","yy-head","LATEST AUTONOMOUS SIGNALS"));
    events.slice(0,7).forEach(event=>{
      const box=el("div","yy-event"); const a=el("a","",event.title||"Untitled event"); a.href=event.url||"#"; a.target="_blank"; a.rel="noopener noreferrer"; box.appendChild(a);
      const sev=event.effective_severity!==undefined?event.effective_severity:event.severity;
      const meta=[event.source,event.domain,event.region,sev!==undefined?`S${sev}`:null,event.published?formatTime(event.published):null].filter(Boolean).join(" // "); box.appendChild(el("div","yy-meta",meta));
      if((event.corroboration_count||1)>1){ const c=el("div","yy-meta yy-corro",`CORROBORATED // ${event.corroboration_count} independent feeds`); box.appendChild(c); }
      parent.appendChild(box);
    });
  }
  const getEvents=(data)=>Array.isArray(data?.events)?data.events:Array.isArray(data?.top_events)?data.top_events:[];
  async function boot(){
    addStyle(); const panel=document.createElement("details"); panel.id="yy-live-panel"; panel.open=window.innerWidth>=980; panel.appendChild(el("summary","",`${labelForPath()} // AUTONOMOUS LIVE`)); const body=el("div","yy-body"); body.appendChild(el("div","yy-note","Connecting to autonomous data layer…")); panel.appendChild(body); document.body.appendChild(panel);
    try{
      const [sr,dr]=await Promise.all([fetch(BASE+"autonomy-status.json",{cache:"no-store"}),fetch(BASE+endpointForPath(),{cache:"no-store"})]); if(!sr.ok) throw new Error(`status ${sr.status}`); if(!dr.ok) throw new Error(`data ${dr.status}`); const [status,data]=await Promise.all([sr.json(),dr.json()]); body.replaceChildren();
      const health=Number(status.source_health_percent ?? Math.round((status.sources_ok/status.sources_total)*100)); const healthClass=health>=80?"yy-good":health>=50?"yy-warn":"yy-bad"; const modeClass=status.mode==="AUTONOMOUS"?"yy-good":status.mode==="DEGRADED"?"yy-warn":"yy-bad"; const mins=ageMinutes(status.last_poll); const freshnessClass=mins!==null&&mins>90?"yy-stale":"";
      addRow(body,"ENGINE",`${status.mode||"AUTONOMOUS"} / v${status.version||1}`,modeClass); addRow(body,"LAST POLL",`${formatTime(status.last_poll)}${mins!==null?` (${mins}m ago)`:""}`,freshnessClass); addRow(body,"SOURCE HEALTH",`${health}% // ${status.sources_ok}/${status.sources_total}`,healthClass); addRow(body,"NEW THIS POLL",status.new_events??0); addRow(body,"STRATEGIC LIVE",status.strategic_live_events??status.live_events??0); addRow(body,"CORROBORATED",status.corroborated_live_events??0); addRow(body,"CHATGPT DEP.",status.chatgpt_dependency?"YES":"NO",status.chatgpt_dependency?"yy-bad":"yy-good");
      if(typeof data.score==="number"){ body.appendChild(el("div","yy-head","MACHINE SIGNAL")); body.appendChild(el("div","yy-score",String(data.score))); if(data.band) body.appendChild(el("div","yy-meta",data.band)); if(data.formula) body.appendChild(el("div","yy-meta",data.formula)); if(data.method) body.appendChild(el("div","yy-note",data.method)); }
      renderEvents(body,getEvents(data)); const failures=Array.isArray(status.source_status)?status.source_status.filter(s=>!s.ok):[]; if(failures.length){ const errors=el("div","yy-errors"); errors.appendChild(el("div","yy-head","SOURCE WARNINGS")); failures.slice(0,5).forEach(s=>errors.appendChild(el("div","",`${s.name}: offline // streak ${s.consecutive_failures||1}`))); body.appendChild(errors); }
      body.appendChild(el("div","yy-note",data.disclaimer||data.note||"Machine-generated public-source layer. Curated Y&Y records remain preserved."));
    }catch(err){ body.replaceChildren(); body.appendChild(el("div","yy-bad","AUTONOMOUS DATA UNAVAILABLE")); body.appendChild(el("div","yy-note",String(err))); }
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded",boot,{once:true}); else boot();
})();
