variable "hcloud_token" {
  description = "Hetzner Cloud API token (from https://console.hetzner.cloud → Security → API Tokens)"
  type        = string
  sensitive   = true
}

variable "server_name" {
  description = "Name of the server"
  type        = string
  default     = "subscriptions"
}

variable "server_type" {
  description = "Hetzner server type (cx22 = 2 vCPU, 4 GB RAM, €3.79/mo)"
  type        = string
  default     = "cx22"
}

variable "location" {
  description = "Hetzner datacenter location"
  type        = string
  default     = "fsn1" # Falkenstein, Germany. Alternatives: nbg1, hel1, ash, hil, sin
}

variable "image" {
  description = "OS image"
  type        = string
  default     = "ubuntu-24.04"
}

variable "ssh_public_key_path" {
  description = "Path to SSH public key for server access"
  type        = string
  default     = "~/.ssh/id_ed25519.pub"
}

variable "domain" {
  description = "Domain name for the analytics server (e.g. analytics.example.com)"
  type        = string
}

variable "domain_zone" {
  description = "Parent DNS zone managed in Hetzner (e.g. example.com)"
  type        = string
}

variable "ssh_allowed_ips" {
  description = "CIDR blocks allowed to SSH (default: everywhere, restrict in production)"
  type        = list(string)
  default     = ["0.0.0.0/0", "::/0"]
}
