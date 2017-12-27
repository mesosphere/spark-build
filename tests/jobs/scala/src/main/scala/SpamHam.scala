import org.apache.spark.ml.Pipeline
import org.apache.spark.ml.classification.NaiveBayes
import org.apache.spark.ml.evaluation.MulticlassClassificationEvaluator
import org.apache.spark.ml.feature._
import org.apache.spark.sql._
import org.apache.spark.sql.{DataFrame, SparkSession}

object SpamHamModelFactory {
  def parseTrainingData(p: String, s: SparkSession): DataFrame = {
    val schema: types.StructType = types.StructType(Array(
      types.StructField("spamorham", types.StringType, nullable = true),
      types.StructField("message", types.StringType, nullable = true)
    ))
    val rawRDD = s.sparkContext.textFile(p).map(_.split("\t")).map { r =>
      Row(r.head, r.tail.mkString(" "))
    }
    s.createDataFrame(rawRDD, schema)
  }

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

  def evaluateModel(predictions: DataFrame): Unit = {
    val evaluator = new MulticlassClassificationEvaluator()
      .setLabelCol("label")
      .setPredictionCol("prediction")
      .setMetricName("accuracy")
    val accuracy = evaluator.evaluate(predictions)
    println("Test set accuracy = " + accuracy)
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
    val dat: DataFrame = parseTrainingData(args(0), spark)
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

