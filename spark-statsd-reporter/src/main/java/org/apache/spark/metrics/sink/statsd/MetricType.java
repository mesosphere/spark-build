package org.apache.spark.metrics.sink.statsd;

/**
 * @see <a href="https://github.com/etsy/statsd/blob/master/docs/metric_types.md">
 *        StatsD metric types</a>
 */
interface MetricType {
    String COUNTER = "c";
    String GAUGE = "g";
    String TIMER = "ms";
}
