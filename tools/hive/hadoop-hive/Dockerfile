FROM ubuntu:16.04

USER root

# install dev tools
RUN apt-get update && \
    apt-get install -y curl wget tar openssh-server openssh-client rsync python-software-properties apt-file apache2 && \
    rm -rf /var/lib/apt/lists/*

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
RUN apt-get update && \
    apt-get install -y software-properties-common && \
    add-apt-repository ppa:webupd8team/java && \
    apt-get update && \
    # to accept license agreement automatically
    echo debconf shared/accepted-oracle-license-v1-1 select true | debconf-set-selections && \
    echo debconf shared/accepted-oracle-license-v1-1 seen true | debconf-set-selections && \
    apt-get install -y oracle-java8-installer && \
    rm -rf /var/lib/apt/lists/*

# java env setup
ENV JAVA_HOME /usr/lib/jvm/java-8-oracle
ENV PATH $PATH:$JAVA_HOME/bin

ENV CDH_VERSION 5
ENV CDH_EXACT_VERSION 5.11.0
ENV HADOOP_VERSION 2.6.0

# download cdh hadoop
RUN curl -L http://archive.cloudera.com/cdh${CDH_VERSION}/cdh/${CDH_VERSION}/hadoop-${HADOOP_VERSION}-cdh${CDH_EXACT_VERSION}.tar.gz \
    | tar -xzC /usr/local && \
    cd /usr/local && \
    ln -s ./hadoop-${HADOOP_VERSION}-cdh${CDH_EXACT_VERSION} hadoop

# need to define JAVA_HOME inside hadoop-env.sh
ENV HADOOP_PREFIX /usr/local/hadoop
RUN sed -i '/^export JAVA_HOME/ s:.*:export JAVA_HOME=/usr/lib/jvm/java-8-oracle\n:' $HADOOP_PREFIX/etc/hadoop/hadoop-env.sh

# pseudo distributed configurations of hadoop
ADD templates/core-site.xml.template $HADOOP_PREFIX/etc/hadoop/core-site.xml.template
ADD templates/hdfs-site.xml.template $HADOOP_PREFIX/etc/hadoop/hdfs-site.xml.template
ADD conf/mapred-site.xml $HADOOP_PREFIX/etc/hadoop/mapred-site.xml
ADD templates/yarn-site.xml.template $HADOOP_PREFIX/etc/hadoop/yarn-site.xml.template

# add and set permissions for bootstrap script
ADD scripts/hadoop-bootstrap.sh /etc/hadoop-bootstrap.sh
RUN chown root:root /etc/hadoop-bootstrap.sh
RUN chmod 700 /etc/hadoop-bootstrap.sh

RUN chmod +x /usr/local/hadoop/etc/hadoop/*-env.sh

# add hadoop to path
ENV HADOOP_HOME /usr/local/hadoop
ENV PATH $PATH:$HADOOP_HOME:$HADOOP_HOME/bin

#for exposed ports refer
#https://www.cloudera.com/documentation/enterprise/5-4-x/topics/cdh_ig_ports_cdh5.html
EXPOSE 50010 50020 50070 50075 50090 8020 9000 10020 19888 8030 8031 8032 8033 8040 8042 8088

# download cdh hive
ENV HIVE_VERSION 1.1.0
RUN curl -L http://archive.cloudera.com/cdh${CDH_VERSION}/cdh/${CDH_VERSION}/hive-${HIVE_VERSION}-cdh${CDH_EXACT_VERSION}.tar.gz \
    | tar -xzC /usr/local && \
    cd /usr/local && \
    mv hive-${HIVE_VERSION}-cdh${CDH_EXACT_VERSION} hive

# to configure postgres as hive metastore backend
RUN sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt/ `lsb_release -cs`-pgdg main" >> /etc/apt/sources.list.d/pgdg.list'
RUN wget -q https://www.postgresql.org/media/keys/ACCC4CF8.asc -O - | apt-key add -
RUN apt-get update -y && \
    apt-get -yq install vim postgresql-9.5 libpostgresql-jdbc-java && \
    rm -rf /var/lib/apt/lists/*

# add hive to path
ENV HIVE_HOME /usr/local/hive
ENV PATH $PATH:$HIVE_HOME/bin

# add postgresql jdbc jar to classpath
RUN ln -s /usr/share/java/postgresql-jdbc4.jar $HIVE_HOME/lib/postgresql-jdbc4.jar

USER postgres
# initialize hive metastore db
# create metastore db, hive user and assign privileges
RUN cd $HIVE_HOME/scripts/metastore/upgrade/postgres/ && \
     /etc/init.d/postgresql start && \
     psql --command "CREATE DATABASE metastore;" && \
     psql --command "CREATE USER hive WITH PASSWORD 'hive';" && \
     psql --command "ALTER USER hive WITH SUPERUSER;" && \
     psql --command "GRANT ALL PRIVILEGES ON DATABASE metastore TO hive;" && \
     psql -U hive -d metastore -h localhost -f hive-schema-${HIVE_VERSION}.postgres.sql

# revert back to default user
USER root

# disable ssl in postgres.conf
ENV POSTGRES_VERSION 9.5
ENV POSTGRESQL_CONFIG_FILE /var/lib/postgresql/${POSTGRES_VERSION}/main/postgresql.conf
ENV POSTGRESQL_MAIN /var/lib/postgresql/9.5/main/
ADD conf/postgresql.conf $POSTGRESQL_MAIN
RUN chown postgres:postgres $POSTGRESQL_CONFIG_FILE
RUN sed -i -e 's/peer/md5/g' /etc/postgresql/$POSTGRES_VERSION/main/pg_hba.conf

# copy config, sql, data files to /opt/files
ENV HIVE_CONF /usr/local/hive/conf
RUN mkdir /opt/files
ADD templates/hive-site.xml.template /opt/files/
ADD templates/hive-site.xml.template $HIVE_CONF/hive-site.xml.template

# set permissions for hive bootstrap file
ADD scripts/hive-bootstrap.sh /etc/hive-bootstrap.sh
RUN chown root:root /etc/hive-bootstrap.sh
RUN chmod 700 /etc/hive-bootstrap.sh

EXPOSE 10000 10001 10002 10003 9083 50111 5432

# run bootstrap script
CMD ["/etc/hive-bootstrap.sh", "-d"]
