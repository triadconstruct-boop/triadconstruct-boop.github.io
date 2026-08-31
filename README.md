# triadconstruct-boop.github.io<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="A terminal-style strategic intelligence archive for the Ronin 1:1-world setting.">
  <title>Ronin World Watch</title>
  <style>
    :root {
      color-scheme: dark;
      --background: #030000;
      --foreground: #ff2a2a;
      --soft: #b82c2c;
      --muted: #7d2020;
      --border: #5d1010;
      --panel: #070101;
    }

    * { box-sizing: border-box; }
    html { background: var(--background); }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--background);
      color: var(--foreground);
      font-family: "Courier New", Courier, monospace;
    }
    button, a { font: inherit; }
    ::selection { background: var(--foreground); color: var(--background); }

    .terminal {
      position: relative;
      width: min(1180px, 100%);
      min-height: 100vh;
      margin: 0 auto;
      padding: 34px clamp(18px, 4vw, 52px) 28px;
      overflow: hidden;
      text-shadow: 0 0 8px rgba(255, 20, 20, .28);
    }
    .terminal::before {
      content: "";
      position: fixed;
      inset: 0;
      z-index: 20;
      pointer-events: none;
      background: radial-gradient(circle at center, transparent 42%, rgba(70, 0, 0, .16) 100%);
    }
    .scanlines {
      position: fixed;
      inset: 0;
      z-index: 19;
      pointer-events: none;
      opacity: .17;
      background: repeating-linear-gradient(to bottom, transparent 0, transparent 3px, rgba(255, 60, 60, .16) 4px);
    }

    header {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 28px;
      border: 1px solid var(--border);
      border-left: 5px solid var(--foreground);
      padding: 22px 24px 18px;
      background: linear-gradient(90deg, rgba(80, 0, 0, .16), transparent 68%);
    }
    .eyebrow { margin: 0 0 7px; color: #a72a2a; font-size: .72rem; letter-spacing: .18em; }
    h1 { margin: 0; font-size: clamp(2.35rem, 7vw, 5.8rem); line-height: .88; letter-spacing: -.07em; }
    .system-readout { display: grid; gap: 8px; justify-items: end; color: #c72c2c; font-size: .75rem; white-space: nowrap; }
    .status-dot { display: inline-block; width: 7px; height: 7px; margin-right: 7px; background: var(--foreground); box-shadow: 0 0 10px var(--foreground); animation: pulse 1.8s ease-in-out infinite; }

    .status-grid { display: grid; grid-template-columns: repeat(4, 1fr); border: 1px solid var(--border); border-top: 0; }
    .status-grid > div { min-height: 82px; padding: 15px 18px; border-right: 1px solid var(--border); display: flex; flex-direction: column; justify-content: space-between; }
    .status-grid > div:last-child { border-right: 0; }
    .status-grid span { color: #8f2424; font-size: .66rem; letter-spacing: .12em; }
    .status-grid strong { color: #ff3434; font-size: clamp(1.05rem, 2.2vw, 1.75rem); letter-spacing: -.04em; }

    .controls { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin: 30px 0 14px; padding-bottom: 12px; border-bottom: 1px dashed #4b0d0d; }
    .prompt { color: #9d2929; font-size: .75rem; }
    .filters { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 4px; }
    .filter {
      border: 0;
      border-radius: 0;
      padding: 5px 7px;
      background: transparent;
      color: #982727;
      font-size: .7rem;
      cursor: pointer;
    }
    .filter:hover, .filter.active { background: #1f0303; color: var(--foreground); text-shadow: 0 0 8px rgba(255, 42, 42, .6); }
    .filter:focus-visible { outline: 1px solid var(--foreground); outline-offset: 2px; }

    .feed-heading { display: flex; justify-content: space-between; align-items: baseline; gap: 24px; padding: 13px 0; }
    .feed-heading h2 { margin: 0; font-size: .82rem; letter-spacing: .16em; }
    .feed-heading span { color: var(--muted); font-size: .64rem; }

    #feed { border-top: 1px solid var(--border); }
    details { border-bottom: 1px solid var(--border); }
    summary { list-style: none; cursor: pointer; }
    summary::-webkit-details-marker { display: none; }
    summary:hover { background: rgba(65, 0, 0, .22); }
    summary:focus-visible { outline: 1px solid var(--foreground); outline-offset: -1px; }
    .trigger { display: grid; grid-template-columns: 44px minmax(0, 1fr) 112px 20px; gap: 16px; padding: 21px 0; }
    .index { color: #6c1919; font-size: .72rem; padding-top: 4px; }
    .classification { display: inline-block; margin-bottom: 7px; padding: 2px 5px; border: 1px solid #941d1d; color: var(--foreground); font-size: .58rem; letter-spacing: .12em; }
    .classification.warning { color: #ff6868; border-style: dashed; }
    .record-title h3 { margin: 0; font-size: clamp(.94rem, 2vw, 1.2rem); line-height: 1.25; letter-spacing: .02em; }
    .record-title p { margin: 7px 0 0; color: #812020; font-size: .66rem; }
    .confidence { color: #7f2020; font-size: .58rem; line-height: 1.5; text-align: right; }
    .confidence strong { color: #c72d2d; font-size: .72rem; }
    .chevron { color: #a82b2b; transition: transform .2s ease; }
    details[open] .chevron { transform: rotate(180deg); }

    .content { padding: 0 34px 25px 60px; }
    .brief-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1px; border: 1px solid #3e0909; background: #3e0909; }
    .brief-grid section { min-width: 0; padding: 18px 20px; background: var(--panel); }
    .brief-grid h4 { margin: 0 0 11px; color: #ff3636; font-size: .68rem; letter-spacing: .1em; }
    .brief-grid p, .brief-grid li { color: var(--soft); font-size: .76rem; line-height: 1.65; }
    .brief-grid p { margin: 0; }
    .brief-grid ul { margin: 0; padding: 0; list-style: none; }
    .brief-grid li { position: relative; margin-top: 5px; padding-left: 14px; }
    .brief-grid li::before { content: ">"; position: absolute; left: 0; color: #681616; }
    .sources { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; padding-top: 13px; color: #641616; font-size: .62rem; }
    .sources a { color: #bc2c2c; text-decoration: none; border-bottom: 1px dotted #7f1c1c; }
    .sources a:hover, .sources a:focus-visible { color: #ff4c4c; border-color: #ff4c4c; outline: none; }

    footer { display: flex; justify-content: space-between; gap: 24px; margin-top: 30px; padding-top: 16px; border-top: 1px dashed #4b0d0d; color: #671818; font-size: .62rem; }
    .empty { padding: 36px 0; color: var(--muted); font-size: .75rem; }

    @keyframes pulse { 0%, 100% { opacity: .35; } 50% { opacity: 1; } }

    @media (max-width: 700px) {
      .terminal { padding: 18px 12px 22px; }
      header { align-items: flex-start; padding: 18px 15px; flex-direction: column; }
      .system-readout { justify-items: start; }
      .status-grid { grid-template-columns: repeat(2, 1fr); }
      .status-grid > div:nth-child(2) { border-right: 0; }
      .status-grid > div:nth-child(-n+2) { border-bottom: 1px solid var(--border); }
      .controls { align-items: flex-start; flex-direction: column; }
      .filters { justify-content: flex-start; }
      .trigger { grid-template-columns: 32px minmax(0, 1fr) 18px; gap: 8px; }
      .confidence { grid-column: 2; text-align: left; }
      .chevron { grid-column: 3; grid-row: 1; }
      .content { padding: 0 4px 18px 40px; }
      .brief-grid { grid-template-columns: 1fr; }
      footer { flex-direction: column; gap: 6px; }
    }

    @media (prefers-reduced-motion: reduce) {
      .status-dot { animation: none; opacity: 1; }
      .scanlines { display: none; }
      .chevron { transition: none; }
    }
  </style>
</head>
<body>
  <main class="terminal">
    <div class="scanlines" aria-hidden="true"></div>

    <header>
      <div>
        <p class="eyebrow">RONIN // STRATEGIC INTELLIGENCE NODE</p>
        <h1>WORLD WATCH</h1>
      </div>
      <div class="system-readout" aria-label="System status">
        <span><i class="status-dot"></i>SYSTEM ONLINE</span>
        <span id="clock">--:--:-- UTC</span>
      </div>
    </header>

    <section class="status-grid" aria-label="Watch summary">
      <div><span>ARCHIVE</span><strong id="archive-count">00</strong></div>
      <div><span>CONFIRMED</span><strong id="confirmed-count">00</strong></div>
      <div><span>WARNINGS</span><strong id="warning-count">00</strong></div>
      <div><span>SNAPSHOT</span><strong>30.AUG.26</strong></div>
    </section>

    <section class="controls" aria-label="Filter intelligence feed">
      <span class="prompt">root@ronin:~$ filter --class</span>
      <div class="filters">
        <button class="filter active" type="button" data-filter="ALL" aria-pressed="true">[ALL]</button>
        <button class="filter" type="button" data-filter="CONFIRMED" aria-pressed="false">[CONFIRMED]</button>
        <button class="filter" type="button" data-filter="CREDIBLE WARNING" aria-pressed="false">[CREDIBLE WARNING]</button>
      </div>
    </section>

    <section aria-labelledby="feed-title">
      <div class="feed-heading">
        <h2 id="feed-title">INTELLIGENCE FEED</h2>
        <span id="record-count">0 RECORDS RETURNED</span>
      </div>
      <div id="feed"></div>
    </section>

    <footer>
      <span>END OF TRANSMISSION</span>
      <span>STATIC ARCHIVE SNAPSHOT // SOURCES OPEN IN NEW WINDOW</span>
    </footer>
  </main>

  <script>
    "use strict";

    const alerts = [
      {
        id: "ME-260830-02",
        timestamp: "2026-08-30 // 23:07 UTC",
        region: "JORDAN / MIDDLE EAST",
        classification: "CONFIRMED",
        confidence: "MEDIUM–HIGH",
        title: "IRAN RETALIATES AGAINST U.S. BASES IN JORDAN",
        summary: "Iran's Revolutionary Guards reported ballistic-missile attacks on the King Hussein and Al Azraq bases. U.S.-sourced reporting corroborated an attack and said nearly all incoming missiles were intercepted, with no significant impact reported at publication. Detailed U.S. and Jordanian assessments remained pending.",
        significance: "The Larak strike has already produced a direct state-on-state retaliatory exchange. Jordan is now an active combat platform and target, widening the confrontation beyond Iran and the Strait of Hormuz.",
        revisions: [
          "Advance the Iran conflict from renewed escalation to active retaliatory exchange.",
          "Add Jordanian bases and regional air-defense coverage to the operational map.",
          "Increase political pressure on governments hosting U.S. forces.",
          "Model interceptor depletion and widening regional-base exposure.",
          "Connect the exchange to Brent crude moving above $90 per barrel."
        ],
        watch: ["Verified impact and casualties", "Jordan's official response", "Additional Iranian salvos", "U.S. counterstrikes", "Attacks on other Gulf bases", "Evidence Iran deliberately limited damage"],
        sources: [
          ["REUTERS // IRGC STATEMENT", "https://www.reuters.com/world/middle-east/irans-irgc-says-it-launched-attack-two-us-bases-jordan-2026-08-30/"],
          ["REUTERS // U.S.-SOURCED ACCOUNT", "https://www.reuters.com/world/middle-east/us-forces-strike-two-iranian-launchers-irans-larak-island-us-official-says-2026-08-30/"],
          ["REUTERS // ENERGY MARKET", "https://www.reuters.com/business/energy/oil-jumps-more-than-2-after-us-attack-irans-larak-island-2026-08-30/"]
        ]
      },
      {
        id: "ME-260830-01",
        timestamp: "2026-08-30 // 20:38 UTC",
        region: "IRAN / STRAIT OF HORMUZ",
        classification: "CONFIRMED",
        confidence: "HIGH",
        title: "U.S.–IRAN FIGHTING RESTARTS AT HORMUZ",
        summary: "U.S. forces struck two Iranian launchers on Larak Island, the first acknowledged U.S. strike on Iran since late July. Washington said IRGC forces were preparing rockets carrying sea mines. Iran confirmed casualties and promised retaliation; the alleged mine-laying preparation was not independently verified.",
        significance: "The conflict moved out of a military lull and back toward direct exchange around the world's most consequential energy chokepoint.",
        revisions: ["Mark Hormuz as an active blockade, mining and shipping-pressure zone.", "Raise risk to oil prices, Gulf infrastructure and maritime insurance.", "Model Iran's asymmetric leverage as surviving conventional losses.", "Increase pressure on U.S. readiness and munitions availability elsewhere."],
        watch: ["Renewed mining or vessel attacks", "Gulf infrastructure strikes", "Coalition mine-clearing losses", "Secondary sanctions on Iran's trading partners"],
        sources: [
          ["REUTERS", "https://www.reuters.com/world/middle-east/us-forces-strike-two-iranian-launchers-irans-larak-island-us-official-says-2026-08-30/"],
          ["ASSOCIATED PRESS", "https://apnews.com/article/iran-strait-hormuz-strike-united-states-6b098da673ac3161a266ee459d5eff44"]
        ]
      },
      {
        id: "AF-260830-01",
        timestamp: "2026-08-30 // 16:00 UTC",
        region: "NIGER / SAHEL",
        classification: "CONFIRMED",
        confidence: "MEDIUM–HIGH",
        title: "NIGER'S ARMED FORCES FRACTURE IN THE CAPITAL",
        summary: "Hundreds of disaffected soldiers reportedly attacked Niamey's main military airbase and areas around the presidency. Loyalist forces retook the base after hours of fighting. Russian and Italian personnel use the installation, while Algeria reportedly supplied aircraft assistance.",
        significance: "The Sahel juntas now face an internal military-cohesion problem in addition to insurgency, creating openings for jihadist expansion, deeper Russian intervention and disruption of uranium supply.",
        revisions: ["Downgrade Niger's regime stability and force cohesion.", "Add frontline-force dissatisfaction as an independent pressure node.", "Expand Russia's role from security partner to possible regime-preservation force.", "Connect instability to uranium supply and AES alliance durability."],
        watch: ["Tiani's public status", "Arrests or military purges", "Further mutinies", "Africa Corps deployments", "Jihadist offensives exploiting the fracture"],
        sources: [["REUTERS", "https://www.reuters.com/world/europe/niger-says-it-regains-control-airbase-after-soldiers-mutiny-2026-08-30/"]]
      },
      {
        id: "EU-260830-01",
        timestamp: "2026-08-30 // 17:15 UTC",
        region: "GERMANY / NATO",
        classification: "CREDIBLE WARNING",
        confidence: "MEDIUM",
        title: "EUROPE NEARS ATTRIBUTION OF HYBRID ATTACK",
        summary: "Germany is preparing a coordinated response to the discovery of an explosives-laden drone near a Ukrainian military-supply aircraft at Leipzig/Halle airport. Berlin had not publicly named the perpetrator. German reporting pointed toward possible attribution to Russia, which denied involvement.",
        significance: "Formal attribution would move attacks on European logistics into a coordinated NATO/EU response cycle while remaining below the conventional-war threshold.",
        revisions: ["Add airports, cargo hubs and defense-logistics aircraft to the hybrid-war map.", "Treat attribution, sanctions and covert retaliation as a distinct escalation ladder.", "Separate rising hybrid activity from NATO's assessment of no imminent conventional attack."],
        watch: ["Germany's attribution statement", "Evidence released publicly", "EU sanctions", "Arrests or counterintelligence action", "Repeat attacks on Ukraine-linked logistics"],
        sources: [
          ["REUTERS // GERMANY", "https://www.reuters.com/world/merz-says-germany-finalising-response-suspected-leipzig-attack-2026-08-30/"],
          ["REUTERS // NATO", "https://www.reuters.com/business/aerospace-defense/nato-sees-no-imminent-threat-attack-official-says-2026-08-30/"]
        ]
      },
      {
        id: "CL-260830-01",
        timestamp: "2026-08-30 // 03:45 UTC",
        region: "NEPAL / TIBET",
        classification: "CONFIRMED",
        confidence: "HIGH",
        title: "HIMALAYAN DISASTER BECOMES SECURITY SHOCK",
        summary: "A glacier-collapse disaster across Nepal and Tibet killed nearly 800 people, left more than 3,000 missing and affected an estimated 90,000. Hydropower facilities and a major border corridor were struck, while new debris dams threatened additional downstream flooding.",
        significance: "The event demonstrates how cryosphere failure can simultaneously damage power generation, border access, public health and regional emergency capacity.",
        revisions: ["Add Himalayan glacier instability and cascading landslide dams to the climate-security map.", "Flag hydropower tunnels and mountain border routes as high-consequence infrastructure.", "Model cross-border disaster response as a test of China–Nepal–India coordination."],
        watch: ["Failure of newly formed debris dams", "Hydropower outages", "Border-route disruption", "Public-health strain", "Requests for international assistance"],
        sources: [["REUTERS", "https://www.reuters.com/world/china/china-identifies-countries-261-foreigners-missing-himalayan-mudslide-2026-08-30/"]]
      }
    ];

    const feed = document.getElementById("feed");
    const recordCount = document.getElementById("record-count");

    function escapeHtml(value) {
      return String(value).replace(/[&<>'"]/g, character => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
      })[character]);
    }

    function list(items) {
      return `<ul>${items.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
    }

    function render(filter = "ALL") {
      const visible = alerts.filter(alert => filter === "ALL" || alert.classification === filter);
      recordCount.textContent = `${visible.length} RECORD${visible.length === 1 ? "" : "S"} RETURNED`;

      if (!visible.length) {
        feed.innerHTML = '<p class="empty">NO RECORDS MATCH THE ACTIVE FILTER.</p>';
        return;
      }

      feed.innerHTML = visible.map((alert, index) => `
        <details ${index === 0 ? "open" : ""}>
          <summary>
            <div class="trigger">
              <span class="index">${String(index + 1).padStart(2, "0")}</span>
              <div class="record-title">
                <span class="classification ${alert.classification === "CREDIBLE WARNING" ? "warning" : ""}">${escapeHtml(alert.classification)}</span>
                <h3>${escapeHtml(alert.title)}</h3>
                <p>${escapeHtml(alert.region)} // ${escapeHtml(alert.timestamp)}</p>
              </div>
              <span class="confidence">CONFIDENCE<br><strong>${escapeHtml(alert.confidence)}</strong></span>
              <span class="chevron" aria-hidden="true">⌄</span>
            </div>
          </summary>
          <div class="content">
            <div class="brief-grid">
              <section><h4>&gt; WHAT CHANGED</h4><p>${escapeHtml(alert.summary)}</p></section>
              <section><h4>&gt; WHY IT MATTERS</h4><p>${escapeHtml(alert.significance)}</p></section>
              <section><h4>&gt; REVISE</h4>${list(alert.revisions)}</section>
              <section><h4>&gt; WATCH NEXT</h4>${list(alert.watch)}</section>
            </div>
            <div class="sources">
              <span>SOURCES:</span>
              ${alert.sources.map(([label, href]) => `<a href="${escapeHtml(href)}" target="_blank" rel="noreferrer">${escapeHtml(label)} ↗</a>`).join("")}
            </div>
          </div>
        </details>
      `).join("");
    }

    document.getElementById("archive-count").textContent = String(alerts.length).padStart(2, "0");
    document.getElementById("confirmed-count").textContent = String(alerts.filter(alert => alert.classification === "CONFIRMED").length).padStart(2, "0");
    document.getElementById("warning-count").textContent = String(alerts.filter(alert => alert.classification === "CREDIBLE WARNING").length).padStart(2, "0");

    document.querySelectorAll(".filter").forEach(button => {
      button.addEventListener("click", () => {
        document.querySelectorAll(".filter").forEach(item => {
          item.classList.toggle("active", item === button);
          item.setAttribute("aria-pressed", String(item === button));
        });
        render(button.dataset.filter);
      });
    });

    function updateClock() {
      document.getElementById("clock").textContent = `${new Intl.DateTimeFormat("en-GB", {
        timeZone: "UTC", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false
      }).format(new Date())} UTC`;
    }

    updateClock();
    setInterval(updateClock, 1000);
    render();
  </script>
</body>
</html>
