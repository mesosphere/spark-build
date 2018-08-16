FROM ubuntu:16.04

USER root

ENV JAVA_HOME /usr/lib/jvm/java-8-oracle
ENV HADOOP_VERSION 2.6.0
ENV CDH_VERSION 5
ENV CDH_EXACT_VERSION 5.11.0
ENV HADOOP_HOME /usr/local/hadoop
ENV HADOOP_PREFIX /usr/local/hadoop
ENV HADOOP_COMMON_HOME /usr/local/hadoop
ENV HADOOP_HDFS_HOME /usr/local/hadoop
ENV HADOOP_MAPRED_HOME /usr/local/hadoop
ENV HADOOP_YARN_HOME /usr/local/hadoop
ENV HADOOP_CONF_DIR /usr/local/hadoop/etc/hadoop
ENV HIVE_HOME /usr/local/hive

# install dev tools
RUN apt-get update
RUN apt-get install -y curl wget tar openssh-server openssh-client rsync python-software-properties apt-file apache2

# for running sshd in ubuntu trusty. https://github.com/docker/docker/issues/5704
RUN mkdir /var/run/sshd
RUN echo 'root:secretpasswd' | chpasswd
RUN sed -i 's/PermitRootLogin without-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# passwordless ssh
RUN yes | ssh-keygen -q -N "" -t dsa -f /etc/ssh/ssh_host_dsa_key
RUN yes | ssh-keygen -q -N "" -t rsa -f /etc/ssh/ssh_host_rsa_key
RUN yes | ssh-keygen -q -N "" -t rsa -f /root/.ssh/id_rsa
RUN cp /root/.ssh/id_rsa.pub /root/.ssh/authorized_keys

# fix the 254 error code
RUN sed  -i "/^[^#]*UsePAM/ s/.*/#&/"  /etc/ssh/sshd_config
RUN echo "UsePAM no" >> /etc/ssh/sshd_config
RUN echo "Port 2122" >> /etc/ssh/sshd_config
RUN /usr/sbin/sshd

# ssh client config
ADD conf/ssh_config /root/.ssh/config
RUN chmod 600 /root/.ssh/config
RUN chown root:root /root/.ssh/config

EXPOSE 22

# oracle jdk 8
RUN apt-get install -y software-properties-common
RUN add-apt-repository ppa:webupd8team/java
RUN apt-get update

# to accept license agreement automatically
RUN echo debconf shared/accepted-oracle-license-v1-1 select true | debconf-set-selections
RUN echo debconf shared/accepted-oracle-license-v1-1 seen true | debconf-set-selections
RUN apt-get install -y oracle-java8-installer

# java env setup
ENV JAVA_HOME /usr/lib/jvm/java-8-oracle
ENV PATH $PATH:$JAVA_HOME/bin

ADD ./deps/hadoop-${HADOOP_VERSION}-cdh${CDH_EXACT_VERSION}.tar.gz /usr/local
RUN cd /usr/local && ln -s ./hadoop-${HADOOP_VERSION}-cdh${CDH_EXACT_VERSION} hadoop

RUN sed -i '/^export JAVA_HOME/ s:.*:export JAVA_HOME=/usr/lib/jvm/java-8-oracle\n:' $HADOOP_PREFIX/etc/hadoop/hadoop-env.sh
#RUN sed -i '/^export HADOOP_CONF_DIR/ s:.*:export HADOOP_CONF_DIR=/usr/local/hadoop/etc/hadoop/:' $HADOOP_PREFIX/etc/hadoop/hadoop-env.sh

# copy hadoop site xml files
#RUN mkdir $HADOOP_PREFIX/input
#RUN cp $HADOOP_PREFIX/etc/hadoop/*.xml $HADOOP_PREFIX/input

# pseudo distributed configurations
ADD templates/core-site.xml.template $HADOOP_PREFIX/etc/hadoop/core-site.xml.template
ADD templates/hdfs-site.xml.template $HADOOP_PREFIX/etc/hadoop/hdfs-site.xml.template
ADD conf/mapred-site.xml $HADOOP_PREFIX/etc/hadoop/mapred-site.xml
ADD templates/yarn-site.xml.template $HADOOP_PREFIX/etc/hadoop/yarn-site.xml.template

# fixing the libhadoop.so
#RUN rm -rf /usr/local/hadoop/lib/native/*
#ADD ./deps/hadoop-native-64-2.6.0.tar /usr/local/hadoop/lib/native/

# add and set permissions for bootstrap script
ADD scripts/bootstrap.sh /etc/hadoop-bootstrap.sh
RUN chown root:root /etc/hadoop-bootstrap.sh
RUN chmod 700 /etc/hadoop-bootstrap.sh

RUN chmod +x /usr/local/hadoop/etc/hadoop/*-env.sh

# add hadoop to path
ENV PATH $PATH:$HADOOP_HOME:$HADOOP_HOME/bin

#for exposed ports refer
#https://www.cloudera.com/documentation/enterprise/5-4-x/topics/cdh_ig_ports_cdh5.html
EXPOSE 50010 50020 50070 50075 50090 8020 9000 10020 19888 8030 8031 8032 8033 8040 8042 8088

# add hive to path
ENV PATH $PATH:$HIVE_HOME/bin
