import java.util.{Date, Properties}

import com.datastax.spark.connector._
import com.datastax.spark.connector.cql.CassandraConnector
import org.apache.kafka.clients.consumer.ConsumerConfig
import org.apache.kafka.clients.producer.{KafkaProducer, ProducerConfig, ProducerRecord}
import org.apache.kafka.common.serialization.StringDeserializer
import org.apache.log4j.{Level, Logger}
import org.apache.spark.internal.Logging
import org.apache.spark.sql.SparkSession
import org.apache.spark.streaming.kafka010.{ConsumerStrategies, KafkaUtils, LocationStrategies}
import org.apache.spark.streaming.{Seconds, StreamingContext}



/**
  * A config class used to set the command line arguments.
  */
case class Config(
                   appName: String = "KafkaRandomFeeder",
                   brokers: String = "" ,
                   topics: String = "",
                   groupId: String = "TODO_USE_A_DIFFERENT_GROUP_ID",
                   wordsPerSecond: Float = 1.0F,
                   batchSizeSeconds: Long = 1L,
                   cassandraKeyspace: String = "kafka_cassandra_stream",
                   cassandraTable: String = "records",
                   cassandra: Boolean = true,
                   kerberized: Boolean = false,
                   isLocal: Boolean = false
                 )

object KafkaRandomFeeder extends Logging {
  def main(args: Array[String]): Unit = {
    StreamingExamples.setStreamingLogLevels(Level.WARN)

    val parser = StreamingExamples.getParser( this.getClass.getSimpleName, true ).parse(args, Config())
    if (parser.isEmpty) {
      logError("Bad arguments")
      System.exit(1)
    }

    val config = parser.get
    println(s"Using config: $config")

    val spark = StreamingExamples.createSparkSession(config)

    val streamingContext = new StreamingContext(spark.sparkContext, Seconds(config.batchSizeSeconds))

    val wordsPerSecond = config.wordsPerSecond
    val stream = streamingContext.receiverStream(new RandomWordReceiver(wordsPerSecond))

    val kafkaProperties = getKafkaProperties(config.brokers, config.kerberized)
    println(s"${kafkaProperties}")
    val topic : String = config.topics

    stream.foreachRDD { rdd =>
      rdd.foreachPartition { partition =>

        val producer = new KafkaProducer[String, String](kafkaProperties)
        partition.foreach { word =>
          println(s"Writing $word to Kafka")
          val msg = new ProducerRecord[String, String](topic, null, word)
          producer.send(msg)
        }
        producer.close()
      }
    }

    streamingContext.start()
    streamingContext.awaitTermination()
  }


  def getKafkaProperties(brokers : String, kerberized: Boolean) : Properties = {

    val props = new Properties()
    props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, brokers)
    props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, "org.apache.kafka.common.serialization.StringSerializer")
    props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, "org.apache.kafka.common.serialization.StringSerializer")
    if (kerberized) {
      props.put("sasl.kerberos.service.name", "kafka")
      props.put("security.protocol", "SASL_PLAINTEXT")
      props.put("sasl.mechanism", "GSSAPI")
    }

    props
  }

}


