terraform {
  required_version = ">= 1.5"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.45"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "hcloud" {
  token = var.hcloud_token
}

# Grafana admin password — generated once and persisted in state.
# Rotate by tainting this resource (`terraform taint random_password.grafana_admin`).
resource "random_password" "grafana_admin" {
  length  = 24
  special = false
}
