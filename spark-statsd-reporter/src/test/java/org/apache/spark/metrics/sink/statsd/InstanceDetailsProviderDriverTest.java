package org.apache.spark.metrics.sink.statsd;

import org.apache.spark.SparkConf;
import org.apache.spark.SparkContext;
import org.junit.Test;

import java.util.Optional;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

public class InstanceDetailsProviderDriverTest {

    @Test
    public void testDefaultDriverInstanceDetails() {
        final String appName = "test1";
        InstanceDetailsProvider provider = new InstanceDetailsProvider();
        SparkConf conf = new SparkConf()
                .setAppName(appName)
                .setMaster("local");
        SparkContext context = SparkContext.getOrCreate(conf);

        Optional<InstanceDetails> instanceDetails = provider.getInstanceDetails();
        context.stop();

        assertTrue(instanceDetails.isPresent());
        instanceDetails.ifPresent(details -> {
            assertEquals("default", details.getNamespace());
            assertEquals(appName, details.getApplicationName());
            assertTrue(details.getApplicationId().startsWith("local-"));
            assertEquals(InstanceType.DRIVER, details.getInstanceType());
            assertEquals("driver", details.getInstanceId());
        });
    }

    @Test
    public void testNamespaceDriverInstanceDetails() {
        final String appName = "test2";
        final String namespace = "mynamespace";
        InstanceDetailsProvider provider = new InstanceDetailsProvider();
        SparkConf conf = new SparkConf()
                .setAppName(appName)
                .setMaster("local");
        conf.set("spark.metrics.namespace", namespace);
        SparkContext context = SparkContext.getOrCreate(conf);

        Optional<InstanceDetails> instanceDetails = provider.getInstanceDetails();
        context.stop();

        assertTrue(instanceDetails.isPresent());
        instanceDetails.ifPresent(details -> {
            assertEquals(namespace, details.getNamespace());
            assertEquals(appName, details.getApplicationName());
            assertTrue(details.getApplicationId().startsWith("local-"));
            assertEquals(InstanceType.DRIVER, details.getInstanceType());
            assertEquals("driver", details.getInstanceId());
        });
    }
}