#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#ubuntu:18.04 - linux; amd64
#https://github.com/docker-library/repo-info/blob/master/repos/ubuntu/tag-details.md#ubuntu1804---linux-amd64
FROM ubuntu@sha256:be159ff0e12a38fd2208022484bee14412680727ec992680b66cdead1ba76d19

ARG DCOS_VERSION=1.13

ENV DEBIAN_FRONTEND="noninteractive" \
    DEBCONF_NONINTERACTIVE_SEEN="true" \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    TERM=xterm-color \
    TEAMCITY_VERSION="2017.2" \
    INTEGRATION_TEST_LOG_COLLECTION='False'

RUN apt-get update \
    && apt-get install -yq --no-install-recommends \
       build-essential \
       curl \
       git \
       openjdk-8-jdk \
       groff \
       openssh-server \
       python3 \
       python3-pip \
       python3-setuptools \
       python3-wheel \
       gnupg \
       dirmngr \
       r-base \
       git \
       software-properties-common \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --upgrade \
       boto3 \
       pytest \
       retrying \
       requests \
       teamcity-messages \
       python-keycloak \
       awscli \
    && curl https://downloads.dcos.io/binaries/cli/linux/x86-64/dcos-${DCOS_VERSION}/dcos -o /usr/local/bin/dcos \
    && chmod +x /usr/local/bin/dcos

# install Go and SBT
RUN curl -LO https://dl.google.com/go/go1.12.linux-amd64.tar.gz \
    && tar -C /usr/local -xzf go1.12.linux-amd64.tar.gz \
    && ln -s /usr/local/go/bin/go /usr/bin/go \
    && echo "deb https://dl.bintray.com/sbt/debian /" | tee -a /etc/apt/sources.list.d/sbt.list \
    && apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 2EE0EA64E40A89B84B2DF73499E82A75642AC823 \
    && apt-get update && apt-get install -y \ 
    sbt \
    && rm -rf /var/lib/apt/lists/*
