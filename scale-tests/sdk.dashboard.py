
from grafanalib.core import Dashboard
from grafanalib.core import Target
from grafanalib.core import Table
from grafanalib.core import Row

from grafanalib.core import *


def pod_count_summary_table() -> Table:
    return Table(
        title="number of pods per pod type",
        dataSource="${DS_PROMETHEUS}",
        span=2,
        targets=[
            Target(
                expr="count(cpus_limit{framework_name=\"$framework\"}) by (executor_name)",
                instant=True,
                legendFormat="{{ executor_name }}",
            )
        ],
        transform=TABLE_TRANSFORM,
        styles=[
            ColumnStyle(
                pattern="Time",
                type=HiddenColumnStyleType()
            ),
            ColumnStyle(
                alias="pod type",
                pattern="Metric",
                type=StringColumnStyleType(True, True)
            ),
            ColumnStyle(
                alias="count",
                pattern="Value",
                type=NumberColumnStyleType(
                    decimals=0,
                )
            )


        ]
    )


def metric(name: str, selection: str) -> str:
    return "{}{{{}}}".format(name, selection)


class Resource:
    def __init__(self, title, metric, units="none", pod_type=None):
        self._title = title
        self._metric = metric
        self._framework_name = "$framework"
        self._pod_type = pod_type
        self._units=units

    def _get_expression(self, op: str) -> str:
        selections = {}
        selections["framework_name"] = "\"{}\"".format(self._framework_name)

        if self._pod_type:
            selections["executor_name"] = "\"{}\"".format(self._pod_type)

        selection_string = ",".join("{}={}".format(k, v) for k, v in selections.items())
        group_string = ",".join(k for k in selections.keys())

        return "{}({}) by ({})".format(op, metric(self._metric, selection_string), group_string)

    def to_single_stat(self, op: str="sum") -> SingleStat:
        return SingleStat(
            title=self._title,
            dataSource="${DS_PROMETHEUS}",
            format=self._units,
            decimals=2,
            span=1,
            targets=[
                Target(
                    expr=self._get_expression(op)
                )
            ]
        )

def resource_row(pod_type: str=None) -> Row:
    if pod_type:
        title = "Resources for pods of type $pod_type"
    else:
        title = "Resources for all pod types"

    return Row(
        title=title,
        repeat="pod_type" if pod_type else "",
        panels=[
            Resource("Pod count", "cpus_limit", pod_type=pod_type).to_single_stat("count"),
            Resource("Used memory", "mem_total", "decbytes", pod_type=pod_type).to_single_stat(),
            Resource("Available memory", "mem_limit", "decbytes", pod_type=pod_type).to_single_stat(),
            Resource("CPU", "cpus_limit", pod_type=pod_type).to_single_stat(),
            Resource("Disk used (placeholder)", "disk_used", "decbytes", pod_type=pod_type).to_single_stat(),
            Resource("Disk available (placeholder)", "disk_limit", "decbytes", pod_type=pod_type).to_single_stat(),
    ])


def sum(metric: str) -> str:
    return "sum({}) by (dcos_service_name)".format(metric)


def aggregate(aggregation: str, metric: str, duration: str) -> str:
    return "{}({}[{}])".format(aggregation, metric, duration)


def service_metric(metric_name: str, aggregation: str=None, duration: str=None) -> str:
    metric = "{}{{dcos_service_name=\"$framework\"}}".format(metric_name)

    if aggregation:
        metric = aggregate(aggregation, metric, duration)

    return metric


def scheduler_row() -> Row:
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

    return Row(
        title="Scheduler statistics",
        panels=[
            Graph(
                title="cumulative offer statistics",
                dataSource="${DS_PROMETHEUS}",
                span=2,
                targets=[Target(expr=sum(service_metric(m)), legendFormat=m) for m in offer_metrics],
                steppedLine=True,
                yAxes=YAxes(left=YAxis(format="short", decimals=0))
            ),
            Graph(
                title="offer events per second [{} rate]".format(resolution),
                dataSource="${DS_PROMETHEUS}",
                span=2,
                targets=[Target(expr=sum(service_metric(m, "rate", resolution)), legendFormat=m) for m in offer_metrics],
                steppedLine=True,
            ),
            Graph(
                title="offer processing time",
                dataSource="${DS_PROMETHEUS}",
                span=2,
                targets=[Target(expr=service_metric(m), legendFormat=m) for m in offer_timers],
                yAxes=YAxes(left=YAxis(format="ns"))
            )
        ]
    )


def task_row() -> Row:
    task_metrics = [
        "task_status_task_running",
        "task_status_task_finished",
        "task_status_task_lost",
        "task_status_task_failed",
    ]

    resolution = "1m"

    return Row(
        title="Task statistics",
        panels=[
            Graph(
                title="cumulative task statistics",
                dataSource="${DS_PROMETHEUS}",
                span=2,
                targets=[Target(expr=sum(service_metric(m)), legendFormat=m) for m in task_metrics],
                steppedLine=True,
                yAxes=YAxes(left=YAxis(format="short", decimals=0))
            ),
            Graph(
                title="task events per second [{} rate]".format(resolution),
                dataSource="${DS_PROMETHEUS}",
                span=2,
                targets=[Target(expr=sum(service_metric(m, "rate", resolution)), legendFormat=m) for m in task_metrics],
                steppedLine=True,
                yAxes=YAxes(left=YAxis(format="short", decimals=0))
            ),
        ]
    )


dashboard = Dashboard(
    title="Generated SDK dashboard",
    rows=[
        resource_row(),
        resource_row("[[pod_type]]"),
        scheduler_row(),
        task_row(),
    ],
    templating=Templating(
        list=[
                {
                    "datasource": "${DS_PROMETHEUS}",
                    "hide": 0,
                    "name": "framework",
                    "options": [],
                    "query": "label_values(offers_received, dcos_service_name)\t",
                    "refresh": 1,
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
                    "datasource": "${DS_PROMETHEUS}",
                    "hide": 2,
                    "includeAll": True,
                    "label": None,
                    "multi": False,
                    "name": "pod_type",
                    "options": [],
                    "query": "label_values(cpus_limit{framework_name=\"$framework\"}, executor_name)",
                    "refresh": 1,
                    "regex": "",
                    "sort": 0,
                    "tagValuesQuery": "",
                    "tags": [],
                    "tagsQuery": "",
                    "type": "query",
                    "useTags": False
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
            "pluginName": "Prometheus"
        }
    ]
).auto_panel_ids()
