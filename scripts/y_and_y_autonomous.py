#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import email.utils
import hashlib
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
USER_AGENT = "YY-Autonomous-OSINT/1.0 (+https://triadconstruct-boop.github.io/)"
TIMEOUT = 25
MAX_EVENTS = 500
FRESH_HOURS = 168
LIVE_WINDOW_HOURS = 120

RSS_SOURCES = [
    {"id":"un_news","name":"UN News","url":"https://news.un.org/feed/subscribe/en/news/all/rss.xml","tier":"institutional","default_domain":"GLOBAL"},
    {"id":"nato_news","name":"NATO News","url":"https://www.nato.int/cps/en/natohq/rss/news.xml","tier":"primary","default_domain":"WAR"},
    {"id":"iaea_topnews","name":"IAEA","url":"https://www.iaea.org/feeds/topnews","tier":"primary","default_domain":"NUCLEAR"},
    {"id":"doj_nsd","name":"U.S. DOJ National Security Division","url":"https://www.justice.gov/news/rss?field_component=361&field_topic%5B0%5D=25321&field_topic%5B1%5D=44971&field_topic%5B2%5D=44956&field_topic%5B3%5D=7881&field_topic%5B4%5D=44951&field_topic%5B5%5D=45186&require_all=0&search_api_language=en&show_public_archived=0&type%5B0%5D=press_release&type%5B1%5D=speech&type%5B2%5D=youtube_video","tier":"primary","default_domain":"SECURITY"},
]
JSON_SOURCES = [
    {"id":"cisa_kev","name":"CISA Known Exploited Vulnerabilities","url":"https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json","tier":"primary","kind":"cisa_kev","default_domain":"CYBER"}
]
PAGES = ["index.html","worldwatch/index.html","atlas/index.html","infrawatch/index.html","brief/index.html","threshold/index.html","wwt/index.html","trfk/index.html"]

DOMAIN_RULES = [
    ("TRAFFICKING",("human trafficking","sex trafficking","labor trafficking","forced labor","trafficking network","trafficked","modern slavery","exploitation ring")),
    ("NUCLEAR",("nuclear","uranium","plutonium","reactor","atomic energy","iaea","enrichment","radiological")),
    ("CYBER",("cyber","malware","ransomware","vulnerability","zero-day","zero day","hacker","hackers","state-sponsored","critical infrastructure","botnet","ddos","exploit")),
    ("INFRA",("power grid","electric grid","pipeline","railway","railroad","port","subsea cable","undersea cable","telecommunications","water system","energy infrastructure","airport","bridge","dam","refinery")),
    ("TERRORISM",("terror","terrorist","isis","isil","al-qaeda","hamas","hezbollah","extremist","bomb plot","attack plot")),
    ("WAR",("war","military","missile","airstrike","air strike","drone strike","troops","armed forces","invasion","ceasefire","cease-fire","mobilization","mobilisation","naval","artillery","combat","strike on","defence","defense")),
    ("BIO",("biosecurity","biological","pathogen","outbreak","laboratory safety","biosafety","gain of function","pandemic")),
    ("SPACE",("satellite","space security","anti-satellite","asat","orbital")),
    ("ECONOMIC",("sanction","sanctions","export control","tariff","shipping disruption","supply chain","oil price","gas price","financial restrictions")),
    ("POLITICAL",("coup","election","government collapse","state of emergency","martial law","constitutional crisis","protest","unrest")),
]
HIGH_IMPACT = ("nuclear","ballistic missile","intercontinental","airstrike","invasion","mobilization","state-sponsored","critical infrastructure","terror plot","terrorist attack","power grid","subsea cable","undersea cable","chemical weapon","biological weapon","military clash","direct clash")
MEDIUM_IMPACT = ("sanctions","cyber","ransomware","drone","missile","troops","naval","ceasefire","proxy","export control","trafficking network","smuggling","exploit","vulnerability")
US_TERMS = ("united states","u.s."," us ","american","america","washington","new york","california","texas","florida","pentagon","homeland")
REGION_RULES = [
    ("IRAN",("iran","tehran","persian gulf","hormuz"),(32.4279,53.6880)),
    ("ISRAEL",("israel","gaza","jerusalem","tel aviv"),(31.0461,34.8516)),
    ("UKRAINE",("ukraine","kyiv","odesa","kharkiv"),(48.3794,31.1656)),
    ("RUSSIA",("russia","moscow","kremlin"),(61.5240,105.3188)),
    ("CHINA",("china","beijing","prc"),(35.8617,104.1954)),
    ("TAIWAN",("taiwan","taipei"),(23.6978,120.9605)),
    ("KOREAN PENINSULA",("north korea","south korea","pyongyang","seoul"),(37.5,127.5)),
    ("UNITED STATES",("united states","u.s.","american","america"),(39.8283,-98.5795)),
    ("EUROPE",("europe","european union","eu ","nato"),(54.5260,15.2551)),
    ("MIDDLE EAST",("middle east","iraq","syria","lebanon","jordan","yemen"),(29.2985,42.5510)),
    ("AFRICA",("africa","sahel","sudan","somalia","congo"),(1.6508,17.6791)),
    ("INDO-PACIFIC",("indo-pacific","south china sea","philippines","japan"),(15.0,125.0)),
]
WWT_VECTOR_RULES = {
    "great_power_direct_clash":("direct clash","u.s. forces","american forces","russian forces","chinese forces","military confrontation","airstrike","naval clash"),
    "alliance_entanglement":("nato","article 5","alliance","collective defense","collective defence","mutual defense treaty","mutual defence treaty"),
    "multi_theater_coupling":("second front","multiple fronts","multi-theater","multi theatre","simultaneously","regional escalation"),
    "nuclear_escalation":("nuclear","strategic forces","nuclear-capable","nuclear capable","enrichment","atomic"),
    "military_mobilization":("mobilization","mobilisation","troop deployment","reservists","military buildup","military build-up","carrier strike group"),
    "economic_warfare":("sanctions","export controls","blockade","embargo","economic warfare","shipping disruption","energy cutoff"),
    "crisis_control_failure":("talks collapse","ceasefire collapse","cease-fire collapse","diplomatic breakdown","walked out","suspended talks"),
    "hybrid_preparation":("state-sponsored","critical infrastructure","sabotage","cyberattack","cyber attack","disinformation","undersea cable","subsea cable"),
}

