import java.util

import scala.collection.mutable
import scala.util.Random

import org.apache.kafka.clients.producer.{KafkaProducer, ProducerConfig, ProducerRecord}
import org.apache.kafka.common.serialization.StringDeserializer

import org.apache.spark.rdd.RDD
import org.apache.spark.storage.StorageLevel
import org.apache.spark.streaming.kafka010._
import org.apache.spark.streaming.receiver._
import org.apache.spark.streaming.{Seconds, StreamingContext, Time}
import org.apache.spark.util.LongAccumulator
import org.apache.spark.{SparkConf, SparkContext}


/**
  * Application that will download a file, count the number of unique words and feed random 'sentences'
  * into a topic on an optionally Kerberos-secured Kafka cluster
  *
  * Usage:
  * {SPARK} {ARGS} {PATH_TO_ASSEMBLY} [brokerlist] [file] [topic] [use kerberos? [true/false]]
  * where {SPARK} is either `dcos spark run` or `./bin/spark-submit`
  * {ARGS} are the configuration arguments to Spark (e.g. `--conf spark.cores.max=8`)
  * {PATH_TO_ASSEMBLY} is the location of the snapshot jar containing this application
  * [file] needs to be accessible to the driver, we recommend using the `--conf spark.mesos.uris=[URI]`
  * configuration to download the file to the driver's sandbox.
  *
  * Example:
  * dcos spark run --submit-args="{ARGS} --class KafkaFeeder \
  * http://path-to-bucket/dcos-spark-scala-tests-assembly-0.1-SNAPSHOT.jar \
  * kafka-0-broker.secure-kafka.autoip.dcos.thisdcos.directory:1025 file:///mnt/mesos/sandbox/big.txt top1 false"
  *
  * this assumes that {ARGS} contains `--conf spark.mesos.uris=http://norvig.com/big.txt`
  */
object KafkaFeeder {
  def main(args: Array[String]): Unit = {
    if (args.length != 4) {
      throw new IllegalArgumentException("USAGE: <brokerlist> <file> <topic> <use kerberos? [true/false]>")
    }
    val Array(brokers, infile, topic, kerberized) = args
    println(s"Got brokers $brokers, and producing to topic $topic")
    val conf = new SparkConf().setAppName("Spark->Kafka Producer")
    val sc = new SparkContext(conf)
    val ssc = new StreamingContext(sc, Seconds(2))
    val words = sc.textFile(infile).flatMap(l => l.split(" "))
      .map(w => (w, 1))
      .reduceByKey(_ + _)
      .map(t => t._1)
    println(s"Got ${words.count} unique words")
    val stream = ssc.receiverStream(new SmartySource(words.collect, 4, 1))
    stream.foreachRDD { rdd =>
      println(s"Number of events: ${rdd.count()}")
      rdd.foreachPartition { p =>
        val props = new util.HashMap[String, Object]()
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, brokers)
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG,
          "org.apache.kafka.common.serialization.StringSerializer")
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG,
          "org.apache.kafka.common.serialization.StringSerializer")
        if (kerberized ==  "true") {
          props.put("sasl.kerberos.service.name", "kafka")
          props.put("security.protocol", "SASL_PLAINTEXT")
          props.put("sasl.mechanism", "GSSAPI")
        }
        val producer = new KafkaProducer[String, String](props)
        p.foreach { r =>
          val d = r.toString()
          val msg = new ProducerRecord[String, String](topic, null, d)
          producer.send(msg)
        }
        producer.close()
      }
    }

    ssc.start()
    ssc.awaitTermination()
  }

  class SmartySource(words: Array[String], sentenceLength: Int, ratePerSec: Int)
    extends Receiver[String](StorageLevel.MEMORY_AND_DISK_2) {

    def onStart(): Unit = {
      // Start the thread that receives data over a connection
      new Thread("Dummy Source") {
        override def run(): Unit = {
          receive()
        }
      }.start()
    }

    def onStop(): Unit = {
      // There is nothing much to do as the thread calling receive()
      // is designed to stop by itself isStopped() returns false
    }

    /** Create a socket connection and receive data until receiver is stopped */
    private def receive(): Unit = {
      while(!isStopped()) {
        // could do something where you wait for the sentence length to get so long
        // and you add words with their frequency probability
        store(Random.shuffle(words.toList).take(sentenceLength).mkString(" "))
        Thread.sleep((1000.toDouble / ratePerSec).toLong)
      }
    }
  }
}

