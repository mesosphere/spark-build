lazy val root = (project in file("."))
  .settings(
    name := "dcos-spark-scala-tests",
    scalaVersion := "2.11.8",
    libraryDependencies ++= Seq(
      "org.apache.spark" %% "spark-core" % "2.1.0" % "provided",
      "org.apache.hadoop" % "hadoop-aws" % "2.6.0",
      "com.github.scopt" %% "scopt" % "3.7.0"
    )
  )

assemblyMergeStrategy in assembly := {
  // https://github.com/sbt/sbt-assembly/issues/80#issuecomment-27927098
  case PathList("META-INF", "MANIFEST.MF") => MergeStrategy.discard
  case _ => MergeStrategy.first
}
