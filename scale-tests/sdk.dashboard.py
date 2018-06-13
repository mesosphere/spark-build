
from grafanalib.core import Dashboard
from grafanalib.core import Target
from grafanalib.core import Table
from grafanalib.core import Row

from grafanalib.core import *


class Resource:

    def __init__(self, title, metric, units="none"):
        self._title = title
        self._metric = metric
        self._framework_name = "$framework"
        self._units=units

    def _get_expression(self) -> str:
        return "sum({}{{framework_name=\"{}\"}})".format(self._metric, self._framework_name)

    def to_single_stat(self):
        return SingleStat(
            title=self._title,
            dataSource="${DS_PROMETHEUS}",
            format=self._units,
            targets=[
                Target(
                    expr=self._get_expression()
                )
            ]
        )


def resource_row() -> Row:
    return Row(panels=[
        Resource("Used memory", "mem_total", "decbytes").to_single_stat(),
        Resource("Available memory", "mem_limit", "decbytes").to_single_stat(),
        Resource("CPU", "cpus_limit").to_single_stat(),
        Resource("Disk used (placeholder)", "disk_used", "decbytes").to_single_stat(),
        Resource("Disk available (placeholder", "disk_limit", "decbytes").to_single_stat(),
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
    ],
    templating=Templating(
        list=[
                {
                    "current": {},
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
