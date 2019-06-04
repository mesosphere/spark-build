package org.apache.spark.metrics.sink.statsd;

import org.apache.http.annotation.NotThreadSafe;
import org.apache.spark.SparkConf;
import org.apache.spark.SparkEnv;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Optional;

/**
 * Class used to access SparkEnv instance and extract relevant tags from SparkConf
 * which is shared across Drivers and Executors. SparkEnv initializes Metric Sinks
 * in its constructor is not available in the Sink during initialization (for Executors).
 */
@NotThreadSafe
class InstanceDetailsProvider  {
    private final static Logger logger = LoggerFactory.getLogger(StatsdReporter.class);

    private InstanceDetails instance = null;
    private boolean initialized = false;

    Optional<InstanceDetails> getInstanceDetails() {
        if (!initialized) {
            if (SparkEnv.get() == null) {
                logger.warn("SparkEnv is not initialized, instance details unavailable");
            } else {
                instance = buildInstanceDetails();
            }
            initialized = true;
        }

        return Optional.ofNullable(instance);
    }

    InstanceDetails buildInstanceDetails() {
        SparkConf sparkConf = SparkEnv.get().conf();
        String instanceType = System.getenv("SPARK_INSTANCE_TYPE") != null
                ? System.getenv("SPARK_INSTANCE_TYPE") : "UNDEFINED";
        return new InstanceDetails(
                sparkConf.getAppId(),
                sparkConf.get("spark.app.name"),
                System.getenv("SPARK_APPLICATION_ORIGIN"),
                InstanceType.valueOf(instanceType.toUpperCase()),
                sparkConf.get("spark.executor.id"),
                sparkConf.get("spark.metrics.namespace", "default")
        );
    }
}
