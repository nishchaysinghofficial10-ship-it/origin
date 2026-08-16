"use strict";

const FALLBACK_EVALUATION = {
  workflows: {
    baseline: {
      experiments: 1,
      conclusions: [
        "fastest on sparse_random is bfs_unit",
        "fastest on dense_random is bfs_unit",
        "fastest on grid_2d is bfs_unit",
        "fastest on unit_weight is spfa"
      ],
      scoped_conclusions: 0,
      replications: 0,
      self_corrections: 0,
      incorrect_candidates_reported_as_winners: [
        "bfs_unit on sparse_random",
        "bfs_unit on dense_random",
        "bfs_unit on grid_2d"
      ]
    },
    proposal_only: {
      experiments: 0,
      conclusions: [
        "Re-measure the full roster on the two most discriminating regimes with extra trials.",
        "Comparison and move counts are not measured, so rankings cannot be separated from constant factors."
      ],
      scoped_conclusions: 0,
      replications: 0,
      self_corrections: 0,
      incorrect_candidates_reported_as_winners: []
    },
    origin_full: {
      experiments: 6,
      conclusions: [
        "SPFA performs fewer relaxations than Bellman-Ford on sparse random graphs. [scoped and replicated]",
        "The BFS candidate is correct on unit-weight graphs and incorrect on every weighted topology. [scoped and replicated]"
      ],
      scoped_conclusions: 2,
      replications: 3,
      self_corrections: 2,
      incorrect_candidates_reported_as_winners: []
    }
  }
};

const WORKFLOW_COPY = {
  baseline: {
    label: "WORKFLOW A / BENCHMARK ONLY",
    headline: "Fast answers.\nThree wrong winners.",
    note: "A single timing run ranked an algorithm that returned incorrect distances. Speed alone could not notice."
  },
  proposal_only: {
    label: "WORKFLOW B / MODEL PROPOSALS",
    headline: "Useful directions.\nNo tested findings.",
    note: "The model suggested reasonable next steps, but produced no experiment, replication, or evidential conclusion."
  },
  origin_full: {
    label: "WORKFLOW C / ORIGIN FULL LOOP",
    headline: "Fewer conclusions.\nNone falsely crowned.",
    note: "Six experiments exposed an invalid speed winner, replicated the surviving findings, and attached explicit scope."
  }
};

const FALLBACK_STATE = {
  meta: {
    question: "Which single-source shortest-path method wins on which graph topology?",
    phase: "completed",
    stop_reason: "no high-value next experiment remained"
  },
  step: 42,
  hypotheses: {},
  experiments: {},
  evidence: {},
  claims: {},
  falsifications: {},
  decisions: [],
  failures: [],
  budget: { experiments_used: 6, experiments_total: 40, compute_seconds_used: 12.8, compute_seconds_total: 1800 }
};

const stateStore = {
  evaluation: FALLBACK_EVALUATION,
  mission: FALLBACK_STATE,
  events: []
};

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}

async function loadText(url) {
  const response = await fetch(url, { credentials: "same-origin" });
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  return response.text();
}

async function loadEvidence() {
  const results = await Promise.allSettled([
    loadText("data/EVALUATION_RESULTS.json"),
    loadText("data/flagship-state.json"),
    loadText("data/flagship-events.jsonl")
  ]);
  if (results[0].status === "fulfilled") {
    stateStore.evaluation = JSON.parse(results[0].value);
  }
  if (results[1].status === "fulfilled") {
    stateStore.mission = JSON.parse(results[1].value);
  }
  if (results[2].status === "fulfilled") {
    stateStore.events = results[2].value.split("\n").filter(Boolean).map(line => JSON.parse(line));
  }
  updateWorkflow("origin_full");
  renderConsole("overview");
}

function countCollection(value) {
  if (Array.isArray(value)) return value.length;
  return value && typeof value === "object" ? Object.keys(value).length : 0;
}

function workflowMetrics(workflow) {
  const conclusions = Array.isArray(workflow.conclusions) ? workflow.conclusions : [];
  const wrong = Array.isArray(workflow.incorrect_candidates_reported_as_winners)
    ? workflow.incorrect_candidates_reported_as_winners : [];
  return {
    experiments: workflow.experiments || 0,
    conclusions: conclusions.length,
    scoped: workflow.scoped_conclusions || 0,
    replications: workflow.replications || 0,
    corrections: workflow.self_corrections || 0,
    incorrect: wrong.length
  };
}

