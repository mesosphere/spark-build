TERRAFORM_DIR := $(ROOT_DIR)/tools/dcos-terraform
TERRAFORM_STATE_FILE := $(TERRAFORM_DIR)/terraform.tfstate
TERRAFORM_PLAN_FILE :=  $(TERRAFORM_DIR)/plan.out
TERRAFORM_TF_VARS_FILE := $(TERRAFORM_DIR)/terraform.tfvars

TERRAFORM_DOCKER_IMAGE_TAG ?= $(shell cat $(TERRAFORM_DIR)/Dockerfile $(TERRAFORM_DIR)/entrypoint.sh | sha1sum  | cut -d' ' -f1)
TERRAFORM_DOCKER_IMAGE_NAME ?= mesosphere/jupyter-terraform:$(TERRAFORM_DOCKER_IMAGE_TAG)

SSH_PRIVATE_KEY_FILE ?= $(TERRAFORM_DIR)/id_key
SSH_PUBLIC_KEY_FILE ?= $(SSH_PRIVATE_KEY_FILE).pub

CLUSTER_OWNER ?= $(USER)
CLUSTER_EXPIRATION ?= 6h
CLUSTER_PASSWORD_HASH ?= $(docker run -rm -i bernadinm/sha512 $(CLUSTER_PASSWORD) | tail -1)
CLUSTER_ADMIN_IPS ?= 0.0.0.0/0

NUM_PRIVATE_AGENTS ?= 7
NUM_PUBLIC_AGENTS ?= 1

AWS_REGION ?= us-east-1

terraform.docker:
	if [[ -z "$(shell docker images -q $(TERRAFORM_DOCKER_IMAGE_NAME))" ]]; then
		docker build -t $(TERRAFORM_DOCKER_IMAGE_NAME) -f $(TERRAFORM_DIR)/Dockerfile $(TERRAFORM_DIR)
	fi
	echo $(TERRAFORM_DOCKER_IMAGE_NAME) > $@

terraform.dcos.vars:
	rm -f $(TERRAFORM_TF_VARS_FILE)
	echo "cluster_owner=\"$(CLUSTER_OWNER)\"" >> $(TERRAFORM_TF_VARS_FILE)
	echo "cluster_expiration=\"$(CLUSTER_EXPIRATION)\"" >> $(TERRAFORM_TF_VARS_FILE)
	echo "aws_region=\"$(AWS_REGION)\"" >> $(TERRAFORM_TF_VARS_FILE)
	echo "dcos_superuser_username=\"$(CLUSTER_USER)\"" >> $(TERRAFORM_TF_VARS_FILE)
	echo "dcos_superuser_password_hash=\"$(CLUSTER_PASSWORD_HASH)\"" >> $(TERRAFORM_TF_VARS_FILE)
	echo "extra_admin_ips=\"$(CLUSTER_ADMIN_IPS)\"" >> $(TERRAFORM_TF_VARS_FILE)
	echo "num_private_agents=\"$(NUM_PRIVATE_AGENTS)\"" >> $(TERRAFORM_TF_VARS_FILE)
	echo "num_public_agents=\"$(NUM_PUBLIC_AGENTS)\"" >> $(TERRAFORM_TF_VARS_FILE)
	env | grep TF_VAR_ | cut -d '_' -f3- | awk -F"=" '{print $$1 "=\"" $$2 "\""}' >> $(TERRAFORM_TF_VARS_FILE)

terraform.init: terraform.docker
terraform.init: terraform.dcos.vars
terraform.init:
	$(call run_terraform,init)
	echo > $@

.PHONY: terraform.cluster.create
terraform.cluster.create: terraform.init
terraform.cluster.create:
	$(call run_terraform,plan -state $(TERRAFORM_STATE_FILE) -out $(TERRAFORM_PLAN_FILE))
	$(call run_terraform,apply -state-out $(TERRAFORM_STATE_FILE) -auto-approve $(TERRAFORM_PLAN_FILE))

.PHONY: terraform.cluster.destroy
terraform.cluster.destroy:
ifneq ("$(wildcard $(TERRAFORM_STATE_FILE))","")
	$(call run_terraform,destroy -auto-approve -state $(TERRAFORM_STATE_FILE))
endif

terraform.cluster.url: terraform.init
terraform.cluster.url:
	$(call run_terraform,output -state $(TERRAFORM_STATE_FILE) masters-ips | tail -1 > $@)

terraform.cluster.public.elb: terraform.init
terraform.cluster.public.elb:
	$(call run_terraform,output -state $(TERRAFORM_STATE_FILE) public-agents-loadbalancer | tail -1 > $@)

# Runs terraform in a docker container
define run_terraform
docker run --rm -i --net=host \
	-v $(TERRAFORM_DIR):$(TERRAFORM_DIR) \
	-w $(TERRAFORM_DIR) \
	-v $(AWS_SHARED_CREDENTIALS_FILE):/aws/credentials \
	-e AWS_SHARED_CREDENTIALS_FILE=/aws/credentials \
	-e AWS_PROFILE=$(AWS_PROFILE) \
	-e TF_WARN_OUTPUT_ERRORS=1 \
	-v $(SSH_PUBLIC_KEY_FILE):/root/.ssh/id_rsa.pub \
	-v $(SSH_PRIVATE_KEY_FILE):/root/.ssh/id_rsa \
	-e SSH_PRIVATE_KEY_FILE=/root/.ssh/id_rsa \
	$(TERRAFORM_DOCKER_IMAGE_NAME) \
	$1
endef

.PHONY: terraform.clean
terraform.clean:
	rm -f $(TERRAFORM_PLAN_FILE)
	rm -rf $(TERRAFORM_DIR)/.terraform $(TERRAFORM_DIR)/*.tfstate* $(ROOT_DIR)/terraform.* $(TERRAFORM_DIR)/*.tfvars
	rm -f $(TERRAFORM_DIR)/.terraform*

