.ONESHELL:
SHELL := /bin/bash
.SHELLFLAGS = -ec

ROOT_DIR := $(CURDIR)
BUILD_DIR := $(ROOT_DIR)/build
DIST_DIR := $(BUILD_DIR)/dist
STATSD_DIR := $(ROOT_DIR)/spark-statsd-reporter
GIT_COMMIT := $(shell git rev-parse HEAD)

# Docker configuration
DOCKER_USERNAME ?=
DOCKER_PASSWORD ?=
DOCKER_DIR := $(ROOT_DIR)/docker
DOCKER_REPO_NAME ?= mesosphere
DOCKER_BUILDER_IMAGE_NAME ?= spark-docker-builder
DOCKER_BUILDER_IMAGE_TAG ?= $(shell cat Dockerfile | sha1sum  | cut -d' ' -f1)
DOCKER_BUILDER_IMAGE_FULL_NAME ?= $(DOCKER_REPO_NAME)/$(DOCKER_BUILDER_IMAGE_NAME):$(DOCKER_BUILDER_IMAGE_TAG)
DOCKER_SPARK_DIST_IMAGE_NAME ?= spark-dev
DOCKER_SPARK_DIST_IMAGE_FULL_NAME ?= $(DOCKER_REPO_NAME)/$(DOCKER_SPARK_DIST_IMAGE_NAME):$(GIT_COMMIT)

# Spark repo build configuration
SPARK_REPO_URL ?= https://github.com/mesosphere/spark
SPARK_DIST_URI ?= $(shell jq ".default_spark_dist.uri" "$(ROOT_DIR)/manifest.json")
HADOOP_VERSION ?= $(shell jq ".default_spark_dist.hadoop_version" "$(ROOT_DIR)/manifest.json")
SCALA_VERSION ?= $(shell jq ".default_spark_dist.scala_version" "$(ROOT_DIR)/manifest.json")
SPARK_DIR ?= $(ROOT_DIR)/spark

# AWS credentials configuration used by tests and Terraform
AWS_SHARED_CREDENTIALS_FILE ?= $(ROOT_DIR)/aws.credentials
AWS_PROFILE ?= default

# release-specific settings provided by CI or users
RELEASE_VERSION ?=
S3_RELEASE_BUCKET ?=
HTTP_RELEASE_SERVER ?=
FORCE_ARTIFACT_UPLOAD ?= "false"

# The following properties are set to Terraform outputs after
# a cluster is provisioned using 'make cluster-create'
CLUSTER_URL ?=
PUBLIC_AGENT_ELB ?=

CLUSTER_USER ?= bootstrapuser
CLUSTER_PASSWORD ?= deleteme

# SSH settings
SSH_PRIVATE_KEY_FILE ?= $(ROOT_DIR)/id_key
SSH_PUBLIC_KEY_FILE ?= $(SSH_PRIVATE_KEY_FILE).pub
DCOS_SSH_USERNAME ?= centos

# Testing
PYTEST_ARGS ?=

include ./tools/dcos-terraform/terraform.mk

# This image can be used to build spark dist and run tests
docker-build:
	if [[ -z "$(shell docker images -q $(DOCKER_BUILDER_IMAGE_FULL_NAME))" ]]; then
		docker build -t $(DOCKER_BUILDER_IMAGE_FULL_NAME) .
	fi
	echo $(DOCKER_BUILDER_IMAGE_FULL_NAME) > $@

