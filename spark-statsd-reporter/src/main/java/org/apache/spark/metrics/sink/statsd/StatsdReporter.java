package org.apache.spark.metrics.sink.statsd;


import com.codahale.metrics.*;
import com.google.common.annotations.VisibleForTesting;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetSocketAddress;
import java.util.SortedMap;
import java.util.concurrent.TimeUnit;

import static java.nio.charset.StandardCharsets.UTF_8;
import static org.apache.spark.metrics.sink.statsd.MetricType.*;

public class StatsdReporter extends ScheduledReporter {
    private final static Logger logger = LoggerFactory.getLogger(StatsdReporter.class);
    private final InetSocketAddress address;
    private final MetricFormatter metricFormatter;

    private StatsdReporter(MetricRegistry registry, MetricFormatter metricFormatter, String reporterName, TimeUnit rateUnit, TimeUnit durationUnit, MetricFilter filter, String host, int port) {
        super(registry, reporterName, filter, rateUnit, durationUnit);
        this.address = new InetSocketAddress(host, port);
        this.metricFormatter = metricFormatter;
    }

    static Builder forRegistry(MetricRegistry registry) {
        return new Builder(registry);
    }

    public static class Builder {
        private final MetricRegistry registry;
        private MetricFormatter metricFormatter;
        private String reporterName = "spark-statsd-reporter";
        private TimeUnit rateUnit = TimeUnit.SECONDS;
        private TimeUnit durationUnit = TimeUnit.MILLISECONDS;
        private MetricFilter filter = MetricFilter.ALL;
        private String host = "127.0.0.1";
        private int port = 8125;


        private Builder(MetricRegistry registry) {
            this.registry = registry;
        }

        Builder formatter(MetricFormatter metricFormatter) {
            this.metricFormatter = metricFormatter;
            return this;
        }

        Builder convertRatesTo(TimeUnit rateUnit) {
            this.rateUnit = rateUnit;
            return this;
        }

        Builder convertDurationsTo(TimeUnit durationUnit) {
            this.durationUnit = durationUnit;
            return this;
        }

        public Builder filter(MetricFilter filter) {
            this.filter = filter;
            return this;
        }

        Builder host(String host) {
            this.host = host;
            return this;
        }

        Builder port(int port) {
            this.port = port;
            return this;
        }

        StatsdReporter build() {
            return new StatsdReporter(registry, metricFormatter, reporterName, rateUnit, durationUnit, filter, host, port);
        }
    }

    @Override
    public void report(SortedMap<String, Gauge> gauges, SortedMap<String, Counter> counters, SortedMap<String, Histogram> histograms, SortedMap<String, Meter> meters, SortedMap<String, Timer> timers) {
        try (DatagramSocket socket = new DatagramSocket()) {
            try {
                reportGauges(gauges, socket);
                reportCounters(counters, socket);
                reportHistograms(histograms, socket);
                reportMeters(meters, socket);
                reportTimers(timers, socket);
            } catch (StatsdReporterException e) {
                logger.warn("Unable to send packets to StatsD", e);
            }
        } catch (IOException e) {
            logger.warn("StatsD datagram socket construction failed", e);
        }
    }

    @VisibleForTesting
    void reportGauges(SortedMap<String, Gauge> gauges, DatagramSocket socket) {
        gauges.forEach((name, value) ->
                send(socket, metricFormatter.buildMetricString(name, value.getValue(), GAUGE))
        );
    }

    @VisibleForTesting
    void reportCounters(SortedMap<String, Counter> counters, DatagramSocket socket) {
        counters.forEach((name, value) ->
                send(socket, metricFormatter.buildMetricString(name, value.getCount(), COUNTER))
        );
    }

