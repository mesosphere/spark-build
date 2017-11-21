package main

import (
    "testing"
	"strings"
)

// test spaces
func TestCleanUpSubmitArgs(t *testing.T) {
	_, args := sparkSubmitArgSetup()
	inputArgs := "--conf    spark.app.name=kerberosStreaming   --conf spark.cores.max=8"
	submitArgs, _ := cleanUpSubmitArgs(inputArgs, args.boolVals)
	if "--conf=spark.app.name=kerberosStreaming" != submitArgs[0] {
		t.Error("Failed to reduce spaces while cleaning submit args.")
	}

	if "--conf=spark.cores.max=8" != submitArgs[1] {
		t.Error("Failed to reduce spaces while cleaning submit args.")
	}
}

// test scopts pattern for app args when have full submit args
func TestScoptAppArgs(t *testing.T) {
	_, args := sparkSubmitArgSetup()
  	inputArgs := `--driver-cores 1 --conf spark.cores.max=1 --driver-memory 512M
  	--class org.apache.spark.examples.SparkPi http://spark-example.jar --input1 value1 --input2 value2`
  	submitArgs, appFlags := cleanUpSubmitArgs(inputArgs, args.boolVals)

  	if "--input1" != appFlags[0] {
  		t.Error("Failed to parse app args.")
	}
	if "value1" != appFlags[1] {
		t.Error("Failed to parse app args.")
	}

	if "--driver-memory=512M" != submitArgs[2] {
		t.Error("Failed to parse submit args..")
  	}
  	if "http://spark-example.jar" != submitArgs[4] {
  		t.Error("Failed to parse submit args..")
  		}
}


func testLongArgInternal(inputArgs string, expectedArgs []string, t *testing.T) {
	_, args := sparkSubmitArgSetup()  // setup
	submitargs, _ := cleanUpSubmitArgs(inputArgs, args.boolVals)
	if len(submitargs) != 2 {  // should have 1 arg that's all the java options and one that's the spark cores config
		t.Errorf("Failed to parse %s, should have 2 args, got %s", inputArgs, len(submitargs))
	}
	java_options_arg := submitargs[0]
	for i, a := range expectedArgs {
		if !strings.Contains(java_options_arg, a) {
			t.Errorf("Expected to find %s at index %d", a, i)
		}
	}
}

// test long args
func TestStringLongArgs(t *testing.T) {
	java_options := []string{"-Djava.firstConfig=firstSetting", "-Djava.secondConfig=secondSetting"}
	inputArgs := "--driver-java-options '-Djava.firstConfig=firstSetting -Djava.secondConfig=secondSetting' --conf spark.cores.max=8"
	testLongArgInternal(inputArgs, java_options, t)
	inputArgs = "--driver-java-options='-Djava.firstConfig=firstSetting -Djava.secondConfig=secondSetting' --conf spark.cores.max=8"
	testLongArgInternal(inputArgs, java_options, t)
	inputArgs = "--conf spark.driver.extraJavaOptions='-Djava.firstConfig=firstSetting -Djava.secondConfig=secondSetting' --conf spark.cores.max=8"
	testLongArgInternal(inputArgs, java_options, t)
	inputArgs = "--executor-java-options '-Djava.firstConfig=firstSetting -Djava.secondConfig=secondSetting' --conf spark.cores.max=8"
	testLongArgInternal(inputArgs, java_options, t)
	inputArgs = "--conf spark.executor.extraJavaOptions='-Djava.firstConfig=firstSetting -Djava.secondConfig=secondSetting' --conf spark.cores.max=8"
	testLongArgInternal(inputArgs, java_options, t)

	java_options = append(java_options, "-Djava.thirdConfig=thirdSetting")
	inputArgs = "--driver-java-option='-Djava.firstConfig=firstSetting -Djava.secondConfig=secondSetting -Djava.thirdConfig=thirdSetting' --conf spark.cores.max=8"
	testLongArgInternal(inputArgs, java_options, t)


}
