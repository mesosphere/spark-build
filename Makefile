ROOT_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
TOOLS_DIR := $(ROOT_DIR)/tools
BUILD_DIR := $(ROOT_DIR)/build
CLI_DIST_DIR := $(BUILD_DIR)/cli_dist
DIST_DIR := $(BUILD_DIR)/dist
GIT_COMMIT := $(shell git rev-parse HEAD)

S3_BUCKET ?= infinity-artifacts
S3_PREFIX ?= autodelete7d

.ONESHELL:
SHELL := /bin/bash
.SHELLFLAGS = -ec

# This image can be used to build spark dist and run tests
DOCKER_BUILD_IMAGE ?= mesosphere/spark-build:$(GIT_COMMIT)
docker-build:
	docker build -t $(DOCKER_BUILD_IMAGE) .
	echo $(DOCKER_BUILD_IMAGE) > $@

# Pulls the spark distribution listed in the manifest as default
SPARK_DIST_URI ?= $(shell jq ".default_spark_dist.uri" "$(ROOT_DIR)/manifest.json")
manifest-dist:
	mkdir -p $(DIST_DIR)
	pushd $(DIST_DIR)
	wget $(SPARK_DIST_URI)
	popd

HADOOP_VERSION ?= $(shell jq ".default_spark_dist.hadoop_version" "$(ROOT_DIR)/manifest.json")

SPARK_DIR ?= $(ROOT_DIR)/spark
$(SPARK_DIR):
	git clone https://github.com/mesosphere/spark $(SPARK_DIR)

