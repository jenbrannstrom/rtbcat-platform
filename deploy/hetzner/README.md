# Hetzner immutable shadow deployment — Part 3

The immutable shadow deployment is accepted on the Hetzner app host. Its
writable activation path is implemented but has not been run live. Neither
entry point changes DNS, exposes either service publicly, starts schedulers or
disables the GCP deployment.

## Runtime shape

```text
SSH/Tailscale acceptance tunnel
        │
        ├── 127.0.0.1:3000 ── dashboard@sha256
        ├── 127.0.0.1:8010 ── MCP@sha256 (kill switch off by default)
        └── 127.0.0.1:8000 ── API@sha256
                                  ├── TLS verify-full ── 10.60.1.20:5432
                                  └── ADC ── retained GSM / BigQuery / GCS
```

There is no Cloud SQL proxy in this Compose file. PostgreSQL uses the fixed
Hetzner private address, and the container entrypoint constructs its DSN from a
mounted password file. The password therefore does not appear in Compose,
Terraform state, the release manifest or Docker image configuration.

The Compose file contains no `build:` keys and accepts image references through
the digest-only release manifest. Docker supports image references in
`name@sha256:digest` form. See the official
[Compose service reference](https://docs.docker.com/reference/compose-file/services/#image).

## 1. Publish one exact commit

Manually run `.github/workflows/build-and-push-ghcr.yml` at the intended frozen
commit and enter `PUBLISH_HETZNER`. The workflow:

- runs deployment-critical tests;
- publishes API, dashboard and MCP images using the full Git SHA as discovery
  tags;
- records each returned image digest;
- attaches source, revision, SBOM and provenance metadata; and
- emits a `hetzner-release-<full-sha>` artifact containing
  `hetzner-release.env` and its checksum-matched `hetzner-compose.yml`.

The deployment uses the digests, never the discovery tags. The workflow uses
its repository-scoped `GITHUB_TOKEN` with `packages: write`, as supported by
[GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#authenticating-in-a-github-actions-workflow).

If the three packages are public, the host can pull anonymously. For private
packages, create a dedicated classic PAT with `read:packages` only, place it in
a temporary mode-0600 file on the host, and run:

```bash
sudo scripts/hetzner/install_ghcr_pull_credentials.sh \
  --username GITHUB_USER \
  --token-file /secure/path/ghcr-read-token
```

Remove the input file after the root-only Docker config has been verified.

## 2. Install runtime files

First move the Terraform-created app-data Volume to the stable path consumed by
Compose. This must happen before secrets or application data are installed:

```bash
sudo scripts/hetzner/bootstrap_app_data_volume.sh \
  --volume-id APP_DATA_VOLUME_ID
```

The existing roughly 93 GB `.catscan` tree is copied server-to-server in the
data rehearsal; it is not routed through the operator laptop. The script above
only prepares the empty target mount.

Copy `runtime.env.example` outside the repository and replace every placeholder.
All three scheduler flags must remain `false` throughout Parts 3 and 4.

Prepare these files on the app host:

- the target database password, mode 0600;
- the PostgreSQL certificate copied from the database host;
- an Application Default Credentials JSON file, mode 0600; and
- the completed non-secret runtime env.

Prefer a renewable `external_account` Workload Identity Federation config backed
by an approved external identity provider. A credential configuration does not
itself create an identity provider or refresh its subject token. If no renewable
IdP is available for the Hetzner host, a dedicated least-privilege service-account
key is the temporary fallback and requires an explicit flag. Google recommends
[Workload Identity Federation for external workloads](https://docs.cloud.google.com/iam/docs/workload-identity-federation)
because service-account keys carry additional security risk.

Install the files without printing their contents:

```bash
sudo scripts/hetzner/install_app_secrets.sh \
  --runtime-env /secure/path/rtbcat-runtime.env \
  --postgres-password /secure/path/postgres-password \
  --postgres-ca /secure/path/postgres-ca.crt \
  --google-credentials /secure/path/google-adc.json
```

Add `--allow-service-account-key` only after approving that fallback. The
installed credentials must have read/access permissions required by the live
application, scoped to the retained Secret Manager secrets, BigQuery dataset
and GCS bucket. No credential is added to Terraform or git.

## 3. Deploy the digest manifest

Keep both downloaded artifact files in the same protected directory on the app
host, then run:

```bash
sudo scripts/hetzner/deploy_app_release.sh \
  --release-file /secure/path/hetzner-release.env \
  --mcp-enabled false \
  --confirm deploy-shadow-no-dns
```

The command verifies the PostgreSQL certificate/private path, pulls all exact
digests, checks their full revision labels and fixed runtime UID where
required, confirms any
current Gmail import is idle, renders Compose, starts the shadow containers,
hydrates the existing Gmail OAuth client/token and Authorized Buyers credential
directly from Secret Manager into the protected app-data mount, and runs
acceptance checks. Google checks are read-only: ADC refresh, Secret Manager
access, BigQuery metadata listing and GCS object listing. Secret values are
discarded or written mode 0600 and never logged.

The exact Compose file is archived beside each accepted manifest. Rollback uses
that archived copy, so a later Compose change cannot silently alter an older
release or prevent its checksum-matched rollback.

The deployment is accepted only when:

- health reports the exact full Git SHA and a working target database;
- the running image references exactly match the approved digests;
- API, dashboard and MCP listen only on loopback;
- MCP health reports the explicitly requested kill-switch state;
- no local PostgreSQL listener exists on the app host;
- all scheduler ownership flags remain false; and
- retained Google services are reachable from the target identity.

## Bounded live writable rehearsal (B1)

This target-only rehearsal is distinct from final activation. It is restricted
to `rtbcat_serving_rehearsal`, keeps the release loopback-only, keeps every
scheduler false, arms a 15-minute read-only restoration deadman, verifies that
all scheduled endpoints refuse execution, performs a rollback-only database
write probe and restores both application and database read-only posture:

```bash
sudo scripts/hetzner/rehearse_live_writable_release.sh \
  --release-file /var/lib/rtbcat/releases/current.env \
  --json-out /secure/evidence/b1-writable-rehearsal.json \
  --confirm REHEARSE_LIVE_WRITABLE_SCHEDULERS_OFF_NO_DNS
```

Bracket B1 with target differential backups. Writable startup can apply
pending migrations and maintenance changes to the stale rehearsal database;
record those separately from the rollback-only probe. B1 never authorizes DNS,
GCP, source-writer, Cloud SQL or scheduler changes and always returns the
target to shadow mode.

## Initial writable activation (approval-gated)

The same checksum-matched Compose artifact defaults to shadow mode. A separate
entry point can render it writable only after final-sync evidence proves source
writers are frozen, subscriber catch-up and sequence synchronization are
complete, final reconciliation and target backup are accepted, DNS is
unchanged, and no target scheduler is enabled:

```bash
sudo scripts/hetzner/activate_writable_release.sh \
  --release-file /var/lib/rtbcat/releases/current.env \
  --cutover-evidence /secure/evidence/writable-activation-input.json \
  --json-out /secure/evidence/writable-activation-receipt.json \
  --confirm ACTIVATE_WRITABLE_SCHEDULERS_OFF_NO_DNS
```

This command is not authorization to run it. It requires its own final-sync
approval. It verifies the currently accepted immutable shadow first, keeps all
three scheduler flags false, preserves loopback-only listeners and restores
shadow mode automatically if activation verification fails. The check-only
rehearsal uses the separate
`REHEARSE_WRITABLE_SCHEDULERS_OFF_NO_DNS` confirmation and changes no
containers.

Use an SSH tunnel for shadow review, for example local port 33000 to target
`127.0.0.1:3000`. Public DNS and ports 80/443 remain unused in this part.

## Temporary public-path acceptance

A non-production hostname can validate public TLS, reverse-proxy routing,
cookies, authentication callbacks and representative API behavior before the
production hostname moves. This gate does not change `scan.rtb.cat`, database
mode, scheduler ownership or GCP authority.

First stage Nginx and Certbot in sealed mode:

```bash
sudo scripts/hetzner/manage_temp_public_ingress.sh stage \
  --hostname scan-hetzner.rtb.cat \
  --confirm STAGE_TEMP_INGRESS_SEALED_NO_DNS
```

Sealed mode serves only the ACME challenge webroot and HTTP 404 for the
temporary hostname; unknown hosts are dropped and no request can reach the
application. Create a DNS-only Cloudflare `A` record for the temporary
hostname only after sealed behavior is verified externally. Never edit the
production record as part of this gate.

After the temporary record resolves directly and exclusively to the stable
Hetzner application IPv4, install the temporary OAuth2 Proxy from root-only
copies of the current production OAuth client pair. Never place either input
in git, a command argument or terminal output:

```bash
sudo scripts/hetzner/install_temp_google_oauth_proxy.sh \
  --hostname scan-hetzner.rtb.cat \
  --allowed-email-domain rtb.cat \
  --allowed-email-domain amazingdo.com \
  --confirm INSTALL_TEMP_GOOGLE_OAUTH_PROXY_NO_DNS
```

Add `https://scan-hetzner.rtb.cat/oauth2/callback` to the existing Web OAuth
client's authorized redirect URIs without removing the production callback.
Install `deploy/hetzner/temp-google-oauth.override.yml` as
`/etc/rtbcat/temp-google-oauth.override.yml`, then enable Google login on the
read-only rehearsal deployment:

```bash
sudo scripts/hetzner/rehearse_temp_google_login.sh \
  --confirm ENABLE_TEMP_GOOGLE_LOGIN_READ_ONLY_SCHEDULERS_OFF
```

The rehearsal arms a 15-minute deadman and refuses any database other than
`rtbcat_serving_rehearsal`, writable mode, scheduler enablement, listener
exposure or release drift. It discovers the API container's exact Docker
gateway and trusts OAuth identity only from that address plus loopback. Password
login is hidden during this read-only gate because creating its database-backed
session and audit record is a write; the accepted base/writable deployment
retains password login.

Activate the operator-restricted proxy with Google routing:

```bash
sudo scripts/hetzner/manage_temp_public_ingress.sh activate \
  --hostname scan-hetzner.rtb.cat \
  --operator-cidr OPERATOR_PUBLIC_IP/32 \
  --expected-ipv4 HETZNER_APP_IPV4 \
  --email ACME_CONTACT_EMAIL \
  --google-oauth \
  --confirm ACTIVATE_TEMP_READ_ONLY_INGRESS_SCHEDULERS_OFF
```

Activation refuses unless the API/dashboard are healthy, ports 3000/8000
remain loopback-only, `CATSCAN_READ_ONLY_SHADOW=true`, every target scheduler
flag is false and DNS resolves to the exact expected IPv4. HTTPS is then
restricted to loopback and the approved operator CIDR. `/api/` is routed to
the loopback API with its prefix removed, while other paths route to the
loopback dashboard. `/oauth2/` routes only to the loopback OAuth2 Proxy.

Return the temporary hostname to sealed ACME-plus-404 behavior without
deleting its certificate:

```bash
sudo scripts/hetzner/manage_temp_public_ingress.sh seal \
  --hostname scan-hetzner.rtb.cat \
  --confirm SEAL_TEMP_INGRESS
```

The temporary hostname must remain read-only until the separately approved
final synchronization and writer-freeze gates are complete. It is not a
canary writer and must never own a scheduler.

## 4. Roll back the application release

Successful manifests remain in `/var/lib/rtbcat/releases`. List and select one:

```bash
sudo scripts/hetzner/rollback_app_release.sh --list

sudo scripts/hetzner/rollback_app_release.sh \
  --to-sha FULL_40_CHARACTER_SHA \
  --mcp-enabled false \
  --confirm rollback-immutable-release
```

Rollback re-runs the same digest, database, Google-access and scheduler gates.
It is an application-image rollback only. Once target writers are enabled in a
later part, database compatibility and the written rollback boundary govern
whether an older application release remains safe.

Each accepted manifest retains its checksum-matched Compose generation.
Pre-MCP manifests have no `MCP_IMAGE` and re-render their archived two-service
Compose file; `--remove-orphans` removes a running MCP container during that
rollback. A with-MCP rollback can pass `--mcp-enabled true` only when retaining
an already approved MCP pilot is intentional.
