import scopt.OptionParser
import org.apache.spark.SparkContext
import org.apache.spark.SparkConf

/**
  * Application that exercises Mesos secrets and scopt and S3 reading/writing. Simply reads a file from an S3
  * location using the s3n:// schema, counts the lines in the file and writes the result back to the
  * designated s3 location. We use Mesos secrets to pass the credentials for AWS authentication and
  * authorization.
  *
  * Usage:
  * {SPARK} {ARGS} {PATH_TO_ASSEMBLY} --readUrl s3n://path/to/input --writeUrl s3n://path/to/output
  * where {SPARK} is either `dcos spark run` or `./bin/spark-submit`
  * {ARGS} are the configuration arguments to Spark. An example with Mesos secrets is below.
  * {PATH_TO_ASSEMBLY} is the location of the snapshot jar containing this application
  *
  * Example:
  * dcos spark run --submit-args="--conf spark.mesos.containerizer=mesos \
  * --conf spark.mesos.driver.secret.names=/aws-access-key,/aws-secret-key \
  * --conf spark.mesos.driver.secret.envkeys=AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY \
  * --class S3Job http://path-to-bucket/dcos-spark-scala-tests-assembly-0.1-SNAPSHOT.jar \
  * --readUrl s3n://my-bucket/linecount.txt --writeUrl s3n://my-bucket/output.txt"
  *
  */
object S3Job {
  def main(args: Array[String]): Unit = {
    object config {
      var readurl: String = null
      var writeurl: String = null
      // Optionally only read and don't write
      var countonly: Boolean = false
    }

    val parser = new OptionParser[Unit]("S3 Job") {
      opt[String]("readUrl").action((x, _) => config.readurl = x)
      opt[String]("writeUrl").action((x, _) => config.writeurl = x)
      opt[Unit]("countOnly").action((_, _) => config.countonly = true)
    }

    if (parser.parse(args)) {
      println("RUNNING S3 JOB")

      val sc = new SparkContext(new SparkConf().setAppName("S3 Test"))

      println(s"Reading from ${config.readurl}.  Writing to ${config.writeurl}.")

      val textRDD = sc.textFile(config.readurl)
      println(s"Read ${textRDD.count()} lines from ${config.readurl}.")

      if (config.writeurl != null) {
        textRDD.map(_.length).saveAsTextFile(config.writeurl)
        println(s"Wrote ${textRDD.count()} lines to ${config.writeurl}.")
      }

      sc.stop()
    } else {
      println("Error bad arguments")
      System.exit(1)
    }
  }
}
