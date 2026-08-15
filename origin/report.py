"""ORIGIN reporting: status box, research dossier, replayable timeline.

The dossier is not a paragraph — it is a traceable record from question to
conclusion: evidence map, contradictions, gaps, hypothesis ledgers,
experiments, failures, and recommended next investigations.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import stats
from .models import HypothesisStatus


# ---------------------------------------------------------------- status box
def status_box(state) -> str:
    c = state.counts()
    runtime = time.time() - state.meta.get("created_at", time.time())
    d, rem = divmod(int(runtime), 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    phase = state.meta.get("phase", "?")
    frac = 1.0 if phase in ("complete", "COMPLETED") else min(0.95, 0.1 + state.budget.fraction_used() * 0.85)
    bar = "█" * int(frac * 22) + "░" * (22 - int(frac * 22))
    current = state.flags.get("current", "—")
    W = 52

    def row(text=""):
        return "║ " + text[:W - 4].ljust(W - 4) + " ║"

    sep = "╠" + "═" * (W - 2) + "╣"
    lines = [
        "╔" + "═" * (W - 2) + "╗",
        row("PROJECT ORIGIN".center(W - 4)),
        sep,
        row(f"Research status: {phase.upper()}"),
        row(f"Runtime: {d}d {h}h {m}m   Step: {state.step}"),
        row(f"Progress: {bar} {frac * 100:3.0f}%"),
        sep,
        row("CURRENT INVESTIGATION"),
        row(current),
        sep,
        row(f"SOURCES        {c['sources']:>6}    CLAIMS      {c['claims']:>6}"),
        row(f"HYPOTHESES     {c['hypotheses']:>6}    EXPERIMENTS {c['experiments']:>6}"),
        row(f"EVIDENCE       {c['evidence']:>6}    FAILURES    {c['failures']:>6}"),
        row(f"CONTRADICTIONS {c['contradictions']:>6}"),
        sep,
        row(f"EXPERIMENT BUDGET  {state.budget.experiments_used}/{state.budget.experiments_total}"),
        row(f"COMPUTE            {state.budget.compute_seconds_used:.0f}s / "
            f"{state.budget.compute_seconds_total:.0f}s"),
        row(f"RETRIES            {state.budget.retries_used}/{state.budget.retries_total}"),
    ]
    if state.meta.get("stop_reason"):
        lines += [sep, row("STOP REASON"), row(state.meta["stop_reason"])]
    lines.append("╚" + "═" * (W - 2) + "╝")
    return "\n".join(lines)


# ------------------------------------------------------------------ timeline
def render_timeline(state) -> str:
    lines = ["# ORIGIN Research Timeline", "",
             f"Question: {state.meta.get('question')}", ""]
    for e in state.read_events():
        day = state.day_of(e["ts"])
        hhmm = time.strftime("%H:%M:%S", time.localtime(e["ts"]))
        lines.append(f"DAY {day} — {hhmm}  [{e['kind']}]")
        lines.append(f"    {e['msg']}")
        lines.append("")
    return "\n".join(lines)


# ------------------------------------------------------------------- dossier
def _latest_results(state):
    recs = [r for r in state.experiments.values() if r.status == "completed"]
    recs.sort(key=lambda r: r.created_at)
    out = []
    for rec in recs:
        p = rec.path(state.root) / "result.json"
        if p.exists():
            out.append((rec, json.loads(p.read_text())))
    return out


def _results_table(rec, result) -> list[str]:
    rows = result["rows"]
    n_top = max(rec.design["sizes"])
    lines = [f"**{rec.id}** — {rec.title} ({rec.duration_s:.1f}s, n = {n_top} shown)", ""]
    for regime in rec.design["regimes"]:
        cells = sorted((r for r in rows if r["regime"] == regime and r["n"] == n_top),
                       key=lambda r: r["mean_s"])
        if not cells:
            continue
        lines.append(f"Regime `{regime}`:")
        lines.append("")
        lines.append("| rank | algorithm | mean (ms) | stdev (ms) | trials |")
        lines.append("|---:|---|---:|---:|---:|")
        for i, r in enumerate(cells, 1):
            lines.append(f"| {i} | {r['algorithm']} | {r['mean_s']*1000:.2f} "
                         f"| {r['stdev_s']*1000:.2f} | {r['trials']} |")
        lines.append("")
    return lines


def render_dossier(state, domain) -> str:
    L: list[str] = []
    add = L.append
    add("# ORIGIN Research Dossier")
    add("")
    from . import __version__ as _origin_version
    add(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}  |  ORIGIN "
        f"v{_origin_version}  |  domain: `{domain.name}`")
    add("")

    add("## 1. Research question")
    add("")
    add(f"> {state.meta.get('question')}")
    add("")

    add("## 2. Initial assumptions")
    add("")
    for a in state.assumptions:
        add(f"- {a}")
    add("")

    add("## 3. Existing knowledge (seeded claims)")
    add("")
    for c in state.claims.values():
        add(f"- **[{c.status.value.upper()}]** {c.text} (confidence {c.confidence:.2f})")
    add("")

    add("## 4. Evidence map (knowledge graph)")
    add("")
    for line in state.graph.relations_readable():
        add(f"- {line}")
    add("")

    add("## 5. Contradictions")
    add("")
    if state.graph.contradictions:
        for c in state.graph.contradictions:
            add(f"- {c['description']}")
    else:
        add("- None detected across experiments in this run.")
    add("")

    add("## 6. Knowledge gaps")
    add("")
    for g in domain.knowledge_gaps(state):
        add(f"- {g}")
    add("")

    add("## 7. Hypotheses (competing pool, with evidence ledgers)")
    add("")
    for h in state.hypotheses.values():
        led = h.ledger()
        add(f"### {h.id} — {h.status.value.upper()}")
        add("")
        add(f"**Statement.** {h.statement}")
        add("")
        add(f"**Rationale.** {h.rationale}")
        add("")
        add(f"Supporting evidence: {led['supporting']} | Contradicting: {led['contradicting']} "
            f"| Experiments: {led['experiments']} | Predictions confirmed: "
            f"{led['predictions_confirmed']} | refuted: {led['predictions_refuted']}")
        add("")
        for p in h.predictions:
            add(f"- [{p.outcome.upper()}] {p.text}" + (f" — {p.detail}" if p.detail else ""))
        add("")

    add("## 8. Experiments")
    add("")
    for rec in state.experiments.values():
        add(f"- `{rec.id}` [{rec.status}] {rec.title} — {rec.duration_s:.1f}s "
            f"(design: {len(rec.design.get('algorithms', []))} algorithms x "
            f"{len(rec.design.get('regimes', []))} regimes x sizes {rec.design.get('sizes')})"
            + (f" — ERROR: {rec.error}" if rec.error else ""))
    add("")

    add("## 9. Results")
    add("")
    for rec, result in _latest_results(state):
        L.extend(_results_table(rec, result))

    add("## 10. Failed approaches (failure log)")
    add("")
    if state.failures:
        for f in state.failures:
            add(f"- **{f.get('experiment')}** / {f.get('hypothesis')}: predicted "
                f"\u201c{f.get('prediction')}\u201d; observed: {f.get('observed')}. "
                f"Action: {f.get('action')}.")
    else:
        add("- No failed predictions or failed runs in this investigation.")
    add("")

    add("## 11. Decision history")
    add("")
    for d in state.decisions:
        add(f"- step {d['step']} [{d['context']}] → **{d['chosen']}** — {d['reason']}")
    add("")

    add("## 12. Current conclusions")
    add("")
    accepted = [h for h in state.hypotheses.values()
                if h.status == HypothesisStatus.ACCEPTED_WITH_SCOPE]
    if accepted:
        add("Accepted with scope (replicated AND survived active falsification):")
        add("")
        for h in accepted:
            add(f"- {h.statement}")
            add(f"  - **scope**: {h.scope or 'unspecified'}")
        add("")
    supported = [h for h in state.hypotheses.values()
                 if h.status == HypothesisStatus.PROVISIONALLY_SUPPORTED]
    rejected = [h for h in state.hypotheses.values() if h.status == HypothesisStatus.REJECTED]
    weakened = [h for h in state.hypotheses.values() if h.status == HypothesisStatus.WEAKENED]
    if supported:
        add("Provisionally supported (survived testing" +
            (" and replication" if any("replicated" in h.tags for h in supported) else "") + "):")
        add("")
        for h in supported:
            rep = " *(independently replicated)*" if "replicated" in h.tags else ""
            add(f"- {h.statement}{rep}")
        add("")
    if weakened:
        add("Weakened (mixed evidence — revision candidates):")
        add("")
        for h in weakened:
            add(f"- {h.statement}")
        add("")
    if rejected:
        add("Rejected by experiment:")
        add("")
        for h in rejected:
            add(f"- {h.statement}")
        add("")

    add("## 13. Confidence and cautions")
    add("")
    for c in state.cautions or ["No cautions recorded."]:
        add(f"- {c}")
    add("")

    add("## 14. Novel findings")
    add("")
    gen = [h for h in state.hypotheses.values() if "generated" in h.tags]
    if gen:
        for h in gen:
            add(f"- ORIGIN synthesized a new candidate from round-1 evidence: **{h.statement}** "
                f"→ outcome: **{h.status.value}**.")
    else:
        add("- None this run.")
    add("")

    add("## 15. Remaining questions & recommended next investigations")
    add("")
    for r in state.recommendations or ["(none recorded)"]:
        add(f"- {r}")
    add("")

    add("## 15b. Measurement environment and scope of performance claims")
    add("")
    envs, refs = {}, []
    for rec, res in _latest_results(state):
        e = res.get("environment") or {}
        if e:
            key = (e.get("python_implementation"), e.get("python_version"),
                   e.get("system"), e.get("machine"), e.get("cpu_count"))
            envs.setdefault(key, []).append(rec.id)
        if res.get("reference_workload_s"):
            refs.append(res["reference_workload_s"])
    if envs:
        for (impl, ver, system, machine, cpus), ids in envs.items():
            add(f"- **{impl} {ver} on {system}/{machine}, {cpus} CPU(s)** — "
                f"{len(ids)} experiment(s)")
        if refs:
            add(f"- Fixed reference workload (sorting 20k floats): median "
                f"{min(refs)*1000:.2f}–{max(refs)*1000:.2f} ms across runs — use "
                f"this to put timings from another machine in proportion.")
    else:
        add("- Environment metadata was not recorded for these experiments "
            "(result schema v1); timings cannot be attributed to a specific "
            "interpreter or machine.")
    add("")
    add("**Every performance statement in this dossier is scoped to:** the "
        "machine and interpreter above; the input regimes "
        f"{state.meta.get('domain_config', {}).get('regimes')}; the input sizes "
        f"{state.meta.get('domain_config', {}).get('sizes')}; "
        f"{state.meta.get('domain_config', {}).get('trials')} trials per "
        "measurement cell; and pure-Python implementations of the listed "
        "algorithms. Nothing here is a claim about these algorithms in general, "
        "in another language, at other input sizes, or on other hardware.")
    add("")
    kinds = getattr(domain, "metric_kinds", {"mean_s": "timing"})
    exact = [k for k, v in kinds.items() if v == "exact"]
    if exact:
        add(f"**This domain reports exact metric(s): {', '.join(exact)}.** Those "
            "are deterministic counts, not timings: they do not vary between "
            "runs or machines, so conclusions resting on them transfer in a way "
            "wall-clock conclusions do not, and they are compared without a "
            "noise gate.")
        add("")
    add("Comparisons are only called decisive when the separation exceeds "
        f"{stats.K_SEM:g}x the combined standard error of the two means AND at "
        f"least {stats.MIN_REL_MARGIN*100:.0f}% of the faster mean, with at "
        f"least {stats.MIN_TRIALS} trials on both sides. Everything else is "
        "recorded as INCONCLUSIVE — not as a win, and not as a refutation.")
    add("")

    add("## 16. Prediction ledger")
    add("")
    add("| Hypothesis | Prediction | Check | Outcome | Basis |")
    add("|---|---|---|---|---|")
    for h in state.hypotheses.values():
        for p in h.predictions:
            detail = (p.detail or "").replace("|", "/")
            add(f"| {h.id} | {p.text} | `{p.check.get('type')}` | "
                f"**{p.outcome}** | {detail[:180]} |")
    add("")
    add("`inconclusive` means the measurement could not resolve the question at "
        "this trial count — it is neither support nor refutation.")
    add("")

    add("## 16b. LLM proposal ledger")
    add("")
    try:
        from .proposals import ProposalAudit
        audit = ProposalAudit(state.root).read()
    except Exception:  # noqa: BLE001 - a missing/unreadable audit is not fatal
        audit = []
    if not audit:
        add("- No LLM proposals were offered in this mission "
            f"(brain: `{state.meta.get('brain', 'none')}`).")
    else:
        acc = [a for a in audit if a.get("verdict") == "accepted"]
        rej = [a for a in audit if a.get("verdict") == "rejected"]
        add(f"Provider `{state.meta.get('brain', '?')}` offered {len(audit)} "
            f"proposal(s): **{len(acc)} accepted, {len(rej)} rejected**. Full "
            f"record, including rejected bodies, in `logs/proposals.jsonl`.")
        add("")
        add("| Proposal | Type | Verdict | What ORIGIN did with it |")
        add("|---|---|---|---|")
        for a in acc:
            add(f"| `{a.get('proposal_id','')}` | {a.get('proposal_type','')} | "
                f"accepted | {str(a.get('outcome',''))[:90]} |")
        for a in rej:
            add(f"| `{a.get('proposal_id','')}` | "
                f"{(a.get('proposal') or {}).get('proposal_type', '?')} | "
                f"rejected ({a.get('stage','')}) | "
                f"{str(a.get('reason',''))[:90]} |")
        add("")
        add("An accepted proposal is **not** a finding. Accepted hypotheses "
            "entered as PROPOSED and were resolved by the experiments, "
            "replication and falsification recorded elsewhere in this dossier; "
            "counterarguments are unverified prose recorded as cautions; "
            "knowledge gaps are recommendations, not results.")
    add("")

    add("## 16c. Candidate validity boundaries")
    add("")
    if not state.invalidities:
        add("- No candidate was found invalid under any tested condition.")
    else:
        add("A candidate recorded here is **excluded from every performance "
            "ranking** for that condition. Being fast is not a result if the "
            "answer is wrong.")
        add("")
        add("| Candidate | Not valid under | Reason | Detected in |")
        add("|---|---|---|---|")
        for inv in state.invalidities.values():
            add(f"| `{inv.candidate}` | {inv.condition} | {inv.reason} | "
                f"{inv.experiment_id or '—'} |")
    add("")

    add("## 17. Falsification attempts (critic attacks)")
    add("")
    if state.falsifications:
        for f in state.falsifications.values():
            add(f"- **{f.hypothesis_id}** — probe `{f.probe or '(none)'}` → **{f.outcome}**")
            add(f"  - {f.detail}")
    else:
        add("- No falsification attempts this run.")
    add("")

    add("## 18. Budget ledger & stop reason")
    add("")
    b = state.budget
    add(f"- Experiments: {b.experiments_used}/{b.experiments_total}")
    add(f"- Compute: {b.compute_seconds_used:.1f}s / {b.compute_seconds_total:.0f}s")
    add(f"- Active runtime (controller): {b.elapsed_seconds_used:.1f}s"
        + (f" / {b.elapsed_seconds_total:.0f}s" if b.elapsed_seconds_total else " (no wall-time cap)"))
    add(f"- Provider calls: {b.provider_calls_used}"
        + (f"/{b.provider_calls_total}" if b.provider_calls_total else " (uncapped)"))
    add(f"- Retries: {b.retries_used}/{b.retries_total}")
    add(f"- **Stop reason**: {state.meta.get('stop_reason', '(mission still active)')}")
    add("")

    add("## 19. Threats to validity")
    add("")
    add("- Single machine, single CPython version: absolute timings will not transfer; "
        "only within-run rankings are meaningful, and only at the tested sizes.")
    add("- Wall-clock time only: no comparison counts, memory, or cache metrics. "
        "A ranking here is a ranking of *this implementation on this host*, not "
        "of the algorithms as such.")
    add(f"- Trial count ({state.meta.get('domain_config', {}).get('trials')} per "
        "cell) supports the conservative separation rule used here, not a "
        "formal hypothesis test; no p-values are computed or implied.")
    add("- Timing noise: evidence strength is capped when winner stdev/mean > 0.30, "
        "but low-margin rankings can still flip between seeds (observed as recorded "
        "contradictions).")
    add("- Scope: falsification probes cover boundary sizes (2x) and two unseen "
        "regimes; conclusions say nothing beyond that envelope.")
    add("- Knowledge-graph `fastest_on` relations are size-agnostic by design in "
        "v1.0; scale-dependent flips appear as contradictions rather than "
        "conditioned relations.")
    if any("llm_proposed" in h.tags for h in state.hypotheses.values()):
        add("- LLM-proposed hypotheses passed schema+vocabulary validation and the "
            "full experimental pipeline; their *statements* are still author-biased "
            "toward the proposer's framing.")
    add("")

    add("## Appendix — reproducibility")
    add("")
    add("- Recreate this mission: `python -m origin init \"<question>\" --dir <new_dir> "
        "--profile <profile>` then `python -m origin run --dir <new_dir>`")
    add("- Replay any experiment from stored metadata: "
        "`python -m origin replay --dir <this_dir> --exp <exp_id>`")
    add("- Verify state consistency: `python -m origin verify --dir <this_dir>`")
    add("- Full machine-readable state: `state.json`, browsable views in `research_state/`")
    add("- Every experiment's generated code + raw results: `experiments/exp_*/` "
        "(each `run.py` is self-contained and re-runnable)")
    add("- Append-only event log: `logs/events.jsonl` — rendered as `reports/timeline.md`")
    add(f"- Budget consumed: {state.budget.experiments_used}/{state.budget.experiments_total} "
        f"experiments, {state.budget.compute_seconds_used:.1f}s compute")
    add("")
    return "\n".join(L)


def write_reports(state, domain) -> None:
    rep = Path(state.root) / "reports"
    rep.mkdir(parents=True, exist_ok=True)
    (rep / "dossier.md").write_text(render_dossier(state, domain))
    (rep / "timeline.md").write_text(render_timeline(state))


# ------------------------------------------------------- mission control html
def render_html(state) -> str:
    """Single-file static mission-control page generated from stored state.
    No server, no JS dependencies — honest view of the durable truth."""
    import html as _html
    e = _html.escape
    c = state.counts()
    b = state.budget

    def bar(used, total):
        pct = 0 if not total else min(100, int(100 * used / total))
        return (f'<div class="bar"><div style="width:{pct}%"></div></div>'
                f'<small>{used:.0f} / {total:.0f} ({pct}%)</small>')

    hyp_rows = ""
    for h in state.hypotheses.values():
        led = h.ledger()
        hyp_rows += (f"<tr><td>{e(h.id)}</td><td class='st {e(h.status.value)}'>"
                     f"{e(h.status.value)}</td><td>{e(h.statement)}</td>"
                     f"<td>{led['supporting']}/{led['contradicting']}</td>"
                     f"<td>{e(h.scope or '—')}</td>"
                     f"<td>{e(', '.join(h.tags) or '—')}</td></tr>")
    fal_rows = "".join(
        f"<tr><td>{e(f.hypothesis_id)}</td><td>{e(f.outcome)}</td>"
        f"<td>{e(f.probe or '—')}</td><td>{e(f.detail[:220])}</td></tr>"
        for f in state.falsifications.values()) or \
        "<tr><td colspan=4>none</td></tr>"
    dec_rows = "".join(
        f"<li><b>step {d['step']}</b> [{e(d['context'])}] → {e(d['chosen'])}"
        f"<br><small>{e(d['reason'])}</small></li>"
        for d in state.decisions[-20:]) or "<li>none</li>"
    con_rows = "".join(f"<li>{e(x['description'])}</li>"
                       for x in state.graph.contradictions) or "<li>none</li>"
    fail_rows = "".join(
        f"<tr><td>{e(str(f.get('experiment','')))}</td>"
        f"<td>{e(str(f.get('hypothesis','')))}</td>"
        f"<td>{e(str(f.get('observed',''))[:160])}</td></tr>"
        for f in state.failures[-15:]) or "<tr><td colspan=3>none</td></tr>"

    return f"""<!doctype html><html><head><meta charset='utf-8'>
