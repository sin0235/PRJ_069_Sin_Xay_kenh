# PRJ_069 NAS runtime

This Compose stack runs the API, Flow browser worker, Next.js web app, and same-origin gateway from pinned image artifacts. Runtime containers use UID 10001 (Nginx uses 101). The one-shot `init` container runs as root only to read a host mode-0600 owner-password secret and then assigns `/data` to UID 10001. The API and worker never mount that password secret.

## Configure and build

Run these commands from this directory. Copy `deploy.env.example` to `deploy.env`, replace every placeholder, and set `chmod 600 deploy.env`. Create `secrets/owner-password` as one UTF-8 line of 12–1024 characters and set mode 600. Keep the owner password, deployment env, backup exports, and database seeds outside the image context; `.gitignore` and the root `.dockerignore` exclude them.

`BAHA_AUTH_JWT_SECRET` and `LLM_ENCRYPTION_MASTER_KEY` must each contain at least 32 random bytes and must be different. The bootstrap stores a PBKDF2-SHA256/600,000 hash for the owner and never replaces an existing password hash. It does not create model credentials or seed E2E data.

`AUTH_ALLOWED_ORIGINS` is a comma-separated list of exact origins such as `https://studio.example.org` or `http://192.168.1.175:3069`; do not add a path or trailing slash. `FLOW_DESKTOP_ALLOWED_ORIGINS` is taken from the same value. The default `AUTH_COOKIE_SECURE=true` is for HTTPS. For a local or LAN HTTP acceptance run, set `AUTH_COOKIE_SECURE=false` and set `WEB_BIND` to the intended interface. Restore `true` when the public origin is served over HTTPS.

Run preflight before building, then build the same backend image for API, init, and worker:

```sh
python3 nas_runtime_ops.py --env-file deploy.env preflight
docker compose --env-file deploy.env build api web gateway
```

The deployment example selects `PRJ069_BOOTSTRAP_MODE=adopt`, so an existing named data volume is retained. To initialize a genuinely new empty store, explicitly set `PRJ069_BOOTSTRAP_MODE=fresh` in `deploy.env`, then run:

```sh
docker compose --env-file deploy.env run --build --rm --no-deps init
docker compose --env-file deploy.env up -d --build
```

The `api` and `flow-session-worker` services depend on successful completion of `init`. The init entrypoint remains active when a command is supplied to `docker compose run`; it runs the command first and transfers `/data` ownership to UID 10001 only after success. For a copied migration source, use the explicit `compose.bootstrap-copy.yaml` overlay and set `PRJ069_BOOTSTRAP_SOURCE_HOST_DIR` to a read-only directory containing the three required SQLite files and `media_assets`:

```sh
PRJ069_BOOTSTRAP_SOURCE_HOST_DIR=/secure/nas-backup docker compose --env-file deploy.env \
  -f compose.yaml -f compose.bootstrap-copy.yaml run --build --rm --no-deps init
```

The overlay sets `PRJ069_BOOTSTRAP_MODE=copy` and mounts only that explicit source at `/seed` read-only; the base stack never mounts `/seed`. The source is excluded from Docker builds.

The durable paths are `/data/sin_content_production.db`, `/data/baha_auth_production.db`, `/data/sin_dieu_phoi_dung.db`, `/data/media_assets`, and `/data/flow-profiles`. Their named volumes survive container replacement. The shared VieNeu model cache is `/models/vieneu`; API mounts it read-only and worker mounts it read-write.

## Models and browser worker

Provision and verify the pinned CPU/ONNX VieNeu snapshots explicitly. API and worker startup do not download or load the model:

```sh
docker compose --env-file deploy.env run --rm --no-deps flow-session-worker python -m src.model_runtime prepare
docker compose --env-file deploy.env run --rm --no-deps flow-session-worker python -m src.model_runtime status
```

