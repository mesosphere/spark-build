package org.apache.spark.metrics.sink.statsd;

import com.codahale.metrics.MetricRegistry;
import com.google.common.base.Joiner;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

import static java.util.Arrays.asList;

class MetricFormatter {
    private final static Pattern whitespacePattern = Pattern.compile("[\\s]+");
    private final static String metricsFormat = "%s,%s:%s|%s";

    private final String prefix;
    private final InstanceDetailsProvider instanceDetailsProvider;
    private final String[] tags;

    public MetricFormatter(InstanceDetailsProvider instanceDetailsProvider, String prefix, String[] tags) {
        this.instanceDetailsProvider = instanceDetailsProvider;
        this.prefix = prefix;
        this.tags = tags;
    }

    public String buildMetricString(String name, String argument, Object value, String metricType) {
        String fullName = MetricRegistry.name(name, argument);
        return buildMetricString(fullName, value, metricType);
    }

    public String buildMetricString(String name, Object value, String metricType) {
        String tagString = buildTags();
        String prefixedName = MetricRegistry.name(prefix, name);
        String metricString =  String.format(metricsFormat, removeIds(prefixedName), tagString, formatValue(value), metricType);

        return sanitize(metricString);
    }

    private String formatValue(Object value) {
        if (value instanceof Float || value instanceof Double || value instanceof BigDecimal) {
            return String.format("%2.2f", value);
        } else if (value instanceof Number) {
            return String.valueOf(value);
        } else {
            return "";
        }
    }

    private String removeIds(String name) {
        //removing variable parts of a metric name (application and executor IDs)
        return instanceDetailsProvider.getInstanceDetails().map(instanceDetails -> {
            String formatted = name;

            //remove spark.app.id if present
            if (formatted.contains(instanceDetails.getApplicationId())) {
                formatted = formatted.replaceAll(instanceDetails.getApplicationId() + "\\.", "");
            }

            //remove spark.executor.id if present
            if (instanceDetails.getInstanceType() == InstanceType.EXECUTOR && formatted.contains(instanceDetails.getInstanceId())) {
                formatted = formatted.replaceAll(instanceDetails.getInstanceId(), "executor");
            }

            return formatted.replaceAll(instanceDetails.getNamespace() + "\\.", "");
        }).orElse(name);
    }

    private String buildTags() {
        //if instance details are available, enrich metric with tags
        return instanceDetailsProvider.getInstanceDetails().map(instanceDetails -> {
            List<String> extractedTags = new ArrayList<>(asList(
                    prefix + "_app_name=" + instanceDetails.getApplicationName(),
                    prefix + "_instance_id=" + instanceDetails.getInstanceId()
            ));

            if (instanceDetails.getApplicationOrigin() != null) {
                extractedTags.add(prefix + "_origin=" + instanceDetails.getApplicationOrigin());
            }

            String namespace = instanceDetails.getNamespace();

            if (namespace != null && !namespace.isEmpty()) {
                extractedTags.add(prefix + "_namespace=" + namespace);
            }

            extractedTags.addAll(asList(tags));
            return Joiner.on(",").join(extractedTags);
        }).orElse(Joiner.on(",").join(tags));
    }


    private String sanitize(String s) {
        return whitespacePattern.matcher(s).replaceAll("_").toLowerCase();
    }
}
