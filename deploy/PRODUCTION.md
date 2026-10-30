# Single-host deployment and release procedure

Status: configuration prepared, Docker/HTTPS/cloud execution NOT VERIFIED.
This is a Linux single-host design, suitable for preparing a Google Cloud VM staging
environment. It is not a Cloud Run or multi-host design: artifact locks, SQLite and
in-memory limiters require one replica per service and a local filesystem.

## Boundaries

Internet -> Caddy :443 -> Web :3000 -> API :8000 / PostgreSQL :5432.
Only Caddy publishes host ports. Its fixed internal IP is the only trusted Web proxy.
The private subnet 172.30.0.0/24 must not overlap the host/VPC/VPN network; if changed,
update both proxy IP and TRUSTED_PROXIES in compose.production.yml together.
Do not attach untrusted containers to this Compose network.

`web/src/app.ts` configures Express and routes without opening a listening socket.
`web/src/server.ts` owns listening, signal handling and database pool shutdown.
`web/docker-entrypoint.sh` starts the process only. All deployment methods now require
explicit migration/catalog jobs; restarting Web no longer mutates schema or catalog.
Python module boundaries and the legacy BM25 pickle shim remain intact.

## Prepare staging

Use a dedicated Linux host, Docker Engine with Compose v2, a DNS name pointing at
the host, and inbound TCP 80/443 (plus UDP 443 if HTTP/3 is wanted). Restrict SSH
to administrators. Do not expose 3000/8000/5432 or reuse a production database.
No cloud resources are created by this change.

From the repository root, copy each `deploy/*.env.example` to the same name without
`.example`: compose.env, postgres.env, web.env, api.env. Actual `.env` files are ignored.
Set file permissions to 600. Supply independent random JWT/admin/database credentials;
the database password in DATABASE_URL must match postgres.env and be URL encoded.
POSTGRES_* values initialize an empty volume only; changing them does not rotate an
existing database password. Never commit credentials or include them in reports.
Set SITE_DOMAIN and APP_ORIGIN consistently. Use unique immutable release image tags.
Pin reviewed image digests for a controlled release; floating base/service tags in
this template do not establish a reproducible supply chain.

Provide trusted, probed artifacts and the required offline embedding model cache in
`var/`. Do not activate, rebuild or migrate real data just to validate the template.
The Web image runs as UID 1000; grant that UID the required access to `var/data`
and the exported web_items.csv on the host, without changing artifact ownership.
API currently runs as the base image user; least-privilege API volume permissions
and a non-root runtime remain a release hardening gate.

For subsequent commands use this Bash function in the repository root:

```bash
dc() { docker compose --env-file deploy/compose.env -f compose.production.yml "$@"; }
dc config --quiet
dc build api web
dc up -d postgres
dc run --rm --no-deps web node dist/db/migrate.js
dc run --rm --no-deps web node dist/db/sync-courses.js
dc up -d api web proxy
dc ps
```

Prepare the CSV with the existing export_web_catalog.py workflow before syncing.
Sync is an upsert preserving enrollments; it does not delete absent courses.
Migrations must run after backup and review; the schema script is not a general
reversible migration framework. `config --quiet` avoids printing resolved credentials.
Caddy needs working public DNS/ports to obtain and renew certificates. Its certificate
state is persistent. Confirm HTTPS, secure cookies, CSRF, forwarded client IP and SSE
through the public endpoint before promoting staging.

## Observe and stop

```bash
dc ps
dc logs --since 15m --tail 200 api web proxy
curl --fail https://learning.example.com/health
curl --fail https://learning.example.com/ready
dc exec -T api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=8).status)"
dc stop web
```

Web `/health` is process liveness; `/ready` checks PostgreSQL only. It does not
confirm RAG readiness. API `/health` must be checked separately with artifact
version/provenance. Monitor disk space, memory/OOM, container restarts, database
availability, API health and HTTP 5xx/latency. External alert delivery is not configured.
Do not log request bodies, chat content or secrets. Web SIGTERM drains connections
for up to 20 seconds, closes remaining SSE connections, then drains the database
pool; the process has a 25-second hard deadline and Compose allows 30 seconds.

## Backup and recovery drill

Run backups from Bash with restrictive permissions; export them encrypted to a
separate host/storage account and monitor freshness. Backups on this VM alone are
not disaster recovery. Before a coordinated backup, stop Web and any refresh/crawler
jobs so database/catalog/artifact state is not changing across the backup window.
Confirm no other writers exist; API can keep reading the active artifacts.

```bash
umask 077
mkdir -p deploy/backups
backup_stamp=$(date -u +%Y%m%dT%H%M%SZ)
dc exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "deploy/backups/db-$backup_stamp.dump"
tar -czf "deploy/backups/var-$backup_stamp.tgz" var
sha256sum "deploy/backups/db-$backup_stamp.dump" "deploy/backups/var-$backup_stamp.tgz" > "deploy/backups/$backup_stamp.sha256"
```

Check every command exit status before marking a backup successful. Record release
image tags and CURRENT.json version alongside the pair. Restore first on a separate
staging instance: verify hashes, inspect archive paths, restore var into that staging
checkout, and use pg_restore into a newly created empty database. Point staging Web
at that restored database and validate accounts/enrollments/catalog and API provenance.
Never run `down -v`, `pg_restore --clean` or overwrite the live var directory as a
routine deployment step. Backup and restore execution is NOT VERIFIED here.

## Release and rollback

Preserve previous image tags, database/var backup pairs and previous artifact versions.
For index/catalog changes use a maintenance window: stop Web, run the existing
staging -> probe -> activate workflow, reload/restart API, export the matching Web
catalog and sync PostgreSQL, then start Web and verify matching provenance. These
systems do not share a cross-service atomic transaction. If a step fails, keep Web
stopped and restore/rollback the matching pair before accepting traffic.

For a code-only rollback, restore previous API_IMAGE/WEB_IMAGE tags in compose.env
and recreate API/Web. Use the existing index rollback CLI for artifacts. A code
rollback cannot undo schema or data changes; restore a tested backup when required.
Do not promote until Docker build, restore drill, real PostgreSQL flows, browser/SSE,
RAG quality and load measurements pass in Linux staging. No deployment has occurred.
