terraform {
  required_version = ">= 1.9.0"

  backend "gcs" {}

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.66"
    }
  }
}

provider "hcloud" {}
