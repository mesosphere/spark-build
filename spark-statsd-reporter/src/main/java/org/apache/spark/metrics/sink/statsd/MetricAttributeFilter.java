package org.apache.spark.metrics.sink.statsd;

import com.codahale.metrics.MetricAttribute;

public interface MetricAttributeFilter {

    boolean matches(MetricAttribute attribute);
}
