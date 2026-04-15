# ---------------------------------------------------------------------------
# Kubernetes resources for the tidemill application
#
# After the cluster is provisioned, this deploys:
# - Namespace
# - PostgreSQL (StatefulSet)
# - Redpanda (StatefulSet)
# - API (Deployment + Service)
# - Worker (Deployment)
# - Ingress (Traefik, TLS via cert-manager)
# - Secrets
# ---------------------------------------------------------------------------

provider "kubernetes" {
  host                   = module.kube_hetzner.kubeconfig.host
  client_certificate     = module.kube_hetzner.kubeconfig.client_certificate
  client_key             = module.kube_hetzner.kubeconfig.client_key
  cluster_ca_certificate = module.kube_hetzner.kubeconfig.cluster_ca_certificate
}

provider "helm" {
  kubernetes {
    host                   = module.kube_hetzner.kubeconfig.host
    client_certificate     = module.kube_hetzner.kubeconfig.client_certificate
    client_key             = module.kube_hetzner.kubeconfig.client_key
    cluster_ca_certificate = module.kube_hetzner.kubeconfig.cluster_ca_certificate
  }
}

# ---------------------------------------------------------------------------
# Namespace
# ---------------------------------------------------------------------------

resource "kubernetes_namespace" "tidemill" {
  metadata {
    name = "tidemill"
  }

  depends_on = [module.kube_hetzner]
}

# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------

resource "random_password" "postgres" {
  length  = 32
  special = false
}

resource "kubernetes_secret" "app" {
  metadata {
    name      = "tidemill"
    namespace = kubernetes_namespace.tidemill.metadata[0].name
  }

  data = {
    POSTGRES_PASSWORD      = random_password.postgres.result
    DATABASE_URL           = "postgresql+asyncpg://tidemill:${random_password.postgres.result}@postgres:5432/tidemill"
    KAFKA_BOOTSTRAP_SERVERS = "redpanda:9092"
  }
}

# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------

resource "kubernetes_stateful_set" "postgres" {
  metadata {
    name      = "postgres"
    namespace = kubernetes_namespace.tidemill.metadata[0].name
  }

  spec {
    service_name = "postgres"
    replicas     = 1

    selector {
      match_labels = { app = "postgres" }
    }

    template {
      metadata {
        labels = { app = "postgres" }
      }

      spec {
        container {
          name  = "postgres"
          image = "postgres:17"

          port {
            container_port = 5432
          }

          env {
            name  = "POSTGRES_DB"
            value = "tidemill"
          }
          env {
            name  = "POSTGRES_USER"
            value = "tidemill"
          }
          env {
            name = "POSTGRES_PASSWORD"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.app.metadata[0].name
                key  = "POSTGRES_PASSWORD"
              }
            }
          }

          volume_mount {
            name       = "data"
            mount_path = "/var/lib/postgresql/data"
          }

          liveness_probe {
            exec {
              command = ["pg_isready", "-U", "tidemill"]
            }
            initial_delay_seconds = 15
            period_seconds        = 10
          }

          resources {
            requests = { cpu = "250m", memory = "256Mi" }
            limits   = { cpu = "1",    memory = "512Mi" }
          }
        }
      }
    }

    volume_claim_template {
      metadata {
        name = "data"
      }
      spec {
        access_modes       = ["ReadWriteOnce"]
        storage_class_name = "hcloud-volumes" # Hetzner CSI driver
        resources {
          requests = { storage = "10Gi" }
        }
      }
    }
  }
}

resource "kubernetes_service" "postgres" {
  metadata {
    name      = "postgres"
    namespace = kubernetes_namespace.tidemill.metadata[0].name
  }
  spec {
    selector = { app = "postgres" }
    port {
      port        = 5432
      target_port = 5432
    }
    cluster_ip = "None" # Headless for StatefulSet
  }
}

# ---------------------------------------------------------------------------
# Redpanda
# ---------------------------------------------------------------------------