def utcnow(): return dt.datetime.now(dt.timezone.utc)
def iso_z(v): return v.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def clean(v):
    if not v: return ""
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",v))).strip()
def parse_iso(v):
    try:
        d=dt.datetime.fromisoformat(v.replace("Z","+00:00")); return (d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)).astimezone(dt.timezone.utc)
    except Exception: return dt.datetime(1970,1,1,tzinfo=dt.timezone.utc)
def parse_date(raw):
    if not raw: return iso_z(utcnow())
    for f in (lambda x: email.utils.parsedate_to_datetime(x), lambda x: dt.datetime.fromisoformat(x.replace("Z","+00:00"))):
        try:
            d=f(raw.strip()); d=d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc); return iso_z(d)
        except Exception: pass
    return iso_z(utcnow())
def fetch_bytes(url):
    req=urllib.request.Request(url,headers={"User-Agent":USER_AGENT,"Accept":"application/rss+xml, application/atom+xml, application/json, text/xml, */*"})
    with urllib.request.urlopen(req,timeout=TIMEOUT) as r: return r.read()
def node_text(node,names):
    wanted=set(names)
    for c in node.iter():
        if c.tag.rsplit("}",1)[-1].lower() in wanted and c.text: return c.text.strip()
    return ""
def parse_feed(src,payload):
    root=ET.fromstring(payload); out=[]
    items=[e for e in root.iter() if e.tag.rsplit("}",1)[-1].lower() in ("item","entry")]
    for item in items[:80]:
        title=clean(node_text(item,("title",))); summary=clean(node_text(item,("description","summary","content"))); link=""
        for c in item.iter():
            if c.tag.rsplit("}",1)[-1].lower()=="link":
                link=(c.attrib.get("href") or (c.text or "")).strip()
                if link: break
        if title and link:
            out.append({"title":title,"summary":summary[:800],"url":link,"published":parse_date(node_text(item,("pubdate","published","updated","date"))),"source_id":src["id"],"source":src["name"],"source_tier":src["tier"],"default_domain":src["default_domain"]})
    return out
def parse_json_source(src,payload):
    doc=json.loads(payload.decode("utf-8",errors="replace")); out=[]
    if src.get("kind")!="cisa_kev": return out
    for v in doc.get("vulnerabilities",[])[:120]:
        cve=v.get("cveID","")
        if not cve: continue
        added=v.get("dateAdded")
        out.append({"title":f"{cve} — {v.get('vendorProject','')} {v.get('product','')}".strip(),"summary":clean(v.get("shortDescription",""))[:800],"url":f"https://www.cisa.gov/known-exploited-vulnerabilities-catalog?search_api_fulltext={urllib.parse.quote(cve)}","published":parse_date(f"{added}T00:00:00+00:00" if added else None),"source_id":src["id"],"source":src["name"],"source_tier":src["tier"],"default_domain":src["default_domain"]})
    return out
