import java.util.concurrent.atomic.AtomicInteger
import java.util.{HashMap => JMap}

import org.apache.kafka.clients.producer._

import scala.collection.JavaConversions._
import scala.concurrent.duration._
import scala.concurrent.{Await, ExecutionContext, Future, Promise}
import scala.util.{Failure, Success}

/**
  * A simple Kafka Producer which should be used in the same way as kafka-console-producer with Kerberized
  * Kafka instance. The idea here is that producer runs as a driver without the need to launch executors.
  */
object KerberizedKafkaProducer {
  private val timeout = 3 minutes
  private val messageCounter = new AtomicInteger()

  def main(args: Array[String]): Unit = {
    if (args.length < 4) {
      throw new IllegalArgumentException("USAGE: <service name> <brokerlist> <topic> [message1, message2, ...]")
    }

    val Array(service, brokers, topic) = args.take(3)
    val messages = args.drop(3).toList
    println(s"Got brokers $brokers, producing ${messages.length} to topic $topic")
    try {
      withProducer(service, brokers, sendMessages(topic, messages))
    } catch {
      case t: Throwable =>
        t.printStackTrace()
    }
  }

  def withProducer(service: String, brokers: String, f: KafkaProducer[Int, String] => _): Unit = {
    val producer = getKafkaProducer(service, brokers)
    f(producer)
    producer.close()
  }

  def sendMessages(topic: String, messages: List[String])(producer: KafkaProducer[Int, String]): Unit = {
    import ExecutionContext.Implicits.global

    val futures = messages.map { str =>
      val msg = new ProducerRecord[Int, String](topic, str)
      sendMessage(producer, msg)
    }

    futures.foreach { future =>
      future.onComplete {
        case Success(metadata) =>
          println(s"Message has been published to (topic_partition@offset): ${metadata.toString}")
        case Failure(exception) => exception.printStackTrace()
      }
    }

    val resultFuture = Future.sequence(futures)
    Await.result(resultFuture, timeout)

    println(
      s"""
         |${messageCounter.get()} messages sent to Kafka
         |===========================================================================
         |Producer metrics by topic:
       """.stripMargin)

    producer.metrics.values
      .filter(m => m.metricName().group().equalsIgnoreCase("producer-topic-metrics"))
      .foreach(metric => println(metric.metricName().description() + ": " + metric.metricValue()))

    println(
      s"""
        |===========================================================================
        |Partition metadata for topic '$topic':
        |${producer.partitionsFor(topic).mkString("\n")}
      """.stripMargin)

  }

  /**
    * Wrapper method which converts Java Future returned by producer.send method to Scala Future
    */
  def sendMessage(producer: KafkaProducer[Int, String], record: ProducerRecord[Int, String]): Future[RecordMetadata] = {
    val promise = Promise[RecordMetadata]()
    producer.send(record, new Callback {
      override def onCompletion(metadata: RecordMetadata, exception: Exception): Unit = {
        if (exception != null) {
          promise.complete(Failure(exception))
        } else {
          messageCounter.incrementAndGet()
          promise.complete(Success(metadata))
        }
      }
    })
    promise.future
  }

  def getKafkaProducer(service: String, brokers: String): KafkaProducer[Int, String] = {
    val properties = new JMap[String, Object]()
    properties.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, brokers)
    properties.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, "org.apache.kafka.common.serialization.StringSerializer")
    properties.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, "org.apache.kafka.common.serialization.IntegerSerializer")
    properties.put("sasl.kerberos.service.name", service)
    properties.put("security.protocol", "SASL_PLAINTEXT")
    properties.put("sasl.mechanism", "GSSAPI")
    properties.put(ProducerConfig.ACKS_CONFIG, "all")
    properties.put(ProducerConfig.MAX_IN_FLIGHT_REQUESTS_PER_CONNECTION, "1")
    properties.put(ProducerConfig.RETRIES_CONFIG, "100")

    new KafkaProducer[Int, String](properties)
  }
}
