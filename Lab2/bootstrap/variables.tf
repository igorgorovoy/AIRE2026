variable "cluster_name" {
  description = "Cluster Name"
  type        = string
  default     = "abox"
}

variable "kubeconfig_path" {
  description = "Path to kubeconfig used by providers"
  type        = string
  default     = "~/.kube/config"
}

variable "kube_context" {
  description = "Kubernetes context name"
  type        = string
  default     = "rancher-desktop"
}

variable "oci_registry" {
  description = "OCI registry base URL"
  type        = string
  default     = "oci://ghcr.io/den-vasyliev/abox"
}

variable "releases_version" {
  description = "Default tag for releases OCI artifact bootstrap"
  type        = string
  default     = "0.1.0"
}
