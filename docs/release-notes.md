---
layout: layout.pug
navigationTitle: 
title: Release Notes
menuWeight: 140
excerpt:
featureMaturity:

---

## Version 2.1.0-2.2.1-1

### Improvements
- Upgraded Spark to 2.2.1.

## Spark-History 2.1.0-2.2.0-1

### Improvements
- Upgraded docker image to 2.1.0-2.2.0-1-hadoop-2.6.
- Wrapped the config properties in a "service" object. (See "Breaking Changes")

### Bug Fixes
- Fixed field names in marathon.json. Installing from the DC/OS UI now works.

### Breaking Changes
- The configuration properties have been wrapped in a new "service" object.
If installing from the CLI, please update your `options.json` file accordingly.
See the Spark history server docs for an example.

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

## Version 1.0.9-2.1.0-1 

- The history server has been removed from the "spark" package, and put into a dedicated "spark-history" package.
