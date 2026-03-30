# ---------------------------------------------------------------------------
# DNS — create an A record pointing the domain to the server
# ---------------------------------------------------------------------------

data "hcloud_zone" "main" {
  name = var.domain_zone
}

# Extract the subdomain part: "analytics.example.com" with zone "example.com" → "analytics"
locals {
  subdomain = trimsuffix(trimsuffix(var.domain, var.domain_zone), ".")
}

resource "hcloud_zone_rrset" "server_a" {
  zone_id = data.hcloud_zone.main.id
  name    = local.subdomain
  type    = "A"
  ttl     = 300
  records = [hcloud_server.subscriptions.ipv4_address]
}

resource "hcloud_zone_rrset" "server_aaaa" {
  zone_id = data.hcloud_zone.main.id
  name    = local.subdomain
  type    = "AAAA"
  ttl     = 300
  records = [hcloud_server.subscriptions.ipv6_address]
}
