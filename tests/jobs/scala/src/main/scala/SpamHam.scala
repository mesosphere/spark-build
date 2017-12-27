import java.util

import org.apache.kafka.clients.producer.{KafkaProducer, ProducerConfig, ProducerRecord}
import org.apache.kafka.common.serialization.StringDeserializer
import org.apache.spark.ml.{Pipeline, PipelineModel}
import org.apache.spark.ml.classification.NaiveBayes
import org.apache.spark.ml.evaluation.MulticlassClassificationEvaluator
import org.apache.spark.ml.feature._
import org.apache.spark.rdd.RDD
import org.apache.spark.sql._
import org.apache.spark.sql.{DataFrame, SparkSession}
import org.apache.spark.storage.StorageLevel
import org.apache.spark.streaming.kafka010.{ConsumerStrategies, KafkaUtils, LocationStrategies}
import org.apache.spark.streaming.{Seconds, StreamingContext, Time}
import org.apache.spark.streaming.receiver.Receiver

import scala.collection.mutable
import scala.util.Random

object SpamHamModelFactory {
  import SpamHamUtils._
  def spamOrHamPipeline(numFeatures: Int): Pipeline = {
    val stringIndexer = new StringIndexer()
      .setInputCol("spamorham")
      .setOutputCol("label")
    val tokenizer = new Tokenizer()
      .setInputCol("message")
      .setOutputCol("tokens")
    val hashingTF = new HashingTF()
      .setInputCol(tokenizer.getOutputCol)
      .setOutputCol("rawFeatures")
      .setNumFeatures(numFeatures)
    val idf = new IDF()
      .setInputCol(hashingTF.getOutputCol)
      .setOutputCol("features")
    val nb = new NaiveBayes()
    new Pipeline().setStages(Array(stringIndexer, tokenizer, hashingTF, idf, nb))
  }

  def parseTrainTestSplit(arg: String): Array[Double] = {
    val trainFraction = arg.toDouble
    val remaining = 1.0 - trainFraction
    Array(trainFraction, remaining)
  }

  def main(args: Array[String]): Unit = {
    if (args.length != 3) {
      throw new IllegalArgumentException("USAGE: <path_to_training_data> <train/test split> <output_model_path>")
    }

    val spark: SparkSession = SparkSession
      .builder()
      .appName("Spam Model Builder")
      .getOrCreate()

    // parse all of the training data together
    val dat = parseTrainingData(args(0), spark)
    val Array(train, test) = dat.randomSplit(parseTrainTestSplit(args(1)), seed = 1234L)
    // get the pipeline
    val pipeline = spamOrHamPipeline(128)  // 128 (2^7) works well from experimentation
    val model = pipeline.fit(train)
    // write the model to disk
    model.write.overwrite().save(args(2))
    val predictions = model.transform(test)
    evaluateModel(predictions)
  }
}

object SpamHam {
  def main(args: Array[String]): Unit = {
    val spark = SparkSession
      .builder()
      .appName("Spam/Ham SMS Classifier")
      .getOrCreate()

    val ssc = new StreamingContext(spark.sparkContext, Seconds(2))

    val Array(topic, brokers, modelUri) = args

    val model = PipelineModel.load(args(2))

    val props = mutable.Map[String, Object](
      "bootstrap.servers" -> brokers,
      "key.deserializer" -> classOf[StringDeserializer],
      "value.deserializer" -> classOf[StringDeserializer],
      "group.id" -> "use_a_separate_group_id_for_each_stream",
      "auto.offset.reset" -> "latest",
      "enable.auto.commit" -> (false: java.lang.Boolean)
    )

    println(s"using properties $props")

    val messages = KafkaUtils.createDirectStream[String, String](
      ssc,
      LocationStrategies.PreferConsistent,
      ConsumerStrategies.Subscribe[String, String](Array(topic), props))

    val lines = messages.map(_.value)
    lines.foreachRDD {
      (rdd: RDD[String], _: Time) =>
        val raw = spark.createDataFrame(SpamHamUtils.lineToRow(rdd), SpamHamUtils.SMSSchema)
        val predictions = model.transform(raw)
        predictions.show()
    }
    ssc.start()
    ssc.awaitTermination()
  }
}

object Spammer {
  class SpammySource(spam: Array[String], ham: Array[String], sentenceLength: Int, ratePerSec: Int)
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
        val p = Random.nextDouble()
        if (p > 0.5) {
          store(Random.shuffle(spam.toList).take(sentenceLength).mkString(" "))
        } else {
          store(Random.shuffle(ham.toList).take(sentenceLength).mkString(" "))
        }
        Thread.sleep((1000.toDouble / ratePerSec).toLong)
      }
    }
  }

  def main(args: Array[String]): Unit = {
    val spark = SparkSession
      .builder()
      .appName("Spammer")
      .getOrCreate()

    val Array(labeledMessages, topic, brokers) = args

    val ssc = new StreamingContext(spark.sparkContext, Seconds(2))

    val allMessages = spark.sparkContext.textFile(labeledMessages)

    val spam = allMessages.filter(_.startsWith("spam")).collect
    val ham = allMessages.filter(_.startsWith("ham")).collect

    // Kafka properties
    val props = new util.HashMap[String, Object]()
    props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, brokers)
    props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG,
      "org.apache.kafka.common.serialization.StringSerializer")
    props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG,
      "org.apache.kafka.common.serialization.StringSerializer")

    val stream = ssc.receiverStream(new SpammySource(spam, ham, 10, 1))
    stream.foreachRDD { rdd =>
      println(s"Number of events: ${rdd.count()}")
      rdd.foreachPartition { p =>
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

object SpamHamUtils {
  val SMSSchema: types.StructType = types.StructType(Array(
    types.StructField("spamorham", types.StringType, nullable = true),
    types.StructField("message", types.StringType, nullable = true)
  ))

  def lineToRow(line: RDD[String]): RDD[Row] = {
    line.map(_.split("\t")).map(r => Row(r.head, r.tail.mkString(" ")))
  }

  def parseTrainingData(p: String, s: SparkSession): DataFrame = {
    val rawRDD = s.sparkContext.textFile(p).map(_.split("\t")).map { r =>
      Row(r.head, r.tail.mkString(" "))
    }
    s.createDataFrame(rawRDD, SMSSchema)
  }

  def evaluateModel(predictions: DataFrame): Unit = {
    val evaluator = new MulticlassClassificationEvaluator()
      .setLabelCol("label")
      .setPredictionCol("prediction")
      .setMetricName("accuracy")
    val accuracy = evaluator.evaluate(predictions)
    println("Test set accuracy = " + accuracy)
  }
}

