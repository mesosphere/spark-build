---
post_title: Limitations
menu_order: 130
feature_maturity: stable
enterprise: 'yes'
---

*   DC/OS Spark only supports submitting jars and Python scripts. It
does not support R.

*   Mesosphere does not provide support for Spark app development.

*   Spark jobs run in Docker containers. The first time you run a
Spark job on a node, it might take longer than you expect because of
the `docker pull`.

*   DC/OS Spark only supports running the Spark Shell from within the
DC/OS cluster. For interactive analytics, we
recommend Zeppelin, which supports visualizations and dynamic
dependency management.