    @VisibleForTesting
    void reportHistograms(SortedMap<String, Histogram> histograms, DatagramSocket socket) {
        histograms.forEach((name, histogram) -> {
            Snapshot snapshot = histogram.getSnapshot();
            send(socket,

                    metricFormatter.buildMetricString(name, "count", histogram.getCount(), GAUGE),
                    metricFormatter.buildMetricString(name, "max", snapshot.getMax(), TIMER),
                    metricFormatter.buildMetricString(name, "mean", snapshot.getMean(), TIMER),
                    metricFormatter.buildMetricString(name, "min", snapshot.getMin(), TIMER),
                    metricFormatter.buildMetricString(name, "stddev", snapshot.getStdDev(), TIMER),
                    metricFormatter.buildMetricString(name, "p50", snapshot.getMedian(), TIMER),
                    metricFormatter.buildMetricString(name, "p75", snapshot.get75thPercentile(), TIMER),
                    metricFormatter.buildMetricString(name, "p95", snapshot.get95thPercentile(), TIMER),
                    metricFormatter.buildMetricString(name, "p98", snapshot.get98thPercentile(), TIMER),
                    metricFormatter.buildMetricString(name, "p99", snapshot.get99thPercentile(), TIMER),
                    metricFormatter.buildMetricString(name, "p999", snapshot.get999thPercentile(), TIMER)
            );
        });
    }

    @VisibleForTesting
    void reportMeters(SortedMap<String, Meter> meters, DatagramSocket socket) {
        meters.forEach((name, meter) -> {
            send(socket,
                    metricFormatter.buildMetricString(name, "count", meter.getCount(), GAUGE),
                    metricFormatter.buildMetricString(name, "m1_rate", convertRate(meter.getOneMinuteRate()), TIMER),
                    metricFormatter.buildMetricString(name, "m5_rate", convertRate(meter.getFiveMinuteRate()), TIMER),
                    metricFormatter.buildMetricString(name, "m15_rate", convertRate(meter.getFifteenMinuteRate()), TIMER),
                    metricFormatter.buildMetricString(name, "mean_rate", convertRate(meter.getMeanRate()), TIMER)
            );
        });
    }

    @VisibleForTesting
    void reportTimers(SortedMap<String, Timer> timers, DatagramSocket socket) {
        timers.forEach((name, timer) -> {
            Snapshot snapshot = timer.getSnapshot();
            send(socket,
                    metricFormatter.buildMetricString(name, "max", convertDuration(snapshot.getMax()), TIMER),
                    metricFormatter.buildMetricString(name, "mean", convertDuration(snapshot.getMean()), TIMER),
                    metricFormatter.buildMetricString(name, "min", convertDuration(snapshot.getMin()), TIMER),
                    metricFormatter.buildMetricString(name, "stddev", convertDuration(snapshot.getStdDev()), TIMER),
                    metricFormatter.buildMetricString(name, "p50", convertDuration(snapshot.getMedian()), TIMER),
                    metricFormatter.buildMetricString(name, "p75", convertDuration(snapshot.get75thPercentile()), TIMER),
                    metricFormatter.buildMetricString(name, "p95", convertDuration(snapshot.get95thPercentile()), TIMER),
                    metricFormatter.buildMetricString(name, "p98", convertDuration(snapshot.get98thPercentile()), TIMER),
                    metricFormatter.buildMetricString(name, "p99", convertDuration(snapshot.get99thPercentile()), TIMER),
                    metricFormatter.buildMetricString(name, "p999", convertDuration(snapshot.get999thPercentile()), TIMER),
                    metricFormatter.buildMetricString(name, "m1_rate", convertRate(timer.getOneMinuteRate()), TIMER),
                    metricFormatter.buildMetricString(name, "m5_rate", convertRate(timer.getFiveMinuteRate()), TIMER),
                    metricFormatter.buildMetricString(name, "m15_rate", convertRate(timer.getFifteenMinuteRate()), TIMER),
                    metricFormatter.buildMetricString(name, "mean_rate", convertRate(timer.getMeanRate()), TIMER)
            );
        });
    }

    @VisibleForTesting
    void send(DatagramSocket socket, String...metrics) {
        for (String metric: metrics) {
            byte[] bytes = metric.getBytes(UTF_8);
            DatagramPacket packet = new DatagramPacket(bytes, bytes.length, address);
            try {
                socket.send(packet);
            } catch (IOException e) {
                throw new StatsdReporterException(e);
            }
        }
    }
}