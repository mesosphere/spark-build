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
# Create snapshot builds with:
# docker build -t spark:git-`git rev-parse --short HEAD` .

#ubuntu:18.04 - linux; amd64
#https://github.com/docker-library/repo-info/blob/master/repos/ubuntu/tag-details.md#ubuntu1804---linux-amd64
FROM ubuntu@sha256:6b9eb699512656fc6ef936ddeb45ab25edcd17ab94901790989f89dbf782344a

# Set environment variables.
ENV DEBIAN_FRONTEND "noninteractive"
ENV DEBCONF_NONINTERACTIVE_SEEN "true"

ARG LIBMESOS_BUNDLE_DOWNLOAD_URL="https://downloads.mesosphere.io/libmesos-bundle/libmesos-bundle-1.12.0.tar.gz"
ARG BOOTSTRAP_DOWNLOAD_URL="https://downloads.mesosphere.com/dcos-commons/artifacts/0.50.0/bootstrap.zip"

ARG JAVA_VERSION="8u192"
ARG JRE_DOWNLOAD_URL="https://downloads.mesosphere.com/java/server-jre-${JAVA_VERSION}-linux-x64.tar.gz"

# Upgrade package index and install basic commands.
RUN apt-get update \
    && apt-get install -y \
               python \
               software-properties-common \
               runit \
               nginx \
               krb5-user \
               curl \
               unzip \
               r-base \
    && rm -rf /var/lib/apt/lists/* /usr/share/doc

# lib mesos
ARG MESOSPHERE_HOME="/opt/mesosphere"
ARG BOOTSTRAP_BINARY="${MESOSPHERE_HOME}/bootstrap.zip"
RUN mkdir -p ${MESOSPHERE_HOME} \
    && curl -L ${LIBMESOS_BUNDLE_DOWNLOAD_URL} | tar -C ${MESOSPHERE_HOME} -zx \
    && curl -L -o ${BOOTSTRAP_BINARY} ${BOOTSTRAP_DOWNLOAD_URL} \
    && unzip ${BOOTSTRAP_BINARY} -d ${MESOSPHERE_HOME} \
    && rm ${BOOTSTRAP_BINARY}

ENV BOOTSTRAP ${MESOSPHERE_HOME}/bootstrap
ENV MESOS_NATIVE_JAVA_LIBRARY ${MESOSPHERE_HOME}/libmesos-bundle/lib/libmesos.so

# JVM
ENV JAVA_HOME /usr/lib/jvm/${JAVA_VERSION}
RUN mkdir -p ${JAVA_HOME} \
    && curl -L ${JRE_DOWNLOAD_URL} | tar -C ${JAVA_HOME} --strip-components=1 -zx

ENV HADOOP_CONF_DIR /etc/hadoop
RUN mkdir ${HADOOP_CONF_DIR}

ADD runit/service /var/lib/runit/service
ADD runit/init.sh /sbin/init.sh
ADD nginx /etc/nginx

# The following symlinks are hacks to make spark-class work under the
# restricted PATH (/usr/bin) set by the DCOS
# --executor-environment-variables option
RUN ln -s /bin/bash /usr/bin/bash \
    && ln -s /bin/ls /usr/bin/ls \
    && ln -s /bin/grep /usr/bin/grep \
    && ln -s /var/lib/runit/service/spark /etc/service/spark \
    && ln -s /var/lib/runit/service/nginx /etc/service/nginx

ADD dist /opt/spark/dist
ADD krb5.conf.mustache /etc/

# Add external jar for pushing metrics via StatsD (https://github.com/vidhyaarvind/spark-statsd)
# current version: Spark 2.2.1, Scala 2.11
ADD jars/spark-statsd-2.2.1-2.11.jar /opt/spark/dist/jars/

# required to run as nobody
RUN addgroup --gid 99 nobody \
    && echo "nobody:x:99:99:nobody:/nonexistent:/usr/sbin/nologin" >> /etc/passwd \
    && usermod -a -G users nobody \
    && chmod -R ugo+rw /etc/nginx \
    && chmod -R ugo+rw /etc/krb5.conf \
    && chmod -R ugo+rw /etc/hadoop \
    && chmod -R ugo+rw /etc/service \
    && chmod -R ugo+rw /var/lib/ \
    && chmod -R ugo+rw /var/run/ \
    && chmod -R ugo+rw /var/log/ \
    && chmod -R ugo+rw /opt/spark/dist

WORKDIR /opt/spark/dist