# Pulls the spark distribution listed in the manifest as default
spark-dist-download:
	if [[ ! -f "$(DIST_DIR)/$(lastword $(subst /, ,$(SPARK_DIST_URI))) ]]; then
		mkdir -p $(DIST_DIR)
		pushd $(DIST_DIR)
		wget $(SPARK_DIST_URI)
		popd
	fi

$(SPARK_DIR):
	git clone $(SPARK_REPO_URL) $(SPARK_DIR)

# Locally build the spark distribution
spark-dist-build: $(SPARK_DIR)
	if [[ ! -d "$(DIST_DIR)" ]]; then
		pushd $(SPARK_DIR)
		rm -rf spark-*.tgz
		./dev/change-scala-version.sh $(SCALA_VERSION)
		./dev/make-distribution.sh --tgz -Pmesos "-Pscala-$(SCALA_VERSION)" "-Phadoop-$(HADOOP_VERSION)" -Pnetlib-lgpl -Psparkr -Phive -Phive-thriftserver -DskipTests -Dmaven.test.skip=true -Dmaven.source.skip=true -Dmaven.site.skip=true -Dmaven.javadoc.skip=true
		filename=`ls spark-*.tgz`
		mkdir -p $(DIST_DIR)
		mv $${filename} $(DIST_DIR)
		echo "Built: $(DIST_DIR)/$${filename}"
	fi

statsd-reporter:
	pushd $(STATSD_DIR)
	docker run -v ~/.m2:/root/.m2 -v $(STATSD_DIR):/spark-statsd-reporter -w /spark-statsd-reporter maven:3.6-jdk-8-alpine mvn clean package
	popd
	echo "$(STATSD_DIR)/target/spark-statsd-reporter.jar" > $@

docker-login:
	docker login --username="$(DOCKER_USERNAME)" --password="$(DOCKER_PASSWORD)"

# To use already published and mentioned spark dist in manifest.json run "make spark-dist-download"
# To instead use a locally built version of spark,
# you must remove already present `build/dist` directory and run "make spark-dist-build".
$(DIST_DIR):
	if [[ ! -f "$(DIST_DIR)/$(lastword $(subst /, ,$(SPARK_DIST_URI))) ]]; then
		mkdir -p $(DIST_DIR)
		pushd $(DIST_DIR)
		wget $(SPARK_DIST_URI)
		popd
	fi

docker-dist: $(DIST_DIR) statsd-reporter
	SPARK_BUILDS=`ls $(DIST_DIR)/spark-*.tgz || exit 0`
	if [ `echo "$${SPARK_BUILDS}" | wc -w` == 1 ]; then
		echo "Using spark: $${SPARK_BUILDS}"
	else
		echo "Should have a single Spark package in $(DIST_DIR), found: $${SPARK_BUILDS}"
		echo "Delete the ones you don't want?"
		exit 1
	fi
	tar xvf $${SPARK_BUILDS} -C $(DIST_DIR)

	rm -rf $(BUILD_DIR)/docker
	mkdir -p $(BUILD_DIR)/docker/dist
	cp -r $(DIST_DIR)/spark-*/. $(BUILD_DIR)/docker/dist
	cp -r conf/* $(BUILD_DIR)/docker/dist/conf
	cp -r docker/* $(BUILD_DIR)/docker
	cp `cat statsd-reporter` $(BUILD_DIR)/docker

	pushd $(BUILD_DIR)/docker
	docker build -t $(DOCKER_SPARK_DIST_IMAGE_FULL_NAME) .
	popd

	docker push $(DOCKER_SPARK_DIST_IMAGE_FULL_NAME)
	echo "$(DOCKER_SPARK_DIST_IMAGE_FULL_NAME)" > $@

clean-dist:
	rm -f $(ROOT_DIR)/docker-dist
	rm -rf $(DIST_DIR)

stub-universe: docker-dist
	if [ -n "$(STUB_UNIVERSE_URL)" ]; then
		echo "Using provided stub universe(s): $(STUB_UNIVERSE_URL)"
		echo "$(STUB_UNIVERSE_URL)" > $@
	else
		TEMPLATE_DEFAULT_DOCKER_IMAGE=`cat docker-dist` \
		TEMPLATE_HTTPS_PROTOCOL='https://' \
			$(ROOT_DIR)/tools/build_package.sh spark-history $(ROOT_DIR)/history aws 2>&1 | tee build.stub.out

		grep 'STUB UNIVERSE' build.stub.out | cut -d ' ' -f3 > $@

		$(ROOT_DIR)/cli/dcos-spark/build.sh

		TEMPLATE_DOCKER_IMAGE=`cat docker-dist` \
		TEMPLATE_HTTPS_PROTOCOL='https://' \
			$(ROOT_DIR)/tools/build_package.sh \
				spark \
				$(ROOT_DIR) \
				-a $(ROOT_DIR)/cli/dcos-spark/dcos-spark-darwin \
				-a $(ROOT_DIR)/cli/dcos-spark/dcos-spark-linux \
				-a $(ROOT_DIR)/cli/dcos-spark/dcos-spark.exe \
				aws 2>&1 | tee build.stub.out

		grep 'STUB UNIVERSE' build.stub.out | cut -d ' ' -f3 >> $@
	fi

clean-stub:
	rm -f $(ROOT_DIR)/build.stub.out $(ROOT_DIR)/stub-universe

# Special directive to assist in speeding up CI builds
# Generates a master checksum against the source files in tests/jobs/scala
# This is later compared to avoid building identical jars from previous CI runs
test-jar-checksum:
	find tests/jobs/scala -type f -exec md5sum '{}' + | sort > checksums
	md5sum checksums | cut -d ' ' -f1 > test-jar-checksum

MD5SUM ?= $(shell cat test-jar-checksum)
TEST_JAR_URL ?= https://infinity-artifacts.s3.amazonaws.com/autodelete7d/spark/jars/dcos-spark-scala-tests-assembly-0.2-$(MD5SUM).jar
TEST_JAR_PATH ?= $(ROOT_DIR)/dcos-spark-scala-tests-assembly-0.2-SNAPSHOT.jar
$(TEST_JAR_PATH): test-jar-checksum
	if wget --spider $(TEST_JAR_URL) 2>/dev/null; then
		wget $(TEST_JAR_URL)
	else
		cd tests/jobs/scala
		sbt assembly
		cp -v target/scala-2.11/dcos-spark-scala-tests-assembly-0.2-SNAPSHOT.jar dcos-spark-scala-tests-assembly-0.2-$(MD5SUM).jar
		aws s3 cp --acl public-read dcos-spark-scala-tests-assembly-0.2-$(MD5SUM).jar \
			s3://infinity-artifacts/autodelete7d/spark/jars/dcos-spark-scala-tests-assembly-0.2-$(MD5SUM).jar
	fi
	cp -v dcos-spark-scala-tests-assembly-0.2-$(MD5SUM).jar $@

# Special directive to allow building the test jars separately from running the tests.
test-jars: $(TEST_JAR_PATH)

mesos-spark-integration-tests:
	git clone https://github.com/typesafehub/mesos-spark-integration-tests $(ROOT_DIR)/mesos-spark-integration-tests

MESOS_SPARK_TEST_JAR_PATH ?= $(ROOT_DIR)/mesos-spark-integration-tests-assembly-0.1.0.jar
$(MESOS_SPARK_TEST_JAR_PATH): mesos-spark-integration-tests
	cd $(ROOT_DIR)/mesos-spark-integration-tests/test-runner
	sbt assembly
	cd ..
	sbt clean compile test
	cp -v test-runner/target/scala-2.11/mesos-spark-integration-tests-assembly-0.1.0.jar $@

ssh.keys:
	if [[ ! -f "$(SSH_PRIVATE_KEY_FILE)" ]]; then
		ssh-keygen -t rsa -f $(SSH_PRIVATE_KEY_FILE) -N ''
		chmod 400 $(SSH_PRIVATE_KEY_FILE)
	fi
	echo > $@

aws.credentials:
	$(ROOT_DIR)/tools/generate_aws_credentials.sh $(AWS_SHARED_CREDENTIALS_FILE) $(AWS_PROFILE)

cluster-create: ssh.keys aws.credentials terraform.cluster.create terraform.cluster.url terraform.cluster.public.elb

cluster-destroy: aws.credentials terraform.cluster.destroy

configure-endpoints:
	$(eval CLUSTER_URL := $(if $(CLUSTER_URL),$(CLUSTER_URL),$(shell cat terraform.cluster.url)))
	$(eval PUBLIC_AGENT_ELB := $(if $(PUBLIC_AGENT_ELB),$(PUBLIC_AGENT_ELB),$(shell cat terraform.cluster.public.elb)))

test: aws.credentials ssh.keys docker-build test-jars stub-universe configure-endpoints
	docker run -i --rm \
		--net=host \
		-v $(ROOT_DIR):/spark -w /spark/tests \
		-v $(AWS_SHARED_CREDENTIALS_FILE):/root/.aws/credentials \
		-v $(SSH_PUBLIC_KEY_FILE):/root/.ssh/id_rsa.pub \
		-v $(SSH_PRIVATE_KEY_FILE):/root/.ssh/id_rsa \
		-e AWS_PROFILE=$(AWS_PROFILE) \
		-e AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) \
		-e AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY) \
		-e CLUSTER_URL=$(CLUSTER_URL) \
		-e PUBLIC_AGENT_ELB=$(PUBLIC_AGENT_ELB) \
		-e STUB_UNIVERSE_URL="$(shell cat stub-universe)" \
		-e DCOS_SSH_USERNAME=$(DCOS_SSH_USERNAME) \
		$(shell cat docker-build) \
		/bin/bash -c \
		"eval \$$(ssh-agent -s) && ssh-add /root/.ssh/id_rsa \
	&& dcos cluster setup --no-check --username=$(CLUSTER_USER) --password=$(CLUSTER_PASSWORD) $(CLUSTER_URL) \
	&& python3 -m pytest -s --ignore soak/ $(PYTEST_ARGS)"

clean: clean-dist clean-stub terraform.clean
	rm -f $(TEST_JAR_PATH) $(MESOS_SPARK_TEST_JAR_PATH) $(SSH_PUBLIC_KEY_FILE) $(SSH_PRIVATE_KEY_FILE) checksums
	rm -f docker-build statsd-reporter ssh.keys aws.credentials $(AWS_SHARED_CREDENTIALS_FILE)* test-jar-checksum

.PHONY: clean clean-dist clean-stub stub-universe spark-dist-download spark-dist-build docker-login docker-build docker-dist test cluster-create cluster-destroy
