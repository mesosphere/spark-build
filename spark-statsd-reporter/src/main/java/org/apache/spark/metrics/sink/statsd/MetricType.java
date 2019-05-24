package org.apache.spark.metrics.sink.statsd;

/**
 * A subset of StatsD metric types used for Spark
 * @see <a href="https://github.com/etsy/statsd/blob/master/docs/metric_types.md">
 *        StatsD metric types</a>
 */
interface MetricType {
    String GAUGE = "g";
    String TIMER = "ms";
}
