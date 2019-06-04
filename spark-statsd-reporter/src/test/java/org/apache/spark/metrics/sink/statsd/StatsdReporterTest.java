package org.apache.spark.metrics.sink.statsd;


import com.codahale.metrics.*;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mockito.Mockito;
import org.mockito.junit.MockitoJUnitRunner;

import java.util.Optional;
import java.util.SortedMap;
import java.util.TreeMap;

import static java.lang.Thread.sleep;
import static junit.framework.TestCase.assertEquals;
import static junit.framework.TestCase.assertTrue;
import static org.mockito.Mockito.when;

@RunWith(MockitoJUnitRunner.class)
public class StatsdReporterTest {

    private MetricFormatter formatter;

    @Before
    public void setupFormatter() {
        InstanceDetailsProvider provider = Mockito.mock(InstanceDetailsProvider.class);

        when(provider.getInstanceDetails()).thenReturn(Optional.of(new InstanceDetails(
                "test-app-01", "Test Spark App", "spark-test",
                InstanceType.DRIVER, "test-instance-01", "default")));
        String[] tags = {};
        this.formatter = new MetricFormatter(provider, "spark", tags);
    }

    @Test
    public void testGauges() throws Exception {
        final int testUdpPort = 4440;
        try (DatagramTestServer server = DatagramTestServer.run(testUdpPort)) {
            StatsdReporter reporter = buildTestReporter(testUdpPort);

            SortedMap<String, Gauge> gauges = new TreeMap<>();
            gauges.put("test-app-01.driver.TestGaugeInt", () -> 42);
            gauges.put("test-app-01.driver.TestGaugeFloat", () -> 123.123f);

            reporter.report(gauges, new TreeMap<>(), new TreeMap<>(), new TreeMap<>(), new TreeMap<>());

            sleep(100); // Pausing to let DatagramTestServer collect all messages before the assertion

            // Check that both gauge metrics were received and app id is dropped
            assertTrue(server.receivedMessages().stream().allMatch(s -> s.startsWith("spark.driver.testgauge")));
            assertTrue(server.receivedMessages().stream().anyMatch(s -> s.endsWith(":42|g")));
            assertTrue(server.receivedMessages().stream().anyMatch(s -> s.endsWith(":123.12|g")));
            assertEquals(2, server.receivedMessages().size());

        }
    }
    @Test
    public void testCounters() throws Exception {
        final int testUdpPort = 4441;
        try (DatagramTestServer server = DatagramTestServer.run(testUdpPort)) {
            StatsdReporter reporter = buildTestReporter(testUdpPort);

            SortedMap<String, Counter> counters = new TreeMap<>();
            Counter counter = new Counter();
            counter.inc();
            counter.inc(2);
            counters.put("test-app-01.driver.TestCounter", counter);

            reporter.report(new TreeMap<>(), counters, new TreeMap<>(), new TreeMap<>(), new TreeMap<>());

            sleep(100);

            assertTrue(server.receivedMessages().stream().allMatch(s -> s.startsWith("spark.driver.testcounter")));
            // counters must be reported as gauges due to StatsD specifics: it treats values as independent increments
            assertTrue(server.receivedMessages().stream().allMatch(s -> s.endsWith(":3|g")));
            assertEquals(1, server.receivedMessages().size());
        }
    }

    @Test
    public void testHistograms() throws Exception {
        final int testUdpPort = 4442;
        try (DatagramTestServer server = DatagramTestServer.run(testUdpPort)) {
            StatsdReporter reporter = buildTestReporter(testUdpPort);

            SortedMap<String, Histogram> histograms = new TreeMap<>();
            Histogram histogram = new Histogram(new ExponentiallyDecayingReservoir());
            histogram.update(1);
            histogram.update(2);
            histogram.update(4);
            histogram.update(0);
            histogram.update(6);
            histograms.put("test-app-01.driver.TestHistogram", histogram);

            reporter.report(new TreeMap<>(), new TreeMap<>(), histograms, new TreeMap<>(), new TreeMap<>());

            sleep(100);

            String prefix = "spark.driver.testhistogram.";
            assertThatExists(server, prefix, "count", "5|g");
            assertThatExists(server, prefix, "max", "6|ms");
            assertThatExists(server, prefix, "mean", "2.60|ms");
            assertThatExists(server, prefix, "min", "0|ms");
            assertThatExists(server, prefix, "stddev", "2.15|ms");
            assertThatExists(server, prefix, "p50", "2.00|ms");
            assertThatExists(server, prefix, "p75", "4.00|ms");
            assertThatExists(server, prefix, "p95", "6.00|ms");
            assertThatExists(server, prefix, "p98", "6.00|ms");
            assertThatExists(server, prefix, "p99", "6.00|ms");
            assertThatExists(server, prefix, "p999", "6.00|ms");
            assertEquals(11, server.receivedMessages().size());
        }
    }

