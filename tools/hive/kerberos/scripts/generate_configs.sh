#!/bin/bash

# Generate kerberos versions of Hadoop config files by taking the unkerberized versions
# and tacking on the associated kerberos properties.
# Assumption is that these two sets of properties do not overlap.

cd "$( dirname "${BASH_SOURCE[0]}" )"
for FILE_BASE in core-site hdfs-site hive-site yarn-site; do
    COMBINED_FILE="../templates/${FILE_BASE}.xml.template"
    echo "Generating config file: kerberos/templates/${FILE_BASE}.xml.template"
    echo '<configuration>' > $COMBINED_FILE
    grep -vh '</\?configuration>' "../../hadoop-hive/templates/${FILE_BASE}.xml.template" >> $COMBINED_FILE
    echo "" >> $COMBINED_FILE
    grep -vh '</\?configuration>' ../templates/${FILE_BASE}-kerberos.xml.template >> $COMBINED_FILE
    echo '</configuration>' >> $COMBINED_FILE
done