/**
  * Application that will subscribe to a topic on an optionally Kerberos-secured Kafka cluster and count
  * the words in the stream until a given number of words are seen.
  *
  * Usage:
  * {SPARK} {ARGS} {PATH_TO_ASSEMBLY} [brokerlist] [topic] [stop_at] [use kerberos? [true/false]]
  * where {SPARK} is either `dcos spark run` or `./bin/spark-submit`
  * {ARGS} are the configuration arguments to Spark (e.g. `--conf spark.cores.max=8`)
  * {PATH_TO_ASSEMBLY} is the location of the snapshot jar containing this application
  * [topic] should be the same as used with KafkaFeeder above.
  * [stop_at] should be a 20-1000 depending on how long you want the job to last
  *
  * Example:
  * dcos spark run --submit-args="{ARGS} --class KafkaConsumer \
  * http://path-to-bucket/dcos-spark-scala-tests-assembly-0.1-SNAPSHOT.jar \
  * kafka-0-broker.secure-kafka.autoip.dcos.thisdcos.directory:1025 top1 100 false"
  *
  */
object KafkaConsumer {
  def main(args: Array[String]): Unit = {
    if (args.length != 4) {
      throw new IllegalArgumentException("USAGE: <brokerlist> <topic> <stop_at> <use kerberos? [true/false]>")
    }

    val Array(brokers, topic, stopcount, kerberized) = args
    val conf = new SparkConf().setAppName("Kafka->Spark Validator Consumer")
    val ssc = new StreamingContext(conf, Seconds(2))

    // unique group ids allow multiple consumers to simultaneously read from the same topic
    val groupId = System.currentTimeMillis().toString

    println(s"Using brokers $brokers and topic $topic for group $groupId")

    val props = mutable.Map[String, Object](
      "bootstrap.servers" -> brokers,
      "key.deserializer" -> classOf[StringDeserializer],
      "value.deserializer" -> classOf[StringDeserializer],
      "group.id" -> s"group-$groupId",
      "auto.offset.reset" -> "latest",
      "enable.auto.commit" -> (false: java.lang.Boolean)
    )

    if (kerberized == "true") {
      val kerbProps = Map[String, Object](
        "sasl.kerberos.service.name" -> "kafka",
        "security.protocol" -> "SASL_PLAINTEXT",
        "sasl.mechanism" -> "GSSAPI"
      )

      props ++= kerbProps
    }

    println(s"using properties $props")

    val messages = KafkaUtils.createDirectStream[String, String](
      ssc,
      LocationStrategies.PreferConsistent,
      ConsumerStrategies.Subscribe[String, String](Array(topic), props))

    val lines = messages.map(_.value)
    val words = lines.flatMap(_.split(" "))
    val wordCounts = words.map(x => (x, 1L)).reduceByKey(_ + _)
    wordCounts.foreachRDD { (rdd: RDD[(String, Long)], time: Time) =>
      val totalCount = WordAccumulator.getInstance(rdd.sparkContext)
      rdd.foreach { case (w, c) => totalCount.add(c) }
      if (totalCount.value >= stopcount.toLong) {
        println(s"Read $stopcount words")
        ssc.stop(true, false)
      }
      println(s"total count is ${totalCount.value}")
    }
    wordCounts.print()

    // Start the computation
    ssc.start()
    ssc.awaitTermination()
  }
}

/**
  * Accumulator for total words seen by the consumer, so we can shutdown the stream after seeing
  * a given number of words. See https://spark.apache.org/docs/2.2.0/rdd-programming-guide.html#accumulators
  * for details on accumulators.
  */
object WordAccumulator {
  @volatile private var instance: LongAccumulator = null
  def getInstance(sc: SparkContext): LongAccumulator = {
    if (instance == null) {
      synchronized {
        if (instance == null) {
          instance = sc.longAccumulator("WordAccumulator")
        }
      }
    }
    instance
  }
}


