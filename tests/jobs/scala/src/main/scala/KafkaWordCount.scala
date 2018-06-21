import java.util.{Date}

import com.datastax.spark.connector._
import com.datastax.spark.connector.cql.CassandraConnector
import org.apache.kafka.clients.consumer.ConsumerConfig
import org.apache.kafka.common.serialization.StringDeserializer
import org.apache.log4j.{Level}
import org.apache.spark.internal.Logging
import org.apache.spark.streaming.kafka010.{ConsumerStrategies, KafkaUtils, LocationStrategies}
import org.apache.spark.streaming.{Seconds, StreamingContext}

object KafkaWordCount extends Logging {
  def main(args: Array[String]): Unit = {
    KafkaCassandraStream.setStreamingLogLevels(Level.WARN)

    val parser = KafkaCassandraStream.getParser(this.getClass.getSimpleName, false).parse(args, Config())

    if (parser.isEmpty) {
      logError("Bad arguments")
      System.exit(1)
    }

    val config = parser.get
    println(s"Using config: $config")

    val spark = KafkaCassandraStream.createSparkSession(config)

    val shouldWriteToCassandra: Boolean = config.shouldWriteToCassandra

    val keyspaceName = config.cassandraKeyspace
    val tableName = config.cassandraTable
    val cassandraColumns = SomeColumns("ts" as "_1", "word" as "_2", "count" as "_3")

    if (shouldWriteToCassandra) {
      CassandraConnector(spark.sparkContext.getConf).withSessionDo { session =>
        session.execute(s"""
          CREATE KEYSPACE IF NOT EXISTS $keyspaceName WITH REPLICATION = {
            'class': 'SimpleStrategy',
            'replication_factor': 3
          }
        """)
        session.execute(s"""
          CREATE TABLE IF NOT EXISTS $keyspaceName.$tableName (
            ts timestamp,
            word text,
            count int,
            PRIMARY KEY(word, ts)
          )
        """)
      }
    }

    val topicsSet = config.topics.split(",").toSet

    val kafkaParams = getKafkaProperties(config.brokers, config.groupId, config.isKerberized)

    val streamingContext = new StreamingContext(spark.sparkContext, Seconds(config.batchSizeSeconds))

    val messages = KafkaUtils.createDirectStream[String, String](
      streamingContext,
      LocationStrategies.PreferConsistent,
      ConsumerStrategies.Subscribe[String, String](topicsSet, kafkaParams)
    )

    // Get the lines, split them into words, count the words and print.
    val lines = messages.map(_.value)
    val words = lines.flatMap(_.split(" "))
    val wordCounts = words
      .map(x => (x, 1L))
      .reduceByKey(_ + _)

    if (shouldWriteToCassandra) {
      wordCounts.foreachRDD((rdd, time) => {
        println(s"Writing ${rdd.count} records to Cassandra with timestamp ${time}")
        rdd.map(x => (time.milliseconds, x._1, x._2)).saveToCassandra(keyspaceName, tableName, cassandraColumns)
      })
    }

    wordCounts.print()

    streamingContext.start()
    streamingContext.awaitTermination()
  }

  def getKafkaProperties(brokers : String, groupId: String, isKerberized: Boolean): Map[String, Object] = {
    val props = Map[String, Object](
      ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG -> brokers,
      ConsumerConfig.GROUP_ID_CONFIG -> groupId,
      ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG -> classOf[StringDeserializer],
      ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG -> classOf[StringDeserializer],
      // Values to match kafka service package server.properties
      ConsumerConfig.METRIC_REPORTER_CLASSES_CONFIG -> "com.airbnb.kafka.kafka09.StatsdMetricsReporter",
      "kafka.metric.reporters" -> "com.airbnb.kafka.kafka08.StatsdMetricsReporter",
      ConsumerConfig.METRICS_NUM_SAMPLES_CONFIG -> "2",
      ConsumerConfig.METRICS_SAMPLE_WINDOW_MS_CONFIG -> "30000",
      "external.kafka.statsd.reporter.enabled" -> "true",
      "external.kafka.statsd.tag.enabled" -> "true",
      "external.kafka.statsd.metrics.exclude_regex" -> ""
    ) ++ (
      if (isKerberized)
        Seq(
          ("sasl.kerberos.service.name" -> "kafka"),
          ("security.protocol" -> "SASL_PLAINTEXT"),
          ("sasl.mechanism" -> "GSSAPI")
        )
      else
        Nil
    )

    props
  }
}
