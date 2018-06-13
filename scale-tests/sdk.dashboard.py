
from grafanalib.core import Dashboard
from grafanalib.core import Target
from grafanalib.core import Table
from grafanalib.core import Row

from grafanalib.core import *


class Resource:
    def __init__(self, title, metric, units="none", pod_type=None):
        self._title = title
        self._metric = metric
        self._framework_name = "$framework"
        self._pod_type = pod_type
        self._units=units

    def _get_expression(self) -> str:
        selections = {}
        selections["framework_name"] = "\"{}\"".format(self._framework_name)

        if self._pod_type:
            selections["executor_name"] = "\"{}\"".format(self._pod_type)

        selection_string = ",".join("{}={}".format(k, v) for k, v in selections.items())
        group_string = ",".join(k for k in selections.keys())

        return "sum({}{{{}}}) by ({})".format(self._metric, selection_string, group_string)

    def to_single_stat(self):
        return SingleStat(
            title=self._title,
            dataSource="${DS_PROMETHEUS}",
            format=self._units,
            span=1,
            targets=[
                Target(
                    expr=self._get_expression()
                )
            ]
        )

def resource_row(pod_type: str=None) -> Row:
    return Row(
        title="Resources for $pod_type",
        repeat="pod_type" if pod_type else "",
        panels=[
            Resource("Used memory", "mem_total", "decbytes", pod_type=pod_type).to_single_stat(),
            Resource("Available memory", "mem_limit", "decbytes", pod_type=pod_type).to_single_stat(),
            Resource("CPU", "cpus_limit", pod_type=pod_type).to_single_stat(),
            Resource("Disk used (placeholder)", "disk_used", "decbytes", pod_type=pod_type).to_single_stat(),
            Resource("Disk available (placeholder)", "disk_limit", "decbytes", pod_type=pod_type).to_single_stat(),
    ])



dashboard = Dashboard(
    title="Generated SDK dashboard",
    rows=[
        Row(panels=[
            Table(
                title="number of pods per pod type",
                dataSource="${DS_PROMETHEUS}",
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
        ]),
        resource_row(),
        resource_row("[[pod_type]]"),
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
