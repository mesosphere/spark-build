package org.apache.spark.metrics.sink.statsd;

class InstanceDetails {
    private final String applicationId;
    private final String applicationName;
    private final String applicationOrigin;
    private final InstanceType instanceType;
    private final String instanceId;
    private final String namespace;

    InstanceDetails(String applicationId, String applicationName, String applicationOrigin, InstanceType instanceType, String instanceId, String namespace) {
        this.applicationId = applicationId;
        this.applicationName = applicationName;
        this.applicationOrigin = applicationOrigin;
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

    public String getApplicationOrigin() {
        return applicationOrigin;
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
                ", applicationOrigin='" + applicationOrigin + '\'' +
                ", instanceType=" + instanceType +
                ", instanceId='" + instanceId + '\'' +
                ", namespace='" + namespace + '\'' +
                '}';
    }
}