def classify(text,default):
    low=f" {text.lower()} "; hits=[]; tags=[]
    for domain,terms in DOMAIN_RULES:
        n=sum(1 for t in terms if t in low)
        if n: hits.append((domain,n)); tags.append(domain)
    if not hits: return default,[default]
    hits.sort(key=lambda x:x[1],reverse=True); return hits[0][0],tags
def locate(text):
    low=f" {text.lower()} "
    for region,terms,coords in REGION_RULES:
        if any(t in low for t in terms): return region,coords[0],coords[1]
    return "GLOBAL",None,None
def severity(text,tier,domain):
    low=f" {text.lower()} "; score=22+9*sum(1 for t in HIGH_IMPACT if t in low)+4*sum(1 for t in MEDIUM_IMPACT if t in low)
    score += 8 if tier=="primary" else 5 if tier=="institutional" else 0
    score += 8 if domain in ("WAR","NUCLEAR","TERRORISM") else 4 if domain in ("CYBER","INFRA","TRAFFICKING") else 0
    return max(0,min(100,score))
def enrich(item):
    text=f"{item.get('title','')} {item.get('summary','')}"; domain,tags=classify(text,item.get("default_domain","GLOBAL")); region,lat,lon=locate(text); low=f" {text.lower()} "
    eid=hashlib.sha256(f"{item.get('source_id','')}|{item.get('url','')}|{item.get('title','')}".encode()).hexdigest()[:20]
    return {"id":eid,"published":item["published"],"source":item["source"],"source_id":item["source_id"],"source_tier":item["source_tier"],"title":item["title"],"summary":item.get("summary",""),"url":item["url"],"domain":domain,"tags":sorted(set(tags)),"region":region,"lat":lat,"lon":lon,"severity":severity(text,item.get("source_tier","institutional"),domain),"us_relevance":any(t in low for t in US_TERMS),"machine_generated":True}
