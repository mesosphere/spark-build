---
post_title: Upgrade
menu_order: 50
feature_maturity: stable
enterprise: 'yes'
---

1.  In the Marathon web interface, destroy the Spark instance to be
updated.
1.  Verify that you no longer see it in the DC/OS web interface.
1.  Reinstall Spark.

        $ dcos package install spark
