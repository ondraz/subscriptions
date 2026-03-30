output "server_ipv4" {
  description = "Public IPv4 address of the server"
  value       = hcloud_server.subscriptions.ipv4_address
}

output "server_ipv6" {
  description = "Public IPv6 address of the server"
  value       = hcloud_server.subscriptions.ipv6_address
}

output "server_status" {
  description = "Server status"
  value       = hcloud_server.subscriptions.status
}

output "domain" {
  description = "Domain name for the analytics server"
  value       = var.domain
}

output "url" {
  description = "URL of the analytics server"
  value       = "https://${var.domain}"
}

output "ssh_command" {
  description = "SSH command to connect to the server"
  value       = "ssh root@${hcloud_server.subscriptions.ipv4_address}"
}
