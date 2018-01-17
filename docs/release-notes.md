---
layout: layout.pug
navigationTitle: 
title: Release Notes
menuWeight: 140
excerpt:
featureMaturity:

---

## Version 2.1.0-2.2.0-1

### Improvements
- Changed image to run as user `nobody` instead of `root` by default. (https://github.com/mesosphere/spark-build/pull/189)

### Bug fixes
- Configuration to allow custom Dispatcher docker image. (https://github.com/mesosphere/spark-build/pull/179)
- CLI breaks with multiple spaces in submit args. (https://github.com/mesosphere/spark-build/pull/193)

### Documentation
- Updated HDFS endpoint in hdfs doc page.
- Added checkpointing instructions. (https://github.com/mesosphere/spark-build/pull/181)
- Updated custom docker image support policy. (https://github.com/mesosphere/spark-build/pull/200)

## Version 2.2.0-2.2.0-2-beta

### Improvements
* Added secrets support in Driver. (SPARK-22131)
* Added Kerberos ticket renewal. (SPARK-21842)
* Added Mesos sandbox URI to Dispatcher UI. (SPARK-13041)
* Updated JRE version to 8u152 JCE.
* Added support for Driver<->Executor TLS with file-based secrets.
* Added support for Driver<->Executor SASL (RPC endpoint authentication and encryption), via file-based secrets.
* Added CLI command to generate a random secret.
* Enabled native BLAS for MLLib.
* Added configuration to deploy Dispatcher on UCR (default is Docker).

### Bug fixes
* First delegation token renewal time is not 75% of renewal time. (SPARK-22583)
* Fixed `supervise` mode with checkpointing. (SPARK-22145)
* Added support for older `SPARK_MESOS_KRB5_CONF_BASE64` environment variable.

### Tests
* Added integration test that reads / writes to a Kerberized HDFS.
* Added integration test that reads / writes to a Kerberized Kafka.
* Added integration test of checkpointing and supervise.

### Documentation
* Updated naming of DC/OS.
* Updated docs links in package post-install notes.
* Updated Kerberos docs. 
* Documented running Spark Streaming jobs with Kerberized Kafka.
* Documented `nobody` limitation on certain OSes.


## Version 2.1.0-2.2.0-1

### Improvements
- Changed image to run as user `nobody` instead of `root` by default. (https://github.com/mesosphere/spark-build/pull/189)

### Bug fixes
- Configuration to allow custom Dispatcher docker image. (https://github.com/mesosphere/spark-build/pull/179)
- CLI breaks with multiple spaces in submit args. (https://github.com/mesosphere/spark-build/pull/193)

### Documentation
- Updated HDFS endpoint in hdfs doc page.
- Added checkpointing instructions. (https://github.com/mesosphere/spark-build/pull/181)
- Updated custom docker image support policy. (https://github.com/mesosphere/spark-build/pull/200)

## Version 2.0.1-2.2.0-1

### Improvements
- Exposed isR and isPython spark run args

### Bug fixes
- Allowed for application args to have arguments without equals sign
- Fixed docs link in Universe package description

## Version 2.0.0-2.2.0-1

### Improvements
- Kerberos support changed to use common code from `spark-core` instead of custom implementation.
- Added file and environment-based secret support.
- Kerberos key tab/TGT login from the DC/OS Spark CLI in cluster mode (uses file-based secrets).
- Added CNI network label support.
- CLI doesn't require spark-submit to be present on client machine.

### Bug fixes
- Drivers are successfully re-launched when `--supervise` flag is set.
- CLI works on 1.9 and 1.10 DC/OS clusters.

### Breaking changes
- Setting `spark.app_id` has been removed (e.g. `dcos config set spark.app_id <dispatcher_app_id>`). To submit jobs with a given
dispatcher use `dcos spark --name <dispatcher_app_id>`.
- `principal` is now `service_account` and `secret` is now `service_account_secret`.

## Version 1.1.1-2.2.0

### Improvements
* Upgrade to Spark 2.2.0
* Spark driver now supports configurable failover_timeout. The default value is 0 when the configuration is not set.
[SPARK-21456](https://issues.apache.org/jira/browse/SPARK-21456). 

### Breaking change

*  Spark CLI no longer supports -Dspark args.

## Version 1.0.9-2.1.0-1 

- The history server has been removed from the "spark" package, and put into a dedicated "spark-history" package.
