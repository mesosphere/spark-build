variable "cluster_prefix" {
  type    = "string"
  default = "spark-cluster-"
}

variable "dcos_variant" {
  type    = "string"
  default = "ee"
}

variable "aws_zone" {
  type    = "string"
  default = "us-east-1"
}

variable "dcos_license_key_file" {
  type    = "string"
  default = "./license.txt"
}

variable "dcos_version" {
  type    = "string"
  default = "2.0.0"
}

variable "dcos_security" {
  type    = "string"
  default = "permissive"
}

variable "dcos_instance_os" {
  type    = "string"
  default = "centos_7.5"
}

variable "bootstrap_instance_type" {
  type    = "string"
  default = "m4.xlarge"
}

variable "master_instance_type" {
  type    = "string"
  default = "m4.xlarge"
}

variable "num_masters" {
  type    = "string"
  default = "1"
}

variable "num_public_agents" {
  type    = "string"
  default = "1"
}

variable "num_private_agents" {
  type    = "string"
  default = "7"
}

variable "public_agent_instance_type" {
  type    = "string"
  default = "m4.xlarge"
}

variable "private_agent_instance_type" {
  type    = "string"
  default = "m4.xlarge"
}

variable "dcos_superuser_username" {
  type    = "string"
}

variable "dcos_superuser_password_hash" {
  type    = "string"
}

variable "ssh_public_key_file" {
  type    = "string"
  default = "~/.ssh/id_rsa.pub"
}

variable "cluster_expiration" {
  type    = "string"
  default = "3h"
}

variable "cluster_owner" {
  type    = "string"
}

variable "extra_admin_ips" {
  type = "string"
  default = ""
}

