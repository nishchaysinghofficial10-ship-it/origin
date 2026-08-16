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
  let accessToken = "";
  let mission = null;
  let pollTimer = null;

  function setMessage(text, isError = false) {
    message.textContent = text;
    message.classList.toggle("is-error", isError);
  }

  function setConnection(text, mode) {
    connection.querySelector("strong").textContent = text;
    connection.dataset.mode = mode;
  }

  async function api(path, options = {}) {
    const headers = { "Authorization": `Bearer ${accessToken}` };
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    const response = await fetch(apiBase + path, {
      method: options.method || "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body)
    });
    const contentType = response.headers.get("Content-Type") || "";
    const payload = contentType.includes("json") ? await response.json() : await response.text();
    if (!response.ok) {
      const reason = payload?.error?.message || `Request failed with HTTP ${response.status}`;
      throw new Error(reason);
    }
    return payload;
  }

  function render(current) {
    mission = current;
    empty.hidden = true;
    live.hidden = false;
    document.querySelector("[data-beta-id]").textContent = current.id;
    document.querySelector("[data-beta-status]").textContent = current.status.toUpperCase();
    document.querySelector("[data-beta-question]").textContent = current.question;
    document.querySelector("[data-beta-phase]").textContent = current.phase;
    document.querySelector("[data-beta-step]").textContent = String(current.step);
    const workUnits = current.domain === "general"
      ? current.provider_calls_used : current.experiments_used;
    document.querySelector("[data-beta-experiments]").textContent = String(workUnits || 0);
    document.querySelector("[data-beta-stop]").textContent = current.stop_reason || current.error || "Mission is active and durably checkpointed.";
    document.querySelectorAll("[data-beta-action]").forEach(button => {
      const action = button.dataset.betaAction;
      button.disabled = (action === "pause" && !["queued", "running"].includes(current.status)) ||
        (action === "resume" && current.status !== "paused") ||
        (action === "cancel" && ["completed", "cancelled", "failed"].includes(current.status));
    });
    const dossier = document.querySelector("[data-beta-dossier]");
    if (current.status === "completed") {
      dossier.hidden = false;
      dossier.href = apiBase + current.links.dossier;
      dossier.onclick = async event => {
        event.preventDefault();
        try {
          const response = await fetch(dossier.href, {headers: {Authorization: `Bearer ${accessToken}`}});
          if (!response.ok) throw new Error("Dossier is not available yet.");
          const blob = await response.blob();
          const url = URL.createObjectURL(blob);
          window.open(url, "_blank", "noopener,noreferrer");
          setTimeout(() => URL.revokeObjectURL(url), 60_000);
        } catch (error) {
          setMessage(error.message, true);
        }
      };
    } else {
      dossier.hidden = true;
    }
  }

  async function poll() {
    if (!mission) return;
    try {
      const payload = await api(`/api/v1/missions/${mission.id}`);
      render(payload.mission);
      if (["completed", "cancelled", "failed", "paused"].includes(mission.status)) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    } catch (error) {
      clearInterval(pollTimer);
      pollTimer = null;
      setMessage(error.message, true);
    }
  }

  async function checkAvailability() {
    if (!apiBase) {
      setConnection("Beta API deployment pending", "offline");
      submit.disabled = true;
      setMessage("The verified public evidence site is live-ready. Interactive execution will be enabled after a container host is connected.");
      return;
    }
    try {
      const response = await fetch(apiBase + "/api/v1/health");
      if (!response.ok) throw new Error("unavailable");
      const health = await response.json();
      setConnection(health.accepting_missions ? "General research beta accepting missions" : "Research beta intake paused",
                    health.accepting_missions ? "online" : "paused");
      submit.disabled = !health.accepting_missions;
    } catch (_error) {
      setConnection("Beta API unavailable", "offline");
      submit.disabled = true;
      setMessage("Interactive execution is temporarily unavailable. The public evidence remains fully accessible.", true);
    }
  }

  form.addEventListener("submit", async event => {
    event.preventDefault();
    const fields = new FormData(form);
    accessToken = String(fields.get("token") || "");
    form.elements.token.value = "";
    submit.disabled = true;
    setMessage("Validating the topic and queueing the research mission…");
    try {
      const domain = String(fields.get("domain"));
      const payload = await api("/api/v1/missions", {
        method: "POST",
        body: {
          question: String(fields.get("question")),
          domain,
          profile: domain === "general" ? "web_research" :
            (domain === "graphbench" ? "graph_fast" : "fast")
        }
      });
      render(payload.mission);
      setMessage("Mission queued. This page is reading its durable status.");
      pollTimer = setInterval(poll, 3000);
      await poll();
    } catch (error) {
      accessToken = "";
      setMessage(error.message, true);
    } finally {
      submit.disabled = false;
    }
  });

  document.querySelectorAll("[data-beta-action]").forEach(button => {
    button.addEventListener("click", async () => {
      if (!mission) return;
      try {
        const payload = await api(`/api/v1/missions/${mission.id}/${button.dataset.betaAction}`, {
          method: "POST", body: {}
        });
        render(payload.mission);
        setMessage(`${button.dataset.betaAction} request recorded durably.`);
        if (["queued", "running", "pause_requested", "cancel_requested"].includes(mission.status) && !pollTimer) {
          pollTimer = setInterval(poll, 3000);
        }
      } catch (error) {
        setMessage(error.message, true);
      }
    });
  });

  form.elements.domain?.addEventListener("change", event => {
    const examples = {
      general: "What evidence supports and challenges four-day work weeks?",
      algobench: "Which sorting strategy wins under which input regime at small sizes?",
      graphbench: "Which shortest-path method wins on which graph topology?"
    };
    const next = examples[event.target.value];
    if (next) form.elements.question.value = next;
  });

  window.addEventListener("pagehide", () => {
    accessToken = "";
    if (pollTimer) clearInterval(pollTimer);
  });
  checkAvailability();
})();