    @Test
    public void testMeters() throws Exception {
        final int testUdpPort = 4443;
        try (DatagramTestServer server = DatagramTestServer.run(testUdpPort)) {
            StatsdReporter reporter = buildTestReporter(testUdpPort);

            SortedMap<String, Meter> meters = new TreeMap<>();
            Meter meter = new Meter();
            meter.mark();
            meter.mark(2);
            meters.put("test-app-01.driver.TestMeter", meter);

            reporter.report(new TreeMap<>(), new TreeMap<>(), new TreeMap<>(), meters, new TreeMap<>());

            sleep(100);

            String prefix = "spark.driver.testmeter.";
            assertThatExists(server, prefix, "count", "3|g");
            assertThatExists(server, prefix, "m1_rate", "0.00|ms");
            assertThatExists(server, prefix, "m5_rate", "0.00|ms");
            assertThatExists(server, prefix, "m15_rate", "0.00|ms");
            // mean value depends on the timing and can't be predicted for the test
            assertThatExists(server, prefix, "mean_rate", "|ms");
            assertEquals(5, server.receivedMessages().size());
        }
    }

    @Test
    public void testTimers() throws Exception {
        final int testUdpPort = 4444;
        try (DatagramTestServer server = DatagramTestServer.run(testUdpPort)) {
            StatsdReporter reporter = buildTestReporter(testUdpPort);

            SortedMap<String, Timer> timers = new TreeMap<>();
            Timer timer = new Timer();
            Timer.Context timerContext = timer.time();
            sleep(100);
            timerContext.stop();
            timers.put("test-app-01.driver.TestTimer", timer);

            reporter.report(new TreeMap<>(), new TreeMap<>(),new TreeMap<>(), new TreeMap<>(), timers);

            sleep(100);

            String prefix = "spark.driver.testtimer.";
            assertThatExists(server, prefix, "max", "|ms");
            assertThatExists(server, prefix, "mean", "|ms");
            assertThatExists(server, prefix, "min", "|ms");
            assertThatExists(server, prefix, "stddev", "|ms");
            assertThatExists(server, prefix, "p50", "|ms");
            assertThatExists(server, prefix, "p75", "|ms");
            assertThatExists(server, prefix, "p95", "|ms");
            assertThatExists(server, prefix, "p98", "|ms");
            assertThatExists(server, prefix, "p99", "|ms");
            assertThatExists(server, prefix, "p999", "|ms");
            assertThatExists(server, prefix, "m1_rate", "0.00|ms");
            assertThatExists(server, prefix, "m5_rate", "0.00|ms");
            assertThatExists(server, prefix, "m15_rate", "0.00|ms");
            assertThatExists(server, prefix, "mean_rate", "|ms");
            assertEquals(14, server.receivedMessages().size());
        }
    }

    private StatsdReporter buildTestReporter(int testUdpPort) {
        return StatsdReporter
                .forRegistry(null)
                .formatter(formatter)
                .host("localhost")
                .port(testUdpPort)
                .build();
    }

    private void assertThatExists(DatagramTestServer server, String expectedMetricNamePrefix, String expectedMetricArgumentName, String expectedValueAndType) {
        assertTrue(server.receivedMessages().stream().anyMatch(
                s -> s.startsWith(expectedMetricNamePrefix + expectedMetricArgumentName)
                        && s.endsWith(expectedValueAndType)));
    }
}