(() => {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";
  const DATA_URL = "/data/edges-live.json";
  const STATUS_URL = "/data/autonomy-status.json";
  const KIND_SCOPE = {
    core: new Set(["CLAIM", "ACTOR", "DOMAIN", "REGION", "SOURCE", "ANOMALY"]),
    actors: new Set(["CLAIM", "ACTOR"]),
    sources: new Set(["CLAIM", "ACTOR", "SOURCE"]),
    history: new Set(["CLAIM", "ACTOR", "DOMAIN", "REGION", "ANOMALY", "HISTORICAL"]),
    full: new Set(["CLAIM", "ACTOR", "DOMAIN", "REGION", "SOURCE", "ANOMALY", "HISTORICAL"]),
  };
  const MODE_LABELS = {names: "NAMES VISIBLE", masks: "STABLE MASKS", edges: "EDGES ONLY"};
  const LAYER_CLASS = {DIRECT: "direct", REPORTED: "reported", ANALYTICAL: "analytical", HISTORICAL: "historical"};
  const KIND_CLASS = {CLAIM: "claim", ACTOR: "actor", DOMAIN: "domain", REGION: "region", SOURCE: "source", ANOMALY: "anomaly", HISTORICAL: "historical"};
  const anchors = {
    CLAIM: [500, 350], ACTOR: [170, 345], DOMAIN: [500, 90], REGION: [830, 345],
    SOURCE: [490, 625], ANOMALY: [790, 105], HISTORICAL: [815, 600],
  };

  const state = {
    data: null,
    status: null,
    mode: "edges",
    activeStates: new Set(),
    activeLayers: new Set(["DIRECT", "REPORTED", "ANALYTICAL"]),
    scope: "core",
    claimLimit: 90,
    query: "",
    selected: null,
    revealSelected: false,
    origin: null,
    traceNodes: new Set(),
    traceEdges: new Set(),
    visible: {nodes: [], edges: []},
    positions: new Map(),
    nodeElements: new Map(),
    edgeElements: new Map(),
    transform: {x: 0, y: 0, scale: 1},
    panning: null,
    draggingNode: null,
  };

  const $ = id => document.getElementById(id);
  const graph = $("graph");
  const viewport = $("viewport");
  const edgeLayer = $("edgeLayer");
  const nodeLayer = $("nodeLayer");
  const detail = $("detail");

  function svgNode(tag, attributes = {}) {
    const element = document.createElementNS(SVG_NS, tag);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
    return element;
  }

  function htmlNode(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = String(text);
    return element;
  }

  function safeUrl(value) {
    try {
      const url = new URL(value, window.location.origin);
      return ["http:", "https:"].includes(url.protocol) ? url.href : null;
    } catch (_) {
      return null;
    }
  }

  function formatDate(value) {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? "UNKNOWN TIME" : parsed.toLocaleString([], {year: "numeric", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit"});
  }

  function hashNumber(value) {
    let hash = 2166136261;
    for (const char of String(value)) {
      hash ^= char.charCodeAt(0);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  function clamp(value, low, high) {
    return Math.max(low, Math.min(high, value));
  }

  function nodeById(id) {
    return state.data?.nodes?.find(node => node.id === id) || null;
  }

  function displayLabel(node, allowReveal = false) {
    if (!node) return "UNRESOLVED NODE";
    if (state.mode === "names" || (allowReveal && state.revealSelected)) return node.label;
    return node.masked_label;
  }

  function shortLabel(node) {
    const raw = displayLabel(node, node.id === state.selected);
    const limit = node.kind === "CLAIM" ? 30 : node.kind === "SOURCE" ? 22 : 24;
    return raw.length > limit ? `${raw.slice(0, limit - 1)}…` : raw;
  }

  function searchable(node) {
    const evidence = (node.evidence || []).flatMap(row => [row.title, row.source, row.provenance_root]);
    return [node.label, node.masked_label, node.kind, node.state, node.description, node.classification_reason, ...(node.domains || []), ...(node.regions || []), ...(node.actors || []), ...evidence].filter(Boolean).join(" ").toLowerCase();
  }

  function scoreNode(node) {
    if (node.kind !== "CLAIM") return Number(node.degree || 0) * 4 + Number(node.claim_count || 0) * 2;
    return Number(node.watch_priority || 0) * 1.4 + Number(node.confidence || 0) + Number(node.degree || 0) * 2;
  }

  function deriveVisibleGraph() {
    const nodes = state.data.nodes || [];
    const allEdges = state.data.edges || [];
    const allowedKinds = KIND_SCOPE[state.scope] || KIND_SCOPE.core;
    const activeEdges = allEdges.filter(edge => state.activeLayers.has(edge.layer));
    const query = state.query.trim().toLowerCase();
    const matchIds = new Set(query ? nodes.filter(node => searchable(node).includes(query)).map(node => node.id) : []);
    const forcedClaimIds = new Set();

    if (query) {
      for (const edge of activeEdges) {
        if (matchIds.has(edge.source) && nodeById(edge.target)?.kind === "CLAIM") forcedClaimIds.add(edge.target);
        if (matchIds.has(edge.target) && nodeById(edge.source)?.kind === "CLAIM") forcedClaimIds.add(edge.source);
      }
    }

    let claims = nodes.filter(node => node.kind === "CLAIM" && state.activeStates.has(node.state));
    if (query) claims = claims.filter(node => matchIds.has(node.id) || forcedClaimIds.has(node.id));
    claims.sort((left, right) => scoreNode(right) - scoreNode(left) || String(right.material_time).localeCompare(String(left.material_time)));
    claims = claims.slice(0, state.claimLimit);

    const visibleIds = new Set(claims.map(node => node.id));
    const contextCandidates = new Map();
    for (const edge of activeEdges) {
      const source = nodeById(edge.source);
      const target = nodeById(edge.target);
      if (!source || !target) continue;
      if (visibleIds.has(source.id) && allowedKinds.has(target.kind)) contextCandidates.set(target.id, target);
      if (visibleIds.has(target.id) && allowedKinds.has(source.kind)) contextCandidates.set(source.id, source);
    }
    for (const id of matchIds) {
      const node = nodeById(id);
      if (node && allowedKinds.has(node.kind)) contextCandidates.set(id, node);
    }

    const context = [...contextCandidates.values()]
      .filter(node => node.kind !== "CLAIM")
      .sort((left, right) => Number(right.degree || 0) - Number(left.degree || 0) || left.id.localeCompare(right.id))
      .slice(0, 140);
    context.forEach(node => visibleIds.add(node.id));

    let edges = activeEdges.filter(edge => visibleIds.has(edge.source) && visibleIds.has(edge.target));
    const connected = new Set(edges.flatMap(edge => [edge.source, edge.target]));
    let visibleNodes = [...claims, ...context].filter(node => connected.has(node.id));
    const finalIds = new Set(visibleNodes.map(node => node.id));
    edges = edges.filter(edge => finalIds.has(edge.source) && finalIds.has(edge.target));

    if (state.selected && !finalIds.has(state.selected)) {
      state.selected = null;
      state.revealSelected = false;
    }
    if (state.origin && !finalIds.has(state.origin)) clearTrace(false);
    return {nodes: visibleNodes, edges};
  }

  function calculateLayout(nodes, edges) {
    const positions = new Map();
    const indexById = new Map(nodes.map((node, index) => [node.id, index]));
    const points = nodes.map(node => {
      const seed = hashNumber(node.id);
      const anchor = anchors[node.kind] || anchors.CLAIM;
      const angle = ((seed % 360) * Math.PI) / 180;
      const radius = 25 + ((seed >>> 8) % 145);
      return {id: node.id, kind: node.kind, x: anchor[0] + Math.cos(angle) * radius, y: anchor[1] + Math.sin(angle) * radius};
    });
    const usableEdges = edges.map(edge => ({...edge, a: indexById.get(edge.source), b: indexById.get(edge.target)})).filter(edge => edge.a !== undefined && edge.b !== undefined);
    const ticks = nodes.length > 190 ? 72 : nodes.length > 120 ? 92 : 120;
    const repulsion = nodes.length > 170 ? 1250 : 1900;

    for (let tick = 0; tick < ticks; tick += 1) {
      const alpha = 1 - tick / ticks;
      const force = points.map(() => ({x: 0, y: 0}));
      for (let i = 0; i < points.length; i += 1) {
        for (let j = i + 1; j < points.length; j += 1) {
          let dx = points[j].x - points[i].x;
          let dy = points[j].y - points[i].y;
          let distanceSquared = dx * dx + dy * dy;
          if (distanceSquared < 1) {
            dx = ((hashNumber(`${points[i].id}-${points[j].id}`) % 9) - 4) / 4;
            dy = 1;
            distanceSquared = dx * dx + dy * dy;
          }
          const push = repulsion / Math.max(60, distanceSquared);
          force[i].x -= dx * push;
          force[i].y -= dy * push;
          force[j].x += dx * push;
          force[j].y += dy * push;
        }
      }
      for (const edge of usableEdges) {
        const left = points[edge.a];
        const right = points[edge.b];
        const dx = right.x - left.x;
        const dy = right.y - left.y;
        const distance = Math.max(1, Math.hypot(dx, dy));
        const ideal = edge.layer === "DIRECT" ? 80 : edge.layer === "REPORTED" ? 92 : edge.layer === "HISTORICAL" ? 132 : 116;
        const pull = (distance - ideal) * .008 * (1 + Number(edge.weight || 1) * .08);
        const fx = (dx / distance) * pull;
        const fy = (dy / distance) * pull;
        force[edge.a].x += fx;
        force[edge.a].y += fy;
        force[edge.b].x -= fx;
        force[edge.b].y -= fy;
      }
      points.forEach((point, index) => {
        const anchor = anchors[point.kind] || anchors.CLAIM;
        const anchorStrength = point.kind === "CLAIM" ? .0018 : .0045;
        force[index].x += (anchor[0] - point.x) * anchorStrength;
        force[index].y += (anchor[1] - point.y) * anchorStrength;
        force[index].x += (500 - point.x) * .0008;
        force[index].y += (350 - point.y) * .0008;
        point.x = clamp(point.x + clamp(force[index].x, -8, 8) * alpha, 24, 976);
        point.y = clamp(point.y + clamp(force[index].y, -8, 8) * alpha, 24, 676);
      });
    }
    points.forEach(point => positions.set(point.id, {x: point.x, y: point.y}));
    return positions;
  }

  function nodeRadius(node) {
    const degree = Math.sqrt(Math.max(1, Number(node.degree || 1)));
    if (node.kind === "SOURCE") return clamp(5 + degree, 6, 12);
    if (node.kind === "CLAIM") return clamp(7 + degree * 1.4, 8, 17);
    if (node.kind === "ANOMALY") return clamp(10 + degree, 12, 21);
    if (node.kind === "HISTORICAL") return clamp(7 + degree, 8, 15);
    return clamp(10 + degree * 1.7, 12, 24);
  }

  function shapeFor(node, radius) {
    if (node.kind === "ACTOR") return svgNode("rect", {class: "shape", x: -radius, y: -radius, width: radius * 2, height: radius * 2});
    if (node.kind === "DOMAIN") return svgNode("polygon", {class: "shape", points: `0,${-radius} ${radius},0 0,${radius} ${-radius},0`});
    if (node.kind === "REGION") return svgNode("rect", {class: "shape", x: -radius * 1.15, y: -radius * .72, width: radius * 2.3, height: radius * 1.44, rx: radius * .3});
    if (node.kind === "ANOMALY") {
      const points = Array.from({length: 6}, (_, index) => {
        const angle = Math.PI / 3 * index - Math.PI / 2;
        return `${Math.cos(angle) * radius},${Math.sin(angle) * radius}`;
      }).join(" ");
      return svgNode("polygon", {class: "shape", points});
    }
    return svgNode("circle", {class: "shape", r: radius});
  }

  function renderGraph() {
    state.visible = deriveVisibleGraph();
    state.positions = calculateLayout(state.visible.nodes, state.visible.edges);
    state.nodeElements.clear();
    state.edgeElements.clear();
    edgeLayer.replaceChildren();
    nodeLayer.replaceChildren();

    for (const edge of state.visible.edges) {
      const source = state.positions.get(edge.source);
      const target = state.positions.get(edge.target);
      if (!source || !target) continue;
      const line = svgNode("line", {
        class: `edge ${LAYER_CLASS[edge.layer] || "reported"}`,
        x1: source.x, y1: source.y, x2: target.x, y2: target.y,
        opacity: clamp(.18 + Number(edge.confidence || 0) / 150, .2, .86),
        "data-id": edge.id,
      });
      const title = svgNode("title");
      title.textContent = `${edge.layer} // ${edge.relationship} // ${edge.explanation}`;
      line.appendChild(title);
      edgeLayer.appendChild(line);
      state.edgeElements.set(edge.id, line);
    }

    for (const node of state.visible.nodes) {
      const position = state.positions.get(node.id);
      if (!position) continue;
      const radius = nodeRadius(node);
      const group = svgNode("g", {
        class: `node ${KIND_CLASS[node.kind] || "claim"}${state.mode === "masks" ? " masked" : ""}`,
        transform: `translate(${position.x} ${position.y})`,
        tabindex: "0",
        role: "button",
        "aria-label": `${node.kind}: ${displayLabel(node, node.id === state.selected)}`,
        "data-id": node.id,
      });
      group.appendChild(shapeFor(node, radius));
      const title = svgNode("title");
      title.textContent = `${node.kind} // ${displayLabel(node, node.id === state.selected)} // ${node.degree || 0} connections`;
      group.appendChild(title);
      const shouldLabel = state.mode !== "edges" && (node.kind !== "CLAIM" || Number(node.degree || 0) >= 4 || state.visible.nodes.length < 85 || node.id === state.selected);
      if (shouldLabel) {
        const text = svgNode("text", {y: radius + 16});
        text.textContent = shortLabel(node);
        group.appendChild(text);
      }
      group.addEventListener("click", event => {
        event.stopPropagation();
        selectNode(node.id, true);
      });
      group.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          selectNode(node.id, true);
        }
      });
      group.addEventListener("pointerenter", () => applyHover(node.id));
      group.addEventListener("pointerleave", clearHover);
      group.addEventListener("pointerdown", event => beginNodeDrag(event, node.id));
      nodeLayer.appendChild(group);
      state.nodeElements.set(node.id, group);
    }

    $("graphEmpty").classList.toggle("show", state.visible.nodes.length === 0);
    $("visibleStats").textContent = `${state.visible.nodes.length} NODES // ${state.visible.edges.length} EDGES // ${componentCount(state.visible.nodes, state.visible.edges)} COMPONENTS`;
    applySelectionClasses();
    applyTransform();
    renderDetail();
  }

  function componentCount(nodes, edges) {
    const adjacency = new Map(nodes.map(node => [node.id, []]));
    edges.forEach(edge => {
      adjacency.get(edge.source)?.push(edge.target);
      adjacency.get(edge.target)?.push(edge.source);
    });
    const seen = new Set();
    let count = 0;
    for (const node of nodes) {
      if (seen.has(node.id)) continue;
      count += 1;
      const queue = [node.id];
      seen.add(node.id);
      while (queue.length) {
        const current = queue.shift();
        for (const next of adjacency.get(current) || []) {
          if (!seen.has(next)) {
            seen.add(next);
            queue.push(next);
          }
        }
      }
    }
    return count;
  }

  function applyHover(id) {
    if (state.traceNodes.size) return;
    const neighbors = new Set([id]);
    const relatedEdges = new Set();
    for (const edge of state.visible.edges) {
      if (edge.source === id || edge.target === id) {
        neighbors.add(edge.source);
        neighbors.add(edge.target);
        relatedEdges.add(edge.id);
      }
    }
    state.nodeElements.forEach((element, nodeId) => element.classList.toggle("dim", !neighbors.has(nodeId)));
    state.edgeElements.forEach((element, edgeId) => element.classList.toggle("dim", !relatedEdges.has(edgeId)));
  }

  function clearHover() {
    state.nodeElements.forEach(element => element.classList.remove("dim"));
    state.edgeElements.forEach(element => element.classList.remove("dim"));
  }

  function applySelectionClasses() {
    state.nodeElements.forEach((element, id) => {
      element.classList.toggle("selected", id === state.selected);
      element.classList.toggle("origin", id === state.origin);
      element.classList.toggle("trace", state.traceNodes.has(id));
    });
    state.edgeElements.forEach((element, id) => element.classList.toggle("trace", state.traceEdges.has(id)));
    if (state.traceNodes.size) {
      state.nodeElements.forEach((element, id) => element.classList.toggle("dim", !state.traceNodes.has(id)));
      state.edgeElements.forEach((element, id) => element.classList.toggle("dim", !state.traceEdges.has(id)));
    } else {
      clearHover();
    }
  }

  function selectNode(id, allowTrace) {
    if (!nodeById(id)) return;
    state.selected = id;
    state.revealSelected = false;
    if (allowTrace && state.origin && state.origin !== id) {
      const path = shortestPath(state.origin, id);
      state.traceNodes = new Set(path.nodes);
      state.traceEdges = new Set(path.edges);
      $("traceStatus").textContent = path.nodes.length ? `TRACE // ${path.edges.length} HOPS` : "TRACE // NO PATH";
    }
    applySelectionClasses();
    renderDetail();
  }

  function shortestPath(start, target) {
    const adjacency = new Map(state.visible.nodes.map(node => [node.id, []]));
    for (const edge of state.visible.edges) {
      adjacency.get(edge.source)?.push({node: edge.target, edge: edge.id});
      adjacency.get(edge.target)?.push({node: edge.source, edge: edge.id});
    }
    const queue = [start];
    const previous = new Map([[start, null]]);
    while (queue.length) {
      const current = queue.shift();
      if (current === target) break;
      for (const next of adjacency.get(current) || []) {
        if (!previous.has(next.node)) {
          previous.set(next.node, {node: current, edge: next.edge});
          queue.push(next.node);
        }
      }
    }
    if (!previous.has(target)) return {nodes: [], edges: []};
    const nodes = [];
    const edges = [];
    let cursor = target;
    while (cursor) {
      nodes.push(cursor);
      const step = previous.get(cursor);
      if (!step) break;
      edges.push(step.edge);
      cursor = step.node;
    }
    return {nodes: nodes.reverse(), edges: edges.reverse()};
  }

  function clearTrace(update = true) {
    state.origin = null;
    state.traceNodes = new Set();
    state.traceEdges = new Set();
    $("traceStatus").textContent = "TRACE // IDLE";
    if (update) {
      applySelectionClasses();
      renderDetail();
    }
  }

  function addBadge(parent, text) {
    parent.appendChild(htmlNode("span", "badge", text));
  }

  function addAction(parent, label, handler) {
    const button = htmlNode("button", "", label);
    button.type = "button";
    button.addEventListener("click", handler);
    parent.appendChild(button);
  }

  function connectionRows(node) {
    return state.visible.edges
      .filter(edge => edge.source === node.id || edge.target === node.id)
      .map(edge => ({edge, other: nodeById(edge.source === node.id ? edge.target : edge.source)}))
      .filter(row => row.other)
      .sort((left, right) => Number(right.other.degree || 0) - Number(left.other.degree || 0) || left.other.id.localeCompare(right.other.id));
  }

  function renderDetail() {
    detail.replaceChildren();
    const selected = nodeById(state.selected);
    if (!selected) {
      detail.appendChild(htmlNode("p", "micro", "IDENTITY-SUPPRESSED ANALYSIS"));
      detail.appendChild(htmlNode("h2", "", state.mode === "edges" ? "THE SHAPE BEFORE THE STORY" : "STRUCTURAL OVERVIEW"));
      detail.appendChild(htmlNode("p", "", state.data?.mode_note || "Inspect topology, then restore identity when the structure gives you a specific question."));
      const stats = htmlNode("div", "badge-row");
      addBadge(stats, `${state.data?.stats?.claims || 0} RETAINED CLAIMS`);
      addBadge(stats, `${state.data?.stats?.nodes || 0} TOTAL NODES`);
      addBadge(stats, `${state.data?.stats?.edges || 0} LABELED EDGES`);
      detail.appendChild(stats);
      const section = htmlNode("section", "detail-section");
      section.appendChild(htmlNode("h3", "", "HIGHEST-LOAD BRIDGES"));
      section.appendChild(htmlNode("p", "", "High degree identifies structural load in this dataset, not command authority or culpability."));
      const list = htmlNode("ul", "bridge-list");
      for (const bridge of (state.data?.bridges || []).slice(0, 10)) {
        const node = nodeById(bridge.id);
        if (!node) continue;
        const item = document.createElement("li");
        const button = document.createElement("button");
        button.type = "button";
        const label = htmlNode("span", "", state.mode === "names" ? bridge.label : bridge.masked_label);
        const meta = htmlNode("small", "", `${bridge.kind} // ${bridge.degree}`);
        button.append(label, meta);
        button.addEventListener("click", () => {
          if (!state.visible.nodes.some(row => row.id === bridge.id)) {
            state.scope = "full";
            $("scope").value = "full";
            renderGraph();
          }
          selectNode(bridge.id, false);
        });
        item.appendChild(button);
        list.appendChild(item);
      }
      section.appendChild(list);
      detail.appendChild(section);
      return;
    }

    detail.appendChild(htmlNode("p", "micro", `${selected.kind} // ${selected.masked_label}`));
    detail.appendChild(htmlNode("h2", "", displayLabel(selected, true)));
    const badges = htmlNode("div", "badge-row");
    addBadge(badges, `${selected.degree || 0} CONNECTIONS`);
    if (selected.claim_count) addBadge(badges, `${selected.claim_count} CLAIM${selected.claim_count === 1 ? "" : "S"}`);
    if (selected.state) addBadge(badges, selected.state);
    if (selected.confidence !== undefined) addBadge(badges, `CONF ${selected.confidence}`);
    if (selected.watch_priority !== undefined) addBadge(badges, `WATCH ${selected.watch_priority}`);
    if (selected.threat_score !== undefined) addBadge(badges, `THREAT ${selected.threat_score}`);
    detail.appendChild(badges);

    const protectedIdentity = state.mode !== "names" && !state.revealSelected;
    if (protectedIdentity) {
      detail.appendChild(htmlNode("p", "", "Identity remains suppressed. Read its degree, edge types, and position first; reveal only when the topology produces a testable question."));
    } else {
      const explanation = selected.classification_reason || selected.description;
      if (explanation) detail.appendChild(htmlNode("p", "", explanation));
      if (selected.material_time) detail.appendChild(htmlNode("p", "micro", `MATERIAL TIME // ${formatDate(selected.material_time)}`));
    }

    const actions = htmlNode("div", "detail-actions");
    if (state.mode !== "names") addAction(actions, state.revealSelected ? "MASK AGAIN" : "REVEAL SELECTED", () => {state.revealSelected = !state.revealSelected; renderGraph();});
    addAction(actions, state.origin === selected.id ? "ORIGIN PINNED" : "PIN AS ORIGIN", () => {
      state.origin = selected.id;
      state.traceNodes = new Set([selected.id]);
      state.traceEdges = new Set();
      $("traceStatus").textContent = `TRACE // ORIGIN ${selected.masked_label}`;
      applySelectionClasses();
      renderDetail();
    });
    if (state.origin) addAction(actions, "CLEAR TRACE", () => clearTrace(true));
    detail.appendChild(actions);

    if (!protectedIdentity && selected.kind === "CLAIM" && (selected.evidence || []).length) {
      const evidenceSection = htmlNode("section", "detail-section");
      evidenceSection.appendChild(htmlNode("h3", "", "DIRECT EVIDENCE"));
      const list = htmlNode("ul", "evidence-list");
      for (const evidence of selected.evidence) {
        const item = document.createElement("li");
        const url = safeUrl(evidence.url);
        const title = evidence.title || "Source observation";
        if (url) {
          const link = htmlNode("a", "", title);
          link.href = url;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          item.appendChild(link);
        } else {
          item.appendChild(htmlNode("span", "", title));
        }
        item.appendChild(htmlNode("small", "", `${evidence.source || "UNRESOLVED SOURCE"} // ${evidence.stance || "REPORT"} // ${evidence.discovery_only ? "DISCOVERY ONLY" : evidence.source_class || "UNCLASSIFIED"}`));
        list.appendChild(item);
      }
      evidenceSection.appendChild(list);
      detail.appendChild(evidenceSection);
    }

    const rows = connectionRows(selected);
    const connectionSection = htmlNode("section", "detail-section");
    connectionSection.appendChild(htmlNode("h3", "", "VISIBLE CONNECTIONS"));
    if (!rows.length) {
      connectionSection.appendChild(htmlNode("p", "", "No connection survives the active filters."));
    } else {
      const list = htmlNode("ul", "connection-list");
      for (const {edge, other} of rows.slice(0, 24)) {
        const item = document.createElement("li");
        const button = htmlNode("button", "connection");
        button.type = "button";
        button.append(htmlNode("strong", "", displayLabel(other)), htmlNode("span", "", `${edge.layer} // ${edge.relationship}`));
        button.title = edge.explanation;
        button.addEventListener("click", () => selectNode(other.id, true));
        item.appendChild(button);
        list.appendChild(item);
      }
      connectionSection.appendChild(list);
    }
    detail.appendChild(connectionSection);
  }

  function renderStateFilters() {
    const parent = $("stateFilters");
    parent.querySelectorAll("button").forEach(button => button.remove());
    for (const name of state.data.states || []) {
      const count = Number(state.data.stats?.state_counts?.[name] || 0);
      const button = htmlNode("button", `filter-button${state.activeStates.has(name) ? " active" : ""}`, `${name} ${count}`);
      button.type = "button";
      button.dataset.state = name;
      button.setAttribute("aria-pressed", String(state.activeStates.has(name)));
      button.addEventListener("click", () => {
        if (state.activeStates.has(name)) state.activeStates.delete(name);
        else state.activeStates.add(name);
        button.classList.toggle("active", state.activeStates.has(name));
        button.setAttribute("aria-pressed", String(state.activeStates.has(name)));
        clearTrace(false);
        renderGraph();
      });
      parent.appendChild(button);
    }
  }

  function syncLayerControls() {
    document.querySelectorAll("[data-layer]").forEach(button => {
      const active = state.activeLayers.has(button.dataset.layer);
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    document.querySelectorAll("[data-toggle-layer]").forEach(button => button.classList.toggle("off", !state.activeLayers.has(button.dataset.toggleLayer)));
  }

  function toggleLayer(layer) {
    if (state.activeLayers.has(layer)) state.activeLayers.delete(layer);
    else state.activeLayers.add(layer);
    syncLayerControls();
    clearTrace(false);
    renderGraph();
  }

  function applyTransform() {
    viewport.setAttribute("transform", `translate(${state.transform.x} ${state.transform.y}) scale(${state.transform.scale})`);
  }

  function zoomAt(factor, x = 500, y = 350) {
    const old = state.transform.scale;
    const next = clamp(old * factor, .55, 4);
    const worldX = (x - state.transform.x) / old;
    const worldY = (y - state.transform.y) / old;
    state.transform.x = x - worldX * next;
    state.transform.y = y - worldY * next;
    state.transform.scale = next;
    applyTransform();
  }

  function fitGraph() {
    state.transform = {x: 0, y: 0, scale: 1};
    applyTransform();
  }

  function svgCoordinates(event) {
    const rect = graph.getBoundingClientRect();
    return {x: (event.clientX - rect.left) * 1000 / rect.width, y: (event.clientY - rect.top) * 700 / rect.height};
  }

  function worldCoordinates(event) {
    const point = svgCoordinates(event);
    return {x: (point.x - state.transform.x) / state.transform.scale, y: (point.y - state.transform.y) / state.transform.scale};
  }

  function beginNodeDrag(event, id) {
    if (event.button !== 0) return;
    event.stopPropagation();
    state.draggingNode = {id, pointerId: event.pointerId};
    graph.setPointerCapture(event.pointerId);
  }

  function updateDraggedNode(event) {
    const drag = state.draggingNode;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const point = worldCoordinates(event);
    const position = {x: clamp(point.x, 12, 988), y: clamp(point.y, 12, 688)};
    state.positions.set(drag.id, position);
    state.nodeElements.get(drag.id)?.setAttribute("transform", `translate(${position.x} ${position.y})`);
    for (const edge of state.visible.edges) {
      if (edge.source !== drag.id && edge.target !== drag.id) continue;
      const line = state.edgeElements.get(edge.id);
      const source = state.positions.get(edge.source);
      const target = state.positions.get(edge.target);
      if (line && source && target) {
        line.setAttribute("x1", source.x);
        line.setAttribute("y1", source.y);
        line.setAttribute("x2", target.x);
        line.setAttribute("y2", target.y);
      }
    }
  }

  function endPointer(event) {
    if (state.draggingNode?.pointerId === event.pointerId) state.draggingNode = null;
    if (state.panning?.pointerId === event.pointerId) {
      state.panning = null;
      graph.classList.remove("panning");
    }
    if (graph.hasPointerCapture?.(event.pointerId)) graph.releasePointerCapture(event.pointerId);
  }

  function bindControls() {
    $("identityMode").querySelectorAll("button").forEach(button => button.addEventListener("click", () => {
      state.mode = button.dataset.mode;
      state.revealSelected = false;
      $("identityMode").querySelectorAll("button").forEach(item => item.classList.toggle("active", item === button));
      $("modeReadout").textContent = MODE_LABELS[state.mode];
      renderGraph();
    }));
    $("search").addEventListener("input", event => {
      state.query = event.target.value;
      clearTrace(false);
      renderGraph();
    });
    $("scope").addEventListener("change", event => {
      state.scope = event.target.value;
      clearTrace(false);
      renderGraph();
    });
    $("claimLimit").addEventListener("input", event => {
      state.claimLimit = Number(event.target.value);
      $("claimLimitValue").textContent = state.claimLimit;
      clearTrace(false);
      renderGraph();
    });
    document.querySelectorAll("[data-layer]").forEach(button => button.addEventListener("click", () => toggleLayer(button.dataset.layer)));
    document.querySelectorAll("[data-toggle-layer]").forEach(button => button.addEventListener("click", () => toggleLayer(button.dataset.toggleLayer)));
    $("reset").addEventListener("click", () => {
      state.mode = "edges";
      state.scope = "core";
      state.claimLimit = 90;
      state.query = "";
      state.selected = null;
      state.revealSelected = false;
      state.activeLayers = new Set(["DIRECT", "REPORTED", "ANALYTICAL"]);
      state.activeStates = new Set((state.data.states || []).filter(name => !["REFUTED", "DORMANT"].includes(name)));
      $("search").value = "";
      $("scope").value = "core";
      $("claimLimit").value = "90";
      $("claimLimitValue").textContent = "90";
      $("identityMode").querySelectorAll("button").forEach(button => button.classList.toggle("active", button.dataset.mode === "edges"));
      $("modeReadout").textContent = MODE_LABELS.edges;
      clearTrace(false);
      fitGraph();
      renderStateFilters();
      syncLayerControls();
      renderGraph();
    });
    $("zoomIn").addEventListener("click", () => zoomAt(1.25));
    $("zoomOut").addEventListener("click", () => zoomAt(.8));
    $("fit").addEventListener("click", fitGraph);
    graph.addEventListener("wheel", event => {
      event.preventDefault();
      const point = svgCoordinates(event);
      zoomAt(event.deltaY < 0 ? 1.12 : .89, point.x, point.y);
    }, {passive: false});
    graph.addEventListener("pointerdown", event => {
      if (event.button !== 0 || event.target.closest?.(".node")) return;
      const start = svgCoordinates(event);
      state.panning = {pointerId: event.pointerId, startX: start.x, startY: start.y, x: state.transform.x, y: state.transform.y};
      graph.setPointerCapture(event.pointerId);
      graph.classList.add("panning");
    });
    graph.addEventListener("pointermove", event => {
      if (state.draggingNode) {
        updateDraggedNode(event);
        return;
      }
      if (!state.panning || state.panning.pointerId !== event.pointerId) return;
      const point = svgCoordinates(event);
      state.transform.x = state.panning.x + point.x - state.panning.startX;
      state.transform.y = state.panning.y + point.y - state.panning.startY;
      applyTransform();
    });
    graph.addEventListener("pointerup", endPointer);
    graph.addEventListener("pointercancel", endPointer);
    graph.addEventListener("click", event => {
      if (event.target === graph || event.target === viewport || event.target === edgeLayer || event.target === nodeLayer) {
        state.selected = null;
        state.revealSelected = false;
        applySelectionClasses();
        renderDetail();
      }
    });
  }

  async function boot() {
    bindControls();
    try {
      const [dataResponse, statusResponse] = await Promise.all([
        fetch(DATA_URL, {cache: "no-store"}),
        fetch(STATUS_URL, {cache: "no-store"}),
      ]);
      if (!dataResponse.ok || !statusResponse.ok) throw new Error(`HTTP ${dataResponse.status}/${statusResponse.status}`);
      [state.data, state.status] = await Promise.all([dataResponse.json(), statusResponse.json()]);
      state.activeStates = new Set((state.data.states || []).filter(name => !["REFUTED", "DORMANT"].includes(name)));
      $("engineState").textContent = `${state.status.mode || "UNKNOWN"} // ${state.status.source_health_percent || 0}% COVERAGE`;
      $("generatedAt").textContent = `GRAPH ${formatDate(state.data.generated_at)}`;
      renderStateFilters();
      syncLayerControls();
      renderGraph();
    } catch (error) {
      $("engineState").textContent = "DATA UNAVAILABLE";
      $("generatedAt").textContent = String(error);
      detail.replaceChildren(htmlNode("h2", "", "RELATIONSHIP PRODUCT UNAVAILABLE"), htmlNode("p", "", "The map could not load its generated data. Do not interpret an empty display as evidence of absence."));
      $("graphEmpty").classList.add("show");
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, {once: true});
  else boot();
})();
