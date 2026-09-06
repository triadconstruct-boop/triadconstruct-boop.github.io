#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import email.utils
import hashlib
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
USER_AGENT = "YY-Autonomous-OSINT/2.1 (+https://triadconstruct-boop.github.io/)"
TIMEOUT = 25
MAX_EVENTS = 700
FRESH_HOURS = 240
LIVE_WINDOW_HOURS = 120
CORROBORATION_HOURS = 48
FUTURE_TOLERANCE_HOURS = 2

RSS_SOURCES = [
    {"id":"iaea_topnews","name":"IAEA","url":"https://www.iaea.org/feeds/topnews","tier":"primary","default_domain":"NUCLEAR","weight":1.00},
    {"id":"doj_nsd","name":"U.S. DOJ National Security Division","url":"https://www.justice.gov/news/rss?field_component=361&field_topic%5B0%5D=25321&field_topic%5B1%5D=44971&field_topic%5B2%5D=44956&field_topic%5B3%5D=7881&field_topic%5B4%5D=44951&field_topic%5B5%5D=45186&require_all=0&search_api_language=en&show_public_archived=0&type%5B0%5D=press_release&type%5B1%5D=speech&type%5B2%5D=youtube_video","tier":"primary","default_domain":"SECURITY","weight":1.00},
    {"id":"fbi_national","name":"FBI National Press Releases","url":"https://www.fbi.gov/feeds/national-press-releases/rss.xml","tier":"primary","default_domain":"SECURITY","weight":1.00},
    {"id":"nist_cyber","name":"NIST Cybersecurity","url":"https://www.nist.gov/news-events/cybersecurity/rss.xml","tier":"primary","default_domain":"CYBER","weight":0.90},
    {"id":"noaa_news","name":"NOAA","url":"https://www.noaa.gov/rss.xml","tier":"primary","default_domain":"CLIMATE","weight":0.85},
    {"id":"whitehouse_actions","name":"White House Presidential Actions","url":"https://www.whitehouse.gov/presidential-actions/feed/","tier":"primary","default_domain":"POLITICAL","weight":0.95},
    {"id":"noaa_spc","name":"NOAA Storm Prediction Center","url":"https://www.spc.noaa.gov/products/spcrss.xml","tier":"primary","default_domain":"CLIMATE","weight":0.85},
]
JSON_SOURCES = [
    {"id":"cisa_kev","name":"CISA Known Exploited Vulnerabilities","url":"https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json","tier":"primary","kind":"cisa_kev","default_domain":"CYBER","weight":1.00},
    {"id":"usgs_significant","name":"USGS Significant Earthquakes","url":"https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.geojson","tier":"primary","kind":"usgs_quakes","default_domain":"CLIMATE","weight":0.90},
    {"id":"federal_register","name":"U.S. Federal Register","url":"https://www.federalregister.gov/api/v1/documents.json?per_page=100&order=newest","tier":"primary","kind":"federal_register","default_domain":"POLITICAL","weight":0.70},
]
ALL_SOURCES = RSS_SOURCES + JSON_SOURCES
PAGES = ["index.html","worldwatch/index.html","atlas/index.html","infrawatch/index.html","brief/index.html","threshold/index.html","wwt/index.html","trfk/index.html"]