<title>ORIGIN mission control</title><style>
body{{font-family:ui-monospace,Menlo,Consolas,monospace;background:#0e1116;
color:#d7dde6;margin:2rem;line-height:1.45}}
h1,h2{{color:#7ee0a3;font-weight:600}} a{{color:#7ab8ff}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.8rem}}
.card{{background:#161b22;border:1px solid #2b3240;border-radius:8px;padding:.8rem}}
.card b{{font-size:1.5rem;color:#fff}}
table{{border-collapse:collapse;width:100%;font-size:.85rem}}
td,th{{border:1px solid #2b3240;padding:.35rem .5rem;text-align:left;vertical-align:top}}
.bar{{background:#2b3240;height:10px;border-radius:5px;overflow:hidden}}
.bar div{{background:#7ee0a3;height:100%}}
.st.accepted_with_scope{{color:#7ee0a3}} .st.provisionally_supported{{color:#a3d8ff}}
.st.rejected{{color:#ff8f8f}} .st.weakened{{color:#ffd27e}}
small{{color:#8b96a5}}</style></head><body>
<h1>ORIGIN — mission control</h1>
<p><b>{e(str(state.meta.get('question','')))}</b><br>
<small>phase <b>{e(str(state.meta.get('phase')))}</b> · step {state.step} ·
stop reason: {e(str(state.meta.get('stop_reason','(active)')))} ·
generated from state.json (single source of truth)</small></p>
<div class='grid'>
<div class='card'>hypotheses<br><b>{c['hypotheses']}</b></div>
<div class='card'>experiments<br><b>{c['experiments']}</b></div>
<div class='card'>evidence<br><b>{c['evidence']}</b></div>
<div class='card'>claims<br><b>{c['claims']}</b></div>
<div class='card'>contradictions<br><b>{c['contradictions']}</b></div>
<div class='card'>failures<br><b>{c['failures']}</b></div>
<div class='card'>falsification attempts<br><b>{len(state.falsifications)}</b></div>
<div class='card'>decisions<br><b>{len(state.decisions)}</b></div>
</div>
<h2>Budgets</h2>
<div class='grid'>
<div class='card'>experiments {bar(b.experiments_used, b.experiments_total)}</div>
<div class='card'>compute seconds {bar(b.compute_seconds_used, b.compute_seconds_total)}</div>
<div class='card'>retries {bar(b.retries_used, b.retries_total)}</div>
</div>
<h2>Hypotheses</h2>
<table><tr><th>id</th><th>status</th><th>statement</th><th>evid +/−</th>
<th>scope</th><th>tags</th></tr>{hyp_rows}</table>
<h2>Falsification attempts</h2>
<table><tr><th>hypothesis</th><th>outcome</th><th>probe</th><th>detail</th></tr>
{fal_rows}</table>
<h2>Contradictions</h2><ul>{con_rows}</ul>
<h2>Recent failures</h2>
<table><tr><th>experiment</th><th>hypothesis</th><th>observed</th></tr>{fail_rows}</table>
<h2>Decision timeline (last 20)</h2><ul>{dec_rows}</ul>
<p><small>Files: state.json · logs/events.jsonl · experiments/exp_*/ ·
reports/dossier.md</small></p></body></html>"""
