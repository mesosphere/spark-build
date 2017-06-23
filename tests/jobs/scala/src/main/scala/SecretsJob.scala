object SecretsJob {
  def main(args: Array[String]): Unit = {
    sys.env.foreach {
      case (key, value) => println(s"${key}:${value}")
    }

    if (args.length > 0) {
      val contents = scala.io.Source.fromFile(args(0)).mkString
      println(s"Contents of file ${args(0)}: ${contents}")
    }
  }
}
