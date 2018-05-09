import org.apache.log4j.{Level, Logger}
import org.apache.spark.internal.Logging
import org.apache.spark.sql.SparkSession

/**
  * A config class used to set the command line arguments.
  */
case class Config(
  appName: String = "",
  brokers: String = "" ,
  topics: String = "",
  groupId: String = "kafka_cassandra_stream",
  wordsPerSecond: Float = 1.0F,
  batchSizeSeconds: Long = 1L,
  cassandraKeyspace: String = "kafka_cassandra_stream",
  cassandraTable: String = "records",
  shouldWriteToCassandra: Boolean = true,
  isKerberized: Boolean = false,
  isLocal: Boolean = false
)

/** Utility functions for Spark Streaming examples. */
object StreamingExamples extends Logging {
  /** Set reasonable logging levels for streaming if the user has not configured log4j. */
  def setStreamingLogLevels(level: Level): Unit = {
    val log4jInitialized = Logger.getRootLogger.getAllAppenders.hasMoreElements
    if (!log4jInitialized) {
      // We first log something to initialize Spark's default logging, then we override the
      // logging level.
      logInfo(s"Setting log level to [$level] for streaming example." +
        " To override add a custom log4j.properties to the classpath.")
      Logger.getRootLogger.setLevel(level)
    }
  }

  /**
    * Create a spark session for a given config.
    */
  def createSparkSession(config: Config): SparkSession = {
    var sparkBuilder = SparkSession.builder().appName(config.appName)

    if (config.isLocal) {
      logInfo("Running in local mode")
      sparkBuilder = sparkBuilder.master("local[1]")
    }

    sparkBuilder.getOrCreate()
  }

  def getParser(programName : String, isSource: Boolean): scopt.OptionParser[Config] = {
    val parser = new scopt.OptionParser[Config](programName) {
      opt[String]("appName").required().action((x, c) =>
        c.copy(appName = x)).text("The application name to use for the Spark streaming app")

      opt[String]("brokers").required().action((x, c) =>
        c.copy(brokers = x)).text("The broker connection information")

      opt[String]("topics").required().action((x, c) =>
        c.copy(topics = x)).text("The comma-separated list of topics to use")

      opt[Unit]('k', "isKerberized").action((_, c) =>
        c.copy(isKerberized = true)).text("Enable Kerberized mode")

      opt[Unit]("isLocal").action((_, c) =>
        c.copy(isLocal = true)).text("Enable remote mode")

      opt[Int]("batchSizeSeconds").action((x, c) =>
        c.copy(batchSizeSeconds = x.toLong)).text("The window size to be used for the Spark streaming batch")

      if (isSource) {
        opt[Double]("wordsPerSecond").action((x, c) =>
          c.copy(wordsPerSecond = x.toFloat)).text("The rate at which words should be written to Kafka")
      } else {
        opt[Unit]("shouldWriteToCassandra").action((_, c) =>
          c.copy(shouldWriteToCassandra = true)).text("Write word counts to Cassandra")

        opt[String]("groupId").action((x, c) =>
          c.copy(groupId = x)).text("The Kafka group ID for consumers")

        opt[String]("cassandraKeyspace").action((x, c) =>
          c.copy(cassandraKeyspace = x) ).text("The Cassandra keyspace to use")

        opt[String]("cassandraTable").action((x, c) =>
          c.copy(cassandraTable = x)).text("The Cassandra table to use")
      }
    }

    parser
  }
}
