package main

import "testing"

// test spaces
func TestCleanUpSubmitArgs(t *testing.T) {
  _, args := sparkSubmitArgSetup()
  inputArgs := "--conf    spark.app.name=kerberosStreaming   --conf spark.cores.max=8"
  submitArgs, _ := cleanUpSubmitArgs(inputArgs, args.boolVals)
    if "--conf=spark.app.name=kerberosStreaming" != submitArgs[0] {
       t.Errorf("Failed to reduce spaces while cleaning submit args.")
    }

    if "--conf=spark.cores.max=8" != submitArgs[1] {
       t.Errorf("Failed to reduce spaces while cleaning submit args.")
    }
}

// test scopts pattern for app args when have full submit args
func TestScoptAppArgs(t *testing.T) {
  _, args := sparkSubmitArgSetup()
  inputArgs := `--driver-cores 1 --conf spark.cores.max=1 --driver-memory 512M
  --class org.apache.spark.examples.SparkPi http://spark-example.jar --input1 value1 --input2 value2`
  submitArgs, appFlags := cleanUpSubmitArgs(inputArgs, args.boolVals)

  if "--input1" != appFlags[0] {
     t.Errorf("Failed to parse app args.")
  }
  if "value1" != appFlags[1] {
     t.Errorf("Failed to parse app args.")
  }

  if "--driver-memory=512M" != submitArgs[2] {
     t.Errorf("Failed to parse submit args..")
  }
  if "http://spark-example.jar" != submitArgs[4] {
     t.Errorf("Failed to parse submit args..")
  }
}
