"""
Generate a generic SDK dashboard.

```bash
pip install grafanalib

generate-dashboard -o sdk.generated.json sdk.dashboard.py
```

This creates an `sdk.json` file that contains the Grafana dashboard definition for monitoring SDK-based frameworks
installed on a Cluster.

*Note*: From https://github.com/weaveworks/grafanalib#generating-dashboards
> If you save the above as frontend.dashboard.py (the suffix must be .dashboard.py), you can then generate the JSON dashboard with:

And thus the Python dashboard definition MUST end in `.dashboard.py`.
"""

import typing

import grafanalib.core as G
import grafanalib.weave as W


REFRESH_ON_TIMERANGE_CHANGE = 2

FRAMEWORK_VARIABLE = "$framework"
POD_TYPE_VARIABLE = "$pod_type"
DCOS_SERVICE_NAME_SELECTION = {"dcos_service_name": FRAMEWORK_VARIABLE}

PROMETHEUS_DATA_SOURCE = "${DS_PROMETHEUS}"


def reduction(op: str, metric_definition: str, by: typing.Dict[str, str]) -> str:
    """
    Construct a reduction string for a metric.
    """
    if not op:
        return metric_definition

    reduced = "{}({})".format(op, metric_definition)

    if not by:
        return reduced

    by_string = ",".join(k.strip() for k in sorted(by.keys()))
    return "{} by ({})".format(reduced, by_string)


def metric(name: str, selection: typing.Dict[str, str]) -> str:
    """
    Construct a metric with a selection string.
    """
    if not selection:
        return name

    selection_string = ",".join(
        '{}="{}"'.format(k.strip(), v.strip()) for k, v in sorted(selection.items())
    )

    return "%s{%s}" % (name, selection_string)


def sum(metric: str) -> str:
    """
    Construct the metric query to calculate the sum for a framework.
    """
    return reduction("sum", metric, DCOS_SERVICE_NAME_SELECTION)


def aggregate(op: str, metric: str, duration: str) -> str:
    """
    Construct the metric query to perform an aggregation.
    """
    return "{}({}[{}])".format(op, metric, duration)


def service_metric(
    metric_name: str, aggregation: str = None, duration: str = None
) -> str:
    """
    Construct the metric query for the specified DC/OS service.
    """
    metric_string = metric(metric_name, DCOS_SERVICE_NAME_SELECTION)
    if aggregation:
        metric_string = aggregate(aggregation, metric_string, duration)

    return metric_string


class ResourceStat:
    """
    Encapsulate a single-stat resource panel for a framework / pod.
    """

    def __init__(self, title, metric, units="none", pod_type=None):
        self._title = title
        self._metric = metric
        self._framework_name = FRAMEWORK_VARIABLE
        self._pod_type = pod_type
        self._units = units

    def _get_expression(self, op: str) -> str:
        """
        Generate the metric expression for the stat.
        """
        selection = {}
        selection["framework_name"] = self._framework_name
        if self._pod_type:
            selection["executor_name"] = self._pod_type

        return reduction(op, metric(self._metric, selection), selection)

    def to_single_stat(self, op: str = "sum") -> G.SingleStat:
        return G.SingleStat(
            title=self._title,
            dataSource="${DS_PROMETHEUS}",
            format=self._units,
            decimals=2,
            span=1,
            height=1,
            targets=[G.Target(expr=self._get_expression(op))],
        )


def resource_row(pod_type: str = None) -> G.Row:
    """
    Construct a Grafana row with resource statistics.
    """
    if pod_type:
        title = "Resources for pods of type {}".format(POD_TYPE_VARIABLE)
    else:
        title = "Resources for all pod types"

    return G.Row(
        title=title,
        repeat=POD_TYPE_VARIABLE.lstrip("$") if pod_type else "",
        panels=[
            ResourceStat("Pod count", "cpus_limit", pod_type=pod_type).to_single_stat(
                "count"
            ),
            ResourceStat(
                "Used memory", "mem_total", "decbytes", pod_type=pod_type
            ).to_single_stat(),
            ResourceStat(
                "Available memory", "mem_limit", "decbytes", pod_type=pod_type
            ).to_single_stat(),
            ResourceStat("CPU", "cpus_limit", pod_type=pod_type).to_single_stat(),
            ResourceStat(
                "Disk used (placeholder)", "disk_used", "decbytes", pod_type=pod_type
            ).to_single_stat(),
            ResourceStat(
                "Disk available (placeholder)",
                "disk_limit",
                "decbytes",
                pod_type=pod_type,
            ).to_single_stat(),
        ],
    )


