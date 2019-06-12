package org.apache.spark.metrics.sink.statsd;

import com.codahale.metrics.MetricAttribute;
import com.codahale.metrics.MetricRegistry;
import com.google.common.collect.ImmutableSet;

import org.apache.spark.metrics.sink.Sink;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Properties;
import java.util.concurrent.TimeUnit;

import static org.apache.spark.metrics.sink.statsd.Configuration.Defaults;
import static org.apache.spark.metrics.sink.statsd.Configuration.Keys;

public class StatsdSink implements Sink {
    private final static Logger logger = LoggerFactory.getLogger(StatsdSink.class);
    // Static prefix is used to distinguish Spark JVM source from other JVM applications in the cluster
    private static final String STATIC_PREFIX = "spark";
    private final StatsdReporter reporter;

    private int pollInterval;
    private TimeUnit pollUnit;
    private final String prefix;

    public StatsdSink(Properties properties, MetricRegistry registry, org.apache.spark.SecurityManager securityMgr) {
        logger.info("Starting StatsdSink with properties:\n{}", properties.toString());
        this.prefix = MetricRegistry.name(properties.getProperty(Keys.PREFIX, Defaults.PREFIX), STATIC_PREFIX);
        this.pollInterval = Integer.parseInt(properties.getProperty(Keys.POLL_INTERVAL, Defaults.POLL_INTERVAL));
        this.pollUnit = TimeUnit.valueOf(properties.getProperty(Keys.POLL_UNIT, Defaults.POLL_UNIT).toUpperCase());

        String host = properties.getProperty(Keys.HOST, Defaults.HOST);
        int port = Integer.parseInt(properties.getProperty(Keys.PORT, Defaults.PORT));

        TimeUnit rateUnit = TimeUnit.valueOf(properties.getProperty(Keys.RATE_UNIT, Defaults.RATE_UNIT).toUpperCase());
        TimeUnit durationUnit = TimeUnit
                .valueOf(properties.getProperty(Keys.DURATION_UNIT, Defaults.DURATION_UNIT).toUpperCase());

        String excludes = properties.getProperty(Keys.EXCLUDES, Defaults.EXCLUDES);
        String includes = properties.getProperty(Keys.INCLUDES, Defaults.INCLUDES);

        String excludesAttributes = properties.getProperty(Keys.EXCLUDES_ATTRIBUTES, Defaults.EXCLUDES_ATTRIBUTES)
                .toUpperCase();
        String includesAttributes = properties.getProperty(Keys.INCLUDES_ATTRIBUTES, Defaults.INCLUDES_ATTRIBUTES)
                .toUpperCase();

        boolean useRegexFilters = Boolean
                .parseBoolean(properties.getProperty(Keys.USE_REGEX_FILTERS, Defaults.USE_REGEX_FILTERS));
        boolean useSubstringMatching = Boolean
                .parseBoolean(properties.getProperty(Keys.USE_SUBSTRING_MATCHING, Defaults.USE_SUBSTRING_MATCHING));

        String[] tags = properties.getProperty(Keys.TAGS, Defaults.TAGS).split(",");

        StatsdReporterFactory reporterFactory = new StatsdReporterFactory();

        reporterFactory.setHost(host);
        reporterFactory.setPort(port);
        reporterFactory.setRateUnit(rateUnit);
        reporterFactory.setDurationUnit(durationUnit);
        reporterFactory.setFormatter(new MetricFormatter(new InstanceDetailsProvider(), prefix, tags));

        if (!excludes.isEmpty()) {
            reporterFactory.setExcludes(parseMetricsString(excludes));
        }

        if (!includes.isEmpty()) {
            reporterFactory.setIncludes(parseMetricsString(includes));
        }

        if (!excludesAttributes.isEmpty()) {
            reporterFactory.setExcludesAttributes(parseAttributesString(excludesAttributes));
        }

        if (!includesAttributes.isEmpty()) {
            reporterFactory.setIncludesAttributes(parseAttributesString(includesAttributes));
        }

        reporterFactory.setUseRegexFilters(useRegexFilters);
        reporterFactory.setUseSubstringMatching(useSubstringMatching);

        this.reporter = reporterFactory.build(registry);
    }

    @Override
    public void start() {
        reporter.start(pollInterval, pollUnit);
        logger.info("StatsdSink started with prefix: {}", prefix);
    }

    @Override
    public void stop() {
        reporter.stop();
        logger.info("StatsdSink stopped");
    }

    /**
     * This method is called by SparkContext, Executors, and Spark Standalone
     * instances prior to shutting down
     */
    @Override
    public void report() {
        reporter.report();
    }

    private ImmutableSet<String> parseMetricsString(String metrics) {
        return ImmutableSet.copyOf(metrics.split(","));
    }

    private EnumSet<MetricAttribute> parseAttributesString(String metricsAttributes) {
        List<MetricAttribute> listOfAttributes = new ArrayList<>();
        for (String attribute : metricsAttributes.split(",")) {
            listOfAttributes.add(MetricAttribute.valueOf(attribute));
        }
        return EnumSet.copyOf(listOfAttributes);
    }
}
