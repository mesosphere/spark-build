package org.apache.spark.metrics.sink.statsd;

import com.codahale.metrics.MetricRegistry;
import org.apache.spark.metrics.sink.Sink;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Properties;
import java.util.concurrent.TimeUnit;

import static org.apache.spark.metrics.sink.statsd.Configuration.Defaults;
import static org.apache.spark.metrics.sink.statsd.Configuration.Keys;

public class StatsdSink implements Sink {
    private final static Logger logger = LoggerFactory.getLogger(StatsdSink.class);
    private final StatsdReporter reporter;

    private int pollInterval;
    private TimeUnit pollUnit;
    private final String prefix;

    public StatsdSink(Properties properties, MetricRegistry registry, org.apache.spark.SecurityManager securityMgr) {
        logger.info("Starting StatsdSink with properties:\n" + properties.toString());
        this.prefix = properties.getProperty(Keys.PREFIX, Defaults.PREFIX);
        this.pollInterval = Integer.parseInt(properties.getProperty(Keys.POLL_INTERVAL, Defaults.POLL_INTERVAL));
        this.pollUnit = TimeUnit.valueOf(properties.getProperty(Keys.POLL_UNIT, Defaults.POLL_UNIT).toUpperCase());

        String host = properties.getProperty(Keys.HOST, Defaults.HOST);
        int port = Integer.parseInt(properties.getProperty(Keys.PORT, Defaults.PORT));

        TimeUnit rateUnit = TimeUnit.valueOf(properties.getProperty(Keys.RATE_UNIT, Defaults.RATE_UNIT).toUpperCase());
        TimeUnit durationUnit = TimeUnit.valueOf(properties.getProperty(Keys.DURATION_UNIT, Defaults.DURATION_UNIT).toUpperCase());

        //TODO: add filtering support

        String[] tags = properties.getProperty(Keys.TAGS, Defaults.TAGS).split(",");

        this.reporter = StatsdReporter
                .forRegistry(registry)
                .formatter(new MetricFormatter(new InstanceDetailsProvider(), prefix, tags))
                .host(host)
                .port(port)
                .convertRatesTo(rateUnit)
                .convertDurationsTo(durationUnit)
                .build();
    }

    @Override
    public void start() {
        reporter.start(pollInterval, pollUnit);
        logger.info("StatsdSink started with prefix: " + prefix);
    }

    @Override
    public void stop() {
        reporter.stop();
        logger.info("StatsdSink stopped");
    }

    /**
     * This method is called by SparkContext, Executors, and Spark Standalone instances prior to shutting down
     */
    @Override
    public void report(){
        reporter.report();
    }
}
