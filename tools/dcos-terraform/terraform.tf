provider "aws" {
  region = "${var.aws_zone}"
}

resource "random_id" "cluster_name" {
  prefix      = "${var.cluster_prefix}"
  byte_length = 2
}

# Used to determine your public IP for secutiry group rules
data "http" "whatismyip" {
  url = "http://whatismyip.akamai.com/"
}

locals {
  cluster_name        = "${random_id.cluster_name.hex}"
  admin_ips           = [
    "${data.http.whatismyip.body}/32",
    "${compact(split(",", var.extra_admin_ips))}"
  ]
}

module "dcos" {
  source                         = "dcos-terraform/dcos/aws"
  version                        = "~> 0.2.0"
  cluster_name                   = "${local.cluster_name}"
  availability_zones             = []
  dcos_superuser_username        = "${var.dcos_superuser_username}"
  dcos_superuser_password_hash   = "${var.dcos_superuser_password_hash}"
  ssh_public_key_file            = "${var.ssh_public_key_file}"
  admin_ips                      = ["${local.admin_ips}"]

  num_masters                    = "${var.num_masters}"
  num_public_agents              = "${var.num_public_agents}"
  num_private_agents             = "${var.num_private_agents}"

  dcos_instance_os               = "${var.dcos_instance_os}"
  
  public_agents_instance_type    = "${var.public_agent_instance_type}"
  private_agents_instance_type   = "${var.private_agent_instance_type}"
  bootstrap_instance_type        = "${var.bootstrap_instance_type}"
  masters_instance_type          = "${var.master_instance_type}"

  providers = {
    aws = "aws"
  }

  dcos_version                   = "${var.dcos_version}"
  dcos_security                  = "${var.dcos_security}"
  dcos_variant                   = "${var.dcos_variant}"
  dcos_license_key_contents      = "${file(var.dcos_license_key_file)}"

  dcos_master_discovery          = "master_http_loadbalancer"
  dcos_exhibitor_storage_backend = "aws_s3"
  dcos_exhibitor_explicit_keys   = "false"
  with_replaceable_masters       = "true"

  tags = {
    owner = "${var.cluster_owner}"
    expiration = "${var.cluster_expiration}"
  }
}

output "masters-ips" {
  value = "${module.dcos.masters-ips}"
}

output "cluster-address" {
  value = "${module.dcos.masters-loadbalancer}"
}

output "public-agents-loadbalancer" {
  value = "${module.dcos.public-agents-loadbalancer}"
}