function updateWorkflow(name) {
  const workflow = stateStore.evaluation.workflows[name];
  if (!workflow) return;
  const copy = WORKFLOW_COPY[name];
  document.querySelectorAll("[data-workflow]").forEach(button => {
    button.setAttribute("aria-selected", String(button.dataset.workflow === name));
  });
  const label = document.querySelector("[data-workflow-label]");
  const headline = document.querySelector("[data-workflow-headline]");
  const note = document.querySelector("[data-workflow-note]");
  if (label) label.textContent = copy.label;
  if (headline) {
    headline.replaceChildren();
    copy.headline.split("\n").forEach((line, index) => {
      if (index) headline.append(document.createElement("br"));
      headline.append(document.createTextNode(line));
    });
  }
  if (note) note.textContent = copy.note;

  const metrics = workflowMetrics(workflow);
  Object.entries(metrics).forEach(([key, value]) => {
    const target = document.querySelector(`[data-metric="${key}"]`);
    if (!target) return;
    target.textContent = String(value).padStart(2, "0");
    target.classList.toggle("is-bad", key === "incorrect" && value > 0);
  });

  const findingList = document.querySelector("[data-findings]");
  if (!findingList) return;
  findingList.replaceChildren();
  const wrong = new Set(workflow.incorrect_candidates_reported_as_winners || []);
  (workflow.conclusions || []).slice(0, 4).forEach(findingText => {
    const finding = el("div", "finding", findingText);
    if (name === "baseline" && [...wrong].some(item => findingText.includes(item.split(" on ")[0]))) {
      finding.classList.add("warning");
    }
    findingList.append(finding);
  });
}

function missionCollections() {
  const mission = stateStore.mission;
  return {
    hypotheses: Object.values(mission.hypotheses || {}),
    experiments: Object.values(mission.experiments || {}),
    evidence: Object.values(mission.evidence || {}),
    falsifications: Object.values(mission.falsifications || {}),
    failures: mission.failures || [],
    decisions: mission.decisions || []
  };
}

function consoleHeader(container, subtitle) {
  const mission = stateStore.mission;
  const top = el("div", "console-topline");
  const copy = el("div");
  copy.append(el("h3", "", mission.meta?.question || FALLBACK_STATE.meta.question));
  copy.append(el("p", "", subtitle));
  top.append(copy);
  top.append(el("span", "phase-badge", String(mission.meta?.phase || "completed").toUpperCase()));
  container.append(top);
}

function renderOverview(container) {
  const mission = stateStore.mission;
  const collections = missionCollections();
  consoleHeader(container, `STEP ${mission.step || 0} · STOP: ${mission.meta?.stop_reason || "active"}`);
  const stats = el("div", "console-stat-grid");
  [
    ["Hypotheses", countCollection(mission.hypotheses)],
    ["Experiments", mission.budget?.experiments_used ?? collections.experiments.length],
    ["Evidence items", countCollection(mission.evidence)],
    ["Falsifications", collections.falsifications.length]
  ].forEach(([label, value]) => {
    const card = el("div", "console-stat");
    card.append(el("small", "", label), el("strong", "", String(value).padStart(2, "0")));
    stats.append(card);
  });
  container.append(stats);
  container.append(el("p", "console-section-title", "ACCEPTED FINDINGS / WITH SCOPE"));
  const table = el("table", "console-table");
  const head = el("tr");
  ["ID", "STATUS", "STATEMENT", "SCOPE"].forEach(value => head.append(el("th", "", value)));
  table.append(head);
  const accepted = collections.hypotheses.filter(h => ["accepted_with_scope", "provisionally_supported"].includes(h.status));
  (accepted.length ? accepted : [
    { id: "hyp_spfa", status: "accepted_with_scope", statement: "SPFA uses fewer relaxations than Bellman-Ford on sparse random graphs.", scope: "Original topology + held-out long_chain and scale_free" },
    { id: "hyp_bfs", status: "accepted_with_scope", statement: "BFS is correct only when every edge has unit weight.", scope: "Unit-weight graphs; rejected on weighted topologies" }
  ]).slice(0, 4).forEach(hypothesis => {
    const row = el("tr");
    [hypothesis.id, hypothesis.status, hypothesis.statement, hypothesis.scope || "—"].forEach(value => row.append(el("td", "", value)));
    table.append(row);
  });
  container.append(table);
}

function renderHypotheses(container) {
  const hypotheses = missionCollections().hypotheses;
  consoleHeader(container, "COMPETING HYPOTHESES · STATUS CHANGES PRESERVED");
  container.append(el("p", "console-section-title", "HYPOTHESIS LEDGER"));
  const table = el("table", "console-table");
  const head = el("tr");
  ["ID", "STATUS", "STATEMENT", "EVIDENCE +/−"].forEach(value => head.append(el("th", "", value)));
  table.append(head);
  (hypotheses.length ? hypotheses : [
    { id: "hyp_heap", status: "rejected", statement: "Heap Dijkstra is fastest on sparse random graphs." },
    { id: "hyp_array", status: "rejected", statement: "Array Dijkstra beats heap Dijkstra on dense graphs." },
    { id: "hyp_bfs", status: "accepted_with_scope", statement: "BFS is correct on unit-weight graphs only." },
    { id: "hyp_spfa", status: "accepted_with_scope", statement: "SPFA uses fewer relaxations on sparse random graphs." }
  ]).forEach(hypothesis => {
    const support = (hypothesis.supporting_evidence || []).length;
    const contradict = (hypothesis.contradicting_evidence || []).length;
    const row = el("tr");
    [hypothesis.id, hypothesis.status, hypothesis.statement, `${support}/${contradict}`].forEach(value => row.append(el("td", "", value)));
    table.append(row);
  });
  container.append(table);
}