def scheduler_row() -> G.Row:
    """
    Construct a Grafana row containing scheduler offer statistics
    """
    offer_metrics = [
        "offers_processed",
        "offers_received",
        "declines_long",
        "revives",
        "revives_throttles",
        "declines_short",
    ]

    resolution = "1m"

    offer_timers = [
        "offers_process_p50",
        "offers_process_p90",
        "offers_process_p99",
        "offers_process_max",
    ]

    return G.Row(
        title="Scheduler statistics",
        panels=[
            W.prometheus.PromGraph(
                data_source=PROMETHEUS_DATA_SOURCE,
                title="cumulative offer statistic",
                expressions=[
                    {"expr": sum(service_metric(m)), "legendFormat": m}
                    for m in offer_metrics
                ],
                span=2,
                steppedLine=True,
                yAxes=G.YAxes(left=G.YAxis(format="short", decimals=0)),
            ),
            W.prometheus.PromGraph(
                data_source=PROMETHEUS_DATA_SOURCE,
                title="offer events per second [{} rate]".format(resolution),
                expressions=[
                    {
                        "expr": sum(service_metric(m, "rate", resolution)),
                        "legendFormat": m,
                    }
                    for m in offer_metrics
                ],
                span=2,
                steppedLine=True,
            ),
            W.prometheus.PromGraph(
                data_source=PROMETHEUS_DATA_SOURCE,
                title="offer processing time",
                expressions=[
                    {"expr": sum(service_metric(m)), "legendFormat": m}
                    for m in offer_timers
                ],
                span=2,
                yAxes=G.YAxes(left=G.YAxis(format="ns")),
            ),
        ],
    )


def task_row() -> G.Row:
    """
    Construct a Grafana row containing scheduler task statistics
    """
    task_metrics = [
        "task_status_task_running",
        "task_status_task_finished",
        "task_status_task_lost",
        "task_status_task_failed",
    ]

    resolution = "1m"

    return G.Row(
        title="Task statistics",
        panels=[
            W.prometheus.PromGraph(
                data_source=PROMETHEUS_DATA_SOURCE,
                title="cumulative task statistic",
                expressions=[
                    {"expr": sum(service_metric(m)), "legendFormat": m}
                    for m in task_metrics
                ],
                span=2,
                steppedLine=True,
                yAxes=G.YAxes(left=G.YAxis(format="short", decimals=0)),
            ),
            W.prometheus.PromGraph(
                data_source=PROMETHEUS_DATA_SOURCE,
                title="task events per second [{} rate]".format(resolution),
                expressions=[
                    {
                        "expr": sum(service_metric(m, "rate", resolution)),
                        "legendFormat": m,
                    }
                    for m in task_metrics
                ],
                span=2,
                steppedLine=True,
            ),
        ],
    )


dashboard = G.Dashboard(
    title="Generated SDK dashboard",
    rows=[resource_row(), resource_row(POD_TYPE_VARIABLE), scheduler_row(), task_row()],
    templating=G.Templating(
        list=[
            {
                "datasource": PROMETHEUS_DATA_SOURCE,
                "hide": 0,
                "name": FRAMEWORK_VARIABLE.lstrip("$"),
                "options": [],
                "query": "label_values(offers_received, dcos_service_name)",
                "refresh": REFRESH_ON_TIMERANGE_CHANGE,
                "regex": "",
                "sort": 0,
                "tagValuesQuery": "",
                "tags": [],
                "tagsQuery": "",
                "type": "query",
            },
            {
                "allValue": "*",
                "current": {},
                "datasource": PROMETHEUS_DATA_SOURCE,
                "hide": 2,
                "includeAll": True,
                "label": None,
                "multi": False,
                "name": POD_TYPE_VARIABLE.lstrip("$"),
                "options": [],
                "query": 'label_values(cpus_limit{framework_name="%s"}, executor_name)'
                % (FRAMEWORK_VARIABLE),
                "refresh": REFRESH_ON_TIMERANGE_CHANGE,
                "regex": "",
                "sort": 0,
                "tagValuesQuery": "",
                "tags": [],
                "tagsQuery": "",
                "type": "query",
                "useTags": False,
            },
        ]
    ),
    inputs=[
        {
            "name": "DS_PROMETHEUS",
            "label": "prometheus",
            "description": "",
            "type": "datasource",
            "pluginId": "prometheus",
            "pluginName": "Prometheus",
        }
    ],
).auto_panel_ids()
