# No-domain macOS beta with Tailscale Funnel

This is ORIGIN's zero-hosting-cost path for a small controlled beta. It uses the
existing Mac as the compute host, Docker Desktop as the container boundary, and
Tailscale Funnel for a stable public `https://…ts.net` endpoint. It does not buy
a domain, expose the home IP, or place a credential in the public site.

This is a beta arrangement, not an always-available production service. It is
online only while this Mac, Docker Desktop, Tailscale, and the ORIGIN containers
are running. Tailscale documents Funnel as beta, subject to fixed bandwidth
limits, and limited to ports 443, 8443, and 10000. The Personal plan currently
includes Funnel at no charge.

Authoritative references:

- [Tailscale Funnel requirements and limitations](https://tailscale.com/kb/1223/funnel)
- [Tailscale Funnel command](https://tailscale.com/docs/reference/tailscale-cli/funnel)
- [Tailscale pricing](https://tailscale.com/pricing)
- [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/)
- [Install Tailscale on macOS](https://tailscale.com/kb/1016/install-mac)

## Security shape

```text
public HTTPS (*.ts.net)
        |
  Tailscale Funnel
        |
127.0.0.1:8080 only ---- public workspace files
        |
authenticated API ---- durable Docker volume

network-disabled worker ---- same durable volume
paid general researcher ---- same volume; outbound only; no published port
```

The API is not published on the LAN or a wildcard host address. The
computational worker keeps `network_mode: none`, receives no credential, and
runs as the non-root image user. The researcher alone receives the Anthropic
secret and outbound access; it has no published port. The API receives only the
tester and administrator secrets.
The API image also contains the dependency-free public workspace, so browser
requests to the workspace and API share one origin. This avoids modern browser
local-network restrictions on a GitHub Pages page calling a `*.ts.net` address
cross-origin. The GitHub Pages bundle contains only the public Funnel origin and
hands research visitors to that same-origin workspace; neither bundle contains
a token.

## 1. Install and sign in

Install current Docker Desktop and Tailscale only from the official links
above. Start both applications and sign in to Tailscale. Funnel activation opens
a Tailscale approval page; the operator must review and approve it. Do not send
the login, recovery codes, passwords, or private keys through chat.

Confirm the local prerequisites:

```bash
docker version
docker compose version
tailscale version
tailscale status
```

Docker must report a running server, not merely a client binary. Tailscale must
show this Mac as connected. Keep macOS awake while testers use the beta.

## 2. Derive the operator-owned Funnel hostname

```bash
ORIGIN_FUNNEL_HOST=$(tailscale status --json | python3 -c \
  'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')
printf '%s\n' "$ORIGIN_FUNNEL_HOST"
```

The value must end in `.ts.net`. It is public configuration, not a credential.
Prepare separate 256-bit tester and administrator tokens with intake closed:

```bash
python3 tools/prepare_beta_deployment.py \
  --host "$ORIGIN_FUNNEL_HOST" \
  --site-origin https://nishchaysinghofficial10-ship-it.github.io
```

The command writes `.env.production` and mode-0600 files under
`deploy/secrets/`; it never prints a token. Do not copy either token into a URL,
GitHub variable, issue, commit, log, or screenshot.

Add and live-check the Anthropic key through hidden terminal input:

```bash
python3 tools/configure_anthropic_key.py
python3 tools/live_general_research_check.py \
  --key-file deploy/secrets/anthropic_api_key.txt
```

## 3. Validate and start only the loopback stack

```bash
python3 tools/compose_beta.py --funnel -- \
  config >/tmp/origin-funnel-compose.yaml

python3 tools/compose_beta.py --funnel -- \
  build api worker researcher backup

python3 tools/compose_beta.py --funnel -- \
  up --detach api worker researcher
```

Do not start `proxy` on this path; Tailscale supplies the public TLS boundary.
Confirm that Docker publishes only loopback and intake is closed:

```bash
python3 tools/compose_beta.py --funnel -- ps
curl --fail --silent --show-error http://127.0.0.1:8080/api/v1/health
```

The port display must begin `127.0.0.1:8080->8080/tcp`, never `0.0.0.0` or
`[::]`.

## 4. Enable public HTTPS and run the closed-intake gate

```bash
tailscale funnel --bg --https=443 http://127.0.0.1:8080
tailscale funnel status --json

python3 tools/verify_beta_deployment.py \
  --api-origin "https://$ORIGIN_FUNNEL_HOST" \
  --beta-token-file deploy/secrets/beta_token.txt \
  --admin-token-file deploy/secrets/admin_token.txt \
  --require-general
```

The first Funnel command can open an approval page. Approve only the public
HTTPS proxy to this loopback service. Never bypass a certificate warning. DNS
can take up to ten minutes on first activation according to Tailscale.

The gate must prove bounded capabilities, a healthy durable queue,
unauthenticated rejection, and tester/admin separation before intake opens.

## 5. Open intake and exercise the real worker

```bash
python3 tools/prepare_beta_deployment.py \
  --host "$ORIGIN_FUNNEL_HOST" \
  --site-origin https://nishchaysinghofficial10-ship-it.github.io \
  --accept-jobs

python3 tools/compose_beta.py --funnel -- \
  up --detach api

python3 tools/verify_beta_deployment.py \
  --api-origin "https://$ORIGIN_FUNNEL_HOST" \
  --beta-token-file deploy/secrets/beta_token.txt \
  --admin-token-file deploy/secrets/admin_token.txt \
  --exercise \
  --require-general
```

The exercise must create, pause, resume, and complete one real mission; validate
its dossier; and create and cancel another. A failure leaves this deployment in
staging until diagnosed.

## 6. Connect the public evidence site

Create the repository Actions **variable** below—never a secret or token:

```text
ORIGIN_BETA_API_URL=https://<this-mac>.<tailnet>.ts.net
```

Run `Deploy public website`, then verify the browser boundary:

```bash
python3 tools/verify_beta_deployment.py \
  --api-origin "https://$ORIGIN_FUNNEL_HOST" \
  --site-url https://nishchaysinghofficial10-ship-it.github.io/origin \
  --beta-token-file deploy/secrets/beta_token.txt \
  --admin-token-file deploy/secrets/admin_token.txt \
  --require-general
```

Also verify the same-origin workspace served by the API image:

```bash
python3 tools/verify_beta_deployment.py \
  --api-origin "https://$ORIGIN_FUNNEL_HOST" \
  --site-url "https://$ORIGIN_FUNNEL_HOST" \
  --beta-token-file deploy/secrets/beta_token.txt \
  --admin-token-file deploy/secrets/admin_token.txt \
  --require-general
```

The second gate must report `site_connection: same-origin`. Opening the public
GitHub Pages URL with `#beta` should move the browser to
`https://$ORIGIN_FUNNEL_HOST/#beta`, where the live connection indicator must
read `Live research service ready` without requesting local-network permission.

Give a named tester only `deploy/secrets/beta_token.txt` through a separate
secure channel. Keep `admin_token.txt` operator-only.

## 7. Operate and stop safely

Use the monitoring, backup, restore, and incident procedures in
[`BETA_DEPLOYMENT_RUNBOOK.md`](BETA_DEPLOYMENT_RUNBOOK.md). Docker volumes live
inside Docker Desktop; an off-Mac copy of verified backups is still required for
recovery from laptop loss or disk failure.

To take the beta offline without deleting data:

```bash
python3 tools/verify_beta_deployment.py \
  --api-origin "https://$ORIGIN_FUNNEL_HOST" \
  --beta-token-file deploy/secrets/beta_token.txt \
  --admin-token-file deploy/secrets/admin_token.txt \
  --intake closed

tailscale funnel --https=443 http://127.0.0.1:8080 off
python3 tools/compose_beta.py --funnel -- down
```

Do not add `--volumes`; that would delete durable mission data. Reconnect the
public site with an empty API origin if this Mac will remain offline.

## Evidence required before calling this live

- exact commit and a green full CI URL;
- rendered two-file Compose configuration;
- Docker `ps` evidence showing loopback-only API publication;
- public TLS health and the read-only gate JSON;
- mutating acceptance JSON with completed and cancelled mission IDs;
- exact-origin public-site gate after Pages redeployment;
- verified backup and separate-volume restoration;
- paid live check and a completed citation-bearing general mission;
- monitor evidence for the API, offline worker, and paid researcher;
- a real named tester receives only the tester credential.

Until all items exist, call this host-ready or staging—not live.