function renderTimeline(container) {
  consoleHeader(container, "APPEND-ONLY EVENT LOG · LATEST EVENTS");
  container.append(el("p", "console-section-title", "RESEARCH TIMELINE"));
  const events = stateStore.events.length ? stateStore.events.slice(-12).reverse() : [
    { step: 42, kind: "transition", detail: "Final review completed; no high-value experiment remains." },
    { step: 41, kind: "falsification", detail: "BFS correctness boundary did not extend to weighted held-out graphs." },
    { step: 38, kind: "replication", detail: "SPFA relaxation finding reproduced with an independent seed." },
    { step: 27, kind: "hypothesis_rejected", detail: "Heap Dijkstra speed claim did not clear the significance gate." }
  ];
  events.forEach((event, index) => {
    const row = el("div", "timeline-row");
    row.append(el("span", "", `#${event.step ?? events.length - index}`));
    row.append(el("b", "", event.kind || event.event || "event"));
    row.append(el("div", "", event.detail || event.description || event.message || "Recorded event"));
    container.append(row);
  });
}

function renderProvenance(container) {
  consoleHeader(container, "EVERY FINDING RESOLVES TO DURABLE ARTIFACTS");
  container.append(el("p", "console-section-title", "VERIFICATION CHAIN"));
  [
    ["01 / PREREGISTRATION", "Question, metrics, held-out conditions, budgets and decision rules were stored before any workflow ran."],
    ["02 / EXPERIMENT ARTIFACTS", "Each experiment keeps generated code, specification, seed, raw result, stdout, and confinement profile."],
    ["03 / STATE + EVENT LOG", "Atomic state snapshots are cross-checked against an append-only event timeline and browsable per-type views."],
    ["04 / REPLAY", "A stored experiment can be executed again and compared by exact output digest and statistical relationship."],
    ["05 / DOSSIER", "The final report cites the evidence ledger, scope, contradictions, cautions, budget use, and explicit stop reason."]
  ].forEach(([title, description]) => {
    const card = el("div", "provenance-card");
    card.append(el("span", "", title), el("h4", "", title.split(" / ")[1]), el("p", "", description));
    container.append(card);
  });
}

function renderConsole(tab) {
  const container = document.querySelector("[data-console-content]");
  if (!container) return;
  document.querySelectorAll("[data-console-tab]").forEach(button => {
    button.classList.toggle("active", button.dataset.consoleTab === tab);
  });
  container.replaceChildren();
  if (tab === "hypotheses") renderHypotheses(container);
  else if (tab === "timeline") renderTimeline(container);
  else if (tab === "provenance") renderProvenance(container);
  else renderOverview(container);
}

function setupNavigation() {
  const toggle = document.querySelector("[data-nav-toggle]");
  const nav = document.querySelector("[data-nav]");
  toggle?.addEventListener("click", () => {
    const open = toggle.getAttribute("aria-expanded") !== "true";
    toggle.setAttribute("aria-expanded", String(open));
    nav?.classList.toggle("is-open", open);
  });
  nav?.querySelectorAll("a").forEach(link => link.addEventListener("click", () => {
    toggle?.setAttribute("aria-expanded", "false");
    nav.classList.remove("is-open");
  }));
  const header = document.querySelector("[data-header]");
  window.addEventListener("scroll", () => header?.classList.toggle("is-stuck", window.scrollY > 180), { passive: true });
}

function setupReveal() {
  const elements = document.querySelectorAll(".reveal");
  elements.forEach(node => node.style.setProperty("--delay", `${node.dataset.delay || 0}ms`));
  if (!("IntersectionObserver" in window)) {
    elements.forEach(node => node.classList.add("is-visible"));
    return;
  }
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: .12 });
  elements.forEach(node => observer.observe(node));
}

function setupInteractions() {
  document.querySelectorAll("[data-workflow]").forEach(button => {
    button.addEventListener("click", () => updateWorkflow(button.dataset.workflow));
  });
  document.querySelectorAll("[data-console-tab]").forEach(button => {
    button.addEventListener("click", () => renderConsole(button.dataset.consoleTab));
  });
}

function restoreHashPosition() {
  if (!window.location.hash) return;
  let id;
  try {
    id = decodeURIComponent(window.location.hash.slice(1));
  } catch (_error) {
    return;
  }
  const target = document.getElementById(id);
  if (!target) return;
  requestAnimationFrame(() => target.scrollIntoView({block: "start"}));
}

setupNavigation();
setupReveal();
setupInteractions();
renderConsole("overview");
loadEvidence().catch(error => {
  console.warn("Using embedded verified snapshot because evidence files could not be loaded.", error);
}).finally(restoreHashPosition);
window.addEventListener("load", restoreHashPosition, {once: true});
