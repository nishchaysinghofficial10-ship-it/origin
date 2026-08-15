# ORIGIN public website and controlled interactive beta

## Status and trust boundary

The public website is a dependency-free static evidence viewer built from the
versioned flagship artifacts. It does not execute research and needs no secret.

The optional interactive beta has two processes:

```text
browser -> authenticated API -> SQLite queue <- exclusive worker -> ORIGIN CLI
                                  audit log                         experiment subprocess
```

The API never imports or invokes the research controller. The worker never
receives the beta access token, an LLM key, or network access in the supplied
container configuration. Only `algobench/fast` and `graphbench/graph_fast` are
accepted. Provider calls and retrievals are fixed at zero.

This remains a controlled beta, not a hostile multi-tenant sandbox. ORIGIN's
experiment confinement is user-space; the worker therefore requires the
additional container boundary in `compose.yaml`. Do not run the worker directly
on a shared public host.

## Build the public website

```bash
python3 -m unittest tests.test_web_site -v
python3 tools/build_web.py --out build/web
python3 -m http.server 4173 --directory build/web
```

The build copies these exact artifacts rather than retyping their claims:

- preregistration and three-workflow evaluation;
- full mission `state.json` and append-only event log;
- dossier and timeline.

GitHub Pages deployment is defined in `.github/workflows/pages.yml`. It runs the
site tests before uploading `build/web` and deploys only from `main` or an
explicit manual dispatch.

The exact single-host TLS deployment, launch gate, site connection, backup,
restore, rollback, and monitoring sequence is in
[`BETA_DEPLOYMENT_RUNBOOK.md`](BETA_DEPLOYMENT_RUNBOOK.md).

## Run the controlled beta locally

Create separate random tester and administrator tokens without placing either in
shell history:

```bash
mkdir -p deploy/secrets
python3 -c 'import secrets; print(secrets.token_urlsafe(32))' \
  > deploy/secrets/beta_token.txt
python3 -c 'import secrets; print(secrets.token_urlsafe(32))' \
  > deploy/secrets/admin_token.txt
chmod 600 deploy/secrets/beta_token.txt deploy/secrets/admin_token.txt
docker compose up --build
```

The API listens on loopback at `http://127.0.0.1:8080`. The worker has no
network interface. For direct development without Docker, use two terminals and
an environment-only token:

```bash
export ORIGIN_WEB_BETA_TOKEN='at-least-24-random-characters'
export ORIGIN_WEB_ADMIN_TOKEN='a-different-24-character-or-longer-token'
export ORIGIN_WEB_ALLOWED_ORIGINS='http://127.0.0.1:4173'
python3 -m origin_web api
python3 -m origin_web worker
```

Never put a real token in a URL, repository file, screenshot, client bundle, or
support message.

## API surface

Public:

- `GET /api/v1/health`
- `GET /api/v1/capabilities`

Bearer-authenticated:

- `POST /api/v1/missions`
- `GET /api/v1/missions`
- `GET /api/v1/missions/{id}`
- `GET /api/v1/missions/{id}/dossier`
- `POST /api/v1/missions/{id}/pause`
- `POST /api/v1/missions/{id}/resume`
- `POST /api/v1/missions/{id}/cancel`

Administrator-token only:

- `GET /api/v1/admin/health`
- `POST /api/v1/admin/intake` with `{"accepting": false}` for emergency stop

Mutation operations require `Content-Type: application/json`; pause, resume and
cancel accept an empty JSON object. Query parameters and unknown mission fields
are rejected.

Example request:

```bash
curl -sS http://127.0.0.1:8080/api/v1/missions \
  -H "Authorization: Bearer $ORIGIN_WEB_BETA_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"question":"Which sorting strategy wins at small sizes?","domain":"algobench","profile":"fast"}'
```

## Production requirements

Before exposing the beta beyond named testers:

1. Terminate TLS at a maintained reverse proxy or managed container platform.
2. Keep one API replica and exactly one worker while SQLite is used.
3. Attach a persistent local volume; do not place SQLite on an object store or
   network filesystem with unreliable locking.
4. Set an exact HTTPS origin in `ORIGIN_WEB_ALLOWED_ORIGINS`.
5. Store distinct beta and administrator tokens in the platform's secret
   manager and rotate either after any suspected exposure. Never give the
   administrator token to ordinary testers.
6. Keep the worker network disabled. The current beta has no provider or live
   retrieval authority.
7. Back up the `/data` volume and test restoration.
8. Monitor `/api/v1/admin/health`, container health, disk space, queue age,
   worker restarts, and failed missions.
9. Set `ORIGIN_WEB_ACCEPT_JOBS=0` or call the intake endpoint before maintenance.
10. Add external identity, per-user tokens, and stronger kernel isolation before
    calling the service generally available.

GitHub Pages cannot be relied on for application-specific response headers.
The checked-in page therefore uses a restrictive CSP meta policy and no remote
runtime assets. Before enabling browser token entry for users beyond named beta
testers, serve the static build behind an edge that adds at least
`Content-Security-Policy`, `X-Content-Type-Options`, `Referrer-Policy`, and
`frame-ancestors 'none'` as HTTP response headers.

## Operations and incident response

Health probes:

```bash
curl -fsS https://BETA_API/api/v1/health
curl -fsS https://BETA_API/api/v1/admin/health \
  -H "Authorization: Bearer $ORIGIN_WEB_ADMIN_TOKEN"
```

The public probe deliberately exposes no queue counts. The authenticated admin
probe reports durable status counts. Alert on an unhealthy container, growing
`queued` age, any persistent `failed` count, worker restart loops, a nearly full
volume, or a backup failure.

Emergency stop and recovery:

```bash
curl -fsS -X POST https://BETA_API/api/v1/admin/intake \
  -H "Authorization: Bearer $ORIGIN_WEB_ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"accepting":false}'
# Inspect running missions, preserve /data, and stop the worker if required.
# Re-open only after the fault is understood and a restore test succeeds.
```

Back up the entire stopped `/data` volume, including the SQLite database, WAL
files if present, and mission directories. `python -m origin_web.backup` uses
SQLite's backup API, archives mission artifacts with a SHA-256 manifest, rejects
unsafe members, and restores only into an empty target. The production runbook
uses a separate restored volume so the live volume remains available for
rollback. Never deploy an older schema blindly over newer data.

## Release gate

The beta is ready to expose only when all of these are true:

- `python -m unittest discover -s tests` passes at the deployment commit;
- the container build and unauthenticated rejection smoke test pass in CI;
- API and worker share one persistent local volume, with exactly one worker;
- the API is behind HTTPS and an exact HTTPS browser origin is configured;
- separate tester and admin credentials are stored outside the repository;
- the worker has no network interface and runs as a non-root user;
- backup, restore, emergency intake closure, restart recovery, and rollback have
  been exercised on the target host;
- the public site is built with that exact API origin and no credential;
- one clean-room tester can create, observe, pause/resume or cancel, and download
  a completed dossier without seeing another tester's mission.

## Known beta limitations

- A single SQLite queue and exclusive worker; no horizontal worker scaling.
- Bearer-token access for named testers, not public account registration.
- Pausing takes effect between durable controller steps. Cancellation can stop a
  running step and then records a durable cancellation in the core mission.
- Dossiers are the only downloadable artifact through the API. Raw files remain
  private to the worker volume.
- The service does not accept user code, file paths, URLs, arbitrary profiles,
  provider settings, or resource budgets.
