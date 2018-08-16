FROM cdh5-hive

# copy kerberized hadoop config files
ADD templates/core-site.xml.template $HADOOP_PREFIX/etc/hadoop/core-site.xml.template
ADD templates/hdfs-site.xml.template $HADOOP_PREFIX/etc/hadoop/hdfs-site.xml.template
ADD templates/yarn-site.xml.template $HADOOP_PREFIX/etc/hadoop/yarn-site.xml.template

# copy kerberized hive config file
RUN echo $HIVE_CONF
ADD templates/hive-site.xml.template /opt/files/
ADD templates/hive-site.xml.template $HIVE_CONF/hive-site.xml.template

# krb5.conf
ADD conf/krb5.conf /etc/

# install kinit, used in bootstrap script
RUN apt-get install -y krb5-user

# run bootstrap script which starts hadoop and hive servers
CMD ["/etc/hive-bootstrap.sh", "-d"]
