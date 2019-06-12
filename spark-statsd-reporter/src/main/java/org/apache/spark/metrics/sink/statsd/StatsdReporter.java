package org.apache.spark.metrics.sink.statsd;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.codahale.metrics.Counter;
import com.codahale.metrics.Gauge;
import com.codahale.metrics.Histogram;
import com.codahale.metrics.Meter;
import com.codahale.metrics.Metric;
import com.codahale.metrics.MetricAttribute;
import com.codahale.metrics.MetricFilter;
import com.codahale.metrics.MetricRegistry;
import com.codahale.metrics.ScheduledReporter;
import com.codahale.metrics.Snapshot;
import com.codahale.metrics.Timer;

import java.io.IOException;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetSocketAddress;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.SortedMap;
import java.util.TreeMap;
import java.util.concurrent.TimeUnit;

import static java.nio.charset.StandardCharsets.UTF_8;
import static org.apache.spark.metrics.sink.statsd.MetricType.*;

public class StatsdReporter extends ScheduledReporter {
    private final static Logger logger = LoggerFactory.getLogger(StatsdReporter.class);
    private final InetSocketAddress address;
    private final MetricFormatter metricFormatter;
    private MetricFilter filter;
    private MetricAttributeFilter attributeFilter;

    protected StatsdReporter(MetricRegistry registry, MetricFormatter metricFormatter, String reporterName,
            TimeUnit rateUnit, TimeUnit durationUnit, MetricFilter filter, MetricAttributeFilter attributeFilter,
            String host, int port) {
        super(registry, reporterName, filter, rateUnit, durationUnit);
        this.filter = filter;
        this.attributeFilter = attributeFilter;
        this.address = new InetSocketAddress(host, port);
        this.metricFormatter = metricFormatter;
    }

    @Override
    public void report(SortedMap<String, Gauge> gauges, SortedMap<String, Counter> counters,
            SortedMap<String, Histogram> histograms, SortedMap<String, Meter> meters, SortedMap<String, Timer> timers) {
        try (DatagramSocket socket = new DatagramSocket()) {
            reportGauges(getFilteredMetrics(gauges), socket);
            reportCounters(getFilteredMetrics(counters), socket);
            reportHistograms(getFilteredMetrics(histograms), socket);
            reportMeters(getFilteredMetrics(meters), socket);
            reportTimers(getFilteredMetrics(timers), socket);
        } catch (StatsdReporterException e) {
            logger.warn("Unable to send packets to StatsD", e);
        } catch (IOException e) {
            logger.warn("StatsD datagram socket construction failed", e);
        }
    }

    private <T extends Metric> SortedMap<String, T> getFilteredMetrics(SortedMap<String, T> metrics) {
        final TreeMap<String, T> filteredMetrics = new TreeMap<>();
        for (Map.Entry<String, T> entry : metrics.entrySet()) {
            if (filter.matches(entry.getKey(), entry.getValue())) {
                filteredMetrics.put(entry.getKey(), entry.getValue());
            }
        }
        return Collections.unmodifiableSortedMap(filteredMetrics);
    }

    private void reportGauges(SortedMap<String, Gauge> gauges, DatagramSocket socket) {
        gauges.forEach((name, value) -> send(socket, metricFormatter.buildMetricString(name, value.getValue(), GAUGE)));
    }

    private void reportCounters(SortedMap<String, Counter> counters, DatagramSocket socket) {
        counters.forEach((name, value) ->
        // counter is reported as a gauge because StatsD treats new values as increments
        // but not as a final value e.g. sending 'foo:1|c' to StatsD increments 'foo' by 1
        send(socket, metricFormatter.buildMetricString(name, value.getCount(), GAUGE)));
    }

