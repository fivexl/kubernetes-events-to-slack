resource "kubernetes_service_account" "events_streamer" {
  metadata {
    name      = "kubernetes-events-to-slack"
    namespace = "kube-system"
  }
}

resource "kubernetes_cluster_role" "watch_events" {
  metadata {
    name      = "allow-watch-events"
  }

  rule {
    api_groups = [""]
    resources  = ["events"]
    verbs      = ["watch"]
  }
}

resource "kubernetes_cluster_role_binding" "watch_events" {
  metadata {
    name      = "kubernetes-events-to-slack"
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = kubernetes_cluster_role.watch_events.metadata[0].name
  }
  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account.events_streamer.metadata[0].name
    namespace = kubernetes_service_account.events_streamer.metadata[0].namespace
  }
}

resource "kubernetes_deployment" "streamer" {

  metadata {
    name      = kubernetes_service_account.events_streamer.metadata[0].name
    namespace = kubernetes_service_account.events_streamer.metadata[0].namespace

    labels = {
      app = "k8s-events-to-slack-streamer"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "k8s-events-to-slack-streamer"
      }
    }

    template {
      metadata {
        labels = {
          app = "k8s-events-to-slack-streamer"
        }
      }

      spec {
        automount_service_account_token = "true"

        service_account_name = kubernetes_service_account.events_streamer.metadata[0].name

        container {
          image             = "fivexl/kubernetes-events-to-slack:1.5.1"
          image_pull_policy = "Always"
          name              = "k8s-events-to-slack-streamer"

          resources {
            limits = {
              cpu    = "100m"
              memory = "150Mi"
            }

            requests = {
              cpu    = "100m"
              memory = "150Mi"
            }
          }

          env {
            name  = "K8S_EVENTS_STREAMER_INCOMING_WEB_HOOK_URL"
            value = var.streamer_hook_url
          }

          env {
            name  = "K8S_CLUSTER_NAME"
            value = var.cluster_name
          }

          env {
            name  = "K8S_SLACK_CHANNEL"
            value = var.slack_channel
          }

          env {
            name  = "K8S_SLACK_USERNAME"
            value = var.slack_username
          }

          env {
            name  = "K8S_EVENTS_STREAMER_SKIP_DELETE_EVENTS"
            value = "True"
          }

          env {
            name  = "K8S_EVENTS_STREAMER_LIST_OF_REASONS_TO_SKIP"
            value = "Scheduled ScalingReplicaSet Pulling Pulled Created Started Killing SuccessfulMountVolume SuccessfulUnMountVolume"
          }
        }
      }
    }
  }
}

variable "streamer_hook_url" {
  type = string
}

variable "cluster_name" {
  type = string
}

variable "slack_channel" {
  type = string
}

variable "slack_username" {
  type = string
}
