package org.apache.spark.metrics.sink.statsd;

class InstanceDetails {
    private final String applicationId;
    private final String applicationName;
    private final InstanceType instanceType;
    private final String instanceId;
    private final String namespace;

    InstanceDetails(String applicationId, String applicationName, InstanceType instanceType, String instanceId, String namespace) {
        this.applicationId = applicationId;
        this.applicationName = applicationName;
        this.instanceType = instanceType;
        this.instanceId = instanceId;
        this.namespace = namespace;
    }

    String getApplicationId() {
        return applicationId;
    }

    String getApplicationName() {
        return applicationName;
    }

    InstanceType getInstanceType() {
        return instanceType;
    }

    String getInstanceId() {
        return instanceId;
    }

    String getNamespace() {
        return namespace;
    }

    @Override
    public String toString() {
        return "InstanceDetails{" +
                "applicationId='" + applicationId + '\'' +
                ", applicationName='" + applicationName + '\'' +
                ", instanceType=" + instanceType +
                ", instanceId='" + instanceId + '\'' +
                ", namespace='" + namespace + '\'' +
                '}';
    }
}
