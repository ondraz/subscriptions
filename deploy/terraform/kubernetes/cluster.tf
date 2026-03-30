# ---------------------------------------------------------------------------
# k3s cluster on Hetzner via kube-hetzner community module
#
# This provisions a production-grade k3s cluster with:
# - 3 control plane nodes (HA)
# - N worker nodes (configurable)
# - Hetzner Cloud Controller Manager (CCM)
# - Hetzner CSI driver for persistent volumes
# - Traefik ingress controller
# - Flannel CNI
#
# Docs: https://github.com/kube-hetzner/terraform-hcloud-kube-hetzner
# ---------------------------------------------------------------------------

module "kube_hetzner" {
  source  = "kube-hetzner/kube-hetzner/hcloud"
  version = "~> 1.6"

  hcloud_token = var.hcloud_token

  # SSH access for provisioning
  ssh_public_key  = file(var.ssh_public_key_path)
  ssh_private_key = file(var.ssh_private_key_path)

  # Network
  network_region = "eu-central" # eu-central, us-east, us-west, ap-southeast

  # ---------- Control plane ----------
  control_plane_nodepools = [
    {
      name        = "cp"
      server_type = var.control_plane_type
      location    = var.location
      labels      = ["node.kubernetes.io/role=control-plane"]
      taints      = []
      count       = 3
    }
  ]

  # ---------- Workers ----------
  agent_nodepools = [
    {
      name        = "worker"
      server_type = var.worker_type
      location    = var.location
      labels      = ["node.kubernetes.io/role=worker"]
      taints      = []
      count       = var.worker_count
    }
  ]

  # Load balancer for ingress
  load_balancer_type     = "lb11"
  load_balancer_location = var.location

  # Enable Hetzner CSI driver for PersistentVolumes
  enable_csi_driver_smb = false

  # Firewall
  firewall_kube_api_source = null # Restrict to your IP in production
}
