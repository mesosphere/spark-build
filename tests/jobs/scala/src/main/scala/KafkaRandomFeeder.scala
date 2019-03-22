import java.util.Properties
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.{Executors, TimeUnit}

import org.apache.kafka.clients.producer.{KafkaProducer, ProducerConfig, ProducerRecord}
import org.apache.log4j.Level
import org.apache.spark.internal.Logging
import org.apache.spark.streaming.scheduler.{StreamingListener, StreamingListenerReceiverStopped}
import org.apache.spark.streaming.{Seconds, StreamingContext}

object KafkaRandomFeeder extends Logging {

  sealed class ReceiverStreamingListener extends StreamingListener {
    private var isStopped = false

    override def onReceiverStopped(receiverStopped: StreamingListenerReceiverStopped): Unit = {
      logInfo("Receiver stopped, shutting down Streaming Context")
      isStopped = true
    }

    def receiverStopped: Boolean = isStopped
  }

  sealed class ContextReaper(receiverListener: ReceiverStreamingListener, ssc: StreamingContext) extends Runnable {
    override def run(): Unit = {
      if (receiverListener.receiverStopped) {
        //'stopGracefully' to drain received messages into Kafka
        ssc.stop(stopSparkContext = true, stopGracefully = true)
      }
    }
  }

  def main(args: Array[String]): Unit = {
    KafkaCassandraStream.setStreamingLogLevels(Level.WARN)

    //FIXME: shared parsing functionality should be generalized in a dedicated class
    val parser = KafkaCassandraStream.getParser(this.getClass.getSimpleName, true).parse(args, Config())

    if (parser.isEmpty) {
      logError("Bad arguments")
      System.exit(1)
    }

    val config = parser.get
    println(s"Using config: $config")

    //FIXME: shared functionality should be generalized in a dedicated class
    val spark = KafkaCassandraStream.createSparkSession(config)
    val streamingContext = new StreamingContext(spark.sparkContext, Seconds(config.batchSizeSeconds))

    //Handling context monitoring and termination in a dedicated thread pool
    val executorService = Executors.newScheduledThreadPool(1)
    val receiverListener = new ReceiverStreamingListener
    val contextReaper = new ContextReaper(receiverListener, streamingContext)

    streamingContext.addStreamingListener(receiverListener)

    /*
    TODO:
    in the long run, it makes sense to switch from Receiver approach to Driver-side publishing only
    to get accurate finite results and simpler design (without reaper tasks, several thread pools etc).

    Receiver is designed to be a long-running source without any control over the context lifecycle e.g. accept
    data via socket. Trying to keep it manageable makes the code too complicated for the task of just
    feeding Kafka with random data.

    @see KerberizedKafkaProducer for an example of Driver-side only Kafka publishing
    */
    val wordCounter = new AtomicLong(config.numberOfWords)
    val isInfiniteStream = config.numberOfWords == 0
    val accumulator = streamingContext.sparkContext.longAccumulator("words_sent")
    val randomWordReceiver = new RandomWordReceiver(config.wordsPerSecond, wordCounter, accumulator, infinite = isInfiniteStream)

    val stream = streamingContext.receiverStream(randomWordReceiver)

    val kafkaProperties = getKafkaProperties(config.brokers, config.isKerberized)
    println(s"${kafkaProperties}")
    val topic: String = config.topics

    stream.foreachRDD { rdd =>
      println(s"Handling streamed RDD of size ${rdd.count}")
      rdd.foreachPartition { partition =>
        val producer = new KafkaProducer[String, String](kafkaProperties)
        println(s"Handling streamed RDD partition")

        partition.foreach { word =>
          println(s"Writing $word to Kafka")
          val msg = new ProducerRecord[String, String](topic, null, word)
          producer.send(msg)
        }

        producer.close()
      }
    }

    executorService.scheduleAtFixedRate(contextReaper, 0, 100, TimeUnit.MILLISECONDS)
    streamingContext.start()
    streamingContext.awaitTermination()
    executorService.shutdown()
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
