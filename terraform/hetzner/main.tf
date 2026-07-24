locals {
  app_name      = "${var.name_prefix}-app"
  database_name = "${var.name_prefix}-db"

  common_labels = merge(
    {
      app         = "rtbcat"
      environment = "production"
      managed_by  = "terraform"
      migration   = "gcp-to-hetzner"
    },
    var.labels,
  )
}

resource "hcloud_ssh_key" "operator" {
  name       = "${var.name_prefix}-operator"
  public_key = trimspace(var.operator_ssh_public_key)
  labels     = local.common_labels
}

resource "hcloud_network" "private" {
  name     = "${var.name_prefix}-private"
  ip_range = var.network_cidr
  labels   = local.common_labels
}

resource "hcloud_network_subnet" "private" {
  network_id   = hcloud_network.private.id
  type         = "cloud"
  network_zone = var.network_zone
  ip_range     = var.subnet_cidr
}

resource "hcloud_placement_group" "spread" {
  name   = "${var.name_prefix}-spread"
  type   = "spread"
  labels = local.common_labels
}

resource "hcloud_primary_ip" "app" {
  name              = "${local.app_name}-ipv4"
  location          = var.location
  type              = "ipv4"
  auto_delete       = false
  delete_protection = var.enable_delete_protection
  labels            = merge(local.common_labels, { role = "app" })
}

resource "hcloud_primary_ip" "database" {
  name              = "${local.database_name}-ipv4"
  location          = var.location
  type              = "ipv4"
  auto_delete       = false
  delete_protection = var.enable_delete_protection
  labels            = merge(local.common_labels, { role = "database" })
}

resource "hcloud_firewall" "app" {
  name   = "${local.app_name}-public"
  labels = merge(local.common_labels, { role = "app" })

  dynamic "rule" {
    for_each = var.enable_public_bootstrap_ssh ? toset(var.ssh_source_cidrs) : toset([])

    content {
      direction   = "in"
      protocol    = "tcp"
      port        = "22"
      source_ips  = [rule.value]
      description = "Bootstrap SSH from an approved operator CIDR"
    }
  }

  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "80"
    source_ips  = ["0.0.0.0/0"]
    description = "Public HTTP for redirect and ACME"
  }

  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "443"
    source_ips  = ["0.0.0.0/0"]
    description = "Public HTTPS"
  }

  rule {
    direction   = "in"
    protocol    = "icmp"
    source_ips  = ["0.0.0.0/0"]
    description = "IPv4 path diagnostics"
  }

  rule {
    direction   = "in"
    protocol    = "udp"
    port        = "41641"
    source_ips  = ["0.0.0.0/0"]
    description = "Tailscale direct WireGuard transport"
  }
}

resource "hcloud_firewall" "database" {
  name   = "${local.database_name}-public"
  labels = merge(local.common_labels, { role = "database" })

  dynamic "rule" {
    for_each = var.enable_public_bootstrap_ssh ? toset(var.ssh_source_cidrs) : toset([])

    content {
      direction   = "in"
      protocol    = "tcp"
      port        = "22"
      source_ips  = [rule.value]
      description = "Bootstrap SSH from an approved operator CIDR"
    }
  }

  rule {
    direction   = "in"
    protocol    = "icmp"
    source_ips  = ["0.0.0.0/0"]
    description = "IPv4 path diagnostics"
  }

  rule {
    direction   = "in"
    protocol    = "udp"
    port        = "41641"
    source_ips  = ["0.0.0.0/0"]
    description = "Tailscale direct WireGuard transport"
  }
}

resource "hcloud_server" "app" {
  name        = local.app_name
  server_type = var.app_server_type
  image       = var.image
  location    = var.location
  ssh_keys    = [hcloud_ssh_key.operator.id]

  backups                  = var.enable_server_backups
  delete_protection        = var.enable_delete_protection
  rebuild_protection       = var.enable_delete_protection
  placement_group_id       = hcloud_placement_group.spread.id
  firewall_ids             = [hcloud_firewall.app.id]
  shutdown_before_deletion = true

  public_net {
    ipv4_enabled = true
    ipv4         = hcloud_primary_ip.app.id
    ipv6_enabled = false
  }

  network {
    subnet_id = hcloud_network_subnet.private.id
    ip        = var.app_private_ip
    alias_ips = []
  }

  user_data = templatefile("${path.module}/cloud-init/app.yaml.tftpl", {
    hostname                = local.app_name
    app_private_ip          = var.app_private_ip
    database_private_ip     = var.database_private_ip
    operator_ssh_public_key = trimspace(var.operator_ssh_public_key)
    ssh_source_cidrs        = var.ssh_source_cidrs
  })

  # Cloud-init is first-boot configuration. Template maintenance after
  # provisioning must not silently turn an unrelated plan into a host rebuild.
  lifecycle {
    ignore_changes = [user_data]
  }

  labels = merge(local.common_labels, { role = "app" })
}

resource "hcloud_server" "database" {
  name        = local.database_name
  server_type = var.database_server_type
  image       = var.image
  location    = var.location
  ssh_keys    = [hcloud_ssh_key.operator.id]

  backups                  = var.enable_server_backups
  delete_protection        = var.enable_delete_protection
  rebuild_protection       = var.enable_delete_protection
  placement_group_id       = hcloud_placement_group.spread.id
  firewall_ids             = [hcloud_firewall.database.id]
  shutdown_before_deletion = true

  public_net {
    ipv4_enabled = true
    ipv4         = hcloud_primary_ip.database.id
    ipv6_enabled = false
  }

  network {
    subnet_id = hcloud_network_subnet.private.id
    ip        = var.database_private_ip
    alias_ips = []
  }

  user_data = templatefile("${path.module}/cloud-init/database.yaml.tftpl", {
    app_private_ip          = var.app_private_ip
    hostname                = local.database_name
    operator_ssh_public_key = trimspace(var.operator_ssh_public_key)
    ssh_source_cidrs        = var.ssh_source_cidrs
  })

  # Replaying changed first-boot data requires an explicit, reviewed replace.
  lifecycle {
    ignore_changes = [user_data]
  }

  labels = merge(local.common_labels, { role = "database" })
}

resource "hcloud_volume" "database" {
  name              = "${local.database_name}-data"
  size              = var.database_volume_size_gb
  server_id         = hcloud_server.database.id
  automount         = true
  format            = "xfs"
  delete_protection = var.enable_delete_protection
  labels            = merge(local.common_labels, { role = "database-data" })
}

resource "hcloud_volume" "app_data" {
  name              = "${local.app_name}-data"
  size              = var.app_data_volume_size_gb
  server_id         = hcloud_server.app.id
  automount         = true
  format            = "xfs"
  delete_protection = var.enable_delete_protection
  labels            = merge(local.common_labels, { role = "app-data" })
}

resource "hcloud_volume" "rehearsal_dump" {
  count = var.enable_rehearsal_dump_volume ? 1 : 0

  name              = "${local.database_name}-rehearsal-dump"
  size              = var.rehearsal_dump_volume_size_gb
  server_id         = hcloud_server.database.id
  automount         = true
  format            = "xfs"
  delete_protection = var.enable_rehearsal_dump_volume_delete_protection
  labels            = merge(local.common_labels, { role = "temporary-rehearsal-dump" })
}
