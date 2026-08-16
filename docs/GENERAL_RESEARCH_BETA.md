# ORIGIN general public-web research beta

This is the operator and engineering contract for ORIGIN's broad-topic mode.
It extends the public beta without changing the verified v2.1.2 computational
core or granting network access to its experiment worker.

## User workflow

1. The user opens the public evidence site and enters a private tester token.
2. They select **General public-web research**, enter a topic, and submit it.
3. The authenticated API normalizes the question, applies the narrow unsafe-
   operations policy, enforces tester quotas, and writes a durable queue item.
4. Only the `researcher` service can claim `general/web_research` items. It
   reserves one global paid slot before making a provider call.
5. Anthropic's server-side web search gathers current sources. ORIGIN requires
   citations, multiple source types, competing interpretations, testable
   predictions, criticism, conclusions, and limitations.
6. ORIGIN validates the response shape, requires at least two distinct usable
   HTTPS cited sources and one paid search, preserves citations beside the associated
   passage, and writes `reports/dossier.md` plus `research-metadata.json`.
7. The authenticated user downloads the dossier. The API never serves the raw
   provider response or the provider credential.

The dossier labels itself **sourced synthesis, not an experimentally verified
ORIGIN finding**. Only `algobench` and `graphbench` produce local experimental
Evidence objects.

## Process and secret boundaries

```text
public browser
    │ HTTPS + tester Bearer token
    ▼
API ─── durable SQLite queue/data volume
 │         │                         │
 │         ├─ algobench/graphbench ─► computational worker
 │         │                          network_mode: none
 │         │                          no API/provider secret
 │         │
 │         └─ general/web_research ─► researcher
 │                                    outbound network, no inbound port
 │                                    Anthropic key secret only here
 ▼
public health only; admin metrics require a distinct operator token
```

The researcher has no local shell, Python, browser, fetch, file-read, MCP, or
custom execution tool exposed to the model. Its only remote tool is Anthropic's
server-executed, hard-capped web search. Search content and user topics are
explicitly wrapped as untrusted data. Provider text is written as a report; it
is never interpreted as a command, experiment design, core Evidence, fact, or
knowledge-graph authority.

## Default paid-usage contract

| Limit | Default | Hard maximum accepted by configuration |
|---|---:|---:|
| General missions per tester / rolling 24h | 2 | 20 |
| Paid missions globally / rolling 24h | 4 | 100 |
| Provider requests per mission | 1 | 1 |
| Web searches per provider turn | 3 | 5 |
| Output tokens per provider turn | 3,200 | 8,192 |
| Provider timeout per request | 120 s | 300 s |
| Active missions per tester | 1 | 10 |

Production fails closed if Anthropic returns `pause_turn`; ORIGIN does not run
an unbounded conversation. A durable attempt counter is
charged immediately before each paid network request. It survives crashes, so
a repeatedly restarting service cannot silently retry beyond the mission cap.
Reservations and actual provider/search/token usage appear only in the
authenticated administrator health response.

## Topic safety policy

General does not mean literally unrestricted. The local gate rejects clear
requests for dangerous operational assistance such as weapon construction,
malware/credential theft, hard-drug manufacture, self-harm methods, and sexual
content involving minors. It intentionally allows safe historical, policy,
prevention, health, and risk research on sensitive subjects.

The system prompt independently requires refusal of dangerous operational
assistance. Medical, legal, and financial topics are limited to general
research information with uncertainty and a non-advice statement. Do not put a
secret, private personal data, or confidential material in a topic: questions
are stored in the mission database and sent to the provider.

## Private key setup

From the repository root, the operator—not a tester—runs:

```bash
python3 tools/configure_anthropic_key.py
```

The command uses hidden terminal input twice, writes
`deploy/secrets/anthropic_api_key.txt` with mode `0600`, never prints the key,
and writes only beneath a Git-ignored directory. Do not paste the key into chat,
GitHub, `.env.production`, a mission topic, a shell-history argument, or the
website.

Run one deliberately bounded paid check before deployment:

```bash
python3 tools/live_general_research_check.py \
  --key-file deploy/secrets/anthropic_api_key.txt \
  --out runs/live_general_check
```

The summary prints model and usage counts, never the key. Inspect the generated
dossier for real HTTPS citations, epistemic labels, useful competing
interpretations, and limitations. A funded key alone is not evidence that web
search is enabled for the Anthropic organization; this command must pass.

## Deployment

Keep intake closed while replacing services:

```bash
docker compose --env-file .env.production \
  --file compose.production.yaml --file compose.funnel.yaml \
  build api worker researcher backup

docker compose --env-file .env.production \
  --file compose.production.yaml --file compose.funnel.yaml \
  up --detach --wait api worker researcher
```

Do not start the Caddy `proxy` when Tailscale Funnel already terminates HTTPS.
The public API must remain bound to `127.0.0.1:8080`; only Funnel publishes it.

Run the read-only gate before opening intake:

```bash
python3 tools/verify_beta_deployment.py \
  --api-origin https://YOUR-FUNNEL-HOST \
  --site-url https://nishchaysinghofficial10-ship-it.github.io/origin \
  --beta-token-file deploy/secrets/beta_token.txt \
  --admin-token-file deploy/secrets/admin_token.txt \
  --require-general
```

Then open intake and run a real general mission through the website. Verify its
status shows nonzero provider/search usage, download the dossier, and inspect
citations before describing the feature as live.

## Monitoring and emergency stop

```bash
python3 tools/monitor_beta.py \
  --api-origin https://YOUR-FUNNEL-HOST \
  --admin-token-file deploy/secrets/admin_token.txt \
  --require-intake-open \
  --require-researcher
```

The monitor checks API, computational worker, researcher health/restarts,
recent lease/traceback errors, queue age, failures, free space, and the paid
24-hour usage ledger. The default global limit is four reservations.

Emergency order:

1. Close durable intake through the administrator endpoint.
2. Stop `researcher`; the website and completed dossiers remain available.
3. If credential exposure is suspected, delete/revoke the key in the Anthropic
   Console, replace the local secret using the hidden-input tool, and recreate
   only `researcher`.
4. Preserve the data volume and logs for investigation. Never use
   `docker compose down --volumes`.

## Evidence required for completion

- All offline tests and the container boundary CI job pass.
- The API and computational worker do not mount the Anthropic secret.
- The computational worker still reports Docker `NetworkMode=none`.
- The researcher has no published port, runs non-root, and is healthy.
- The host key file has mode `0600`, is absent from Git, and is mounted
  read-only only into the researcher container.
- The paid live check succeeds with real searches and citations.
- A topic submitted through the public HTTPS API completes and downloads a
  citation-bearing dossier.
- The deployment verifier passes with `--require-general`.
- The monitor passes with `--require-researcher`.

Until all of these exist, say **general research implemented but not live-
verified**. Do not infer completion from code, credits, or container health.
