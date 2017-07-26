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
FROM mesosphere/mesos-modules-private:dcos-ee-mesos-modules-1.8.5-rc2
MAINTAINER Michael Gummelt <mgummelt@mesosphere.io>

# Set environment variables.
ENV DEBIAN_FRONTEND "noninteractive"
ENV DEBCONF_NONINTERACTIVE_SEEN "true"

# Upgrade package index and install basic commands.
RUN apt-get update && \
    apt-get install -y \
            software-properties-common \
            runit \
            nginx \
            krb5-user

RUN apt-get update && \
    apt-get install -y curl
RUN apt-get install -y r-base

RUN cd /usr/lib/jvm && \
    curl -L -O https://downloads.mesosphere.com/java/jre-8u112-linux-x64-jce-unlimited.tar.gz && \
    tar zxf jre-8u112-linux-x64-jce-unlimited.tar.gz && \
    rm jre-8u112-linux-x64-jce-unlimited.tar.gz

ENV JAVA_HOME /usr/lib/jvm/jre1.8.0_112
ENV MESOS_NATIVE_JAVA_LIBRARY /usr/lib/libmesos.so
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

# Commenting these for now, because we're running Spark as root in strict mode
# RUN chmod -R ugo+rw /etc/nginx
# RUN chmod -R ugo+rw /etc/service
# RUN chmod -R ugo+rw /var/lib/
# RUN chmod -R ugo+rw /var/run/
# RUN chmod -R ugo+rw /var/log/
# RUN chmod -R ugo+rw /opt/spark/dist

WORKDIR /opt/spark/dist
