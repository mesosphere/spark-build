import java.util

import KafkaFeeder.SmartySource
import org.apache.kafka.clients.producer.{KafkaProducer, ProducerConfig, ProducerRecord}
import org.apache.kafka.common.serialization.StringDeserializer
import org.apache.spark.{SparkConf, SparkContext}
import org.apache.spark.mllib.regression.LabeledPoint
import org.apache.spark.mllib.linalg.Vectors
import org.apache.spark.rdd.RDD
import org.apache.spark.streaming.{Seconds, StreamingContext, Time}
import org.apache.spark.streaming.kafka010.{ConsumerStrategies, KafkaUtils, LocationStrategies}

import scala.collection.mutable

object SpamHamModelFactory {
  def main(args: Array[String]): Unit = {
    if (args.length != 4) {
      throw new IllegalArgumentException("USAGE: <brokerlist> <topic> <stop_at> <use kerberos? [true/false]>")
    }

    val Array(brokers, topic, stopcount, kerberized) = args
    val conf = new SparkConf().setAppName("Kafka->Spark Validator Consumer")
    val ssc = new StreamingContext(conf, Seconds(2))

    println(s"Using brokers $brokers and topic $topic")

    val props = mutable.Map[String, Object](
      "bootstrap.servers" -> brokers,
      "key.deserializer" -> classOf[StringDeserializer],
      "value.deserializer" -> classOf[StringDeserializer],
      "group.id" -> "use_a_separate_group_id_for_each_stream",
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

object SpamHamProducer {
  def toLabeledPoint(sl: Seq[String]): Option[LabeledPoint] = {
    if (sl.head == "spam" || sl.head == "ham") {
      val label = if (sl.head == "spam") 1.0 else 0.0
      val features = sl.slice(1, sl.length)
      LabeledPoint(label, Vectors.dense(features.toArray))
    }
  }
  def main(args: Array[String]): Unit = {
    if (args.length != 4) {
      throw new IllegalArgumentException("USAGE: <brokerlist> <file> <topic> <use kerberos? [true/false]>")
    }
    val Array(brokers, infile, topic, kerberized) = args
    println(s"Got brokers $brokers, and producing to topic $topic")
    val conf = new SparkConf().setAppName("Spam/Ham Labeled Data Producer")
    val sc = new SparkContext(conf)
    val ssc = new StreamingContext(sc, Seconds(2))
    val data = sc.textFile(infile)
      .map(l => l.split(" "))

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
}


case class SMSMessage(spam: Int, words: Seq[String])
