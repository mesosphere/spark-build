import scopt.OptionParser
import org.apache.spark.SparkContext
import org.apache.spark.SparkContext._
import org.apache.spark.SparkConf

object S3Job {
  def main(args: Array[String]): Unit = {
    object config {
      var readurl: String = null
      var writeurl: String = null
      var countonly: Boolean = false
    }

    val parser = new OptionParser[Unit]("S3 Job") {
      opt[String]("readUrl").action((x, _) => config.readurl = x)
      opt[String]("writeUrl").action((x, _) => config.writeurl = x)
      opt[Unit]("countOnly").action((_, _) => config.countonly = true)
    }

    if (parser.parse(args)) {
      println("RUNNING S3 JOB")
      val conf = new SparkConf().setAppName("S3 Test")
      val sc = new SparkContext(conf)

      val readURL = config.readurl
      val writeURL = config.writeurl

      println(s"Reading from ${readURL}.  Writing to ${writeURL}.")

      val textRDD = sc.textFile(readURL)
      println(s"Read ${textRDD.count()} lines from ${readURL}.")

      textRDD.map(_.length).saveAsTextFile(writeURL)
      println(s"Wrote ${textRDD.count()} lines to ${writeURL}.")

      sc.stop()
    } else {
      println("Error bad arguments")
      System.exit(1)
    }
  }
}