DOMAIN_RULES = [
    ("TRAFFICKING",("human trafficking","sex trafficking","labor trafficking","labour trafficking","forced labor","forced labour","trafficking network","trafficked","modern slavery","exploitation ring")),
    ("NUCLEAR",("nuclear","uranium","plutonium","reactor","atomic energy","iaea","enrichment","radiological","strategic forces")),
    ("CYBER",("cyber","malware","ransomware","vulnerability","zero-day","zero day","hacker","hackers","state-sponsored","critical infrastructure","botnet","ddos","exploit")),
    ("INFRA",("power grid","electric grid","pipeline","railway","railroad","port","subsea cable","undersea cable","telecommunications","water system","energy infrastructure","airport","bridge","dam","refinery","satellite outage")),
    ("TERRORISM",("terror","terrorist","isis","isil","al-qaeda","al qaeda","hamas","hezbollah","extremist","bomb plot","attack plot")),
    ("WAR",("war","military","missile","airstrike","air strike","drone strike","troops","armed forces","invasion","ceasefire","cease-fire","mobilization","mobilisation","naval","artillery","combat","strike on","defence","defense")),
    ("BIO",("biosecurity","biological","pathogen","outbreak","laboratory safety","biosafety","gain of function","pandemic","public health emergency")),
    ("SPACE",("satellite","space security","anti-satellite","asat","orbital","space force")),
    ("ECONOMIC",("sanction","sanctions","export control","tariff","shipping disruption","supply chain","oil price","gas price","financial restrictions","embargo")),
    ("CLIMATE",("earthquake","tsunami","hurricane","tropical storm","tornado","wildfire","flood","extreme weather","storm surge","severe thunderstorm")),
    ("POLITICAL",("coup","election","government collapse","state of emergency","martial law","constitutional crisis","protest","unrest","executive order","presidential action")),
]
STRATEGIC_DOMAINS = {"WAR","NUCLEAR","TERRORISM","CYBER","INFRA","BIO","SPACE","ECONOMIC","POLITICAL","TRAFFICKING","CLIMATE","SECURITY"}
HIGH_IMPACT = ("nuclear","ballistic missile","intercontinental","airstrike","invasion","mobilization","state-sponsored","critical infrastructure","terror plot","terrorist attack","power grid","subsea cable","undersea cable","chemical weapon","biological weapon","military clash","direct clash","state of emergency","major earthquake","tsunami warning")
MEDIUM_IMPACT = ("sanctions","cyber","ransomware","drone","missile","troops","naval","ceasefire","proxy","export control","trafficking network","smuggling","exploit","vulnerability","earthquake","hurricane","tornado","wildfire")
US_TERMS = ("united states","u.s."," u.s ","american","america","washington","new york","california","texas","florida","pentagon","homeland","fbi","cisa")
HOMELAND_PATHWAY_TERMS = ("homeland","inside the united states","in the united states","against americans","u.s. infrastructure","american infrastructure","u.s. grid","u.s. soil","domestic terrorism","attack plot","bomb plot","critical infrastructure","ransomware","state-sponsored","biological threat")
FEDERAL_REGISTER_INTEREST = ("department of defense","department of homeland security","department of state","nuclear regulatory commission","department of energy","department of the treasury","cybersecurity","critical infrastructure","sanction","export control","national security","military","terror","biological","biosecurity","trafficking","maritime security","emergency","foreign assets","intelligence")
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
STOPWORDS = {"the","and","for","with","from","into","over","under","after","before","that","this","their","about","against","amid","says","new","update","press","release","department","national","united","states"}


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
def fetch_bytes(url,retries=2):
    last=None
    for attempt in range(retries+1):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":USER_AGENT,"Accept":"application/rss+xml, application/atom+xml, application/json, application/geo+json, text/xml, */*"})
            with urllib.request.urlopen(req,timeout=TIMEOUT) as r: return r.read()
        except Exception as exc:
            last=exc
            if attempt<retries: time.sleep(1.2*(attempt+1))
    raise last
def node_text(node,names):
    wanted=set(names)
    for c in node.iter():
        if c.tag.rsplit("}",1)[-1].lower() in wanted and c.text: return c.text.strip()
    return ""
def source_item(src,title,summary,url,published,**extra):
    out={"title":clean(title),"summary":clean(summary)[:900],"url":url,"published":published,"source_id":src["id"],"source":src["name"],"source_tier":src["tier"],"source_weight":src.get("weight",0.8),"default_domain":src["default_domain"]}
    out.update(extra); return out

def parse_feed(src,payload):
    payload=payload.lstrip(b"\xef\xbb\xbf\x00\t\r\n ")
    root=ET.fromstring(payload); out=[]
    items=[e for e in root.iter() if e.tag.rsplit("}",1)[-1].lower() in ("item","entry")]
    for item in items[:100]:
        title=clean(node_text(item,("title",))); summary=clean(node_text(item,("description","summary","content","encoded"))); link=""
        for c in item.iter():
            if c.tag.rsplit("}",1)[-1].lower()=="link":
                candidate=(c.attrib.get("href") or (c.text or "")).strip()
                if candidate and (not c.attrib.get("rel") or c.attrib.get("rel") in ("alternate","self")):
                    link=candidate
                    if c.attrib.get("rel")!="self": break
        if title and link:
            raw_date=node_text(item,("pubdate","published","updated","date"))
            out.append(source_item(src,title,summary,link,parse_date(raw_date),published_inferred=not bool(raw_date)))
    return out

def parse_json_source(src,payload):
    doc=json.loads(payload.decode("utf-8",errors="replace")); out=[]; kind=src.get("kind")
    if kind=="cisa_kev":
        for v in doc.get("vulnerabilities",[])[:160]:
            cve=v.get("cveID","")
            if not cve: continue
            added=v.get("dateAdded")
            out.append(source_item(src,f"{cve} — {v.get('vendorProject','')} {v.get('product','')}",v.get("shortDescription",""),f"https://www.cisa.gov/known-exploited-vulnerabilities-catalog?search_api_fulltext={urllib.parse.quote(cve)}",parse_date(f"{added}T00:00:00+00:00" if added else None),published_inferred=not bool(added)))
    elif kind=="usgs_quakes":
        for f in doc.get("features",[])[:80]:
            p=f.get("properties") or {}; g=f.get("geometry") or {}; coords=g.get("coordinates") or []
            when=p.get("time"); inferred=not isinstance(when,(int,float)); published=iso_z(dt.datetime.fromtimestamp(when/1000,dt.timezone.utc)) if not inferred else iso_z(utcnow())
            summary=f"Magnitude {p.get('mag')} earthquake. Alert={p.get('alert') or 'none'}; significance={p.get('sig')}; tsunami={p.get('tsunami',0)}."
            out.append(source_item(src,p.get("title") or f"USGS earthquake {f.get('id','')}",summary,p.get("url") or src["url"],published,published_inferred=inferred,lat=(coords[1] if len(coords)>1 else None),lon=(coords[0] if len(coords)>1 else None),usgs_significance=p.get("sig") or 0,tsunami=bool(p.get("tsunami"))))
    elif kind=="federal_register":
        for r in doc.get("results",[])[:100]:
            title=r.get("title") or "Federal Register document"; agencies=", ".join(a.get("name","") for a in (r.get("agencies") or []) if a.get("name")); abstract=r.get("abstract") or ""
            interest=f"{title} {agencies} {abstract}".lower()
            if not any(term in interest for term in FEDERAL_REGISTER_INTEREST): continue
            pub=r.get("publication_date"); summary=f"{agencies}. {abstract}".strip(); published=parse_date(f"{pub}T00:00:00+00:00" if pub else None)
            out.append(source_item(src,title,summary,r.get("html_url") or r.get("raw_text_url") or src["url"],published,published_inferred=not bool(pub)))
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

def severity(text,tier,domain,source_weight=0.8,extra=None):
    low=f" {text.lower()} "; score=18+9*sum(1 for t in HIGH_IMPACT if t in low)+4*sum(1 for t in MEDIUM_IMPACT if t in low)
    score += 10 if tier=="primary" else 6 if tier=="institutional" else 0
    score += round(source_weight*5)
    score += 9 if domain in ("WAR","NUCLEAR","TERRORISM") else 5 if domain in ("CYBER","INFRA","TRAFFICKING","BIO") else 2 if domain in ("CLIMATE","ECONOMIC","POLITICAL") else 0
    if extra:
        sig=extra.get("usgs_significance",0) or 0
        if sig>=1000: score+=18
        elif sig>=600: score+=12
        elif sig>=400: score+=7
        if extra.get("tsunami"): score+=8
    return max(0,min(100,score))

def enrich(item):
    text=f"{item.get('title','')} {item.get('summary','')}"; domain,tags=classify(text,item.get("default_domain","GLOBAL")); region,lat,lon=locate(text)
    if item.get("lat") is not None and item.get("lon") is not None: lat,lon=item["lat"],item["lon"]
    low=f" {text.lower()} "; eid=hashlib.sha256(f"{item.get('source_id','')}|{item.get('url','')}|{item.get('title','')}".encode()).hexdigest()[:20]
    sev=severity(text,item.get("source_tier","institutional"),domain,item.get("source_weight",0.8),item)
    us_rel=any(t in low for t in US_TERMS); pathway=us_rel and (any(t in low for t in HOMELAND_PATHWAY_TERMS) or domain in ("TERRORISM","INFRA","BIO"))
    if region=="GLOBAL" and us_rel: region="UNITED STATES"
    seen=iso_z(utcnow())
    return {"id":eid,"published":item["published"],"published_inferred":bool(item.get("published_inferred")),"first_seen":seen,"last_seen":seen,"source":item["source"],"source_id":item["source_id"],"source_tier":item["source_tier"],"source_weight":item.get("source_weight",0.8),"title":item["title"],"summary":item.get("summary",""),"url":item["url"],"domain":domain,"tags":sorted(set(tags)),"region":region,"lat":lat,"lon":lon,"severity":sev,"effective_severity":sev,"us_relevance":us_rel,"homeland_pathway":pathway,"corroborated_by":[],"corroboration_count":1,"machine_generated":True}

def load_json(path,default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default

def write_json(path,obj): path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
def recent(events,hours):
    now=utcnow(); cutoff=now-dt.timedelta(hours=hours); ceiling=now+dt.timedelta(hours=FUTURE_TOLERANCE_HOURS)
    return [e for e in events if cutoff<=parse_iso(e.get("published",""))<=ceiling]
def title_tokens(e):
    return {w for w in re.findall(r"[a-z0-9]{4,}",(e.get("title") or "").lower()) if w not in STOPWORDS}
def corroborate(events):
    pool=recent(events,CORROBORATION_HOURS)
    for i,e in enumerate(pool):
        a=title_tokens(e); matches=[]
        if len(a)<3: continue
        for j,o in enumerate(pool):
            if i==j or e.get("source_id")==o.get("source_id"): continue
            if e.get("domain")!=o.get("domain"): continue
            if e.get("region") not in (o.get("region"),"GLOBAL") and o.get("region")!="GLOBAL": continue
            b=title_tokens(o)
            if len(b)<3: continue
            inter=len(a&b); union=max(1,len(a|b)); sim=inter/union
            if inter>=4 or sim>=0.42: matches.append(o.get("source"))
        uniq=sorted(set(x for x in matches if x))
        e["corroborated_by"]=uniq; e["corroboration_count"]=1+len(uniq); e["effective_severity"]=min(100,e.get("severity",0)+min(12,len(uniq)*4))
    by_id={e.get("id"):e for e in pool}
    for e in events:
        if e.get("id") in by_id: e.update({k:by_id[e["id"]][k] for k in ("corroborated_by","corroboration_count","effective_severity")})
    return events

def threshold_signal(events):
    rel=[e for e in recent(events,96) if e.get("homeland_pathway") and e.get("domain") in ("WAR","TERRORISM","CYBER","INFRA","BIO","NUCLEAR","SECURITY") and e.get("effective_severity",0)>=45]
    rel=sorted(rel,key=lambda e:(e.get("effective_severity",0),e.get("corroboration_count",1),e.get("published","")),reverse=True)
    contributions=[]
    for e in rel[:12]:
        base=max(0,e.get("effective_severity",0)-40); confidence=1.0 if e.get("source_tier")=="primary" else .8; contributions.append(base*confidence)
    score=min(100,round(sum(contributions[:6])/3.6)) if contributions else 0
    band="HIGH SIGNAL" if score>=75 else "ELEVATED SIGNAL" if score>=55 else "WATCH SIGNAL" if score>=30 else "BASELINE SIGNAL"
    return {"generated_at":iso_z(utcnow()),"score":score,"band":band,"basis_event_count":len(rel),"method":"Public-source pathway signal weighted by event severity, source authority and corroboration; not a probability.","disclaimer":"Machine-generated public-source signal only. It is not a calibrated probability forecast and does not replace the curated THRESHOLD assessment.","top_events":rel[:12]}

def vector_value(events,terms):
    total=0
    for e in recent(events,120):
        if e.get("effective_severity",0)<45: continue
        text=f" {e.get('title','')} {e.get('summary','')} ".lower(); m=sum(1 for t in terms if t in text)
        if m:
            authority=1.0 if e.get("source_tier")=="primary" else .8; corroboration=min(1.25,1+.08*max(0,e.get("corroboration_count",1)-1)); total+=min(20,(5+m*4+max(0,e.get("effective_severity",0)-55)//8)*authority*corroboration)
    return max(0,min(100,round(total)))

def wwt_signal(events):
    vectors={name:vector_value(events,terms) for name,terms in WWT_VECTOR_RULES.items()}; vals=list(vectors.values()); highest=max(vals) if vals else 0; avg=round(sum(vals)/len(vals)) if vals else 0
    systemic=[e for e in recent(events,120) if e.get("effective_severity",0)>=65 and e.get("domain") in ("WAR","NUCLEAR","CYBER","INFRA","ECONOMIC")]; pressure=min(100,round(sum(max(0,e.get("effective_severity",0)-60) for e in systemic[:20])/4)); score=round(highest*.40+avg*.35+pressure*.25)
    return {"generated_at":iso_z(utcnow()),"score":score,"formula":"40% highest vector + 35% vector average + 25% systemic pressure","highest_vector":highest,"vector_average":avg,"systemic_pressure":pressure,"vectors":vectors,"basis_event_count":len(systemic),"method":"Machine pressure index using authoritative public sources, severity and corroboration.","disclaimer":"Machine-generated public-source pressure signal only. It is not a statistically calibrated forecast of world war and does not replace the curated WWT assessment.","top_events":sorted(systemic,key=lambda e:(e.get("effective_severity",0),e.get("published","")),reverse=True)[:12]}

def brief_signal(events):
    live=sorted([e for e in recent(events,72) if e.get("effective_severity",0)>=40],key=lambda e:(e.get("effective_severity",0),e.get("corroboration_count",1),e.get("published","")),reverse=True); domains={}
    for e in live: domains[e.get("domain","GLOBAL")]=domains.get(e.get("domain","GLOBAL"),0)+1
    return {"generated_at":iso_z(utcnow()),"headline_count":len(live),"domain_counts":dict(sorted(domains.items(),key=lambda kv:kv[1],reverse=True)),"top_events":live[:16],"note":"Autonomous machine-generated public-source brief; curated Y&Y analysis remains separate."}

def inject_panel():
    changed=[]; tag='<script src="/assets/y-and-y-live.js" defer></script>'
    for rel in PAGES:
        p=ROOT/rel
        if not p.exists(): continue
        text=p.read_text(encoding="utf-8")
        if "/assets/y-and-y-live.js" in text: continue
        text=text.replace("</body>",f"  {tag}\n</body>",1) if "</body>" in text else text+f"\n{tag}\n"; p.write_text(text,encoding="utf-8"); changed.append(rel)
    return changed

def health_status(src,ok,count,error,previous):
    prev=(previous.get("source_status_by_id") or {}).get(src["id"],{}) if isinstance(previous,dict) else {}
    now=iso_z(utcnow()); failures=0 if ok else int(prev.get("consecutive_failures",0))+1
    return {"id":src["id"],"name":src["name"],"url":src["url"],"tier":src["tier"],"weight":src.get("weight",0.8),"ok":ok,"items":count,"error":error,"last_success":now if ok else prev.get("last_success"),"last_failure":None if ok else now,"consecutive_failures":failures}

def main():
    now=utcnow(); previous_events=load_json(DATA/"live-events.json",{"events":[]}); old=previous_events.get("events",[]) if isinstance(previous_events,dict) else []; previous_status=load_json(DATA/"autonomy-status.json",{}); by_id={e.get("id"):e for e in old if e.get("id")}; status=[]; fetched=[]
    for src in RSS_SOURCES:
        try:
            items=parse_feed(src,fetch_bytes(src["url"])); fetched.extend(items); status.append(health_status(src,True,len(items),None,previous_status))
        except Exception as exc: status.append(health_status(src,False,0,f"{type(exc).__name__}: {exc}"[:260],previous_status))
    for src in JSON_SOURCES:
        try:
            items=parse_json_source(src,fetch_bytes(src["url"])); fetched.extend(items); status.append(health_status(src,True,len(items),None,previous_status))
        except Exception as exc: status.append(health_status(src,False,0,f"{type(exc).__name__}: {exc}"[:260],previous_status))
    cutoff=now-dt.timedelta(hours=FRESH_HOURS); ceiling=now+dt.timedelta(hours=FUTURE_TOLERANCE_HOURS); new_count=0; future_rejected=0
    for item in fetched:
        e=enrich(item); existing=by_id.get(e["id"])
        if existing:
            e["first_seen"]=existing.get("first_seen") or existing.get("published") or e["first_seen"]
            if e.get("published_inferred") and existing.get("published"): e["published"]=existing["published"]
        published=parse_iso(e["published"])
        if published>ceiling:
            future_rejected+=1; continue
        if published<cutoff: continue
        if e["id"] not in by_id: new_count+=1
        by_id[e["id"]]=e
    candidates=[e for e in by_id.values() if cutoff<=parse_iso(e.get("published",""))<=ceiling]
    events=sorted(candidates,key=lambda e:parse_iso(e.get("published","")),reverse=True)[:MAX_EVENTS]; events=corroborate(events); live=recent(events,LIVE_WINDOW_HOURS)
    world=sorted([e for e in live if e.get("domain") in STRATEGIC_DOMAINS and e.get("effective_severity",0)>=40],key=lambda e:(e.get("effective_severity",0),e.get("corroboration_count",1),e.get("published","")),reverse=True)
    atlas=[e for e in world if e.get("lat") is not None and e.get("lon") is not None]; infra=[e for e in world if e.get("domain") in ("INFRA","CYBER","ECONOMIC","CLIMATE")]; trfk=[e for e in world if e.get("domain")=="TRAFFICKING"]
    ok=sum(1 for s in status if s["ok"]); injected=inject_panel(); health_pct=round((ok/len(status))*100) if status else 0; mode="AUTONOMOUS" if health_pct>=80 else "DEGRADED" if health_pct>=50 else "CRITICAL"
    status_by_id={s["id"]:s for s in status}
    state={"engine":"Y&Y Autonomous Core","version":2.1,"last_poll":iso_z(now),"sources_total":len(status),"sources_ok":ok,"sources_failed":len(status)-ok,"source_health_percent":health_pct,"source_status":status,"source_status_by_id":status_by_id,"fetched_items":len(fetched),"new_events":new_count,"future_dated_items_rejected":future_rejected,"live_events":len(live),"strategic_live_events":len(world),"archive_events":len(events),"corroborated_live_events":sum(1 for e in live if e.get("corroboration_count",1)>1),"mode":mode,"chatgpt_dependency":False,"pages_injected_this_run":injected,"notes":["Machine-generated live signals are kept separate from curated strategic assessments.","Source failures are isolated; successful sources continue updating the system.","Undated feed items preserve their first observed timestamp instead of appearing newly published every poll.","Future-dated publication records are rejected until their publication time arrives."]}
    registry={"generated_at":iso_z(now),"sources":[{k:s[k] for k in ("id","name","url","tier","weight","default_domain")} for s in ALL_SOURCES]}
    write_json(DATA/"source-registry.json",registry); write_json(DATA/"live-events.json",{"generated_at":iso_z(now),"events":events}); write_json(DATA/"autonomy-status.json",state); write_json(DATA/"worldwatch-live.json",{"generated_at":iso_z(now),"events":world[:160]}); write_json(DATA/"atlas-live.json",{"generated_at":iso_z(now),"events":atlas[:160]}); write_json(DATA/"infrawatch-live.json",{"generated_at":iso_z(now),"events":infra[:160]}); write_json(DATA/"trfk-live.json",{"generated_at":iso_z(now),"events":trfk[:160]}); write_json(DATA/"threshold-live.json",threshold_signal(events)); write_json(DATA/"wwt-live.json",wwt_signal(events)); write_json(DATA/"brief-live.json",brief_signal(events))
    print(f"Y&Y v2.1 poll: health {health_pct}% ({ok}/{len(status)}); fetched {len(fetched)}; new {new_count}; future rejected {future_rejected}; live {len(live)}; strategic {len(world)}; corroborated {state['corroborated_live_events']}")
    for s in status:
        if not s["ok"]: print(f"WARN {s['name']}: {s['error']}",file=sys.stderr)
    return 0

if __name__=="__main__": raise SystemExit(main())
