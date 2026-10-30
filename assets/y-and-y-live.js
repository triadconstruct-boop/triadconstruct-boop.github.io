(() => {
  "use strict";

  const route = (window.location.pathname || "/").toLowerCase();
  const remoteProject = /\/ronin-(atlas|intake|infrawatch|academy|brief)\.github\.io\//.test(route);
  const BASE = remoteProject
    ? "https://raw.githubusercontent.com/triadconstruct-boop/triadconstruct-boop.github.io/main/data/"
    : "/data/";
  const endpoint = route.includes("/threshold") ? "threshold-live.json"
    : route.includes("/wwt") ? "wwt-live.json"
    : route.includes("/trfk") ? "trfk-live.json"
    : route.includes("/edges") ? "edges-live.json"
    : route.includes("/infrawatch") ? "infrawatch-live.json"
    : route.includes("/atlas") ? "atlas-live.json"
    : route.includes("/brief") ? "brief-live.json"
    : "worldwatch-live.json";
  const routeLabel = route.includes("/threshold") ? "THRESHOLD"
    : route.includes("/wwt") ? "WWT"
    : route.includes("/trfk") ? "TRFK"
    : route.includes("/edges") ? "EDGES"
    : route.includes("/infrawatch") ? "INFRAWATCH"
    : route.includes("/atlas") ? "ATLAS"
    : route.includes("/brief") ? "BRIEF"
    : route.includes("/academy") ? "ACADEMY"
    : route.includes("/intake") ? "INTAKE"
    : route.includes("/system") ? "SYSTEM"
    : route.includes("/worldwatch") ? "WORLDWATCH" : "Y&Y";
  const STATES = ["ALL", "CONFIRMED", "CREDIBLE REPORT", "EARLY WARNING", "SPECULATIVE", "UNVERIFIED CLAIM", "REFUTED", "DORMANT"];

  const node = (tag, className, text) => {
    const value = document.createElement(tag);
    if (className) value.className = className;
    if (text !== undefined && text !== null) value.textContent = String(text);
    return value;
  };
  const score = value => Number.isFinite(Number(value)) ? Number(value) : 0;
  const date = value => {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? "—" : parsed.toLocaleString([], {year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit"});
  };
  const age = value => {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? null : Math.max(0, Math.round((Date.now() - parsed.getTime()) / 60000));
  };
  const claimsFrom = data => {
    if (Array.isArray(data?.claims)) return data.claims;
    if (Array.isArray(data?.top_claims)) return data.top_claims;
    if (Array.isArray(data?.top_events)) return data.top_events;
    if (Array.isArray(data?.events)) return data.events;
    return [];
  };

  function addStyles() {
    if (document.getElementById("yy-intelligence-styles")) return;
    const style = node("style");
    style.id = "yy-intelligence-styles";
    style.textContent = `
      :root{--yy-red:#ff3030;--yy-dark:#050000;--yy-panel:#090202;--yy-line:#591010;--yy-muted:#9a5d5d;--yy-good:#74d474;--yy-warn:#ffb347}
      #yy-live-panel,#yy-intel-layer,#yy-dual-layer{box-sizing:border-box;color:#eee;background:rgba(4,0,0,.98);border:1px solid var(--yy-line);font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;line-height:1.42;text-shadow:none}
      #yy-live-panel * ,#yy-intel-layer *,#yy-dual-layer *{box-sizing:border-box}
      #yy-live-panel{position:fixed;right:12px;bottom:12px;z-index:2147483000;width:min(460px,calc(100vw - 24px));max-height:min(75vh,720px);overflow:auto;box-shadow:0 0 26px rgba(160,0,0,.32);font-size:12px}
      #yy-live-panel summary{cursor:pointer;list-style:none;padding:10px 12px;color:var(--yy-red);background:#080000;border-bottom:1px solid #421010;font-weight:900;letter-spacing:.09em}
      #yy-live-panel summary::-webkit-details-marker{display:none}.yy-live-body{padding:10px 12px}.yy-row{display:flex;justify-content:space-between;gap:14px;padding:3px 0;border-bottom:1px dotted #262020}.yy-key{color:#a78d8d}.yy-value{text-align:right;color:#eee}.yy-good{color:var(--yy-good)}.yy-warn{color:var(--yy-warn)}.yy-bad{color:#ff6868}.yy-stale{color:var(--yy-warn)}
      .yy-section-title{margin:11px 0 5px;color:var(--yy-red);font-size:11px;letter-spacing:.1em;font-weight:900}.yy-claim-mini{padding:8px 0;border-top:1px solid #281818}.yy-claim-mini a{color:#f2dddd;text-decoration:none}.yy-claim-mini a:hover{color:#ff5a5a;text-decoration:underline}.yy-meta,.yy-note{color:#a48787;font-size:11px}.yy-note{margin-top:8px}.yy-state{display:inline-block;padding:1px 5px;border:1px solid currentColor;font-size:10px;font-weight:900;letter-spacing:.04em}.yy-state-confirmed{color:#70d870}.yy-state-credible-report{color:#dadada}.yy-state-early-warning{color:#ffb347}.yy-state-speculative{color:#ff7a7a}.yy-state-unverified-claim{color:#bb7777}.yy-state-refuted{color:#8f8f8f;text-decoration:line-through}.yy-state-dormant{color:#766060}
      #yy-intel-layer{width:min(1180px,calc(100% - 28px));margin:18px auto 28px;padding:16px;background:linear-gradient(180deg,#090202,#030000);box-shadow:0 0 25px rgba(120,0,0,.16)}.yy-layer-head{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;border-bottom:1px solid var(--yy-line);padding-bottom:12px}.yy-layer-head h2{margin:0;color:var(--yy-red);font-size:clamp(16px,2vw,23px);letter-spacing:.1em}.yy-layer-head p{margin:5px 0 0;color:#a97a7a;font-size:11px;max-width:760px}.yy-coverage{text-align:right;color:#ddd;font-weight:900;white-space:nowrap}.yy-filters{display:flex;flex-wrap:wrap;gap:5px;margin:12px 0}.yy-filter{border:1px solid #572020;background:#070101;color:#ad7777;padding:5px 7px;font:700 10px/1.2 inherit;cursor:pointer}.yy-filter[aria-pressed="true"]{color:#fff;border-color:var(--yy-red);background:#280505}.yy-claim-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(360px,100%),1fr));gap:9px}.yy-card{border:1px solid #321313;background:#070202;padding:11px}.yy-card-top{display:flex;justify-content:space-between;align-items:center;gap:8px}.yy-scores{color:#bdaaaa;font-size:10px;white-space:nowrap}.yy-card h3{font-size:13px;line-height:1.35;margin:8px 0 5px;color:#f0dede}.yy-card .yy-reason{color:#b89090;font-size:11px}.yy-evidence{margin:8px 0 0;padding:7px 0 0;border-top:1px dotted #321919}.yy-evidence a{color:#e8caca;text-decoration:none;font-size:11px}.yy-evidence a:hover{color:#ff5555}.yy-branch{margin-top:8px;border-top:1px dotted #321919;padding-top:6px}.yy-branch summary{cursor:pointer;color:#c54b4b;font-size:10px;letter-spacing:.06em}.yy-branch p,.yy-branch li{font-size:10px;color:#a98a8a}.yy-branch ul{padding-left:17px;margin:4px 0}.yy-empty{padding:16px;color:#a87575;border:1px dashed #482020}
      #yy-dual-layer{width:min(1120px,calc(100% - 28px));margin:14px auto 22px;padding:12px}.yy-dual-title{color:var(--yy-red);font-size:11px;letter-spacing:.12em;font-weight:900;margin-bottom:8px}.yy-dual-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.yy-signal-box{border:1px solid #351414;padding:10px;background:#070202}.yy-signal-box h3{margin:0;color:#c7aaaa;font-size:11px;letter-spacing:.07em}.yy-signal-score{font-size:30px;font-weight:900;color:var(--yy-red);line-height:1.2}.yy-signal-box p{margin:3px 0;color:#9f7a7a;font-size:10px}
      @media(max-width:680px){#yy-live-panel{right:7px;bottom:7px;width:calc(100vw - 14px);max-height:66vh}.yy-layer-head{display:block}.yy-coverage{text-align:left;margin-top:7px}.yy-dual-grid{grid-template-columns:1fr}}
      @media print{#yy-live-panel{display:none!important}}
      #worldwatch-live-mount #yy-intel-layer{width:100%;margin:18px 0 24px;padding:18px}.yy-geography{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:18px 0 8px}.yy-select-label{display:flex;flex-direction:column;gap:7px;color:#ba9999;font-size:11px;letter-spacing:.08em}.yy-select{width:100%;min-height:44px;border:1px solid #703030;border-radius:0;background:#100404;color:#f4dfdf;padding:9px 30px 9px 10px;font:13px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}.yy-select:focus-visible,.yy-filter:focus-visible,.yy-more:focus-visible{outline:2px solid #ff7777;outline-offset:3px}.yy-view-summary{margin:14px 0;color:#cbaaaa;font-size:12px}.yy-view-note{margin:8px 0 14px;color:#a48787;font-size:11px}.yy-region-label{display:block;color:#ff8f8f;font-size:10px;letter-spacing:.07em;margin-bottom:8px}.yy-more{display:block;min-height:44px;margin:18px auto 0;padding:10px 22px;border:1px solid #823030;background:#200606;color:#f0dede;font:12px ui-monospace,monospace;cursor:pointer}.yy-more[hidden]{display:none}.yy-coverage{font-size:11px}.yy-region-counts{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0}.yy-region-jump{border:1px solid #482020;background:#0c0303;color:#bd9999;padding:7px 9px;font:10px ui-monospace,monospace;cursor:pointer}.yy-region-jump[aria-pressed="true"]{color:#fff;border-color:#e94040}.yy-region-jump:focus-visible{outline:2px solid #ff7777;outline-offset:2px}@media(max-width:600px){.yy-geography{grid-template-columns:1fr}#worldwatch-live-mount #yy-intel-layer{padding:12px}.yy-card-top{align-items:flex-start;flex-wrap:wrap}.yy-scores{white-space:normal}}
    `;
    document.head.appendChild(style);
  }

  function registerPortalRoute() {
    const selector = document.getElementById("tool");
    if (!selector || selector.querySelector('option[value="/edges/"]')) return;
    const option = node("option", "", "EDGES");
    option.value = "/edges/";
    const atlas = selector.querySelector('option[value="/atlas/"]');
    selector.insertBefore(option, atlas);
  }

  function addRow(parent, key, value, className = "") {
    const row = node("div", "yy-row");
    row.append(node("span", "yy-key", key), node("span", `yy-value ${className}`, value));
    parent.appendChild(row);
  }

  function stateBadge(state) {
    const normalized = String(state || "UNVERIFIED CLAIM");
    return node("span", `yy-state yy-state-${normalized.toLowerCase().replaceAll(" ", "-")}`, normalized);
  }

  function evidenceLink(claim) {
    const evidence = Array.isArray(claim.evidence) ? claim.evidence.find(item => item.url) : null;
    return evidence || (claim.url ? {url: claim.url, title: claim.title, source: claim.source} : null);
  }

  function renderMiniClaims(parent, claims) {
    parent.appendChild(node("div", "yy-section-title", "LATEST LAYERED CLAIMS"));
    if (!claims.length) {
      parent.appendChild(node("div", "yy-note", "No qualifying claims in this view. Check collection coverage before interpreting silence."));
      return;
    }
    claims.slice(0, 6).forEach(claim => {
      const box = node("div", "yy-claim-mini");
      const linkData = evidenceLink(claim);
      if (linkData) {
        const link = node("a", "", claim.headline || claim.title || "Untitled claim");
        link.href = linkData.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        box.appendChild(link);
      } else {
        box.appendChild(node("div", "", claim.headline || claim.title || "Untitled claim"));
      }
      const state = claim.state || "UNVERIFIED CLAIM";
      box.appendChild(node("div", "yy-meta", `${state} // C${score(claim.confidence)} // W${score(claim.watch_priority)} // T${score(claim.threat_score)} // ${date(claim.material_time || claim.published)}`));
      parent.appendChild(box);
    });
  }

  function renderPanel(status, data) {
    const panel = document.createElement("details");
    panel.id = "yy-live-panel";
    const keepClosed = route === "/" || route.includes("/worldwatch") || route.includes("/threshold") || route.includes("/wwt") || route.includes("/system");
    panel.open = !keepClosed && window.innerWidth >= 980;
    panel.appendChild(node("summary", "", `${routeLabel} // INTELLIGENCE LIVE`));
    const body = node("div", "yy-live-body");
    const freshness = age(status.last_poll);
    const coverage = score(status.source_health_percent);
    addRow(body, "ENGINE", `${status.mode || "UNKNOWN"} / v${status.version || "—"}`, status.mode === "AUTONOMOUS" ? "yy-good" : "yy-warn");
    addRow(body, "SITUATION", status.situation || "UNASSESSED", String(status.situation || "").includes("GAP") ? "yy-warn" : "yy-good");
    addRow(body, "LAST POLL", `${date(status.last_poll)}${freshness !== null ? ` (${freshness}m ago)` : ""}`, freshness !== null && freshness > 90 ? "yy-stale" : "");
    addRow(body, "SOURCE COVERAGE", `${coverage}% // ${status.sources_ok || 0}/${status.sources_total || 0}`, coverage >= 80 ? "yy-good" : coverage >= 55 ? "yy-warn" : "yy-bad");
    addRow(body, "CLAIMS", status.claim_count || 0);
    addRow(body, "ANOMALIES", status.anomaly_count || 0);
    addRow(body, "CHATGPT DEP.", status.chatgpt_dependency ? "YES" : "NO", status.chatgpt_dependency ? "yy-bad" : "yy-good");
    if (status.quiet_interpretation) body.appendChild(node("div", "yy-note", status.quiet_interpretation));
    renderMiniClaims(body, claimsFrom(data));
    const gaps = Array.isArray(status.collection_blind_spots) ? status.collection_blind_spots : [];
    if (gaps.length) {
      body.appendChild(node("div", "yy-section-title", "COLLECTION BLIND SPOTS"));
      gaps.slice(0, 6).forEach(gap => body.appendChild(node("div", "yy-meta yy-warn", `${gap.source}: ${gap.status}`)));
    }
    body.appendChild(node("div", "yy-note", data.disclaimer || data.note || "Every machine claim retains an explicit state. Speculation is never presented as fact."));
    panel.appendChild(body);
    document.body.appendChild(panel);
  }

  function renderBranch(claim) {
    const branch = claim.branch_analysis || {};
    const details = node("details", "yy-branch");
    details.appendChild(node("summary", "", "WHY / BRANCHES / FALSIFIERS"));
    details.appendChild(node("p", "", claim.classification_reason || "No classification reason supplied."));
    if (branch.escalation_branch) details.appendChild(node("p", "", `ESCALATION: ${branch.escalation_branch}`));
    if (branch.de_escalation_branch) details.appendChild(node("p", "", `DE-ESCALATION: ${branch.de_escalation_branch}`));
    const list = node("ul");
    [...(branch.confirm_indicators || []).slice(0, 2), ...(branch.falsify_indicators || []).slice(0, 2)].forEach(value => list.appendChild(node("li", "", value)));
    details.appendChild(list);
    return details;
  }

  function renderCard(claim) {
    const card = node("article", "yy-card");
    const top = node("div", "yy-card-top");
    top.append(stateBadge(claim.state), node("span", "yy-scores", `CONF ${score(claim.confidence)} ${claim.confidence_direction || ""} · WATCH ${score(claim.watch_priority)} · THREAT ${score(claim.threat_score)}`));
    card.appendChild(top);
    card.appendChild(node("h3", "", claim.headline || "Untitled claim"));
    card.appendChild(node("div", "yy-meta", `${(claim.domains || []).join("+") || "SECURITY"} // ${(claim.regions || []).join(", ") || "GLOBAL"} // ${date(claim.material_time)}`));
    card.appendChild(node("div", "yy-reason", claim.classification_reason || "Classification explanation unavailable."));
    const sources = node("div", "yy-evidence");
    sources.appendChild(node("div", "yy-meta", `${claim.independent_provenance_count || 0} independent provenance root(s) // ${(claim.sources || []).join(", ") || "unresolved source"}`));
    (claim.evidence || []).slice(0, 3).forEach(item => {
      const line = node("div");
      const link = node("a", "", `${item.stance === "refutation" ? "CONTRADICTS" : "SUPPORTS"} // ${item.source}: ${item.title}`);
      link.href = item.url || "#";
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      line.appendChild(link);
      sources.appendChild(line);
    });
    card.appendChild(sources);
    if ((claim.historical_matches || []).length) card.appendChild(node("div", "yy-meta", `HISTORICAL RECURRENCE // ${claim.historical_matches.length} pattern match(es)`));
    if ((claim.anomaly_ids || []).length) card.appendChild(node("div", "yy-meta yy-warn", `ANOMALY CONVERGENCE // ${claim.anomaly_ids.length}`));
    card.appendChild(renderBranch(claim));
    return card;
  }

  function renderWorldwatch(status, data) {
    if (!route.includes("/worldwatch")) return;
    const section = node("section");
    section.id = "yy-intel-layer";
    const head = node("div", "yy-layer-head");
    const copy = node("div");
    copy.append(node("h2", "", "WORLDWIDE OVERVIEW"), node("p", "", "Reporting from across the world. Choose a region, then a conflict or topic, to explore the developments behind the overview."));
    head.append(copy, node("div", "yy-coverage", `${status.sources_ok || 0}/${status.sources_total || 0} SOURCES CURRENT`));
    section.appendChild(head);
    const regions = data.geography?.regions || [{id: "global", label: "Global & Cross-border", conflicts: []}];
    const legacyRegions = {RUSSIA: "europe-eurasia", UKRAINE: "europe-eurasia", EUROPE: "europe-eurasia", IRAN: "middle-east-north-africa", "ISRAEL/PALESTINE": "middle-east-north-africa", "MIDDLE EAST": "middle-east-north-africa", AFRICA: "sub-saharan-africa", CHINA: "east-asia-pacific", TAIWAN: "east-asia-pacific", "KOREAN PENINSULA": "east-asia-pacific", "INDO-PACIFIC": "east-asia-pacific", "UNITED STATES": "north-america", "LATIN AMERICA": "latin-america-caribbean"};
    const allClaims = claimsFrom(data).map(claim => {
      if (claim.worldwatch) return claim;
      const ids = [...new Set((claim.regions || []).map(tag => legacyRegions[tag]).filter(Boolean))];
      return {...claim, worldwatch: {primary_region: ids.length === 1 ? ids[0] : "global", regions: ids.length ? ids : ["global"], conflicts: []}};
    });
    const geography = node("div", "yy-geography");
    const makeSelect = (id, text) => {
      const field = node("div", "yy-select-label");
      const label = node("label", "yy-select-label", text);
      label.htmlFor = id;
      const select = node("select", "yy-select");
      select.id = id;
      field.append(label, select);
      geography.appendChild(field);
      return select;
    };
    const regionSelect = makeSelect("yy-region-select", "REGION");
    const conflictSelect = makeSelect("yy-conflict-select", "CONFLICT / TOPIC");
    const addOption = (parent, value, label) => {
      const option = node("option", "", label);
      option.value = value;
      parent.appendChild(option);
    };
    addOption(regionSelect, "overview", "Worldwide overview · regional mix");
    addOption(regionSelect, "all", "All regions · priority order");
    regions.forEach(region => addOption(regionSelect, region.id, `${region.label} (${region.count ?? allClaims.filter(claim => claim.worldwatch.regions.includes(region.id)).length})`));
    const populateConflicts = () => {
      conflictSelect.replaceChildren();
      addOption(conflictSelect, "all", "All conflicts & topics");
      const scoped = regions.filter(region => ["overview", "all", region.id].includes(regionSelect.value));
      scoped.forEach(region => {
        if (!region.conflicts?.length) return;
        const group = node("optgroup");
        group.label = region.label;
        region.conflicts.forEach(conflict => addOption(group, conflict.id, `${conflict.label} (${conflict.count})`));
        conflictSelect.appendChild(group);
      });
      conflictSelect.disabled = !scoped.some(region => region.conflicts?.length);
    };
    populateConflicts();
    section.appendChild(geography);
    const regionCounts = node("div", "yy-region-counts");
    regionCounts.setAttribute("aria-label", "Browse regions");
    regions.forEach(region => {
      const button = node("button", "yy-region-jump", `${region.label} · ${region.count ?? 0}`);
      button.type = "button";
      button.dataset.region = region.id;
      button.setAttribute("aria-pressed", "false");
      button.addEventListener("click", () => { regionSelect.value = region.id; populateConflicts(); show(true); });
      regionCounts.appendChild(button);
    });
    section.appendChild(regionCounts);
    const filters = node("div", "yy-filters");
    filters.setAttribute("aria-label", "Filter by evidence state");
    const grid = node("div", "yy-claim-grid");
    grid.id = "yy-worldwatch-cards";
    const summary = node("p", "yy-view-summary");
    summary.setAttribute("role", "status");
    summary.setAttribute("aria-live", "polite");
    const note = node("p", "yy-view-note");
    const more = node("button", "yy-more", "Show more reports");
    more.type = "button";
    more.setAttribute("aria-controls", grid.id);
    let state = "ALL";
    let visibleCount = 24;
    const show = (reset = false) => {
      if (reset) visibleCount = 24;
      grid.replaceChildren();
      const selectedClaims = window.WorldwatchViews.selectClaims(allClaims, regions, {region: regionSelect.value, conflict: conflictSelect.value, state, limit: data.geography?.overview_limit || 24});
      const visible = selectedClaims.slice(0, visibleCount);
      const desk = regions.find(region => region.id === regionSelect.value);
      const selectedConflict = regions.flatMap(region => region.conflicts || []).find(conflict => conflict.id === conflictSelect.value);
      const label = selectedConflict?.label || desk?.label || (regionSelect.value === "overview" ? "Worldwide overview" : "All regions");
      summary.textContent = `${label} · ${visible.length} of ${selectedClaims.length} reports${state === "ALL" ? "" : ` · ${state}`}`;
      const overview = regionSelect.value === "overview" && conflictSelect.value === "all";
      note.textContent = `${overview ? "The overview rotates through regions and topics. Regional views retain their priority order." : "Reports are listed in their existing priority order."} Updated ${date(data.generated_at)}. Cross-border reports can appear in multiple regional views. Gaps do not establish that a region is quiet.`;
      if (!selectedClaims.length) grid.appendChild(node("div", "yy-empty", "No matching reports in this view. Try another region, conflict or evidence state, and consult source gaps before interpreting an absence of reporting."));
      visible.forEach(claim => {
        const card = renderCard(claim);
        card.dataset.claimId = claim.id;
        card.dataset.region = claim.worldwatch.primary_region;
        const region = regions.find(item => item.id === claim.worldwatch.primary_region);
        card.prepend(node("span", "yy-region-label", region?.label || "Global & Cross-border"));
        grid.appendChild(card);
      });
      more.hidden = visible.length >= selectedClaims.length;
      regionCounts.querySelectorAll("button").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.region === regionSelect.value)));
    };
    STATES.forEach((value, index) => {
      const button = node("button", "yy-filter", value);
      button.type = "button";
      button.setAttribute("aria-pressed", index === 0 ? "true" : "false");
      button.addEventListener("click", () => {
        filters.querySelectorAll("button").forEach(item => item.setAttribute("aria-pressed", String(item === button)));
        state = value;
        show(true);
      });
      filters.appendChild(button);
    });
    regionSelect.addEventListener("change", () => { populateConflicts(); show(true); });
    conflictSelect.addEventListener("change", () => {
      if (conflictSelect.value !== "all") {
        const region = regions.find(item => item.conflicts?.some(conflict => conflict.id === conflictSelect.value));
        if (region && regionSelect.value !== region.id) {
          const selected = conflictSelect.value;
          regionSelect.value = region.id;
          populateConflicts();
          conflictSelect.value = selected;
        }
      }
      show(true);
    });
    more.addEventListener("click", () => { visibleCount += 24; show(); });
    section.append(filters, summary, note, grid, more);
    show();
    const mount = document.getElementById("worldwatch-live-mount");
    if (mount) { mount.replaceChildren(section); return; }
    const anchor = document.querySelector("main") || document.body.firstElementChild;
    if (anchor && anchor.parentNode === document.body) document.body.insertBefore(section, anchor);
    else document.body.insertBefore(section, document.body.firstChild);
  }

  function renderDual(data) {
    const threshold = route.includes("/threshold");
    const wwt = route.includes("/wwt");
    if (!threshold && !wwt) return;
    const hardKey = threshold ? "confirmed_homeland_signal" : "verified_pressure";
    const earlyKey = threshold ? "precursor_speculative_signal" : "early_warning_pressure";
    const hardLabel = threshold ? "CONFIRMED HOMELAND SIGNAL" : "VERIFIED PRESSURE";
    const earlyLabel = threshold ? "PRECURSOR / SPECULATIVE SIGNAL" : "EARLY-WARNING PRESSURE";
    const section = node("section");
    section.id = "yy-dual-layer";
    section.appendChild(node("div", "yy-dual-title", "AUTONOMOUS LAYER // SEPARATED EVIDENCE CHANNELS"));
    const grid = node("div", "yy-dual-grid");
    [[hardKey, hardLabel], [earlyKey, earlyLabel]].forEach(([key, label]) => {
      const value = data[key] || {};
      const box = node("div", "yy-signal-box");
      box.append(node("h3", "", label), node("div", "yy-signal-score", score(value.score)), node("p", "", `${value.claim_count || 0} qualifying claim(s)`));
      grid.appendChild(box);
    });
    section.appendChild(grid);
    section.appendChild(node("div", "yy-note", data.safeguard || "Weak signals cannot enter the verified channel."));
    const header = document.querySelector("header");
    if (header) header.insertAdjacentElement("afterend", section);
    else document.body.insertBefore(section, document.body.firstChild);
  }

  async function boot() {
    addStyles();
    registerPortalRoute();
    try {
      const [statusResponse, dataResponse] = await Promise.all([
        fetch(`${BASE}autonomy-status.json`, {cache: "no-store"}),
        fetch(`${BASE}${endpoint}`, {cache: "no-store"}),
      ]);
      if (!statusResponse.ok || !dataResponse.ok) throw new Error(`HTTP ${statusResponse.status}/${dataResponse.status}`);
      const [status, data] = await Promise.all([statusResponse.json(), dataResponse.json()]);
      renderWorldwatch(status, data);
      renderDual(data);
      renderPanel(status, data);
    } catch (error) {
      const mount = document.getElementById("worldwatch-live-mount");
      if (mount) mount.replaceChildren(node("p", "yy-empty", "Current reporting is unavailable. Check the status panel or open the earlier briefings below."));
      const panel = document.createElement("details");
      panel.id = "yy-live-panel";
      panel.open = true;
      panel.append(node("summary", "", `${routeLabel} // DATA UNAVAILABLE`), node("div", "yy-live-body yy-bad", String(error)));
      document.body.appendChild(panel);
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, {once: true});
  else boot();
})();

