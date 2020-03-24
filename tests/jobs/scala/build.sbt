lazy val SparkVersion = sys.env.getOrElse("SPARK_VERSION", "2.4.5")

lazy val root = (project in file("."))
  .settings(
    name := "dcos-spark-scala-tests",
    version := "0.2-SNAPSHOT",
    scalaVersion := "2.11.8",
    libraryDependencies ++= Seq(
      "org.apache.spark" %% "spark-core" % SparkVersion % "provided",
      "org.apache.spark" %% "spark-streaming" % SparkVersion % "provided",
      "org.apache.spark" %% "spark-sql" % SparkVersion % "provided",
      "org.apache.spark" %% "spark-mllib" % SparkVersion % "provided",
      "org.apache.spark" %% "spark-streaming-kafka-0-10" % SparkVersion,
      "org.apache.spark" %% "spark-sql-kafka-0-10" % SparkVersion,
      "org.apache.hadoop" % "hadoop-aws" % "2.9.2",
      "com.github.scopt" %% "scopt" % "3.7.1",
      "com.datastax.spark" %% "spark-cassandra-connector" % "2.0.7",
      "com.airbnb" % "kafka-statsd-metrics2" % "0.5.2+issue28" from "https://infinity-artifacts.s3.amazonaws.com/scale-tests/kafka-statsd-metrics2-0.5.2+issue28-20180612-8c1e3c4f3fa83.jar",
      "com.datadoghq" % "java-dogstatsd-client" % "2.5",
      "com.google.guava" % "guava" % "23.0" % "provided",
      "org.apache.httpcomponents" % "httpclient" % "4.5"
    )
  )

scalacOptions ++= Seq(
  "-deprecation",
  "-encoding", "UTF-8",
  "-feature",
  "-language:existentials",
  "-language:higherKinds",
  "-language:implicitConversions",
  "-language:experimental.macros",
  "-language:postfixOps",
  "-unchecked",
  "-Xlint",
  "-Yinline-warnings",
  "-Yno-adapted-args",
  "-Ywarn-dead-code",
  "-Ywarn-numeric-widen",
  "-Ywarn-unused-import",
  "-Xfuture")

assemblyMergeStrategy in assembly := {
  // https://github.com/sbt/sbt-assembly/issues/80#issuecomment-27927098
  case PathList("META-INF", "MANIFEST.MF") => MergeStrategy.discard
  case _ => MergeStrategy.first
}