object KafkaWordCount extends Logging {
  def main(args: Array[String]) : Unit = {
    StreamingExamples.setStreamingLogLevels(Level.WARN)

    val parser = StreamingExamples.getParser( this.getClass.getSimpleName, false ).parse(args, Config())
    if (parser.isEmpty) {
      logError("Bad arguments")
      System.exit(1)
    }

    val config = parser.get
    println(s"Using config: $config")

    val spark = StreamingExamples.createSparkSession(config)

    val streamingContext = new StreamingContext(spark.sparkContext, Seconds(config.batchSizeSeconds))

    // Create direct kafka stream with brokers and topics
    val topicsSet = config.topics.split(",").toSet

    val kafkaParams = getKafkaProperties(config.brokers, config.groupId, config.kerberized)

    val cassandraEnabled : Boolean = config.cassandra

    // Set up the cassandra session:
    val keyspaceName = config.cassandraKeyspace
    val tableName = config.cassandraTable
    val cassandraColumns = SomeColumns("ts" as "_1", "word" as "_2", "count" as "_3")

    if (cassandraEnabled) {
      CassandraConnector(spark.sparkContext.getConf).withSessionDo { session =>

        session.execute(
          s"""CREATE KEYSPACE IF NOT EXISTS $keyspaceName WITH REPLICATION = {
            'class': 'SimpleStrategy',
            'replication_factor': 3
          }""")
        session.execute(
          s"""
            CREATE TABLE IF NOT EXISTS $keyspaceName.$tableName (
              ts timestamp,
              word text,
              count int,
              PRIMARY KEY(word, ts)
            );"""
        )
      }
    }

    val messages = KafkaUtils.createDirectStream[String, String](
      streamingContext,
      LocationStrategies.PreferConsistent,
      ConsumerStrategies.Subscribe[String, String](topicsSet, kafkaParams))

    // Get the lines, split them into words, count the words and print
    val lines = messages.map(_.value)
    val words = lines.flatMap(_.split(" "))
    val wordCounts = words
      .map(x => (x, 1L))
      .reduceByKey(_ + _)
      .map(x => (new Date().getTime(), x._1, x._2))

    if (cassandraEnabled) {
      wordCounts.foreachRDD(rdd => {
        println(s"Writing ${rdd.toString} to Cassandra")
        rdd.saveToCassandra(keyspaceName, tableName, cassandraColumns)
      })
    }

    wordCounts.print()

    // Start the computation
    streamingContext.start()
    streamingContext.awaitTermination()
  }

  def getKafkaProperties(brokers : String, groupId: String, kerberized: Boolean) : Map[String, Object] = {

    val props = Map[String, Object](
      ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG -> brokers,
      ConsumerConfig.GROUP_ID_CONFIG -> groupId,
      ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG -> classOf[StringDeserializer],
      ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG -> classOf[StringDeserializer])

    //    if (kerberized) {
    //      props.put("sasl.kerberos.service.name", "kafka")
    //      props.put("security.protocol", "SASL_PLAINTEXT")
    //      props.put("sasl.mechanism", "GSSAPI")
    //    }

    props
  }

}


/** Utility functions for Spark Streaming examples. */
object StreamingExamples extends Logging {

  /** Set reasonable logging levels for streaming if the user has not configured log4j. */
  def setStreamingLogLevels(level: Level) : Unit = {
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
  def createSparkSession(config: Config) : SparkSession = {
    var sparkBuilder = SparkSession.builder().appName(config.appName)

    if (config.isLocal) {
      logInfo("Running in local mode")
      sparkBuilder = sparkBuilder.master("local[1]")
    }

    sparkBuilder.getOrCreate()
  }

  def getParser(programName : String, isSource: Boolean) : scopt.OptionParser[Config] = {

    val parser = new scopt.OptionParser[Config](programName) {

      opt[String]("appName").action( (x, c) =>
        c.copy(appName = x) ).text("The application name to use for the Spark streaming app")

      opt[String]("brokers").required().action( (x, c) =>
        c.copy(brokers = x) ).text("The broker connection information")

      opt[String]("topics").required().action( (x, c) =>
        c.copy(topics = x) ).text("The comma-separated list of topics to use")

      opt[Unit]('k', "kerberized").action( (_, c) =>
        c.copy(kerberized = true) ).text("Enable Kerberized mode")

      opt[Unit]("isLocal").action( (_, c) =>
        c.copy(isLocal = true) ).text("Enable remote mode")

      opt[Int]("batchSizeSeconds").action( (x, c) =>
        c.copy(batchSizeSeconds = x.toLong) ).text("The window size to be used for the Spark streaming batch")

      if (isSource) {
        opt[Double]("wordsPerSecond").action( (x, c) =>
          c.copy(wordsPerSecond = x.toFloat) ).text("The rate at which words should be used to Kafka")
      } else {
        opt[Unit]("noCassandra").action( (_, c) =>
          c.copy(cassandra = false) ).text("Disable cassandra usage")

        opt[String]("groupId").action( (x, c) =>
          c.copy(groupId = x) ).text("The group ID for a consumer")

        opt[String]("cassandraKeyspace = ").action( (x, c) =>
          c.copy(cassandraKeyspace = x) ).text("The Cassandra keyspace to use")

        opt[String]("cassandraTable = ").action( (x, c) =>
          c.copy(cassandraTable = x) ).text("The Cassandra table to use")
      }


    }

    parser
  }
}
