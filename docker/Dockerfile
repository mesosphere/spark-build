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

# Basing from Mesos image so the Mesos native library is present.
FROM ubuntu:14.04

# Set environment variables.
ENV DEBIAN_FRONTEND "noninteractive"
ENV DEBCONF_NONINTERACTIVE_SEEN "true"

# Upgrade package index and install basic commands.
RUN apt-get update && \
    apt-get install -y \
            software-properties-common \
            runit \
            nginx \
            krb5-user \
            curl \
            unzip \
            r-base

# lib mesos
RUN mkdir -p /opt/mesosphere/ && \
    cd /opt/mesosphere && \
    curl -L -O https://downloads.mesosphere.io/libmesos-bundle/libmesos-bundle-1.10-1.4.x-a35c801.tar.gz && \
    tar zxf libmesos-bundle-1.10-1.4.x-a35c801.tar.gz && \
    rm libmesos-bundle-1.10-1.4.x-a35c801.tar.gz && \
    curl -L -O https://downloads.mesosphere.com/dcos-commons/artifacts/0.30.0/bootstrap.zip && \
    unzip bootstrap.zip && \
    rm bootstrap.zip

# JVM
RUN mkdir -p /usr/lib/jvm/ && \
    cd /usr/lib/jvm && \
    curl -L -O https://downloads.mesosphere.com/java/server-jre-8u172-linux-x64.tar.gz && \
    tar zxf server-jre-8u172-linux-x64.tar.gz && \
    rm server-jre-8u172-linux-x64.tar.gz

ENV BOOTSTRAP /opt/mesosphere/bootstrap
ENV JAVA_HOME /usr/lib/jvm/jdk1.8.0_172/jre
ENV MESOS_NATIVE_JAVA_LIBRARY /opt/mesosphere/libmesos-bundle/lib/libmesos.so
ENV LD_LIBRARY_PATH /opt/mesosphere/libmesos-bundle/lib/
ENV HADOOP_CONF_DIR /etc/hadoop

RUN mkdir /etc/hadoop

ADD runit/service /var/lib/runit/service
ADD runit/init.sh /sbin/init.sh
ADD nginx /etc/nginx

# The following symlinks are hacks to make spark-class work under the
# restricted PATH (/usr/bin) set by the DCOS
# --executor-environment-variables option
RUN ln -s /bin/bash /usr/bin/bash
RUN ln -s /bin/ls /usr/bin/ls
RUN ln -s /bin/grep /usr/bin/grep

RUN ln -s /var/lib/runit/service/spark /etc/service/spark
RUN ln -s /var/lib/runit/service/nginx /etc/service/nginx

ADD dist /opt/spark/dist
ADD krb5.conf.mustache /etc/

# required to run as nobody
RUN chmod -R ugo+rw /etc/nginx
RUN chmod -R ugo+rw /etc/krb5.conf
RUN chmod -R ugo+rw /etc/hadoop
RUN chmod -R ugo+rw /etc/service
RUN chmod -R ugo+rw /var/lib/
RUN chmod -R ugo+rw /var/run/
RUN chmod -R ugo+rw /var/log/
RUN chmod -R ugo+rw /opt/spark/dist

WORKDIR /opt/spark/dist
