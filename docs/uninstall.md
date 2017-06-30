---
post_title: Uninstall
menu_order: 60
feature_maturity: stable
enterprise: 'no'
---

    dcos package uninstall --app-id=<app-id> spark

The Spark dispatcher persists state in ZooKeeper, so to fully
uninstall the Spark DC/OS package, you must go to
`http://<dcos-url>/exhibitor`, click on `Explorer`, and delete the
znode corresponding to your instance of Spark. By default this is
`spark_mesos_Dispatcher`.
