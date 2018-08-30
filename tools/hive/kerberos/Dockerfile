FROM cdh5-hive

ENV SENTRY_VERSION 1.5.1
ENV SENTRY_HOME /usr/local/sentry

# download sentry
RUN curl -L http://archive.cloudera.com/cdh${CDH_VERSION}/cdh/${CDH_VERSION}/sentry-${SENTRY_VERSION}-cdh${CDH_EXACT_VERSION}.tar.gz \
    | tar -xzC /usr/local && \
    cd /usr/local && \
    ln -s apache-sentry-${SENTRY_VERSION}-cdh${CDH_EXACT_VERSION}-bin/ sentry

# copy kerberized hadoop config files
ADD templates/core-site.xml.template $HADOOP_PREFIX/etc/hadoop/core-site.xml.template
ADD templates/hdfs-site.xml.template $HADOOP_PREFIX/etc/hadoop/hdfs-site.xml.template
ADD templates/yarn-site.xml.template $HADOOP_PREFIX/etc/hadoop/yarn-site.xml.template

# copy kerberized hive config file
ADD templates/hive-site.xml.template /opt/files/
ADD templates/hive-site.xml.template $HIVE_CONF/hive-site.xml.template

# sentry config files
ADD templates/sentry-site.xml.hive-client.template /usr/local/hive/conf/sentry-site.xml.template
ADD templates/sentry-site.xml.server.template /usr/local/sentry/conf/sentry-site.xml.template

# hive / sentry test script
ADD scripts/grant-hive-privileges.sh /etc/grant-hive-privileges.sh
RUN chmod 700 /etc/grant-hive-privileges.sh

# krb5.conf
ADD conf/krb5.conf /etc/

# install kinit, used in bootstrap script
RUN apt-get update && \
    apt-get install -y krb5-user && \
    rm -rf /var/lib/apt/lists/*

# run bootstrap script which starts hadoop and hive servers
CMD ["/etc/hive-bootstrap.sh", "-d"]
