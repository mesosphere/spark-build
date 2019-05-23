package org.apache.spark.metrics.sink.statsd;

import org.apache.spark.SparkConf;
import org.apache.spark.SparkEnv;
import org.apache.spark.metrics.MetricsSystem;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mockito.Mock;
import org.powermock.api.mockito.PowerMockito;
import org.powermock.core.classloader.annotations.PrepareForTest;
import org.powermock.modules.junit4.PowerMockRunner;

import java.util.Optional;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;
import static org.mockito.Mockito.when;

@RunWith(PowerMockRunner.class)
@PrepareForTest(SparkEnv.class)
public class InstanceDetailsProviderExecutorTest {

    @Mock SparkEnv env;
    @Mock MetricsSystem metricsSystem;
    @Mock SparkConf conf;

    @Test
    public void getInstanceDetails() {
        final String appName = "test-app";
        final String appId = "test-id";
        final String execId = "test-exec-0";
        final String namespace = "default";

        PowerMockito.mockStatic(SparkEnv.class);

        when(metricsSystem.instance()).thenReturn("executor");
        when(env.metricsSystem()).thenReturn(metricsSystem);
        when(conf.getAppId()).thenReturn(appId);
        when(conf.get("spark.app.name")).thenReturn(appName);
        when(conf.get("spark.executor.id")).thenReturn(execId);
        when(conf.get("spark.metrics.namespace", "default")).thenReturn(namespace);
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
}