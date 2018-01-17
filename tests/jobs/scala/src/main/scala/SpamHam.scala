import scala.util.Random
import java.util

import org.apache.spark.ml.classification.NaiveBayes
import org.apache.spark.ml.evaluation.MulticlassClassificationEvaluator
import org.apache.spark.ml.feature._
import org.apache.spark.ml.{Pipeline, PipelineModel}
import org.apache.spark.rdd.RDD
import org.apache.spark.sql.{DataFrame, SparkSession, _}
import org.apache.spark.storage.StorageLevel
import org.apache.spark.streaming.kafka010.{ConsumerStrategies, KafkaUtils, LocationStrategies}
import org.apache.spark.streaming.receiver.Receiver
import org.apache.spark.streaming.{Seconds, StreamingContext}
import org.apache.kafka.clients.producer.{KafkaProducer, ProducerConfig, ProducerRecord}
import org.apache.kafka.common.serialization.StringDeserializer
import org.apache.spark.SparkContext
import org.apache.spark.util.{DoubleAccumulator, LongAccumulator}


/**
  * Application that will train a model based on some labeled input. In this case we use a file with the
  * format:
  *   [spam/ham]\t[message]
  * where 'spam' or 'ham' is the label and the following message contains the features we would like to
  * classify with our model. The dataset we use to train the model can be downloaded at the UC-Irvine
  * ML Repository (https://archive.ics.uci.edu/ml/datasets/sms+spam+collection)
  *
  * Usage:
  * {SPARK} {ARGS} {PATH_TO_ASSEMBLY} [training_data] [train-test_split] [output_path]
  * where {SPARK} is either `dcos spark run` or `./bin/spark-submit`
  * {ARGS} are the configuration arguments to Spark (e.g. `--conf spark.cores.max=8` and Kerberos args for
  * saving to HDFS)
  * {PATH_TO_ASSEMBLY} is the location of the snapshot jar containing this application
  * [training_data] needs to be accessible to the driver, we recommend using the
  * `--conf spark.mesos.uris=[URI]` configuration to download the file to the driver's sandbox, see above
  * for the required format.
  *
  * Example:
  * dcos spark run --submit-args="{ARGS} --class SpamHamModelFactory \
  * http://path-to-bucket/dcos-spark-scala-tests-assembly-0.1-SNAPSHOT.jar \
  * file:///mnt/mesos/sandbox/SMSSpamCollection.txt 0.8 hdfs:///nb_model"
  *
  * Notes:
  * To save to HDFS, this application requires the hdfs-site.xml and core-site.xml configuration files
  * to be present in the HADOOP_CONF_DIR directory (`/etc/hadoop` by default). We also assume that {ARGS}
  * contains `--conf spark.mesos.uris=http://path/to/SMSSPamCollection.txt`
  *
  */
object SpamHamModelFactory {
  def main(args: Array[String]): Unit = {
    if (args.length != 3) {
      throw new IllegalArgumentException("USAGE: <path_to_training_data> <train/test split> <output_model_path>")
    }

    val spark: SparkSession = SparkSession
      .builder()
      .appName("Spam Model Builder")
      .getOrCreate()

    // parse all of the training data together
    val dat = SpamHamUtils.parseTrainingData(args(0), spark)
    val Array(train, test) = dat.randomSplit(parseTrainTestSplit(args(1)), seed = 1234L)
    // get the pipeline
    val pipeline = spamOrHamPipeline(128)  // 128 (2^7) works well from experimentation
    val model = pipeline.fit(train)
    // write the model to disk
    model.write.overwrite().save(args(2))
    val predictions = model.transform(test)
    SpamHamUtils.evaluateModel(predictions)
  }

  /**
    * Main pipeline for preparing our data and training the model. A full explanation of how
    * ML pipelines work in Spark can be found at the official documentation:
    * https://spark.apache.org/docs/latest/ml-pipeline.html
    * @return Ml Pipeline for training a Naive Bayes Spam classifier
    */
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
}