resource "kubernetes_stateful_set" "redpanda" {
  metadata {
    name      = "redpanda"
    namespace = kubernetes_namespace.tidemill.metadata[0].name
  }

  spec {
    service_name = "redpanda"
    replicas     = 1

    selector {
      match_labels = { app = "redpanda" }
    }

    template {
      metadata {
        labels = { app = "redpanda" }
      }

      spec {
        container {
          name  = "redpanda"
          image = "redpandadata/redpanda:latest"

          args = [
            "redpanda", "start",
            "--smp", "1",
            "--memory", "256M",
            "--overprovisioned",
            "--node-id", "0",
            "--kafka-addr", "PLAINTEXT://0.0.0.0:9092",
            "--advertise-kafka-addr", "PLAINTEXT://redpanda:9092",
          ]

          port {
            container_port = 9092
          }

          volume_mount {
            name       = "data"
            mount_path = "/var/redpanda/data"
          }

          resources {
            requests = { cpu = "250m", memory = "256Mi" }
            limits   = { cpu = "1",    memory = "512Mi" }
          }
        }
      }
    }

    volume_claim_template {
      metadata {
        name = "data"
      }
      spec {
        access_modes       = ["ReadWriteOnce"]
        storage_class_name = "hcloud-volumes"
        resources {
          requests = { storage = "10Gi" }
        }
      }
    }
  }
}

resource "kubernetes_service" "redpanda" {
  metadata {
    name      = "redpanda"
    namespace = kubernetes_namespace.tidemill.metadata[0].name
  }
  spec {
    selector = { app = "redpanda" }
    port {
      port        = 9092
      target_port = 9092
    }
    cluster_ip = "None"
  }
}

# ---------------------------------------------------------------------------
# API Deployment
# ---------------------------------------------------------------------------

resource "kubernetes_deployment" "api" {
  metadata {
    name      = "api"
    namespace = kubernetes_namespace.tidemill.metadata[0].name
  }

  spec {
    replicas = 2

    selector {
      match_labels = { app = "api" }
    }

    template {
      metadata {
        labels = { app = "api" }
      }

      spec {
        security_context {
          run_as_user     = 1000
          run_as_group    = 1000
          run_as_non_root = true
          fs_group        = 1000
        }

        container {
          name  = "api"
          image = "ghcr.io/ondraz/tidemill:latest" # TODO: replace with actual image
          args  = ["uvicorn", "tidemill.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

          port {
            container_port = 8000
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.app.metadata[0].name
            }
          }

          liveness_probe {
            http_get {
              path = "/healthz"
              port = 8000
            }
            initial_delay_seconds = 10
            period_seconds        = 10
          }

          readiness_probe {
            http_get {
              path = "/readyz"
              port = 8000
            }
            initial_delay_seconds = 5
            period_seconds        = 5
          }

          resources {
            requests = { cpu = "100m", memory = "128Mi" }
            limits   = { cpu = "500m", memory = "256Mi" }
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "api" {
  metadata {
    name      = "api"
    namespace = kubernetes_namespace.tidemill.metadata[0].name
  }
  spec {
    selector = { app = "api" }
    port {
      port        = 80
      target_port = 8000
    }
  }
}

# ---------------------------------------------------------------------------
# Worker Deployment
# ---------------------------------------------------------------------------

resource "kubernetes_deployment" "worker" {
  metadata {
    name      = "worker"
    namespace = kubernetes_namespace.tidemill.metadata[0].name
  }

  spec {
    replicas = 2

    selector {
      match_labels = { app = "worker" }
    }

    template {
      metadata {
        labels = { app = "worker" }
      }

      spec {
        security_context {
          run_as_user     = 1000
          run_as_group    = 1000
          run_as_non_root = true
          fs_group        = 1000
        }

        container {
          name  = "worker"
          image = "ghcr.io/ondraz/tidemill:latest"
          args  = ["python", "-m", "tidemill.worker"]

          env_from {
            secret_ref {
              name = kubernetes_secret.app.metadata[0].name
            }
          }

          resources {
            requests = { cpu = "100m", memory = "128Mi" }
            limits   = { cpu = "500m", memory = "256Mi" }
          }
        }
      }
    }
  }
}

# ---------------------------------------------------------------------------
# Ingress (Traefik, installed by kube-hetzner)
# ---------------------------------------------------------------------------

resource "kubernetes_ingress_v1" "api" {
  metadata {
    name      = "api"
    namespace = kubernetes_namespace.tidemill.metadata[0].name

    annotations = {
      "traefik.ingress.kubernetes.io/router.tls"            = "true"
      "traefik.ingress.kubernetes.io/router.tls.certresolver" = "le"
    }
  }

  spec {
    rule {
      host = var.domain

      http {
        path {
          path      = "/"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service.api.metadata[0].name
              port {
                number = 80
              }
            }
          }
        }
      }
    }

    tls {
      hosts       = [var.domain]
      secret_name = "tidemill-tls"
    }
  }
}
