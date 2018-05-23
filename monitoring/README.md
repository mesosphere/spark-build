# Monitoring Spark DC/OS Service

To start collecting metrics and visualize them, you should initially install the [mesosphere/prometheus](https://github.com/mesosphere/prometheus)
service. This service installs Grafana, Prometheus and the Mesos exporter.

To push/fetch metrics to Prometheus, you need to previously install the `dcos-metrics`
Prometheus plugin on each agent for `DC/OS` version older than `1.11`. For `DC/OS`
version greater or equal than `v.1.11`, this plugin is already integrated into
`dcos-metrics`.

In this repository, we added few [dashboards](./dashboards) that will show some graphs for you:
- DC/OS: This dashboard only works in DC/OS v1.11.X where the dcos-metrics also exposes
task metrics.
- Mesos: This dashboard plots some metrics related to Mesos.
- Spark: This dashboard shows a bunch of graphs with related Spark metrics.
- GPU: This dashboard plots metrics pulled from nvidia-smi queries

To load this dashboards in Grafana, you need at least one public agent on your
cluster to access to the Grafana UI. Grafana is exposed in the url: `http://<public_agent_ip>:<grafana_port>`.
