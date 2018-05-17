import java.util.{Properties}

import org.apache.kafka.clients.producer.{KafkaProducer, ProducerConfig, ProducerRecord}
import org.apache.log4j.{Level}
import org.apache.spark.internal.Logging
import org.apache.spark.streaming.{Seconds, StreamingContext}

object KafkaRandomFeeder extends Logging {
  def main(args: Array[String]): Unit = {
    KafkaCassandraStream.setStreamingLogLevels(Level.WARN)

    val parser = KafkaCassandraStream.getParser(this.getClass.getSimpleName, true).parse(args, Config())

    if (parser.isEmpty) {
      logError("Bad arguments")
      System.exit(1)
    }

    val config = parser.get
    println(s"Using config: $config")

    val spark = KafkaCassandraStream.createSparkSession(config)

    val streamingContext = new StreamingContext(spark.sparkContext, Seconds(config.batchSizeSeconds))

    val stream = streamingContext.receiverStream(new RandomWordReceiver(config.wordsPerSecond, config.numberOfWords))

    val kafkaProperties = getKafkaProperties(config.brokers, config.isKerberized)
    println(s"${kafkaProperties}")
    val topic: String = config.topics

    stream.foreachRDD { rdd =>
      println(s"Handling streamed RDD of size ${rdd.count}")
      rdd.foreachPartition { partition =>
        val producer = new KafkaProducer[String, String](kafkaProperties)
        println(s"Handling streamed RDD partition")

        partition.foreach { word =>
          println(s"Writing ${word} to Kafka")
          val msg = new ProducerRecord[String, String](topic, null, word)
          producer.send(msg)
        }

        producer.close()
      }
    }

    streamingContext.start()
    streamingContext.awaitTermination()
  }


  def getKafkaProperties(brokers : String, isKerberized: Boolean): Properties = {
    val props = new Properties()
    props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, brokers)
    props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, "org.apache.kafka.common.serialization.StringSerializer")
    props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, "org.apache.kafka.common.serialization.StringSerializer")
    if (isKerberized) {
      props.put("sasl.kerberos.service.name", "kafka")
      props.put("security.protocol", "SASL_PLAINTEXT")
      props.put("sasl.mechanism", "GSSAPI")
    }

    props
  }
}
