---
post_title: Release Notes
menu_order: 140
post_excerpt: ""
feature_maturity: ""
enterprise: 'no'
---

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

## Version 2.0.1-2.2.0-1

### Improvements
- Exposed isR and isPython spark run args

### Bug fixes
- Allowed for application args to have arguments without equals sign
- Fixed docs link in Universe package description
