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

## Backing up dashboards

A tool like [`grafcli`](https://github.com/m110/grafcli) can be used to backup the dashboards on a Grafana server.

### Install `grafcli` using pip:
```bash
pip3 install grafcli
```

### Create a config file for `grafcli` with contents similar to:
```ini
[grafcli]
# Your favorite editor - this name will act as a command!
editor = vim
# Executable used as merge tool. Paths will be passed as arguments.
mergetool = vimdiff
# Commands history file. Leave empty to disable.
history = ~/.grafcli_history
# Additional verbosity, if needed.
verbose = on
# Answer 'yes' to all overwrite prompts.
force = on

[resources]
# Directory where all local data will be stored (including backups).
data-dir = ~/.grafcli

# List of remote Grafana hosts.
# The key names do not matter, as long as matching section exists.
# Set the value to off to disable the host.
[hosts]
dashboards = on

[dashboards]
type = api
url = http://<public_agent_ip>:<grafana_port>/api
ssl = off
# HTTP user and password, if any.
user = username
password = mysuperpassword
```
(Note that we have chosen to use `dashboards` as the remote id)

### Get the current list of dashboards
```bash
grafcli ls remote/dashboards
```

### To backup a specific dashboard run:
```bash
grafcli backup remote/dashboards/{{dashboard_name}} backup.tar.gz
```

### To backup all dashboards:
```bash
grafcli backup remote/dashboards full-backup.tar.gz
```
(Note that the current verison of `grafcli` has an issue that causes the backup to crash if no rows are defined in the dashboard)
