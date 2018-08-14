FROM cdh5-hadoop

ENV JAVA_HOME /usr/lib/jvm/java-8-oracle
ENV HIVE_HOME /usr/local/hive
ENV HIVE_CONF /usr/local/hive/conf
ENV HIVE_VERSION 1.1.0
ENV HADOOP_VERSION 2.6.0
ENV CDH_VERSION 5
ENV CDH_EXACT_VERSION 5.11.0
ENV POSTGRES_VERSION 9.5
ENV POSTGRESQL_MAIN /var/lib/postgresql/9.5/main/
ENV POSTGRESQL_CONFIG_FILE /var/lib/postgresql/9.5/main/postgresql.conf
ENV POSTGRESQL_BIN /usr/lib/postgresql/9.5/bin/postgres
ENV PGPASSWORD hive
ENV HADOOP_HOME /usr/local/hadoop
ENV HADOOP_PREFIX /usr/local/hadoop
ENV HADOOP_COMMON_HOME /usr/local/hadoop
ENV HADOOP_HDFS_HOME /usr/local/hadoop
ENV HADOOP_MAPRED_HOME /usr/local/hadoop
ENV HADOOP_YARN_HOME /usr/local/hadoop
ENV HADOOP_CONF_DIR /usr/local/hadoop/etc/hadoop

ENV PATH $PATH:$JAVA_HOME/bin:$HIVE_HOME/bin:$HADOOP_HOME:$HADOOP_HOME/bin

# add hive
ADD ./deps/hive-1.1.0-cdh${CDH_EXACT_VERSION}.tar.gz /usr/local/
RUN mv /usr/local/hive-${HIVE_VERSION}-cdh${CDH_EXACT_VERSION} /usr/local/hive


# add postgresql jdbc jar to classpath
RUN ln -s /usr/share/java/postgresql-jdbc4.jar $HIVE_HOME/lib/postgresql-jdbc4.jar

# to configure postgres as hive metastore backend
RUN sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt/ `lsb_release -cs`-pgdg main" >> /etc/apt/sources.list.d/pgdg.list'
RUN wget -q https://www.postgresql.org/media/keys/ACCC4CF8.asc -O - | sudo apt-key add -
RUN apt-get update -y
RUN apt-get -yq install vim postgresql-9.5 libpostgresql-jdbc-java

USER postgres
# initialize hive metastore db
# create metastore db, hive user and assign privileges
RUN cd $HIVE_HOME/scripts/metastore/upgrade/postgres/ &&\
     /etc/init.d/postgresql start &&\
     psql --command "CREATE DATABASE metastore;" &&\
     psql --command "CREATE USER hive WITH PASSWORD 'hive';" && \
     psql --command "ALTER USER hive WITH SUPERUSER;" && \
     psql --command "GRANT ALL PRIVILEGES ON DATABASE metastore TO hive;" && \
     psql -U hive -d metastore -h localhost -f hive-schema-${HIVE_VERSION}.postgres.sql


# revert back to default user
USER root

# disable ssl in postgres.conf
ADD conf/postgresql.conf $POSTGRESQL_MAIN
RUN echo $POSTGRESQL_MAIN
RUN echo $POSTGRESQL_CONFIG_FILE
RUN chown postgres:postgres $POSTGRESQL_CONFIG_FILE
RUN sed -i -e 's/peer/md5/g' /etc/postgresql/$POSTGRES_VERSION/main/pg_hba.conf


# copy config, sql, data files to /opt/files
RUN mkdir /opt/files
RUN echo $HIVE_CONF
ADD templates/hive-site.xml.template /opt/files/
ADD conf/hive-log4j.properties /opt/files/
ADD templates/hive-site.xml.template $HIVE_CONF/hive-site.xml.template
ADD conf/hive-log4j.properties $HIVE_CONF/hive-log4j.properties

# set permissions for hive bootstrap file
ADD scripts/bootstrap.sh /etc/hive-bootstrap.sh
RUN chown root:root /etc/hive-bootstrap.sh
RUN chmod 700 /etc/hive-bootstrap.sh

EXPOSE 10000 10001 10002 10003 9083 50111 5432

# run bootstrap script
ENTRYPOINT ["/etc/hive-bootstrap.sh", "-d"]
