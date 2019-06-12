package org.apache.spark.metrics.sink.statsd;

final class Configuration {
    public static final class Keys {

        private Keys() {
        }

        public static final String HOST = "host";
        public static final String PORT = "port";
        public static final String PREFIX = "prefix";
        public static final String TAGS = "tags";
        public static final String POLL_INTERVAL = "poll.interval";
        public static final String POLL_UNIT = "poll.unit";
        public static final String RATE_UNIT = "rate.unit";
        public static final String DURATION_UNIT = "duration.unit";
        public static final String EXCLUDES = "excludes";
        public static final String INCLUDES = "includes";
        public static final String EXCLUDES_ATTRIBUTES = "excludes.attributes";
        public static final String INCLUDES_ATTRIBUTES = "includes.attributes";
        public static final String USE_REGEX_FILTERS = "use.regex.filters";
        public static final String USE_SUBSTRING_MATCHING = "use.substring.matching";
    }

    public static final class Defaults {

        private Defaults() {
        }

        public static final String HOST = "127.0.0.1";
        public static final String PORT = "8125";
        public static final String TAGS = "";
        public static final String POLL_INTERVAL = "10";
        public static final String POLL_UNIT = "SECONDS";
        public static final String RATE_UNIT = "SECONDS";
        public static final String DURATION_UNIT = "MILLISECONDS";
        public static final String PREFIX = "";
        public static final String EXCLUDES = "";
        public static final String INCLUDES = "";
        public static final String EXCLUDES_ATTRIBUTES = "";
        public static final String INCLUDES_ATTRIBUTES = "";
        public static final String USE_REGEX_FILTERS = "false";
        public static final String USE_SUBSTRING_MATCHING = "false";
    }
}