def load_json(path,default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default
def write_json(path,obj): path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
def recent(events,hours):
    cutoff=utcnow()-dt.timedelta(hours=hours); return [e for e in events if parse_iso(e.get("published",""))>=cutoff]
def threshold_signal(events):
    rel=[e for e in recent(events,96) if e.get("us_relevance") and e.get("domain") in ("WAR","TERRORISM","CYBER","INFRA","BIO","NUCLEAR","SECURITY")]
    score=max(0,min(100,round(sum(max(0,e.get("severity",0)-45) for e in rel[:30])/7)))
    band="ELEVATED SIGNAL" if score>=70 else "WATCH SIGNAL" if score>=40 else "BASELINE SIGNAL"
    return {"generated_at":iso_z(utcnow()),"score":score,"band":band,"basis_event_count":len(rel),"disclaimer":"Machine-generated public-source signal only. It is not a calibrated probability forecast and does not replace the curated THRESHOLD assessment.","top_events":sorted(rel,key=lambda e:(e.get("severity",0),e.get("published","")),reverse=True)[:12]}
def vector_value(events,terms):
    total=0
    for e in recent(events,120):
        text=f" {e.get('title','')} {e.get('summary','')} ".lower(); m=sum(1 for t in terms if t in text)
        if m: total+=min(18,5+m*4+max(0,e.get("severity",0)-55)//8)
    return max(0,min(100,total))
def wwt_signal(events):
    vectors={name:vector_value(events,terms) for name,terms in WWT_VECTOR_RULES.items()}; vals=list(vectors.values()); highest=max(vals) if vals else 0; avg=round(sum(vals)/len(vals)) if vals else 0
    systemic=[e for e in recent(events,120) if e.get("severity",0)>=65 and e.get("domain") in ("WAR","NUCLEAR","CYBER","INFRA","ECONOMIC")]; pressure=min(100,len(systemic)*7); score=round(highest*.40+avg*.35+pressure*.25)
    return {"generated_at":iso_z(utcnow()),"score":score,"formula":"40% highest vector + 35% vector average + 25% systemic pressure","highest_vector":highest,"vector_average":avg,"systemic_pressure":pressure,"vectors":vectors,"basis_event_count":len(systemic),"disclaimer":"Machine-generated public-source pressure signal only. It is not a statistically calibrated forecast of world war and does not replace the curated WWT assessment.","top_events":sorted(systemic,key=lambda e:(e.get("severity",0),e.get("published","")),reverse=True)[:12]}
def brief_signal(events):
    live=sorted(recent(events,72),key=lambda e:(e.get("severity",0),e.get("published","")),reverse=True); domains={}
    for e in live: domains[e.get("domain","GLOBAL")]=domains.get(e.get("domain","GLOBAL"),0)+1
    return {"generated_at":iso_z(utcnow()),"headline_count":len(live),"domain_counts":dict(sorted(domains.items(),key=lambda kv:kv[1],reverse=True)),"top_events":live[:16],"note":"Autonomous machine-generated public-source brief; curated Y&Y analysis remains separate."}
def inject_panel():
    changed=[]; tag='<script src="/assets/y-and-y-live.js" defer></script>'
    for rel in PAGES:
        p=ROOT/rel
        if not p.exists(): continue
        text=p.read_text(encoding="utf-8")
        if "/assets/y-and-y-live.js" in text: continue
        text=text.replace("</body>",f"  {tag}\n</body>",1) if "</body>" in text else text+f"\n{tag}\n"
        p.write_text(text,encoding="utf-8"); changed.append(rel)
    return changed

def main():
    now=utcnow(); previous=load_json(DATA/"live-events.json",{"events":[]}); old=previous.get("events",[]) if isinstance(previous,dict) else []; by_id={e.get("id"):e for e in old if e.get("id")}; status=[]; fetched=[]
    for src in RSS_SOURCES:
        try:
            items=parse_feed(src,fetch_bytes(src["url"])); fetched.extend(items); status.append({"id":src["id"],"name":src["name"],"ok":True,"items":len(items),"error":None})
        except Exception as exc: status.append({"id":src["id"],"name":src["name"],"ok":False,"items":0,"error":f"{type(exc).__name__}: {exc}"[:260]})
    for src in JSON_SOURCES:
        try:
            items=parse_json_source(src,fetch_bytes(src["url"])); fetched.extend(items); status.append({"id":src["id"],"name":src["name"],"ok":True,"items":len(items),"error":None})
        except Exception as exc: status.append({"id":src["id"],"name":src["name"],"ok":False,"items":0,"error":f"{type(exc).__name__}: {exc}"[:260]})
    cutoff=now-dt.timedelta(hours=FRESH_HOURS); new_count=0
    for item in fetched:
        e=enrich(item)
        if parse_iso(e["published"])<cutoff: continue
        if e["id"] not in by_id: new_count+=1
        by_id[e["id"]]=e
    events=sorted(by_id.values(),key=lambda e:parse_iso(e.get("published","")),reverse=True)[:MAX_EVENTS]; live=recent(events,LIVE_WINDOW_HOURS); world=sorted(live,key=lambda e:(e.get("severity",0),e.get("published","")),reverse=True)
    atlas=[e for e in world if e.get("lat") is not None and e.get("lon") is not None]; infra=[e for e in world if e.get("domain") in ("INFRA","CYBER","ECONOMIC")]; trfk=[e for e in world if e.get("domain")=="TRAFFICKING"]
    ok=sum(1 for s in status if s["ok"]); injected=inject_panel()
    state={"engine":"Y&Y Autonomous Core","version":1,"last_poll":iso_z(now),"sources_total":len(status),"sources_ok":ok,"sources_failed":len(status)-ok,"source_status":status,"fetched_items":len(fetched),"new_events":new_count,"live_events":len(live),"archive_events":len(events),"mode":"AUTONOMOUS","chatgpt_dependency":False,"pages_injected_this_run":injected,"notes":["Machine-generated live signals are kept separate from curated strategic assessments.","Source failures are isolated; successful sources continue updating the system."]}
    write_json(DATA/"live-events.json",{"generated_at":iso_z(now),"events":events}); write_json(DATA/"autonomy-status.json",state); write_json(DATA/"worldwatch-live.json",{"generated_at":iso_z(now),"events":world[:120]}); write_json(DATA/"atlas-live.json",{"generated_at":iso_z(now),"events":atlas[:120]}); write_json(DATA/"infrawatch-live.json",{"generated_at":iso_z(now),"events":infra[:120]}); write_json(DATA/"trfk-live.json",{"generated_at":iso_z(now),"events":trfk[:120]}); write_json(DATA/"threshold-live.json",threshold_signal(events)); write_json(DATA/"wwt-live.json",wwt_signal(events)); write_json(DATA/"brief-live.json",brief_signal(events))
    print(f"Y&Y poll: sources {ok}/{len(status)}; fetched {len(fetched)}; new {new_count}; live {len(live)}; injected {len(injected)}")
    for s in status:
        if not s["ok"]: print(f"WARN {s['name']}: {s['error']}",file=sys.stderr)
    return 0

if __name__=="__main__": raise SystemExit(main())
