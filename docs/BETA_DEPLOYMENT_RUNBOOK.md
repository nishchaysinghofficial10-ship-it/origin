# Controlled beta production deployment runbook

This is the exact single-host handoff for ORIGIN's interactive computational
beta. It preserves the verified v2.1.2 core and adds three boundaries around
it: an automatic-HTTPS proxy, an authenticated queue API, and a network-disabled
exclusive worker.

The public evidence site does not need this server. It is already deployed at
`https://nishchaysinghofficial10-ship-it.github.io/origin/`.

## Required operator-owned values

- A persistent Linux server capable of running current Docker Engine and Docker
  Compose.
- A DNS hostname such as `beta.example.com` whose A/AAAA record points to that
  server.
- Inbound TCP ports 80 and 443, plus optional UDP 443, open to the server.
- The exact browser origin allowed to call the API. For the current GitHub Pages
  site this is `https://nishchaysinghofficial10-ship-it.github.io`—an Origin
  never includes the `/origin/` path.

Caddy requires the hostname and public ports to obtain and renew a trusted
certificate. See Caddy's
[official HTTPS prerequisites](https://caddyserver.com/docs/quick-starts/https).
Install Docker using the current instructions for the server's distribution,
not a copied third-party install script.

Do not send server passwords, access tokens, or private keys through chat. Use
the host/provider's normal secure login and secret facilities.

## 1. Prepare the server fail-closed

```bash
git clone https://github.com/nishchaysinghofficial10-ship-it/origin.git
cd origin
git status --short

python3 tools/prepare_beta_deployment.py \
  --host beta.example.com \
  --site-origin https://nishchaysinghofficial10-ship-it.github.io
```

The preparation command:

- validates both origins;
- creates separate 256-bit tester and administrator credentials with mode 0600;
- never prints either credential;
- writes `.env.production` with mission intake set to `0`;
- refuses to overwrite a deployment configured for another host.

Verify the rendered production configuration before starting anything:

```bash
docker compose --env-file .env.production \
  --file compose.production.yaml config >/tmp/origin-production-compose.yaml
docker compose --env-file .env.production \
  --file compose.production.yaml pull proxy
docker compose --env-file .env.production \
  --file compose.production.yaml build api worker backup
```

Only the Caddy proxy publishes host ports. The API is reachable only on the
private Compose network. The worker has `network_mode: none`, receives neither
credential, runs as a non-root user, and shares only the durable data volume.

## 2. Start with intake closed

```bash
docker compose --env-file .env.production \
  --file compose.production.yaml up --detach api worker proxy
docker compose --env-file .env.production \
  --file compose.production.yaml ps
docker compose --env-file .env.production \
  --file compose.production.yaml logs --tail 100 api worker proxy
```

Confirm DNS, TLS, and the deliberately closed public health response:

```bash
curl --fail --silent --show-error https://beta.example.com/api/v1/health
```

Never bypass a TLS warning. A certificate failure means DNS, ports, system time,
or Caddy's certificate state must be fixed before proceeding.

## 3. Run the read-only deployment gate

```bash
python3 tools/verify_beta_deployment.py \
  --api-origin https://beta.example.com \
  --beta-token-file deploy/secrets/beta_token.txt \
  --admin-token-file deploy/secrets/admin_token.txt
```

This proves the public health response is bounded, provider and retrieval
authority remain zero, unauthenticated access is rejected, a tester cannot use
administrator endpoints, and the durable queue is healthy. The command never
prints either credential.

If it fails, keep intake closed and inspect the request ID alongside container
logs. Do not weaken authentication, CORS, TLS, or worker isolation to make the
gate pass.

## 4. Open intake and exercise the real workflow

Change only the fail-closed intake setting with the same validated preparation
tool, then recreate the API container:

```bash
python3 tools/prepare_beta_deployment.py \
  --host beta.example.com \
  --site-origin https://nishchaysinghofficial10-ship-it.github.io \
  --accept-jobs
docker compose --env-file .env.production \
  --file compose.production.yaml up --detach api
```

Run the mutating acceptance gate:

```bash
python3 tools/verify_beta_deployment.py \
  --api-origin https://beta.example.com \
  --beta-token-file deploy/secrets/beta_token.txt \
  --admin-token-file deploy/secrets/admin_token.txt \
  --exercise
```

The exercise creates a real bounded sorting mission, pauses it durably, resumes
it, waits for completion, downloads and validates its dossier, then creates and
cancels a second mission. Add `--other-beta-token-file PATH` when a second tester
credential exists to prove cross-tester mission isolation on the live host.

## 5. Connect the public site

In the GitHub repository, create an Actions **variable**, not a secret:

```text
ORIGIN_BETA_API_URL=https://beta.example.com
```

Manually run the `Deploy public website` workflow. Its builder accepts only a
bare HTTPS origin and writes no credential into the site. After deployment,
verify the exact browser connection:

```bash
python3 tools/verify_beta_deployment.py \
  --api-origin https://beta.example.com \
  --site-url https://nishchaysinghofficial10-ship-it.github.io/origin \
  --beta-token-file deploy/secrets/beta_token.txt \
  --admin-token-file deploy/secrets/admin_token.txt
```

The gate confirms the site runtime configuration names this API exactly, the
configured CORS origin is allowed, an untrusted origin is not reflected, and no
Bearer credential appears in the public bundle.

## 6. Back up and prove restoration

First close durable intake with the credential-safe operator tool, stop the
worker, and wait for it to stop before taking the artifact snapshot:

```bash
python3 tools/verify_beta_deployment.py \
  --api-origin https://beta.example.com \
  --beta-token-file deploy/secrets/beta_token.txt \
  --admin-token-file deploy/secrets/admin_token.txt \
  --intake closed
docker compose --env-file .env.production \
  --file compose.production.yaml stop worker
docker compose --env-file .env.production \
  --file compose.production.yaml --profile ops run --rm backup create \
  --data-dir /data --out /backup/origin-beta-latest.tar.gz
docker compose --env-file .env.production \
  --file compose.production.yaml --profile ops run --rm backup verify \
  --archive /backup/origin-beta-latest.tar.gz
```

The archive contains an online SQLite backup plus all mission artifacts and a
SHA-256 manifest. It rejects symlinks, special files, path traversal, unlisted
members, duplicate paths, corrupt digests, and an invalid database. Credentials
are outside `/data` and cannot enter the archive.

Prove restoration into a separate volume—never over the live one:

```bash
docker volume create origin-beta-restored
docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid \
  --mount source=origin-beta-backups,target=/backup,readonly \
  --mount source=origin-beta-restored,target=/restore \
  origin-beta:2.1.2-web-beta \
  python -m origin_web.backup restore \
  --archive /backup/origin-beta-latest.tar.gz --target /restore
```

To perform an actual recovery, leave the old volume intact, set
`ORIGIN_DATA_VOLUME=origin-beta-restored` in `.env.production`, start only the
API with intake closed, run the administrator health gate, then start the worker
and repeat the full acceptance test. Roll back by pointing to the untouched old
volume; never mix one database with another volume's mission directory.

After a routine backup, restart the worker and reopen durable intake with the
same verifier using `--intake open` only when maintenance is complete.

## 7. Monitor and respond

At minimum monitor:

- `GET /api/v1/health` from outside the server;
- authenticated `GET /api/v1/admin/health` from a protected monitor;
- container health/restart counts and worker lease errors;
- queue age, failed mission count, and available space on data/backup volumes;
- Caddy certificate renewal and 4xx/5xx rates;
- successful backup creation, digest verification, and periodic restore tests.

Compose rotates API, worker, and proxy logs at five 10 MiB files per service.
Caddy logs method and path to stdout; tokens are accepted only in the
Authorization header and are not placed in URLs or application logs.

Emergency response:

1. Close durable intake through the administrator endpoint.
2. Set `ORIGIN_WEB_ACCEPT_JOBS=0` in `.env.production` and recreate the API for a
   second independent kill switch.
3. Stop the worker if an active mission must be interrupted.
4. Preserve logs and the data volume; do not delete evidence during triage.
5. Rotate tester/admin credentials and recreate the API after any suspected
   credential exposure.
6. Restore into a new volume and run every gate before reopening.

## Evidence required before declaring the beta live

- Git commit deployed and corresponding green CI run URL.
- `docker compose config` and Caddy validation succeeded at that commit.
- Public TLS health response succeeded without overrides.
- Read-only gate JSON recorded.
- Mutating exercise JSON recorded, including completed and cancelled mission IDs.
- Site-connection gate succeeded after the Pages rebuild.
- Backup manifest verification and separate-volume restoration succeeded.
- One real named tester received only the tester credential; the administrator
  credential remained operator-only.

Until every item exists, describe the service as deployment-ready or staging,
not as a live interactive beta.
