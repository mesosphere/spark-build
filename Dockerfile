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
# Set environment variables for apt to be noninteractive
ENV DEBIAN_FRONTEND "noninteractive"
ENV DEBCONF_NONINTERACTIVE_SEEN "true"

RUN apt-get update && apt-get install -y \
    bc \
    curl \
    default-jdk \
    gfortran \
    git \
    jq \
    libbz2-dev \
    liblzma-dev \
    libcurl4-openssl-dev \
    libpcre++-dev \
    libssl-dev \
    python-pip \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    r-base \
    software-properties-common \
    wget \
    zip && \
    rm -rf /var/lib/apt/lists/*
# install go 1.7
RUN add-apt-repository -y ppa:longsleep/golang-backports && apt-get update && apt-get install -y golang-go
# AWS CLI for uploading build artifacts
RUN pip install awscli
# Install dcos-launch to create clusters for integration testing
RUN wget https://downloads.dcos.io/dcos-launch/bin/linux/dcos-launch -O /usr/bin/dcos-launch
RUN chmod +x /usr/bin/dcos-launch
# shakedown and dcos-cli require this to output cleanly
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
# use an arbitrary path for temporary build artifacts
ENV GOPATH=/go-tmp


RUN apt-get update && apt-get install -y apt-transport-https \
  && echo "deb https://dl.bintray.com/sbt/debian /" | tee -a /etc/apt/sources.list.d/sbt.list \
  && apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 2EE0EA64E40A89B84B2DF73499E82A75642AC823 \
  && apt-get update \
  && apt-get install -y sbt \
  && rm -rf /var/lib/apt/lists/*
