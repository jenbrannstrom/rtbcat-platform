# Hetzner immutable shadow deployment — Part 3

This deployment is prepared but has not been run. It starts the API and
dashboard on the Hetzner app host without changing DNS, exposing either service
publicly, starting schedulers, or disabling the GCP deployment.

## Runtime shape

```text
SSH/Tailscale acceptance tunnel
        │
        ├── 127.0.0.1:3000 ── dashboard@sha256
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
- publishes API and dashboard images using the full Git SHA as a discovery tag;
- records each returned image digest;
- attaches source, revision, SBOM and provenance metadata; and
- emits a `hetzner-release-<full-sha>` artifact containing
  `hetzner-release.env` and its checksum-matched `hetzner-compose.yml`.

The deployment uses the digests, never the discovery tags. The workflow uses
its repository-scoped `GITHUB_TOKEN` with `packages: write`, as supported by
[GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#authenticating-in-a-github-actions-workflow).

If the two packages are public, the host can pull anonymously. For private
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
  --confirm deploy-shadow-no-dns
```

The command verifies the PostgreSQL certificate/private path, pulls both exact
digests, checks their full revision labels and fixed runtime UID, confirms any
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
- API and dashboard listen only on loopback;
- no local PostgreSQL listener exists on the app host;
- all scheduler ownership flags remain false; and
- retained Google services are reachable from the target identity.

Use an SSH tunnel for shadow review, for example local port 33000 to target
`127.0.0.1:3000`. Public DNS and ports 80/443 remain unused in this part.

## 4. Roll back the application release

Successful manifests remain in `/var/lib/rtbcat/releases`. List and select one:

```bash
sudo scripts/hetzner/rollback_app_release.sh --list

sudo scripts/hetzner/rollback_app_release.sh \
  --to-sha FULL_40_CHARACTER_SHA \
  --confirm rollback-immutable-release
```

Rollback re-runs the same digest, database, Google-access and scheduler gates.
It is an application-image rollback only. Once target writers are enabled in a
later part, database compatibility and the written rollback boundary govern
whether an older application release remains safe.
