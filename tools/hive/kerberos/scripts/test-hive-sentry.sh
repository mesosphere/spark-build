#!/bin/bash
set -x

# Create a user "alice" since Sentry authorization relies on the Linux user and group information
useradd alice

# Grant permissions to user “alice”
echo "Grant permissions to user alice ..."
kdestroy
kinit -k -t /usr/local/hadoop/etc/hadoop/hdfs.keytab hive/${HOSTNAME}@LOCAL
cat <<EOF >grant_alice.sql
CREATE ROLE test_role;
GRANT ROLE test_role to GROUP alice;
GRANT ROLE test_role to GROUP root;
GRANT ALL on DATABASE default to ROLE test_role WITH GRANT OPTION;
EOF
beeline -u "jdbc:hive2://localhost:10000/default;principal=hive/${HOSTNAME}@LOCAL" -f grant_alice.sql

# Test Hive / Sentry
#echo "Create a table in Hive with Sentry as alice ..."
#kdestroy
#kinit -k -t /usr/local/hadoop/etc/hadoop/hdfs.keytab alice/${HOSTNAME}@LOCAL
#cat <<EOF >create_table.sql
#CREATE TABLE test1 (col1 INT);
#SHOW TABLES;
#EOF
#beeline -u "jdbc:hive2://localhost:10000/default;principal=alice/${HOSTNAME}@LOCAL" -f create_table.sql

# Log back in as hdfs
kdestroy
kinit -k -t /usr/local/hadoop/etc/hadoop/hdfs.keytab hdfs@LOCAL
