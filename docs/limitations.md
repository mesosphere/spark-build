---
post_title: Limitations
menu_order: 130
feature_maturity: stable
enterprise: 'no'
---

*   DC/OS Spark only supports submitting jars and Python scripts. It
does not support R.

*   Mesosphere does not provide support for Spark app development.

*   Spark jobs run in Docker containers. The first time you run a
Spark job on a node, it might take longer than you expect because of
the `docker pull`.

*   DC/OS Spark only supports running the Spark shell from within a
DC/OS cluster. See [the Spark Shell section](spark-shell.md) for more information. 
For interactive analytics, we
recommend Zeppelin, which supports visualizations and dynamic
dependency management.
