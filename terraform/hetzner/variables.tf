variable "name_prefix" {
  description = "Prefix for all Hetzner resources."
  type        = string
  default     = "rtbcat-production"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,40}[a-z0-9]$", var.name_prefix))
    error_message = "name_prefix must be a lowercase, hyphenated name between 3 and 42 characters."
  }
}

variable "location" {
  description = "Hetzner location for the phase-one RTBcat migration."
  type        = string
  default     = "sin"

  validation {
    condition     = var.location == "sin"
    error_message = "This stack is intentionally constrained to Hetzner Singapore (sin)."
  }
}

variable "network_zone" {
  description = "Hetzner network zone containing the Singapore location."
  type        = string
  default     = "ap-southeast"

  validation {
    condition     = var.network_zone == "ap-southeast"
    error_message = "Singapore belongs to the ap-southeast Hetzner network zone."
  }
}

variable "network_cidr" {
  description = "Private network CIDR."
  type        = string
  default     = "10.60.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.network_cidr))
    error_message = "network_cidr must be valid CIDR notation."
  }
}

variable "subnet_cidr" {
  description = "Private subnet CIDR for the app and database hosts."
  type        = string
  default     = "10.60.1.0/24"

  validation {
    condition     = can(cidrnetmask(var.subnet_cidr))
    error_message = "subnet_cidr must be valid CIDR notation."
  }
}

variable "app_private_ip" {
  description = "Fixed private IPv4 address for the app host."
  type        = string
  default     = "10.60.1.10"

  validation {
    condition     = can(cidrhost("${var.app_private_ip}/32", 0))
    error_message = "app_private_ip must be a valid IPv4 address."
  }
}

variable "database_private_ip" {
  description = "Fixed private IPv4 address for the PostgreSQL host."
  type        = string
  default     = "10.60.1.20"

  validation {
    condition     = can(cidrhost("${var.database_private_ip}/32", 0))
    error_message = "database_private_ip must be a valid IPv4 address."
  }
}

variable "operator_ssh_public_key" {
  description = "Operator SSH public key. Pass only public key material; never pass a private key."
  type        = string

  validation {
    condition = anytrue([
      startswith(trimspace(var.operator_ssh_public_key), "ssh-ed25519 "),
      startswith(trimspace(var.operator_ssh_public_key), "ssh-rsa "),
      startswith(trimspace(var.operator_ssh_public_key), "ecdsa-sha2-")
    ])
    error_message = "operator_ssh_public_key must be an OpenSSH public key."
  }
}

variable "ssh_source_cidrs" {
  description = "Narrow public CIDRs allowed to SSH during bootstrap. Replace with Tailscale-only access in Part 2."
  type        = list(string)

  validation {
    condition = (
      length(var.ssh_source_cidrs) > 0 &&
      alltrue([for cidr in var.ssh_source_cidrs : can(cidrnetmask(cidr))]) &&
      alltrue([for cidr in var.ssh_source_cidrs : !contains(["0.0.0.0/0", "::/0"], cidr)])
    )
    error_message = "Provide at least one valid, narrow SSH CIDR; world-open SSH is prohibited."
  }
}

variable "enable_public_bootstrap_ssh" {
  description = "Expose public TCP/22 from ssh_source_cidrs. Disable after Tailscale SSH is verified; this changes firewalls only."
  type        = bool
  default     = true
}

variable "image" {
  description = "Hetzner base image."
  type        = string
  default     = "ubuntu-24.04"
}

variable "app_server_type" {
  description = "App host type. CPX22 provides 2 shared AMD vCPUs, 4 GB RAM and an 80 GB local disk."
  type        = string
  default     = "cpx22"
}

variable "database_server_type" {
  description = "Database host type used for rehearsal. CCX23 provides 4 dedicated vCPUs and 16 GB RAM; benchmark before freezing the production size."
  type        = string
  default     = "ccx23"
}

variable "app_data_volume_size_gb" {
  description = "Permanent app-data volume size in decimal GB. Production currently has about 93 GB under .catscan."
  type        = number
  default     = 150

  validation {
    condition     = var.app_data_volume_size_gb >= 150 && var.app_data_volume_size_gb <= 10240
    error_message = "app_data_volume_size_gb must be between 150 GB and Hetzner's 10240 GB volume limit."
  }
}

variable "database_volume_size_gb" {
  description = "Permanent database volume size in decimal GB. The source is about 420 GiB; dump bytes use the separate temporary rehearsal volume."
  type        = number
  default     = 750

  validation {
    condition     = var.database_volume_size_gb >= 750 && var.database_volume_size_gb <= 10240
    error_message = "database_volume_size_gb must be between 750 GB and Hetzner's 10240 GB volume limit."
  }
}

variable "enable_rehearsal_dump_volume" {
  description = "Create a temporary XFS volume for the production-sized directory dump. Disable it only after the dump is no longer needed and the mount is cleanly unmounted."
  type        = bool
  default     = true
}

variable "rehearsal_dump_volume_size_gb" {
  description = "Temporary directory-dump volume size in decimal GB. Delete it after the accepted restore and checksum evidence are retained elsewhere."
  type        = number
  default     = 400

  validation {
    condition     = var.rehearsal_dump_volume_size_gb >= 400 && var.rehearsal_dump_volume_size_gb <= 10240
    error_message = "rehearsal_dump_volume_size_gb must be between 400 GB and Hetzner's 10240 GB volume limit."
  }
}

variable "enable_rehearsal_dump_volume_delete_protection" {
  description = "Protect the temporary rehearsal-dump volume until restore evidence is accepted. Disable in a separate reviewed apply before removing the volume."
  type        = bool
  default     = true
}

variable "enable_server_backups" {
  description = "Enable Hetzner backups for server system disks. These do not include attached Volumes."
  type        = bool
  default     = true
}

variable "enable_delete_protection" {
  description = "Protect servers, primary IPs and permanent Volumes from accidental deletion."
  type        = bool
  default     = true
}

variable "labels" {
  description = "Additional labels applied to all supported Hetzner resources."
  type        = map(string)
  default     = {}
}