/**
  * Application that will send spam and ham messages to a kafka topic. Sends them in the same format
  * as we trained our model so that we can use the same pipeline.
  *
  * Usage:
  * {SPARK} {ARGS} {PATH_TO_ASSEMBLY} [path_to_labeled_data] [topic] [brokers] [kerberos [true/false]]
  * where {SPARK} is either `dcos spark run` or `./bin/spark-submit`
  * {ARGS} are the configuration arguments to Spark (e.g. `--conf spark.cores.max=8` and Kerberos args)
  * {PATH_TO_ASSEMBLY} is the location of the snapshot jar containing this application
  * [path_to_labeled_data] needs to be accessible to the driver, we recommend using the
  * `--conf spark.mesos.uris=[URI]` configuration to download the file to the driver's sandbox,
  * see above [[SpamHamModelFactory]] for the required format.
  *
  * Example:
  * dcos spark run --submit-args="{ARGS} --class Spammer \
  * http://path-to-bucket/dcos-spark-scala-tests-assembly-0.1-SNAPSHOT.jar \
  * file:///mnt/mesos/sandbox/SMSSpamCollection.txt top1 \
  * kafka-0-broker.kafka.autoip.dcos.thisdcos.directory:1025 false"
  *
  * Notes:
  * This application assumes that that {ARGS} contains
  * `--conf spark.mesos.uris=http://path/to/SMSSPamCollection.txt`
  *
  */
