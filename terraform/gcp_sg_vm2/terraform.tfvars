gcp_project = "catscan-prod-202601"
gcp_region  = "asia-southeast1"
gcp_zone    = "asia-southeast1-b"

app_name    = "catscan"
environment = "production"

machine_type   = "e2-medium"
boot_disk_size = 80

domain_name  = ""
enable_https = false

github_repo   = "https://github.com/jenbrannstrom/rtbcat-platform.git"
github_branch = "unified-platform"

google_oauth_client_id     = "449322304772-2k5kcue958iuiu19lefa1rbsccm78r24.apps.googleusercontent.com"
google_oauth_client_secret = "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"
allowed_email_domains      = ["rtb.cat"]

service_account_email    = "catscan-production-sa@catscan-prod-202601.iam.gserviceaccount.com"
artifact_registry_domain = "asia-southeast1-docker.pkg.dev"

gcs_bucket = "catscan-production-data-99957252"