    private void reportHistograms(SortedMap<String, Histogram> histograms, DatagramSocket socket) {
        histograms.forEach((name, histogram) -> {
            Snapshot snapshot = histogram.getSnapshot();
            List<String> metrics = new ArrayList<>();
            addIfMatches(metrics, MetricAttribute.COUNT, name, histogram.getCount(), GAUGE);
            addIfMatches(metrics, MetricAttribute.MAX, name, snapshot.getMax(), TIMER);
            addIfMatches(metrics, MetricAttribute.MEAN, name, snapshot.getMean(), TIMER);
            addIfMatches(metrics, MetricAttribute.MIN, name, snapshot.getMin(), TIMER);
            addIfMatches(metrics, MetricAttribute.STDDEV, name, snapshot.getStdDev(), TIMER);
            addIfMatches(metrics, MetricAttribute.P50, name, snapshot.getMedian(), TIMER);
            addIfMatches(metrics, MetricAttribute.P75, name, snapshot.get75thPercentile(), TIMER);
            addIfMatches(metrics, MetricAttribute.P95, name, snapshot.get95thPercentile(), TIMER);
            addIfMatches(metrics, MetricAttribute.P98, name, snapshot.get98thPercentile(), TIMER);
            addIfMatches(metrics, MetricAttribute.P99, name, snapshot.get99thPercentile(), TIMER);
            addIfMatches(metrics, MetricAttribute.P999, name, snapshot.get999thPercentile(), TIMER);
            send(socket, metrics.toArray(new String[0]));
        });
    }

    private void reportMeters(SortedMap<String, Meter> meters, DatagramSocket socket) {
        meters.forEach((name, meter) -> {
            List<String> metrics = new ArrayList<>();
            addIfMatches(metrics, MetricAttribute.COUNT, name, meter.getCount(), GAUGE);
            addIfMatches(metrics, MetricAttribute.M1_RATE, name, convertRate(meter.getOneMinuteRate()), TIMER);
            addIfMatches(metrics, MetricAttribute.M5_RATE, name, convertRate(meter.getFiveMinuteRate()), TIMER);
            addIfMatches(metrics, MetricAttribute.M15_RATE, name, convertRate(meter.getFifteenMinuteRate()), TIMER);
            addIfMatches(metrics, MetricAttribute.MEAN_RATE, name, convertRate(meter.getMeanRate()), TIMER);
            send(socket, metrics.toArray(new String[0]));
        });
    }

    private void reportTimers(SortedMap<String, Timer> timers, DatagramSocket socket) {
        timers.forEach((name, timer) -> {
            Snapshot snapshot = timer.getSnapshot();
            List<String> metrics = new ArrayList<>();
            addIfMatches(metrics, MetricAttribute.MAX, name, convertDuration(snapshot.getMax()), TIMER);
            addIfMatches(metrics, MetricAttribute.MEAN, name, convertDuration(snapshot.getMean()), TIMER);
            addIfMatches(metrics, MetricAttribute.MIN, name, convertDuration(snapshot.getMin()), TIMER);
            addIfMatches(metrics, MetricAttribute.STDDEV, name, convertDuration(snapshot.getStdDev()), TIMER);
            addIfMatches(metrics, MetricAttribute.P50, name, convertDuration(snapshot.getMedian()), TIMER);
            addIfMatches(metrics, MetricAttribute.P75, name, convertDuration(snapshot.get75thPercentile()), TIMER);
            addIfMatches(metrics, MetricAttribute.P95, name, convertDuration(snapshot.get95thPercentile()), TIMER);
            addIfMatches(metrics, MetricAttribute.P98, name, convertDuration(snapshot.get98thPercentile()), TIMER);
            addIfMatches(metrics, MetricAttribute.P99, name, convertDuration(snapshot.get99thPercentile()), TIMER);
            addIfMatches(metrics, MetricAttribute.P999, name, convertDuration(snapshot.get999thPercentile()), TIMER);
            addIfMatches(metrics, MetricAttribute.M1_RATE, name, convertRate(timer.getOneMinuteRate()), TIMER);
            addIfMatches(metrics, MetricAttribute.M5_RATE, name, convertRate(timer.getFiveMinuteRate()), TIMER);
            addIfMatches(metrics, MetricAttribute.M15_RATE, name, convertRate(timer.getFifteenMinuteRate()), TIMER);
            addIfMatches(metrics, MetricAttribute.MEAN_RATE, name, convertRate(timer.getMeanRate()), TIMER);
            send(socket, metrics.toArray(new String[0]));
        });
    }

    private void send(DatagramSocket socket, String... metrics) {
        for (String metric : metrics) {
            byte[] bytes = metric.getBytes(UTF_8);
            DatagramPacket packet = new DatagramPacket(bytes, bytes.length, address);
            try {
                socket.send(packet);
            } catch (IOException e) {
                throw new StatsdReporterException(e);
            }
        }
    }

    private void addIfMatches(List<String> metrics, MetricAttribute metricAttribute, String name, Object value,
            String type) {
        if (attributeFilter.matches(metricAttribute)) {
            metrics.add(metricFormatter.buildMetricString(name, metricAttribute.getCode(), value, type));
        }
    }
}
