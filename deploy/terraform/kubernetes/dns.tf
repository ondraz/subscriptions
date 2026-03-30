# ---------------------------------------------------------------------------
# DNS — point the domain to the load balancer
# ---------------------------------------------------------------------------

data "hcloud_zone" "main" {
  name = var.domain_zone
}

locals {
  subdomain = trimsuffix(trimsuffix(var.domain, var.domain_zone), ".")
}

resource "hcloud_zone_rrset" "lb_a" {
  zone_id = data.hcloud_zone.main.id
  name    = local.subdomain
  type    = "A"
  ttl     = 300
  records = [module.kube_hetzner.load_balancer_public_ipv4]
}

resource "hcloud_zone_rrset" "lb_aaaa" {
  zone_id = data.hcloud_zone.main.id
  name    = local.subdomain
  type    = "AAAA"
  ttl     = 300
  records = [module.kube_hetzner.load_balancer_public_ipv6]
}
