package org.apache.spark.metrics.sink.statsd;

import com.codahale.metrics.Gauge;
import com.codahale.metrics.MetricRegistry;
import org.junit.Test;

import java.util.Properties;

import static java.lang.Thread.sleep;
import static org.junit.Assert.assertEquals;

public class StatsdSinkTest {

    @Test
    public void testDefaultConfiguration() throws Exception {
        try (DatagramTestServer server = DatagramTestServer.run(Integer.parseInt(Configuration.Defaults.PORT))) {
            MetricRegistry registry = new MetricRegistry();

            Properties props = new Properties(); // empty configuration
            StatsdSink sink = new StatsdSink(props, registry, null);

            // Report simple gauge metric
            registry.register("test_gauge", (Gauge<Integer>) () -> 1);
            sink.report();

            sleep(100);

            // Default host, port and prefix check
            assertEquals("spark.test_gauge,:1|g", server.receivedMessages().get(0));
        }
    }

    @Test
    public void testPortPrefixAndTagsConfiguration() throws Exception {
        final int testUdpPort = 4540;
        try (DatagramTestServer server = DatagramTestServer.run(testUdpPort)) {
            MetricRegistry registry = new MetricRegistry();

            Properties props = new Properties();
            props.put(Configuration.Keys.PORT, Integer.toString(testUdpPort));
            props.put(Configuration.Keys.PREFIX, "myprefix");
            props.put(Configuration.Keys.TAGS, "foo=bar");

            StatsdSink sink = new StatsdSink(props, registry, null);

            // Report simple gauge metric
            registry.register("test_gauge", (Gauge<Integer>) () -> 1);
            sink.report();

            sleep(100);

            // Provided port, prefix and tags check
            assertEquals("myprefix.spark.test_gauge,foo=bar:1|g", server.receivedMessages().get(0));
        }
    }
}