The worker sets `BROWSER_CHANNEL=chromium`, uses the Playwright Chromium installed by the backend image, and persists profiles at `/data/flow-profiles`. It opens Xvfb, x11vnc, and noVNC only for an active leased login session. Internal worker ports 6080 (noVNC) and 8090 (control) are never published to the host. The API and worker share a private network; the web app and gateway cannot connect to the worker directly. Browser HTTP and WebSocket access goes through the owner-authorized API route and the generic `/v1` gateway proxy. The gateway does not implement an auth bypass.

The worker has a hard limit of two CPUs and sets OMP, OpenBLAS, and MKL to two threads. Its stable project-scoped hostname keeps persistent Chromium lock ownership interpretable across recreation. Init assigns model/profile volume ownership to UID 10001 after bootstrap and sets profile directories to mode 0700.

Only the gateway publishes a host port, defaulting to `127.0.0.1:3069`. Put a TLS reverse proxy in front of it for remote use. For direct LAN HTTP, bind only the intended interface, set the matching exact `http://host:port` origin, and explicitly set `AUTH_COOKIE_SECURE=false`. Nginx uses one worker, has a 501 MiB request-body ceiling (500 MiB file plus multipart framing), and logs `$uri` without query strings.

Check the running stack with:

```sh
docker compose --env-file deploy.env ps
curl -fsS http://127.0.0.1:3069/healthz
curl -fsS http://127.0.0.1:3069/readyz
```

Both public probes proxy to the API; they return an upstream error when the API is stopped. Compose checks gateway `/readyz`. Run the reversible failure test only against the isolated acceptance stack; it stops that project's API, checks both probes fail, then restarts the API and checks recovery:

```sh
PRJ069_RUNTIME_ENV_FILE=/absolute/path/to/deploy.env.infra-test \
  python3 tests/test_gateway_readiness_runtime.py
```

The gateway and frontend are public entry points. Do not publish API, worker, CDP, VNC, or Docker socket ports.

## Preflight, backup, and restore

Preflight checks the rendered Compose contract, credentials without printing them, owner-password format, exact origins, runtime UIDs, memory limits, and available disk. A backup stops API, worker, and web while it archives `/data` and `/data/flow-profiles`, copies `deploy.env` and `owner-password` separately with mode 0600, writes SHA-256 checksums, and atomically renames the completed backup directory. It restarts services that were running before the backup. The model cache is intentionally excluded because pinned snapshots can be downloaded again.

```sh
python3 nas_runtime_ops.py --env-file deploy.env backup ./backups/2026-10-28
python3 nas_runtime_ops.py verify ./backups/2026-10-28
```

Restore never overwrites a populated volume. It restores only into two new empty named volumes, verifies the checksummed archives, extracts to a staging directory, and writes `.prj069-restore-complete.json` markers after each volume is ready. Keep the application stopped until both markers exist. It writes the env and owner-password files to a separate new directory with private permissions; update the restored env file's `AUTH_OWNER_PASSWORD_SECRET_FILE` path before using it. Keep the model cache volume or run the model preparation commands again.

```sh
python3 nas_runtime_ops.py --env-file deploy.env restore ./backups/2026-10-28 \
  --data-volume prj069-restored-data-20261028 \
  --profile-volume prj069-restored-profiles-20261028 \
  --secrets-output /secure/prj069-restored-secrets \
  --image prj069-nas-backend:release
```

Do not point Compose at restored volumes until restore reports success and the marker files are present. Keep the previous volumes intact until the recovered service has been reviewed.

## Release image export

Export the exact locally built image IDs, image archive SHA-256, source revision and dirty-state marker, Compose and runtime-file hashes, dependency-lock hash, and `nas_live: NOT_VERIFIED` into a new release directory:

```sh
python3 nas_runtime_ops.py --env-file deploy.env export-images ./releases/2026-10-28
sha256sum ./releases/2026-10-28/images.tar
```

Transfer `images.tar` and `release-manifest.json` to the NAS, verify the archive checksum, and load with `docker load`. Point Compose image variables at the exported tags. A successful local Docker acceptance does not establish NAS reachability or NAS runtime acceptance; record those as `NOT_VERIFIED` until checked on that host.
