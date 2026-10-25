# Historical operations, 24 October 2026

These scripts record one-time fixes already applied to the production hosts.
They are evidence, not a routine deployment entry point. Their original-state
assertions and dated backup paths intentionally prevent blindly repeating them.

- `rtbcat-cert-prepare-20261024.py`: add the MCP HTTP ACME challenge route.
- `rtbcat-cert-install-20261024.py`: switch both production sites to the issued
  `rtbcat-production` Certbot lineage and install the Nginx renewal hook.
- `rtbcat-app-host-cleanup-20261024.py`: correct cloud-init virtual-NIC matching
  and the obsolete optional PAM login module.
- `verify_archives_20261024.py`: validate the initial bidstream archive set.

Certificate issuance itself used Certbot; private keys, credentials, production
data and raw host configuration backups are not source artifacts. PostgreSQL
15.19 installation and the restored executable mode on both MOTD scripts are
recorded in the operations document, not replayed by these scripts.
