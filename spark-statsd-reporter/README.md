Spark StatsD Reporter
---

# Overview
Spark StatsD Reporter provides a custom implementation of Spark sink which supports metric tagging, filtering, and 
name formatting. Provided `MetricFormatter` normalizes metric names to a consistent form by removing variable parts and 
placing them into tags.

# Motivation
Spark assigns metric **names** using `spark.app.id` and `spark.executor.id` as a part of them. Thus the number of metrics 
is continuously growing because those IDs are unique between executions whereas the metrics themselves report the same thing. 
It makes problematic the use of changing metric names in dashboards.

For example, `jvm_heap_used` reported by all Spark instances (components):
- `jvm_heap_used` (Dispatcher)
- `<spark.app.id>_driver_jvm_heap_used` (driver)
- `<spark.app.id>_<spark.executor.id>_jvm_heap_used` (executor)

# Tag enrichment
All the metrics reported by Driver or Executor instances are enriched with additional tags:

- `<prefix>_app_name` for Spark application name
- `<prefix>_instance` which is either `driver` or `executor`
- `<prefix>_instance_id` which is Mesos Framework ID for Driver and Mesos Task ID for Executor
- `<prefix>_namespace` contains the value of `spark.metrics.namespace` configuration property

# Metric name formatting
## Driver
### Default naming
Spark Driver metrics naming has the following format:
```
<spark.app.id>_driver_<source>_<metric>
```

If `spark.metrics.namespace` is provided, it replaces `spark.app.id`:
```
<spark.metrics.namespace>_driver_<source>_<metric>
```

`spark.app.id` is assigned to Mesos Framework ID and cannot be overwritten via configuration.

Examples:
```
<prefix>_a4d898f4_e1cf_4019_9950_c739bf9a3730_0003_driver_20190502210339_0002_driver_jvm_heap_used

# with --conf spark.metrics.namespace=namespace:
<prefix>_namespace_driver_jvm_heap_used
```

### Formatted metrics
Examples:
```
# without spark.metrics.namespace (namespace tag is set to 'default'):
before: <prefix>_a4d898f4_e1cf_4019_9950_c739bf9a3730_0003_driver_20190502210339_0002_driver_jvm_heap_used
after: <prefix>_driver_jvm_heap_used,<prefix>_namespace=default,<prefix>_app_name={value of spark.app.name},<prefix>_instance_type=driver,<prefix>_instance_id=a4d898f4_e1cf_4019_9950_c739bf9a3730_0003_driver_20190502210339_0002

# with --conf spark.metrics.namespace=namespace (namespace tag is set to the value of spark.metrics.namespace):
before: <prefix>_namespace_driver_jvm_heap_used
after: <prefix>_driver_jvm_heap_used,<prefix>_namespace=namespace,<prefix>_app_name={value of spark.app.name},<prefix>_instance_type=driver,<prefix>_instance_id=a4d898f4_e1cf_4019_9950_c739bf9a3730_0003_driver_20190502210339_0002
```

## Executor
### Default naming
Spark Executor metrics naming has the following format:
```
<spark.app.id>_<spark.executor.id>_<source>_<metric>
```

If `spark.metrics.namespace` is provided, it replaces `spark.app.id`:
```
<spark.metrics.namespace>_<spark.executor.id>_<source>_<metric>
```

`spark.app.id` is assigned to Mesos Framework ID and cannot be overwritten via configuration.

Examples:
```
<prefix>_a4d898f4_e1cf_4019_9950_c739bf9a3730_0003_driver_20190502210339_0002_aa6ee344_1314_46ea_b346_dcf6a5cfeceb_0_jvm_heap_used

# with --conf spark.metrics.namespace=namespace:
<prefix>_namespace_aa6ee344_1314_46ea_b346_dcf6a5cfeceb_0_jvm_heap_used
```

### Formatted metrics
Examples:
```
# without spark.metrics.namespace (namespace tag is set to 'default'):
before: <prefix>_a4d898f4_e1cf_4019_9950_c739bf9a3730_0003_driver_20190502210339_0002_aa6ee344_1314_46ea_b346_dcf6a5cfeceb_0_jvm_heap_used
after: <prefix>_executor_jvm_heap_used,<prefix>_namespace=default,<prefix>_app_name={value of spark.app.name},<prefix>_instance_type=executor,<prefix>_instance_id=aa6ee344_1314_46ea_b346_dcf6a5cfeceb_0

# with --conf spark.metrics.namespace=namespace (namespace tag is set to the value of spark.metrics.namespace):
before: <prefix>_namespace_aa6ee344_1314_46ea_b346_dcf6a5cfeceb_0_jvm_heap_used
after: <prefix>_executor_jvm_heap_used,<prefix>_namespace=namespace,<prefix>_app_name={value of spark.app.name},<prefix>_instance_type=executor,<prefix>_instance_id=aa6ee344_1314_46ea_b346_dcf6a5cfeceb_0
```
