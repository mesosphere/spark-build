import org.apache.spark.SparkContext
import org.apache.spark.SparkContext._
import org.apache.spark.SparkConf

object S3Job {
  def main(args: Array[String]): Unit = {
    val conf = new SparkConf().setAppName("S3 Test")
    val sc = new SparkContext(conf)

    val readURL = args(0)
    val writeURL = args(1)
    println(s"Reading from ${readURL}.  Writing to ${writeURL}.")

    val textRDD = sc.textFile(readURL)
    println(s"Read ${textRDD.count()} lines from${readURL}.")

    textRDD.map(_.length).saveAsTextFile(writeURL)
    println(s"Wrote ${textRDD.count()} lines to ${writeURL}.")

    sc.stop()
  }
}
