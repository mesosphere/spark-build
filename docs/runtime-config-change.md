---
post_title: Runtime Configuration Change
menu_order: 70
feature_maturity: stable
enterprise: 'no'
---

You can customize DC/OS Spark in-place when it is up and running.

1.  View your Marathon dashboard at `http://<dcos-url>/marathon`

1.  In the list of `Applications`, click the name of the Spark
framework to be updated.

1.  Within the Spark instance details view, click the `Configuration`
tab, then click the `Edit` button.

1.  In the dialog that appears, expand the `Environment Variables`
section and update any field(s) to their desired value(s).

1.  Click `Change and deploy configuration` to apply any changes and
cleanly reload Spark.
