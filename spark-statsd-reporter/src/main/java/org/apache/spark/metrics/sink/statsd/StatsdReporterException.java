package org.apache.spark.metrics.sink.statsd;

class StatsdReporterException extends RuntimeException {
    StatsdReporterException(String message) {
        super(message);
    }

    StatsdReporterException(Throwable cause) {
        super(cause);
    }
}
