---
post_title: Limitations
menu_order: 105
feature_maturity: stable
enterprise: 'yes'
---

*   DC/OS Spark only supports submitting jars and Python scripts. It
does not support R.

*   Spark jobs run in Docker containers. The first time you run a
Spark job on a node, it might take longer than you expect because of
the `docker pull`.

*   For interactive analytics, we
recommend Zeppelin, which supports visualizations and dynamic
dependency management.


TODO
get names consistent with current names
get other docs in here
add metadata in the right order
work on script