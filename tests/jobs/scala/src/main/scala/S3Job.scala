import org.apache.spark.sql.SparkSession

/**
  * Application that exercises Mesos secrets and scopt and S3 reading/writing. Simply reads a file from an S3
  * location using the s3a:// schema, counts the lines in the file and writes the result back to the
  * designated s3 location. We use Mesos secrets to pass the credentials for AWS authentication and
  * authorization.
  *
  * Usage:
  * {SPARK} {ARGS} {PATH_TO_ASSEMBLY} --readUrl s3a://path/to/input --writeUrl s3a://path/to/output
  * where {SPARK} is either `dcos spark run` or `./bin/spark-submit`
  * {ARGS} are the configuration arguments to Spark. An example with Mesos secrets is below.
  * {PATH_TO_ASSEMBLY} is the location of the snapshot jar containing this application
  *
  * Example:
  * dcos spark run --submit-args="--conf spark.mesos.containerizer=mesos \
  * --conf spark.mesos.driver.secret.names=/aws-access-key,/aws-secret-key \
  * --conf spark.mesos.driver.secret.envkeys=AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY \
  * --class S3Job http://path-to-bucket/dcos-spark-scala-tests-assembly-0.1-SNAPSHOT.jar \
  * --readUrl s3a://my-bucket/linecount.txt --writeUrl s3a://my-bucket/output.txt"
  *
  */

case class Args(readUrl: String = null,
                  writeUrl: String = null)

object S3Job {

  private val parser = new scopt.OptionParser[Args]("S3Job") {
    head("Test S3 integration", "0.1")
    opt[String]("readUrl") required() action { (x, a) => a.copy(readUrl = x) } text "s3 bucket to read from"
    opt[String]("writeUrl") optional() action { (x, a) => a.copy(writeUrl = x) } text "s3 bucket to write to"
  }

  def main(args: Array[String]): Unit = {

    parser.parse(args, Args()) match {
      case Some(args) =>
        readS3(args)

      case None =>
        println(parser.usage)
        System.exit(1)
    }

  }

    private def readS3(args: Args): Unit = {
      val spark = SparkSession
        .builder
        .appName("S3 Test")
        .getOrCreate()

      val sc = spark.sparkContext

      println(s"Reading from ${args.readUrl}.  Writing to ${args.writeUrl}.")

      val textRDD = sc.textFile(args.readUrl)
      println(s"Read ${textRDD.count()} lines from ${args.readUrl}.")

      if (args.writeUrl != null) {
        textRDD.map(_.length).saveAsTextFile(args.writeUrl)
        println(s"Wrote ${textRDD.count()} lines to ${args.writeUrl}.")
      }

      sc.stop()
    }
}