# Builds a quick dev version of spark from the mesosphere fork
dev-dist: $(SPARK_DIR)
	cd $(SPARK_DIR)
	rm -rf spark-*.tgz
	build/sbt -Xmax-classfile-name -Pmesos "-Phadoop-$(HADOOP_VERSION)" -Phive -Phive-thriftserver package
	rm -rf /tmp/spark-SNAPSHOT*
	mkdir -p /tmp/spark-SNAPSHOT/jars
	cp -r assembly/target/scala*/jars/* /tmp/spark-SNAPSHOT/jars
	mkdir -p /tmp/spark-SNAPSHOT/examples/jars
	cp -r examples/target/scala*/jars/* /tmp/spark-SNAPSHOT/examples/jars
	for f in /tmp/spark-SNAPSHOT/examples/jars/*; do \
		name=$$(basename "$$f"); \
		if [ -f "/tmp/spark-SNAPSHOT/jars/$${name}" ]; then \
			rm "/tmp/spark-SNAPSHOT/examples/jars/$${name}"; \
		fi; \
	done; \
	cp -r data /tmp/spark-SNAPSHOT/
	mkdir -p /tmp/spark-SNAPSHOT/conf
	cp conf/* /tmp/spark-SNAPSHOT/conf
	cp -r bin /tmp/spark-SNAPSHOT
	cp -r sbin /tmp/spark-SNAPSHOT
	cp -r python /tmp/spark-SNAPSHOT
	cd /tmp
	tar czf spark-SNAPSHOT.tgz spark-SNAPSHOT
	mkdir -p $(DIST_DIR)
	cp /tmp/spark-SNAPSHOT.tgz $(DIST_DIR)/

prod-dist: $(SPARK_DIR)
	cd $(SPARK_DIR)
	rm -rf spark-*.tgz
	if [ -f make-distribution.sh ]; then \
		./make-distribution.sh --tgz "-Phadoop-$(HADOOP_VERSION)" -Phive -Phive-thriftserver -DskipTests; \
	else \
		if [ -n $(does_profile_exist,mesos) ]; then \
			MESOS_PROFILE="-Pmesos"; \
		else \
			MESOS_PROFILE=""; \
		fi; \
		./dev/make-distribution.sh --tgz "$${MESOS_PROFILE}" "-Phadoop-$(HADOOP_VERSION)" -Psparkr -Phive -Phive-thriftserver -DskipTests; \
	fi; \
	mkdir -p $(DIST_DIR)
	cp spark-*.tgz $(DIST_DIR)

# this target serves as default dist type
$(DIST_DIR):
	$(MAKE) manifest-dist

clean-dist:
	@[ ! -e $(DIST_DIR) ] || rm -rf $(DIST_DIR)

docker-login:
	docker login --email="$(DOCKER_EMAIL)" --username="$(DOCKER_USERNAME)" --password="$(DOCKER_PASSWORD)"

DOCKER_DIST_IMAGE ?= mesosphere/spark-dev:$(GIT_COMMIT)
docker-dist: $(DIST_DIR)
	tar xvf $(DIST_DIR)/spark-*.tgz -C $(DIST_DIR)
	rm -rf $(BUILD_DIR)/docker
	mkdir -p $(BUILD_DIR)/docker/dist
	cp -r $(DIST_DIR)/spark-*/. $(BUILD_DIR)/docker/dist
	cp -r conf/* $(BUILD_DIR)/docker/dist/conf
	cp -r docker/* $(BUILD_DIR)/docker
	pushd $(BUILD_DIR)/docker
	docker build -t $(DOCKER_DIST_IMAGE) .
	popd
	docker push $(DOCKER_DIST_IMAGE)
	echo "$(DOCKER_DIST_IMAGE)" > $@

CLI_VERSION := $(shell jq -r ".cli_version" "$(ROOT_DIR)/manifest.json")
$(CLI_DIST_DIR):
	$(MAKE) --directory=cli all
	mkdir -p $@
	mv $(ROOT_DIR)/cli/dcos-spark/dcos-spark-darwin $@/
	mv $(ROOT_DIR)/cli/dcos-spark/dcos-spark-linux $@/
	mv $(ROOT_DIR)/cli/dcos-spark/dcos-spark.exe $@/
	mv $(ROOT_DIR)/cli/python/dist/*.whl $@/

cli: $(CLI_DIST_DIR)

UNIVERSE_URL_PATH := stub-universe-url
$(UNIVERSE_URL_PATH): $(CLI_DIST_DIR) docker-dist
	UNIVERSE_URL_PATH=$(UNIVERSE_URL_PATH) \
	TEMPLATE_CLI_VERSION=$(CLI_VERSION) \
	TEMPLATE_DOCKER_IMAGE=`cat docker-dist` \
		$(TOOLS_DIR)/publish_aws.py \
		spark \
        $(ROOT_DIR)/universe/ \
        $(CLI_DIST_DIR)/dcos-spark-darwin \
        $(CLI_DIST_DIR)/dcos-spark-linux \
        $(CLI_DIST_DIR)/dcos-spark.exe \
        $(CLI_DIST_DIR)/*.whl;

DCOS_SPARK_TEST_JAR_PATH := $(ROOT_DIR)/dcos-spark-scala-tests-assembly-0.1-SNAPSHOT.jar
$(DCOS_SPARK_TEST_JAR_PATH):
	cd tests/jobs/scala
	sbt assembly
	cp $(ROOT_DIR)/tests/jobs/scala/target/scala-2.11/dcos-spark-scala-tests-assembly-0.1-SNAPSHOT.jar $(DCOS_SPARK_TEST_JAR_PATH)

test-env:
	python3 -m venv test-env
	source test-env/bin/activate
	pip3 install -r tests/requirements.txt

cluster-url:
	$(eval export DCOS_LAUNCH_CONFIG_BODY)
	@if [ -z $(CLUSTER_URL) ]; then \
	  source $(ROOT_DIR)/test-env/bin/activate; \
	  echo "$$DCOS_LAUNCH_CONFIG_BODY" > dcos_launch_config.yaml; \
	  dcos-launch create -c dcos_launch_config.yaml; \
	  dcos-launch wait; \
	  echo https://`dcos-launch describe | jq -r .masters[0].public_ip` > $@; \
	else \
	  echo "CLUSTER_URL detected in env; not deploying a new cluster"; \
	  echo $(CLUSTER_URL) > $@; \
	fi; \

clean-cluster:
	@dcos-launch delete || echo "Error deleting cluster"
	[ ! -e cluster-url ] || rm cluster-url

mesos-spark-integration-tests:
	git clone https://github.com/typesafehub/mesos-spark-integration-tests $(ROOT_DIR)/mesos-spark-integration-tests

MESOS_SPARK_TEST_JAR_PATH := $(ROOT_DIR)/mesos-spark-integration-tests-assembly-0.1.0.jar
$(MESOS_SPARK_TEST_JAR_PATH): mesos-spark-integration-tests
	cd $(ROOT_DIR)/mesos-spark-integration-tests/test-runner
	sbt assembly
	cd ..
	sbt clean compile test
	cp test-runner/target/scala-2.11/mesos-spark-integration-tests-assembly-0.1.0.jar $(MESOS_SPARK_TEST_JAR_PATH)

PYTEST_ARGS ?= -s -vv -m sanity
test: test-env $(DCOS_SPARK_TEST_JAR_PATH) $(MESOS_SPARK_TEST_JAR_PATH) $(UNIVERSE_URL_PATH) cluster-url
	source $(ROOT_DIR)/test-env/bin/activate
	if [ -z $(CLUSTER_URL) ]; then \
	    if [ `cat cluster_info.json | jq .key_helper` == 'true' ]; then \
	      cat cluster_info.json | jq -r .ssh_private_key > test_cluster_ssh_key; \
	      chmod 600 test_cluster_ssh_key; \
		  eval `ssh-agent -s`; \
		  ssh-add test_cluster_ssh_key; \
	    fi; \
	fi; \
	export CLUSTER_URL=`cat cluster-url`
	$(TOOLS_DIR)/./dcos_login.py
	if [ "$(SECURITY)" = "strict" ]; then \
        $(TOOLS_DIR)/setup_permissions.sh root "*"; \
        $(TOOLS_DIR)/setup_permissions.sh root hdfs-role; \
    fi; \
	dcos package repo add --index=0 spark-aws `cat stub-universe-url`
	SCALA_TEST_JAR_PATH=$(DCOS_SPARK_TEST_JAR_PATH) \
	  TEST_JAR_PATH=$(MESOS_SPARK_TEST_JAR_PATH) \
	  S3_BUCKET=$(S3_BUCKET) \
	  S3_PREFIX=$(S3_PREFIX) \
	  py.test $(PYTEST_ARGS) $(ROOT_DIR)/tests

clean: clean-dist clean-cluster
	rm -rf test-env
	rm -rf $(CLI_DIST_DIR)
	for f in  "$(MESOS_SPARK_TEST_JAR_PATH)" "$(DCOS_SPARK_TEST_JAR_PATH)" "cluster-url" "$(UNIVERSE_URL_PATH)" "docker-build" "docker-dist" ; do \
		[ ! -e $$f ] || rm $$f; \
	done; \



define spark_dist
`cd $(DIST_DIR) && ls spark-*.tgz`
endef

define does_profile_exist
`cd "$(SPARK_DIR)" && ./build/mvn help:all-profiles | grep $(1)`
endef


define DCOS_LAUNCH_CONFIG_BODY
---
launch_config_version: 1
deployment_name: dcos-ci-test-spark-build-$(shell cat /dev/urandom | tr -dc 'a-z0-9' | fold -w 10 | head -n 1)
template_url: https://s3.amazonaws.com/downloads.mesosphere.io/dcos-enterprise/testing/master/cloudformation/ee.single-master.cloudformation.json
provider: aws
key_helper: true
template_parameters:
  AdminLocation: 0.0.0.0/0
  PublicSlaveInstanceCount: 1
  SlaveInstanceCount: 5
ssh_user: core
endef


.PHONY: clean clean-dist clean-cluster cli manifest-dist dev-dist prod-dist docker-login test
