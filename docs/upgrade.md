---
post_title: Upgrade
menu_order: 50
feature_maturity: stable
enterprise: 'no'
---

1.  In the **Services** section of the DC/OS web UI, destroy the Spark instance to be
updated.
1.  Verify that you no longer see it in the DC/OS web UI.
1.  Reinstall Spark.

        $ dcos package install spark
