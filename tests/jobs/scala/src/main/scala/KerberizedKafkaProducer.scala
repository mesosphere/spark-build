import java.util.{HashMap => JMap}

import org.apache.kafka.clients.producer.{Callback, KafkaProducer, ProducerRecord, RecordMetadata, ProducerConfig}

import scala.collection.JavaConversions._

/**
  * A simple Kafka Producer which should be used in the same way as kafka-console-producer with Kerberized
  * Kafka instance. The idea here is that producer runs as a driver without the need to launch executors.
  */
object KerberizedKafkaProducer {
  def main(args: Array[String]): Unit = {
    if (args.length < 4) {
      throw new IllegalArgumentException("USAGE: <service name> <brokerlist> <topic> [message1, message2, ...]")
    }

    val Array(service, brokers, topic) = args.take(3)
    val messages = args.drop(3)
    println(s"Got brokers $brokers, producing ${messages.length} to topic $topic")
    try {
      withProducer(service, brokers, sendMessages(topic, messages))
    } catch {
      case t: Throwable =>
        t.printStackTrace()
    }

    println(s"${messages.length} messages sent to Kafka")
  }

  def withProducer(service: String, brokers: String, f: KafkaProducer[Int, String] => _): Unit = {
    val producer = getKafkaProducer(service, brokers)
    f(producer)
    producer.close()
  }

  def sendMessages(topic: String, messages: Array[String])(producer: KafkaProducer[Int, String]): Unit = {
    messages.foreach { str =>
      val msg = new ProducerRecord[Int, String](topic, str)
      println(s"sending message: $msg")

      producer.send(msg, new Callback {
      override def onCompletion(metadata: RecordMetadata, exception: Exception): Unit = {
        if (exception != null) {
          exception.printStackTrace()
        } else {
          println(s"Message has been published to (topic_partition@offset): ${metadata.toString}")
        }
      }
      })
    }
    Thread.sleep(3000) // wait a few seconds for metrics update
    println("===========================================================================")
    println("Producer metrics by topic:")
    producer.metrics.values
      .filter(m => m.metricName().group().equalsIgnoreCase("producer-topic-metrics"))
      .foreach(metric => println(metric.metricName().description() + ": " + metric.metricValue()))
    println("===========================================================================")
    println(s"Partition metadata for topic '$topic':")
    producer.partitionsFor(topic).foreach(p => println(p))
  }

  def getKafkaProducer(service: String, brokers: String): KafkaProducer[Int, String] = {
    val properties = new JMap[String, Object]()
    properties.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, brokers)
    properties.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, "org.apache.kafka.common.serialization.StringSerializer")
    properties.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, "org.apache.kafka.common.serialization.IntegerSerializer")
    properties.put("sasl.kerberos.service.name", service)
    properties.put("security.protocol", "SASL_PLAINTEXT")
    properties.put("sasl.mechanism", "GSSAPI")

    new KafkaProducer[Int, String](properties)
  }
}
