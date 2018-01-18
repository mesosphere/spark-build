## Spark on DC/OS Walkthroughs

Herein we include some step-by-step examples and reference architectures for more complex Spark deployments on DC/OS.
Some of these features (security with file-based-secrets, for example) require DC/OS Enterprise edition. These features
will be called out explicitly. The purpose of these walkthroughs is to provide an example of how to use specific
functionality and demonstrate best-practices, they are not meant to be fully production-ready.

These examples require the following:
1.  A DC/OS Cluster with at least 5 private agents with >= 4 cores/agent. This requirement is for HDFS.
1.  Some tutorials may also require a user-accessible S3 bucket to serve various artifacts. 
