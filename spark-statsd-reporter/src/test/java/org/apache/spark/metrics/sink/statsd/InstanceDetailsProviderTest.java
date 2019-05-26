package org.apache.spark.metrics.sink.statsd;

import org.apache.spark.SparkConf;
import org.apache.spark.SparkContext;
import org.apache.spark.SparkEnv;
import org.apache.spark.metrics.MetricsSystem;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mockito.Mock;
import org.powermock.api.mockito.PowerMockito;
import org.powermock.core.classloader.annotations.PrepareForTest;
import org.powermock.modules.junit4.PowerMockRunner;

import java.util.Optional;
import java.util.UUID;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;
import static org.mockito.Mockito.*;

@RunWith(PowerMockRunner.class)
@PrepareForTest(SparkEnv.class)
public class InstanceDetailsProviderTest {

    @Mock SparkEnv env;
    @Mock MetricsSystem metricsSystem;

    private static final String appName = "test-app";
    private static final String appId = "test-id";
    private static final String execId = "test-exec-0";
    private static final String namespace = "default";

    private SparkConf getDefaultSparkConf() {
        SparkConf sparkConf = new SparkConf();
        sparkConf.set("spark.app.id", appId);
        sparkConf.set("spark.app.name", appName);
        sparkConf.set("spark.executor.id", execId);

        return sparkConf;
    }

    @Test
    public void testInitialization() {
        PowerMockito.mockStatic(SparkEnv.class);
        SparkConf conf = getDefaultSparkConf();

        when(metricsSystem.instance()).thenReturn("driver");
        when(env.metricsSystem()).thenReturn(metricsSystem);
        when(env.conf()).thenReturn(conf);
        when(SparkEnv.get()).thenReturn(env);

        InstanceDetailsProvider provider = spy(InstanceDetailsProvider.class);
        provider.getInstanceDetails();
        provider.getInstanceDetails();

        verify(provider, times(1)).buildInstanceDetails();
    }

    @Test
    public void testExecutorInstanceDetails() {
        PowerMockito.mockStatic(SparkEnv.class);
        SparkConf conf = getDefaultSparkConf();

        when(metricsSystem.instance()).thenReturn("executor");
        when(env.metricsSystem()).thenReturn(metricsSystem);
        when(env.conf()).thenReturn(conf);
        when(SparkEnv.get()).thenReturn(env);

        InstanceDetailsProvider provider = new InstanceDetailsProvider();
        Optional<InstanceDetails> instanceDetails = provider.getInstanceDetails();

        assertTrue(instanceDetails.isPresent());
        instanceDetails.ifPresent(details -> {
            assertEquals(namespace, details.getNamespace());
            assertEquals(appName, details.getApplicationName());
            assertEquals(appId, details.getApplicationId());
            assertEquals(InstanceType.EXECUTOR, details.getInstanceType());
            assertEquals(execId, details.getInstanceId());
        });
    }

    @Test
    public void testDriverInstanceDetails() {
        PowerMockito.mockStatic(SparkEnv.class);

        String applicationId = UUID.randomUUID().toString() + "-driver-" + System.currentTimeMillis();
        SparkConf conf = getDefaultSparkConf();
        conf.set("spark.app.id", applicationId);
        conf.set("spark.executor.id", applicationId);


        when(metricsSystem.instance()).thenReturn("driver");
        when(env.metricsSystem()).thenReturn(metricsSystem);
        when(env.conf()).thenReturn(conf);
        when(SparkEnv.get()).thenReturn(env);

        InstanceDetailsProvider provider = new InstanceDetailsProvider();
        Optional<InstanceDetails> instanceDetails = provider.getInstanceDetails();

        assertTrue(instanceDetails.isPresent());
        instanceDetails.ifPresent(details -> {
            assertEquals(namespace, details.getNamespace());
            assertEquals(appName, details.getApplicationName());
            assertEquals(applicationId, details.getApplicationId());
            assertEquals(InstanceType.DRIVER, details.getInstanceType());
            assertEquals(applicationId, details.getInstanceId());
        });
    }

    @Test
    public void testDriverNamespaceInstanceDetails() {
        PowerMockito.mockStatic(SparkEnv.class);

        String namespace = "test_namespace";
        SparkConf conf = getDefaultSparkConf();
        conf.set("spark.metrics.namespace", namespace);

        when(metricsSystem.instance()).thenReturn("driver");
        when(env.metricsSystem()).thenReturn(metricsSystem);
        when(env.conf()).thenReturn(conf);
        when(SparkEnv.get()).thenReturn(env);

        InstanceDetailsProvider provider = new InstanceDetailsProvider();
        Optional<InstanceDetails> instanceDetails = provider.getInstanceDetails();

        assertTrue(instanceDetails.isPresent());
        instanceDetails.ifPresent(details -> {
            assertEquals(namespace, details.getNamespace());
            assertEquals(appName, details.getApplicationName());
            assertEquals(appId, details.getApplicationId());
            assertEquals(InstanceType.DRIVER, details.getInstanceType());
            assertEquals(execId, details.getInstanceId());
        });
    }
}