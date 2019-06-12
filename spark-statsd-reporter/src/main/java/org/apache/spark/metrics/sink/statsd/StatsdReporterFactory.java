package org.apache.spark.metrics.sink.statsd;

import com.codahale.metrics.MetricRegistry;

import io.dropwizard.metrics.BaseReporterFactory;

public class StatsdReporterFactory extends BaseReporterFactory {

    private String host = "127.0.0.1";
    private int port = 8125;
    private String reporterName = "spark-statsd-reporter";
    private MetricFormatter metricFormatter = null;

    public void setHost(String host) {
        this.host = host;
    }

    public void setPort(int port) {
        this.port = port;
    }

    public void setFormatter(MetricFormatter metricFormatter) {
        this.metricFormatter = metricFormatter;
    }

    public MetricAttributeFilter getAttributeFilter() {
        return (attribute) -> !getExcludesAttributes().contains(attribute)
                && getIncludesAttributes().contains(attribute);
    }

    @Override
    public StatsdReporter build(MetricRegistry registry) {
        return new StatsdReporter(registry, metricFormatter, reporterName, getRateUnit(), getDurationUnit(),
                getFilter(), getAttributeFilter(), host, port);
    }
}
