# General research beta threat model

Scope: `origin_web/general_research.py`, `researcher.py`, paid usage in
`store.py`, the `general/web_research` API schema, and production Compose.

## Trust boundaries

| Component | Trust | Authority |
|---|---|---|
| Browser topic/token | untrusted | submit within authenticated quotas |
| Queue API | trusted code | validate/authenticate; no provider credential |
| SQLite + mission volume | operator-controlled durable data | queue, audit, reports, paid ledger |
| General researcher | trusted code as fixed UID/GID 10001 in a container with root-owned application filesystem | Anthropic secret + outbound network; writable data volume and noexec tmpfs; no inbound port |
| Anthropic/model/search content | untrusted external data | return text, search results and citations only |
| Computational worker | separate trusted code | fixed local templates; no network or provider secret |

## Threats and controls

| Threat | Control | Evidence |
|---|---|---|
| Anonymous credit exhaustion | tester Bearer token; one active mission; tester/global rolling daily limits | API/store tests |
| Crash loop repeats paid calls | durable reservation and attempt charge immediately before each request; production maximum one | provider budget tests |
| Topic requests harmful instructions | narrow local operational-harm gate plus independent provider policy prompt; safe sensitive research allowed | policy/API tests |
| Topic breaks the prompt envelope | XML escaping; topic explicitly declared untrusted and unable to override method | client body test |
| Search-page prompt injection | every source declared untrusted; no client-side tool execution; output is report text only | architecture assertion/tests |
| Model invents or omits sources | mission fails without a paid search and two distinct usable HTTPS citations; source URLs are scheme/authority validated | ungrounded-response test |
| Provider text executes locally | researcher exposes no local tool; output never enters CLI, sandbox design, Evidence, facts or graph | service separation tests |
| Secret leaks to API/worker/site | Docker secret only on researcher; key only in header; Git-ignored mode-0600 host file becomes a mode-0400 runtime secret owned by fixed non-root UID; metadata tests scan outputs | Compose/key/client tests |
| Cross-tester report access | owner-hash filter on every mission and dossier route | API isolation test |
| Researcher steals compute work | domain-filtered atomic claims; offline worker has complementary filter | researcher integration test |
| Malicious Markdown URL | source ledger accepts HTTPS only; user topic is Markdown-escaped; dossier served as `text/markdown` with `nosniff` | client tests/API headers |
| Unbounded response/resource use | 8 MB provider response cap, 3,200-token requested final-output ceiling, hard 3-search limit, timeout, zero production continuations, 2 MB public dossier cap | config/client/API tests |

## Residual risks

1. A citation can support only part of a model-written passage or be
   misinterpreted. Users must inspect original sources.
2. Web/model outputs are nondeterministic and cannot satisfy the computational
   core's exact replay guarantee.
3. The researcher has ordinary outbound container networking. The code targets
   only the fixed Anthropic HTTPS endpoint, but Docker Compose does not enforce
   a domain-level egress firewall. Run it on a dedicated host or add an
   operator-managed egress proxy for a higher-assurance deployment.
4. A paid request can complete after a user asks to cancel because a blocking
   provider request cannot be interrupted safely. Cancellation is applied when
   the response returns, and the paid attempt remains recorded.
5. Provider retention, abuse monitoring and availability are governed by the
   operator's Anthropic account and contract, not by ORIGIN.
6. Topic screening is intentionally narrow and is not a complete content-
   moderation system. Provider safeguards remain defense in depth, not proof.
7. The secret bridge places values in the short-lived Docker Compose client's
   process environment because Compose needs an environment-backed source to
   enforce runtime UID/GID/mode portably. The values are never put in a service
   environment. Other processes with authority to inspect the operator's
   processes or Docker daemon are already inside the deployment trust boundary.