object Spammer {
  def main(args: Array[String]): Unit = {
    if (args.length != 4) {
      throw new IllegalArgumentException("USAGE: <path_to_labeled_data> <topic> <brokers> <Kerberos true/false>")
    }

    val spark = SparkSession
      .builder()
      .appName("Spammer")
      .getOrCreate()

    val Array(labeledMessages, topic, brokers, kerberized) = args

    val ssc = new StreamingContext(spark.sparkContext, Seconds(2))

    val allMessages = spark.sparkContext.textFile(labeledMessages)
    val spamCounts = cullWordCounts(allMessages, "spam")
    val hamCounts = cullWordCounts(allMessages, "ham")

    // The kafka producer requires a Java HashMap
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

    val stream = ssc.receiverStream(new MessageSource(spamCounts.collect, hamCounts.collect, 15, 1))

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

  def cullWordCounts(lines: RDD[String], label: String): RDD[(String, Int)] = {
    lines.filter(_.startsWith(label))
      .map(_.split("\t"))
      .map(l => l.tail.mkString(" "))
      .flatMap(_.split(" "))
      .map(w => (w, 1))
      .reduceByKey(_ + _)
  }

  class MessageSource(
      spamCounts: Array[(String, Int)],
      hamCounts: Array[(String, Int)],
      sentenceLength: Int,
      ratePerSec: Int) extends Receiver[String](StorageLevel.MEMORY_AND_DISK_2) {

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

    private def receive(): Unit = {
      while (!isStopped()) {
        val p = Random.nextDouble()
        val (label, sampled): (String, Seq[String]) = if (p > 0.5) {
          ("spam", SpamHamUtils.weightedSample(spamCounts, sentenceLength))
        } else {
          ("ham", SpamHamUtils.weightedSample(hamCounts, sentenceLength))
        }
        val message: String = s"$label\t${sampled.mkString(" ")}"
        store(message)
        Thread.sleep((1000.toDouble / ratePerSec).toLong)
      }
    }
  }
}

/**
  * Application that will use a pre-trained model (loaded from S3 or HDFS) and classify messages on the fly
  * by subscribing to a Kafka topic and classifying the messages that are published to that topic.
  *
  * Usage:
  * {SPARK} {ARGS} {PATH_TO_ASSEMBLY} [topic] [brokers] [modelUri [hdfs:// or s3n://]] [kerberos [true/false]]
  * where {SPARK} is either `dcos spark run` or `./bin/spark-submit`
  * {ARGS} are the configuration arguments to Spark (e.g. `--conf spark.cores.max=8` and Kerberos args)
  * {PATH_TO_ASSEMBLY} is the location of the snapshot jar containing this application
  *
  * Example:
  * dcos spark run --submit-args="{ARGS} --class SpamHamStreamingClassifier \
  * http://path-to-bucket/dcos-spark-scala-tests-assembly-0.1-SNAPSHOT.jar \
  * top1 kafka-0-broker.kafka.autoip.dcos.thisdcos.directory:1025 hdfs:///nb_model false"
  *
  */
object SpamHamStreamingClassifier {
  def main(args: Array[String]): Unit = {
    if (args.length != 4) {
      throw new IllegalArgumentException("USAGE: <topic> <brokers> <modelURI> <Kerberos true/false>")
    }

    val spark = SparkSession
      .builder()
      .appName("Spam/Ham SMS Classifier")
      .getOrCreate()

    // make a streaming context, load the model
    val ssc = new StreamingContext(spark.sparkContext, Seconds(2))
    val Array(topic, brokers, modelUri, kerberized) = args
    val model = PipelineModel.load(modelUri)

    val basicProps = Map[String, Object](
      "bootstrap.servers" -> brokers,
      "key.deserializer" -> classOf[StringDeserializer],
      "value.deserializer" -> classOf[StringDeserializer],
      "group.id" -> "use_a_separate_group_id_for_each_stream",
      "auto.offset.reset" -> "latest",
      "enable.auto.commit" -> (false: java.lang.Boolean)
    )

    val kerbProps = Map[String, Object](
      "sasl.kerberos.service.name" -> "kafka",
      "security.protocol" -> "SASL_PLAINTEXT",
      "sasl.mechanism" -> "GSSAPI"
    )

    val props = if (kerberized == "true") {
      basicProps ++ kerbProps
    } else {
      basicProps
    }

    val messages = KafkaUtils.createDirectStream[String, String](
      ssc,
      LocationStrategies.PreferConsistent,
      ConsumerStrategies.Subscribe[String, String](Array(topic), props))

    val lines = messages.map(_.value)
    lines.foreachRDD { rdd: RDD[String] =>
        val raw = spark.createDataFrame(SpamHamUtils.lineToRow(rdd), SpamHamUtils.SMSSchema)
        val predictions = model.transform(raw)
        val correct = CorrectAccumulator.getInstance(rdd.sparkContext)
        val total = TrialCounter.getInstance(rdd.sparkContext)
        predictions.foreach { r =>
          val label = r.getAs[Double](2)
          val prediction = r.getAs[Double](8)
          if (prediction == label) correct.add(1)
          total.add(1)
        }
        println(s"Running accuracy ${correct.value.toFloat / total.value}")
    }
    ssc.start()
    ssc.awaitTermination()
  }
}

object CorrectAccumulator {
  @volatile private var instance: DoubleAccumulator = null
  def getInstance(sc: SparkContext): DoubleAccumulator = {
    if (instance == null) {
      synchronized {
        if (instance == null) {
          instance = sc.doubleAccumulator("Accuracy")
        }
      }
    }
    instance
  }
}

object TrialCounter {
  @volatile private var instance: LongAccumulator = null
  def getInstance(sc: SparkContext): LongAccumulator = {
    if (instance == null) {
      synchronized {
        if (instance == null) {
          instance = sc.longAccumulator("Counter")
        }
      }
    }
    instance
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

  def evaluateModel(predictions: DataFrame): Double = {
    val evaluator = new MulticlassClassificationEvaluator()
      .setLabelCol("label")
      .setPredictionCol("prediction")
      .setMetricName("accuracy")
    val accuracy = evaluator.evaluate(predictions)
    println("Test set accuracy = " + accuracy)
    accuracy
  }

  /**
    * Randomly Sample from an array weighted by how frequently the element occurs
    */
  def weightedSample(wordCounts: Array[(String, Int)], sampleCount: Int): Seq[String] = {
    def selectInternal(acc: Int): String = {
      val shuffled = Random.shuffle[(String, Int), Seq](wordCounts)
      var _r = acc
      for ((w, c) <- shuffled) {
        _r -= c
        if (_r <= 0) {
          return w
        }
      }
      ""
    }

    val totalWeight = wordCounts.foldLeft(0)((ac, t) => ac + t._2)
    (0 until sampleCount).map { i =>
      val r = Random.nextInt(totalWeight)
      selectInternal(r)
    }
  }
}

