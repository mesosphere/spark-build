import org.apache.spark.{SparkConf, SparkContext}

object HDFSWordCount {
  def main(args: Array[String]): Unit = {
    val conf = new SparkConf()
    val sc = new SparkContext(conf)
    val file = args(0)
    val rdd = sc.textFile(file)
    print(s"number of words in ${file}: ${rdd.count()}")
  }
}
