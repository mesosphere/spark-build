FROM cdh5-hive

# copy kerberized hadoop config files
ADD templates/core-site.xml.template $HADOOP_PREFIX/etc/hadoop/core-site.xml.template
ADD templates/hdfs-site.xml.template $HADOOP_PREFIX/etc/hadoop/hdfs-site.xml.template
ADD templates/yarn-site.xml.template $HADOOP_PREFIX/etc/hadoop/yarn-site.xml.template

# copy kerberized hive config file
ADD templates/hive-site.xml.template /opt/files/
ADD templates/hive-site.xml.template $HIVE_CONF/hive-site.xml.template

# kerberized sentry config files
ADD templates/sentry-site.xml.hive-client.template /usr/local/hive/conf/sentry-site.xml.template
ADD templates/sentry-site.xml.server.template /usr/local/sentry/conf/sentry-site.xml.template

# hive / sentry test script
ADD scripts/test-hive-sentry.sh /etc/test-hive-sentry.sh
RUN chmod 700 /etc/test-hive-sentry.sh

# krb5.conf
ADD conf/krb5.conf /etc/

# install kinit, used in bootstrap script
RUN apt-get update && \
    apt-get install -y krb5-user && \
    rm -rf /var/lib/apt/lists/*

# run bootstrap script which starts hadoop and hive servers
CMD ["/etc/hive-bootstrap.sh", "-d"]
