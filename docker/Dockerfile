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
FROM mesosphere/mesos-modules-private:git-e348e3f
MAINTAINER Michael Gummelt <mgummelt@mesosphere.io>

# Set environment variables.
ENV DEBIAN_FRONTEND "noninteractive"
ENV DEBCONF_NONINTERACTIVE_SEEN "true"

# Upgrade package index and install basic commands.
RUN apt-get update && \
    apt-get install -y software-properties-common runit nginx
RUN add-apt-repository ppa:openjdk-r/ppa
RUN apt-get update && \
    apt-get install -y openjdk-8-jdk curl

ENV JAVA_HOME /usr/lib/jvm/java-8-openjdk-amd64
ENV MESOS_NATIVE_JAVA_LIBRARY /usr/local/lib/libmesos.so
ENV HADOOP_CONF_DIR /etc/hadoop

RUN mkdir /etc/hadoop

ADD dist /opt/spark/dist
ADD runit/service /var/lib/runit/service
ADD runit/init.sh /sbin/init.sh
ADD nginx /etc/nginx

#RUN ln -sf /usr/lib/libmesos.so /usr/lib/libmesos-0.23.1.so

# The following symlinks are hacks to make spark-class work under the
# restricted PATH (/usr/bin) set by the DCOS
# --executor-environment-variables option
RUN ln -s /bin/bash /usr/bin/bash
RUN ln -s /bin/ls /usr/bin/ls
RUN ln -s /bin/grep /usr/bin/grep

RUN ln -s /var/lib/runit/service/spark /etc/service/spark
RUN ln -s /var/lib/runit/service/nginx /etc/service/nginx

WORKDIR /opt/spark/dist
