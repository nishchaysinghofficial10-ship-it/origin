# ORIGIN 2.1.2

**A persistent computational research engine.** Give it a research question in a
supported domain and a budget. It maintains competing hypotheses, turns them
into machine-checkable predictions, runs reproducible experiments in a confined
subprocess, analyses the results, attacks its own conclusions with independent
replications and falsification probes, records every decision and confidence
change, and stops with an explicit reason.

Zero third-party dependencies. Python 3.10+. Everything it concludes is
traceable to a stored experiment.

**Public evidence site:**
[nishchaysinghofficial10-ship-it.github.io/origin](https://nishchaysinghofficial10-ship-it.github.io/origin/)
— the site is generated from the exact flagship artifacts in this repository.
The optional interactive service is a controlled, token-gated computational
beta; it is not an open code-execution service.

---

## Why it exists

The shipped flagship evaluation runs one pre-registered question through three
workflows:

| | benchmark & report | ask a model | ORIGIN |
|---|---:|---:|---:|
| Experiments | 1 | 0 | 6 |
| Conclusions | 4 | 2 | 2 |
| Carrying explicit scope | 0 | 0 | **2** |
| Independent replications | 0 | 0 | **3** |
| **Incorrect candidate named a winner** | **3** | 0 | **0** |

The benchmark workflow reported `bfs_unit` as fastest on three graph topologies.
It *is* fastest there — and it is **wrong** there, returning incorrect distances
whenever edge weights differ. A benchmark measures speed; it has no way to
notice. ORIGIN spent six experiments instead of one, produced *fewer*
conclusions, and got none of them wrong in that way.

That trade — more cost, fewer claims, each one scoped and checked — is the whole
design. Details: [`docs/reports/FLAGSHIP_EVALUATION.md`](docs/reports/FLAGSHIP_EVALUATION.md).

## What ORIGIN is **not**

- Not a general "autonomous scientist". It runs *computational* experiments in a
  registered domain — currently sorting benchmarks and graph shortest paths.
- Not a web researcher. It retrieves URLs you approve; it does not search,
  crawl, or browse, and everything it retrieves is untrusted input.
- Not an unrestricted code-execution agent. It executes only code generated from
  its own audited domain templates — never LLM-written or web-derived code.
- Not an oracle. Generated prose is never evidence. A model may *propose*;
  proposals survive the same experimental pipeline as everything else.
- Not unsupervised. "Autonomous" means it chooses which *permitted* action runs
  next, inside limits you set, with no daemon and no background service.

## Quick start

```bash
unzip origin-v2.1.2.zip && cd origin-project     # or: git clone …
python3 -m unittest discover -s tests

python3 -m origin init "Which sorting strategy wins under which input regime?" \
    --dir runs/demo --profile fast
python3 -m origin run    --dir runs/demo
python3 -m origin status --dir runs/demo
python3 -m origin report --dir runs/demo         # the research dossier
```

The repository contains 298 test cases, including the public site and controlled
beta boundary. The complete suite passes locally on native macOS/arm64 and in
hosted Linux CI with CPython 3.10–3.14. The release
workflow also checks macOS on stable CPython 3.14, portability, archive
round-trip, replay, a fresh end-to-end mission, bounded autonomy, and fixture
evidence. See the
[`v2.1.2 verification record`](docs/release/V2_1_2_VERIFICATION.md).

## Supported domains

| Domain | Question shape | Metrics |
|---|---|---|
| `algobench` | which sorting strategy wins under which input distribution | wall-clock time (host-specific) |
| `graphbench` | which shortest-path method wins on which graph topology | wall-clock **and edge relaxations — machine-independent** |

```bash
python -m origin init "…" --dir runs/g --domain graphbench --profile graph_fast
```

The second domain existed to test whether the core was genuinely
domain-agnostic. It was — eleven core modules never name a domain, asserted by
test — and it exposed two real architecture gaps, documented rather than hidden
in [`docs/SECOND_DOMAIN.md`](docs/SECOND_DOMAIN.md).

## Commands

| Command | Purpose |
|---|---|
| `init` | create a mission (question, domain, profile, budgets, brain) |
| `run [--steps N]` | run or resume; checkpoints after every step |
| `status` / `report` / `timeline` / `html` | inspect the mission |
| `verify` | cross-check durable state against artifacts and the event log |
| `replay --exp ID` | re-execute a stored experiment and compare |
| `ingest --file F \| --url U` | ingest a document as untrusted evidence |
| `autonomy plan\|tick\|run\|pause\|resume\|cancel\|status\|recover-lock` | bounded autonomy |
| `cancel` | terminate with a recorded reason |

## What a result means

Three different claims, kept separate on purpose:

```text
Exact reproducibility       code, inputs, seeds, config, correctness and outputs
                            match — verified by digest, asserted always
Statistical reproducibility performance RELATIONSHIPS hold, judged only when the
                            data supports it — reported, asserted with --strict
Absolute timings            belong to one host at one moment — never asserted
```

A performance difference counts as decisive only with ≥5 trials per side,
separation beyond 3× the combined standard error, **and** a ≥10 % relative
margin. Anything weaker is `inconclusive` — neither support nor refutation. No
p-values: at these trial counts they would imply precision the data lacks.

That rule governs the research, not just replay. In the shipped graph mission it
refused to name a winner on four topologies and downgraded two
textbook-plausible hypotheses ORIGIN had proposed itself.

## Safety boundaries

- **Experiments** run under user-space confinement: CPU/file/process rlimits,
  Linux `RLIMIT_AS` or a fail-closed macOS process-group RSS watchdog, `python
  -I`, a scrubbed environment carrying no credentials, an experiment working
  directory, output caps and a wall-clock timeout. Every experiment writes its
  exact profile to `confinement.json`. Designs exceeding policy are rejected
  *before* a process exists. This is **not** kernel-grade isolation — see
  [`docs/SECURITY.md`](docs/SECURITY.md).
- **LLM output** is parsed, schema-validated and mapped through a fixed domain
  vocabulary. There is no path from a provider response to a fact, an evidence
  item, or a knowledge-graph relation.
- **Retrieved pages** are https-only, address-checked (loopback, private,
  link-local and metadata ranges refused), redirect-re-validated, size-capped
  while streaming, content-type allow-listed, robots-honouring. Claims keep the
  passage they came from and stay `SPECULATION`.
- **Autonomy** chooses among already-permitted actions. It cannot create an
  action type, widen a limit, or use the network or a provider without a per-run
  flag. One mission has one writer; a stale lease is never stolen automatically.
- **Credentials** live in environment variables only, and every logged string
  passes a redactor.

## Reproduce the evidence

```bash
python tools/flagship_evaluation.py --dir runs/flageval    # the table above
python tools/autonomy_demo.py       --dir runs/autonomy    # bounded autonomy
python tools/web_evidence_demo.py   --dir runs/evidence --mode fixture
python -m origin verify --dir examples/flagship_run
python -m origin replay --dir examples/flagship_run --exp <exp_id>
```

Shipped missions in `examples/`: `flagship_run` (sorting), `graph_mission`
(shortest paths, run autonomously), `final_flagship_mission` (the three-workflow
evaluation), `autonomy_demo`, `evidence_demo`, `demo_run`.

## Known limitations

- **Two domains only**, both computational and deterministic. Nothing here
  addresses wet-lab, medical, legal or financial research, and it must not be
  used for those.
- **Timings are single-machine.** Only within-run rankings are meaningful, and
  only at tested sizes and trial counts. Relaxation counts do transfer.
- **Confinement is user-space.** No network or filesystem namespacing.
- **The live LLM path is UNVERIFIED** — no API key was available during
  development, so the socket write has never executed. Everything around it is
  tested through a stubbed transport.
- **General-web retrieval is unverified**; the live path was proven only against
  an allow-listed host.
- **Autonomy gives no exactly-once guarantee** for external actions: a crash
  mid-action is recorded as `interrupted` for operator review, never guessed.
- **No daemon, no multi-agent coordination, no distributed execution, no source
  discovery.** None are implemented and none are claimed.

## Documentation

[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) ·
[`docs/RESEARCH_MODEL.md`](docs/RESEARCH_MODEL.md) ·
[`docs/AUTONOMY.md`](docs/AUTONOMY.md) ·
[`docs/SECOND_DOMAIN.md`](docs/SECOND_DOMAIN.md) ·
[`docs/LLM_INTEGRATION.md`](docs/LLM_INTEGRATION.md) ·
[`docs/EVIDENCE_ACQUISITION.md`](docs/EVIDENCE_ACQUISITION.md) ·
[`docs/OPERATIONS.md`](docs/OPERATIONS.md) ·
[`docs/WEB_SERVICE.md`](docs/WEB_SERVICE.md) ·
[`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) ·
[`docs/SECURITY.md`](docs/SECURITY.md) ·
[`docs/DECISIONS.md`](docs/DECISIONS.md)

Verification reports (every number produced by a command at that commit):
[`docs/verification/`](docs/verification) · security analysis:
[`docs/security/`](docs/security) · executed attacks:
[`docs/red_team/RED_TEAM_REPORT.md`](docs/red_team/RED_TEAM_REPORT.md)

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md), [`SECURITY.md`](SECURITY.md),
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md), [`CHANGELOG.md`](CHANGELOG.md), and
the release evidence in
[`docs/release/V2_1_2_RELEASE_CHECKLIST.md`](docs/release/V2_1_2_RELEASE_CHECKLIST.md).

The one rule: **no capability is complete without evidence.** A feature comes with a test; a claim comes with the
command that produced it. Saying "unverified" is welcome — overclaiming is not,
and there are tests that fail the build if the documentation starts doing it.

## License

MIT — see [`LICENSE`](LICENSE).
