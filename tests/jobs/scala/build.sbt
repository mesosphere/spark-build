lazy val root = (project in file("."))
  .settings(
    name := "dcos-spark-scala-tests",
    version := "0.2-SNAPSHOT",
    scalaVersion := "2.11.8",
    libraryDependencies ++= Seq(
      "org.apache.spark" %% "spark-core" % "2.2.0" % "provided",
      "org.apache.spark" % "spark-streaming_2.11" % "2.2.0" % "provided",
      "org.apache.spark" %% "spark-mllib" % "2.2.0" % "provided",
      "org.apache.spark" % "spark-streaming-kafka-0-10_2.11" % "2.2.0",
      "org.apache.hadoop" % "hadoop-aws" % "2.6.0",
      "org.apache.kafka" % "kafka_2.11" % "0.10.0.1",
      "com.github.scopt" %% "scopt" % "3.7.0",
      "com.datastax.spark" %% "spark-cassandra-connector" % "2.0.7"
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
