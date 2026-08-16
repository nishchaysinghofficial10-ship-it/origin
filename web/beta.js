"use strict";

(() => {
  const form = document.querySelector("[data-beta-form]");
  if (!form) return;

  const apiBase = String(window.ORIGIN_BETA?.apiBase || "").replace(/\/$/, "");
  const connection = document.querySelector("[data-beta-connection]");
  const submit = document.querySelector("[data-beta-submit]");
  const message = document.querySelector("[data-beta-message]");
  const empty = document.querySelector("[data-beta-empty]");
  const live = document.querySelector("[data-beta-live]");
  const intakeSteps = [...document.querySelectorAll("[data-intake-step]")];
  const progressItems = [...document.querySelectorAll("[data-intake-progress]")];
  const topic = form.elements.topic;
  const tokenField = form.elements.token;
  const activityList = document.querySelector("[data-beta-activity]");
  const dossierPanel = document.querySelector("[data-dossier-panel]");
  const dossierView = document.querySelector("[data-dossier-view]");
  const dossierMessage = document.querySelector("[data-dossier-message]");
  const reviewHeading = form.querySelector('[data-intake-step="3"] > h3');
  const reviewIntro = form.querySelector('[data-intake-step="3"] > .step-intro');

  const FINAL_STATUSES = new Set(["completed", "cancelled", "failed"]);
  const PHASE_LABELS = {
    queued: "Waiting for the bounded research worker",
    planning_and_web_research: "Searching and synthesizing public evidence",
    finalizing_cited_dossier: "Validating citations and building the dossier",
    completed: "Research complete — cited dossier ready",
    paused: "Research paused at a durable checkpoint",
    cancelled: "Mission cancelled",
    failed: "Research stopped with a recorded error"
  };
  const STATUS_LABELS = {
    queued: "QUEUED",
    running: "RESEARCHING",
    pause_requested: "PAUSING",
    paused: "PAUSED",
    cancel_requested: "CANCELLING",
    completed: "COMPLETE",
    cancelled: "CANCELLED",
    failed: "NEEDS REVIEW"
  };

  let accessToken = "";
  let mission = null;
  let intakeStep = 1;
  let pollTimer = null;
  let serviceAvailable = false;
  let lastActivityKey = "";
  let dossierText = "";
  let dossierMissionId = "";

  function setMessage(text, isError = false) {
    message.textContent = text;
    message.classList.toggle("is-error", isError);
  }

  function setConnection(text, mode) {
    connection.querySelector("strong").textContent = text;
    connection.dataset.mode = mode;
  }

  function formatNumber(value) {
    return new Intl.NumberFormat("en-US").format(Number(value || 0));
  }

  function clean(value) {
    return String(value || "").trim().replace(/\s+/g, " ");
  }

  function selectedPriorities() {
    return [...form.querySelectorAll('input[name="priority"]:checked')]
      .map(input => input.value);
  }

  function buildResearchBrief() {
    const fields = new FormData(form);
    const punctuate = value => /[.!?]$/.test(value) ? value : `${value}.`;
    const parts = [
      `Topic: ${punctuate(clean(fields.get("topic")))}`,
      `Goal: ${punctuate(clean(fields.get("goal")))}`,
      `Scope: ${punctuate(clean(fields.get("scope")))}`,
      `Time: ${punctuate(clean(fields.get("timeframe")))}`,
      `Prioritize: ${punctuate(selectedPriorities().join(", "))}`
    ];
    return parts.join(" ");
  }

  function clearValidity(control) {
    control?.setCustomValidity("");
    control?.removeAttribute("aria-invalid");
  }

  function reject(control, reason) {
    control.setCustomValidity(reason);
    control.setAttribute("aria-invalid", "true");
    control.reportValidity();
    control.focus();
    setMessage(reason, true);
    return false;
  }

  function validateStep(step) {
    setMessage("");
    if (step === 1) {
      clearValidity(topic);
      const value = clean(topic.value);
      if (value.length < 12) {
        return reject(topic, "Please enter a focused research topic using at least 12 characters.");
      }
      return true;
    }
    if (step === 2) {
      for (const [name, reason] of [
        ["goal", "Choose what you want this research to help you accomplish."],
        ["timeframe", "Choose the time horizon that matters to you."],
        ["scope", "Add the people, place, industry, or situation this research should focus on."]
      ]) {
        const control = form.elements[name];
        clearValidity(control);
        if (!clean(control.value) || !control.checkValidity()) return reject(control, reason);
      }
      if (!selectedPriorities().length) {
        const first = form.querySelector('input[name="priority"]');
        return reject(first, "Choose at least one kind of evidence to prioritize.");
      }
      const brief = buildResearchBrief();
      if (brief.length > 500) {
        return reject(form.elements.scope, "Shorten the topic or scope so the complete research brief stays under 500 characters.");
      }
      return true;
    }
    clearValidity(tokenField);
    if (clean(tokenField.value).length < 24) {
      return reject(tokenField, "Paste the private beta access token to launch this mission.");
    }
    return true;
  }

  function updateProgress(step) {
    progressItems.forEach(item => {
      const value = Number(item.dataset.intakeProgress);
      item.classList.toggle("is-complete", value < step);
      if (value === step) item.setAttribute("aria-current", "step");
      else item.removeAttribute("aria-current");
    });
  }

  function showIntakeStep(step, focus = true) {
    intakeStep = step;
    intakeSteps.forEach(panel => {
      panel.hidden = Number(panel.dataset.intakeStep) !== step;
    });
    updateProgress(step);
    if (step === 3) {
      document.querySelector("[data-research-brief]").textContent = buildResearchBrief();
    }
    if (focus) {
      intakeSteps.find(panel => Number(panel.dataset.intakeStep) === step)
        ?.querySelector("h3")?.focus({preventScroll: true});
    }
  }

  function moveIntake(direction) {
    if (direction > 0 && !validateStep(intakeStep)) return;
    showIntakeStep(Math.max(1, Math.min(3, intakeStep + direction)));
  }

  async function api(path, options = {}) {
    if (!accessToken) throw new Error("This research session no longer has an access token.");
    const headers = {"Authorization": `Bearer ${accessToken}`};
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    const response = await fetch(apiBase + path, {
      method: options.method || "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      cache: "no-store",
      credentials: "omit",
      referrerPolicy: "no-referrer"
    });
    const contentType = response.headers.get("Content-Type") || "";
    const payload = contentType.includes("json") ? await response.json() : await response.text();
    if (!response.ok) {
      const reason = payload?.error?.message || `Request failed with HTTP ${response.status}`;
      throw new Error(reason);
    }
    return payload;
  }

  function humanPhase(current) {
    if (current.status === "completed") return PHASE_LABELS.completed;
    if (current.status === "paused") return PHASE_LABELS.paused;
    if (current.status === "cancelled") return PHASE_LABELS.cancelled;
    if (current.status === "failed") return PHASE_LABELS.failed;
    return PHASE_LABELS[current.phase] || clean(current.phase).replaceAll("_", " ") || "Research state received";
  }

  function activeStage(current) {
    if (current.status === "queued") return 1;
    if (["running", "pause_requested", "paused", "cancel_requested"].includes(current.status)) {
      return Number(current.step || 0) >= 7 ? 3 : 2;
    }
    if (current.status === "completed") return 4;
    return Number(current.step || 0) >= 7 ? 3 : 2;
  }

  function renderPipeline(current) {
    const active = activeStage(current);
    const failed = ["failed", "cancelled"].includes(current.status);
    [...document.querySelectorAll("[data-live-stage]")].forEach((item, index) => {
      const stage = index + 1;
      item.classList.toggle("is-complete", current.status === "completed" || stage < active);
      item.classList.toggle("is-current", current.status !== "completed" && stage === active);
      item.classList.toggle("is-error", failed && stage === active);
    });
  }

  function appendActivity(current) {
    const key = [current.status, current.phase, current.step, current.stop_reason, current.error].join("|");
    if (key === lastActivityKey) return;
    lastActivityKey = key;
    const row = document.createElement("li");
    const timestamp = document.createElement("time");
    timestamp.dateTime = new Date().toISOString();
    timestamp.textContent = new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit"});
    const text = document.createElement("span");
    text.textContent = `${STATUS_LABELS[current.status] || current.status}: ${humanPhase(current)}`;
    row.append(timestamp, text);
    activityList.prepend(row);
  }

  function renderStats(current) {
    const general = current.domain === "general";
    document.querySelector("[data-beta-calls-label]").textContent = general ? "CLAUDE REQUESTS" : "EXPERIMENTS";
    document.querySelector("[data-beta-searches-label]").textContent = general ? "WEB SEARCHES" : "MISSION STEP";
    document.querySelector("[data-beta-input-label]").textContent = general ? "INPUT TOKENS" : "WORK BUDGET USED";
    document.querySelector("[data-beta-output-label]").textContent = general ? "OUTPUT TOKENS" : "CURRENT PHASE";
    document.querySelector("[data-beta-calls]").textContent = formatNumber(general ? current.provider_calls_used : current.experiments_used);
    document.querySelector("[data-beta-searches]").textContent = general ? `${formatNumber(current.web_searches_used)} / 3` : formatNumber(current.step);
    document.querySelector("[data-beta-input]").textContent = general ? formatNumber(current.input_tokens) : formatNumber(current.experiments_used);
    document.querySelector("[data-beta-output]").textContent = general ? formatNumber(current.output_tokens) : clean(current.phase).replaceAll("_", " ");
  }

  function appendSafeInline(container, value) {
    const text = value.replaceAll("**", "");
    const linkPattern = /\[([^\]]{1,240})\]\(<(https:[^>\s]+)>\)/g;
    let cursor = 0;
    for (const match of text.matchAll(linkPattern)) {
      container.append(document.createTextNode(text.slice(cursor, match.index)));
      try {
        const url = new URL(match[2]);
        if (url.protocol !== "https:") throw new Error("unsupported link");
        const link = document.createElement("a");
        link.href = url.href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = match[1];
        container.append(link);
      } catch (_error) {
        container.append(document.createTextNode(match[1]));
      }
      cursor = match.index + match[0].length;
    }
    container.append(document.createTextNode(text.slice(cursor)));
  }

  function renderDossier(text) {
    const fragment = document.createDocumentFragment();
    text.split(/\r?\n/).forEach(rawLine => {
      const line = rawLine.trim();
      if (!line) return;
      if (/^-{3,}$/.test(line)) {
        fragment.append(document.createElement("hr"));
        return;
      }
      const heading = /^(#{1,4})\s+(.+)$/.exec(line);
      if (heading) {
        const node = document.createElement(heading[1].length <= 1 ? "h2" : heading[1].length === 2 ? "h3" : "h4");
        appendSafeInline(node, heading[2]);
        fragment.append(node);
        return;
      }
      const paragraph = document.createElement("p");
      const list = /^(?:[-*]|\d+\.)\s+(.+)$/.exec(line);
      if (list) paragraph.className = "is-list";
      appendSafeInline(paragraph, list ? list[1] : line);
      fragment.append(paragraph);
    });
    dossierView.replaceChildren(fragment);
  }

  async function loadDossier(current) {
    dossierPanel.hidden = false;
    dossierMessage.textContent = "Loading the completed dossier…";
    if (dossierMissionId === current.id && dossierText) {
      dossierMessage.textContent = "Dossier loaded from this private browser session.";
      return;
    }
    try {
      const response = await fetch(apiBase + current.links.dossier, {
        headers: {Authorization: `Bearer ${accessToken}`},
        cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer"
      });
      if (!response.ok) throw new Error("The dossier is not available yet.");
      dossierText = await response.text();
      dossierMissionId = current.id;
      renderDossier(dossierText);
      dossierMessage.textContent = "Rendered safely from the cited Markdown dossier. Source links open in a new tab.";
    } catch (error) {
      dossierMessage.textContent = error.message;
    }
  }

  function render(current) {
    mission = current;
    form.classList.add("is-launched");
    reviewHeading.textContent = "Your mission is underway.";
    reviewIntro.textContent = "The research brief is locked in. Follow the live service state and completed dossier beside it.";
    empty.hidden = true;
    live.hidden = false;
    updateProgress(4);
    document.querySelector("[data-beta-id]").textContent = current.id;
    document.querySelector("[data-beta-status]").textContent = STATUS_LABELS[current.status] || current.status.toUpperCase();
    document.querySelector("[data-beta-question]").textContent = current.question;
    document.querySelector("[data-beta-phase]").textContent = humanPhase(current);
    document.querySelector("[data-beta-stop]").textContent = current.stop_reason || current.error || "The service has durably recorded this research state.";
    document.querySelector("[data-beta-updated]").textContent = `Updated ${new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit"})}`;
    live.setAttribute("aria-busy", String(!FINAL_STATUSES.has(current.status) && current.status !== "paused"));
    renderPipeline(current);
    renderStats(current);
    appendActivity(current);
    document.querySelectorAll("[data-beta-action]").forEach(button => {
      const action = button.dataset.betaAction;
      button.disabled = (action === "pause" && !["queued", "running"].includes(current.status)) ||
        (action === "resume" && current.status !== "paused") ||
        (action === "cancel" && FINAL_STATUSES.has(current.status));
    });
    if (current.status === "completed") loadDossier(current);
    else dossierPanel.hidden = true;
  }

  function stopPolling() {
    if (pollTimer) clearTimeout(pollTimer);
    pollTimer = null;
  }

  function schedulePoll() {
    stopPolling();
    pollTimer = setTimeout(poll, 2500);
  }

  async function poll() {
    if (!mission) return;
    try {
      const payload = await api(`/api/v1/missions/${mission.id}`);
      render(payload.mission);
      if (!FINAL_STATUSES.has(mission.status) && mission.status !== "paused") schedulePoll();
      else stopPolling();
    } catch (error) {
      stopPolling();
      setMessage(`Live updates paused: ${error.message}`, true);
    }
  }

  async function checkAvailability() {
    if (!apiBase) {
      setConnection("Research service deployment pending", "offline");
      submit.disabled = true;
      setMessage("The evidence site is available, but interactive research is not connected yet.");
      return;
    }
    try {
      const response = await fetch(apiBase + "/api/v1/health", {
        cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer"
      });
      if (!response.ok) throw new Error("unavailable");
      const health = await response.json();
      serviceAvailable = Boolean(health.accepting_missions);
      setConnection(serviceAvailable ? "Live research service ready" : "New research temporarily paused",
                    serviceAvailable ? "online" : "paused");
      submit.disabled = !serviceAvailable;
    } catch (_error) {
      serviceAvailable = false;
      setConnection("Research service unavailable", "offline");
      submit.disabled = true;
      setMessage("The public evidence site remains available. Live research will return when the service reconnects.", true);
    }
  }

  function resetWorkspace() {
    stopPolling();
    accessToken = "";
    mission = null;
    lastActivityKey = "";
    dossierText = "";
    dossierMissionId = "";
    activityList.replaceChildren();
    dossierView.replaceChildren();
    dossierPanel.hidden = true;
    live.hidden = true;
    empty.hidden = false;
    form.reset();
    form.classList.remove("is-launched");
    reviewHeading.textContent = "Review your research brief.";
    reviewIntro.textContent = "ORIGIN will use this complete brief for one bounded research mission.";
    topic.value = "";
    document.querySelector("[data-topic-count]").textContent = "0";
    showIntakeStep(1, false);
    submit.disabled = !serviceAvailable;
    setMessage("Ready for a new research topic.");
    topic.focus();
  }

  document.querySelectorAll("[data-intake-next]").forEach(button => {
    button.addEventListener("click", () => moveIntake(1));
  });
  document.querySelectorAll("[data-intake-back]").forEach(button => {
    button.addEventListener("click", () => moveIntake(-1));
  });
  document.querySelectorAll("[data-topic-example]").forEach(button => {
    button.addEventListener("click", () => {
      topic.value = button.dataset.topicExample;
      topic.dispatchEvent(new Event("input"));
      topic.focus();
    });
  });
  topic.addEventListener("input", () => {
    clearValidity(topic);
    document.querySelector("[data-topic-count]").textContent = String(topic.value.length);
  });
  form.querySelectorAll("input, select, textarea").forEach(control => {
    control.addEventListener("change", () => clearValidity(control));
  });

  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!validateStep(3)) return;
    const fields = new FormData(form);
    const question = buildResearchBrief();
    const domain = String(fields.get("domain"));
    accessToken = clean(fields.get("token"));
    tokenField.value = "";
    submit.disabled = true;
    setMessage("Validating the brief and creating a durable research mission…");
    updateProgress(4);
    try {
      const payload = await api("/api/v1/missions", {
        method: "POST",
        body: {
          question,
          domain,
          profile: domain === "general" ? "web_research" : (domain === "graphbench" ? "graph_fast" : "fast")
        }
      });
      render(payload.mission);
      setMessage("Mission launched. Every update below comes from the live ORIGIN service.");
      await poll();
    } catch (error) {
      accessToken = "";
      updateProgress(3);
      setMessage(error.message, true);
      tokenField.focus();
    } finally {
      submit.disabled = !serviceAvailable;
    }
  });

  document.querySelectorAll("[data-beta-action]").forEach(button => {
    button.addEventListener("click", async () => {
      if (!mission) return;
      try {
        const action = button.dataset.betaAction;
        const payload = await api(`/api/v1/missions/${mission.id}/${action}`, {method: "POST", body: {}});
        render(payload.mission);
        setMessage(`${action[0].toUpperCase()}${action.slice(1)} request recorded durably.`);
        if (![...FINAL_STATUSES, "paused"].includes(mission.status)) schedulePoll();
      } catch (error) {
        setMessage(error.message, true);
      }
    });
  });

  document.querySelector("[data-new-mission]").addEventListener("click", resetWorkspace);
  document.querySelector("[data-dossier-download]").addEventListener("click", () => {
    if (!dossierText || !mission) return;
    const blob = new Blob([dossierText], {type: "text/markdown;charset=utf-8"});
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `origin-${mission.id}-dossier.md`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  form.elements.domain.addEventListener("change", event => {
    if (topic.value) return;
    const examples = {
      algobench: "Which sorting strategy wins under which input regime at small sizes?",
      graphbench: "Which shortest-path method wins on which graph topology?"
    };
    if (examples[event.target.value]) {
      topic.value = examples[event.target.value];
      topic.dispatchEvent(new Event("input"));
    }
  });

  window.addEventListener("pagehide", () => {
    accessToken = "";
    stopPolling();
  });

  showIntakeStep(1, false);
  checkAvailability();
})();
