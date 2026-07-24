# RTBcat Hetzner foundation — Part 1

This stack is the first implementation part of the GCP-to-Hetzner migration.
It defines the target foundation but does not deploy RTBcat, install
PostgreSQL, migrate data, update DNS or disable any GCP service.

## Topology

- One app host in Singapore (`sin`), default `cpx22` (2 shared AMD vCPUs,
  4 GB RAM and 80 GB local storage).
- A protected 150 GB XFS app-data Volume for the roughly 93 GB live `.catscan`
  tree; the smaller host system disk is reserved for the OS and images.
- One database host in Singapore, default `ccx23` (4 dedicated vCPUs and
  16 GB RAM).
- A 750 GB permanent XFS database Volume plus a 400 GB temporary XFS rehearsal
  dump Volume. The temporary Volume is removed after accepted restore evidence.
- Fixed primary IPv4 addresses for controlled rebuilds and allowlists.
- A private `ap-southeast` network with fixed app and database IPs.
- Separate public firewalls. PostgreSQL is never opened on the public IP.
- Host-level UFW rules because Hetzner Cloud Firewalls do not filter traffic
  inside private Cloud Networks.
- Tailscale UDP transport is admitted, while interactive authorization remains
  outside Terraform so no tailnet key reaches state or cloud-init.
- Delete/rebuild protection and server-system-disk backups enabled by default.
- Remote state uses the retained GCS control plane. The bucket identifier is
  private operational inventory supplied through an ignored `backend.hcl`.

The attached database Volume is triple-replicated block storage, but Hetzner
does not include Volumes in server backups or snapshots. It is not a backup.
Part 2 must add independent WAL archiving plus a tested restore path before
any production data is placed here.

## Deliberate boundaries

- The database remains publicly addressable for bootstrap and outbound restore
  work, but its public firewall exposes only SSH from narrow operator CIDRs.
- Terraform passes no secrets through cloud-init. Set `HCLOUD_TOKEN` only in
  the operator environment.
- The app is not deployed and the PostgreSQL package is not installed yet.
  The Part 2 scripts under `scripts/hetzner/` pin PostgreSQL 15.17, make the
  Volume mount deterministic, install Tailscale, and configure backup/PITR.
- No DNS resource is present. Production DNS is a later, explicit cutover act.
- The GCS backend must be initialized only after the access-controlled bucket,
  isolated prefix and recovery owner have been selected and recovery access
  has been tested.

## Local validation

```bash
cd terraform/hetzner
terraform init -backend=false
terraform fmt -check -recursive
terraform validate
```

## Prepare a real plan

Creating a plan is read-only against Hetzner, but it requires a project token.

```bash
cd terraform/hetzner
cp terraform.tfvars.example terraform.tfvars
cp backend.hcl.example backend.hcl
# Edit the public key and narrow SSH CIDR first.
# Set the private state-bucket name in backend.hcl.
export HCLOUD_TOKEN='set-in-the-shell-or-a-secure-runner'
terraform init -reconfigure -backend-config=backend.hcl
terraform plan -out=tfplan
terraform show tfplan
```

Do not run `terraform apply` until all of these are true:

- the intended Hetzner project and Singapore product availability are
  confirmed, and the project's Console **Limits** evidence is retained;
- current server, IPv4, backup, 150 GB app-data Volume, 750 GB permanent
  database Volume and temporary rehearsal Volume costs are approved;
- the state backend and recovery owner are selected;
- operator SSH source CIDRs are correct;
- the Part 2 backup target is independent from this Hetzner failure domain;
- the plan contains no DNS or GCP changes.

The resources are billed hourly once applied. Delete protection means a later
destroy requires an explicit reviewed apply that disables protection first.
For the temporary dump Volume, first set
`enable_rehearsal_dump_volume_delete_protection=false` and apply that isolated
change. Only then set `enable_rehearsal_dump_volume=false` in a second reviewed
apply after the accepted restore evidence is retained and the Volume is
cleanly unmounted.

After Tailscale SSH is verified, set `enable_public_bootstrap_ssh=false`. The
reviewed plan should update only the two public firewall resources; it must not
replace either server.
