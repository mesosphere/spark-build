package main

import (
	"encoding/json"
	"fmt"
	"testing"
)

const image = "mesosphere/spark"
const driverCores = "1"
const maxCores = "1"
const driverMemory = "512M"
const space = "TEST_SPACE"
const appJar = "http://spark-example.jar"
const mainClass = "org.apache.spark.examples.SparkPi"
const principal = "client@local"
const keytab_prefixed = "__dcos_base64__keytab"
const keytab = "keytab"

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

func TestPayloadSimple(t *testing.T) {
	inputArgs := fmt.Sprintf(
		"--driver-cores %s "+
			"--conf spark.cores.max=%s "+
			"--driver-memory %s "+
			"--class %s "+
			"%s --input1 value1 --input2 value2", driverCores, maxCores, driverMemory, mainClass, appJar)

	cmd := SparkCommand{
		"subId",
		inputArgs,
		image,
		space,
		make(map[string]string),
		"",
		false,
		false,
		0,
		"",
	}
	payload, err := buildSubmitJson(&cmd)

	m := make(map[string]interface{})

	json.Unmarshal([]byte(payload), &m)

	if err != nil {
		t.Errorf("%s", err.Error())
	}

	if m["appResource"] != "http://spark-example.jar" {
		t.Errorf("App resource incorrect, got %s, should be http://", m["appResource"])
	}

	if m["mainClass"] != mainClass {
		t.Errorf("mainClass should be %s got %s", mainClass, m["mainClass"])
	}

	//v := reflect.ValueOf(m["sparkProperties"])
	stringProps := map[string]string{
		"spark.driver.cores": driverCores,
		"spark.cores.max": maxCores,
		"spark.mesos.executor.docker.forcePullImage": "true",
		"spark.mesos.executor.docker.image": image,
		"spark.mesos.task.labels": fmt.Sprintf("DCOS_SPACE:%s", space),
		"spark.ssl.noCertVerification": "true",
		"spark.executor.memory": "1G", // default
		"spark.submit.deployMode": "cluster",
		"spark.mesos.driver.labels": fmt.Sprintf("DCOS_SPACE:%s", space),
		"spark.driver.memory": driverMemory,
		"spark.jars": appJar,
	}

	v, ok := m["sparkProperties"].(map[string]interface{})
	if !ok {
		t.Errorf("%s", ok)
	}

	checkProps(v, stringProps, t)
}

func checkProps(obs map[string]interface{}, expected map[string]string, t *testing.T) {
	for prop, value := range expected {
		setting, contains := obs[prop]
		if !contains {
			t.Errorf("Should have property %s", prop)
		}
		if setting != value {
			t.Errorf("config %s should be %s, got %s", prop, value, setting)
		}
	}
}

func checkSecret(secretPath, secretFile string, t *testing.T) {
	inputArgs := fmt.Sprintf(
		"--driver-cores %s "+
			"--kerberos-principal %s " +
			"--keytab-secret-path /%s " +
			"--conf spark.cores.max=%s "+
			"--driver-memory %s "+
			"--class %s "+
			"%s --input1 value1 --input2 value2",
		driverCores, principal, secretPath, maxCores, driverMemory, mainClass, appJar)

	cmd := SparkCommand{
		"subId",
		inputArgs,
		image,
		space,
		make(map[string]string),
		"",
		false,
		false,
		0,
		"",
	}
	payload, err := buildSubmitJson(&cmd)

	m := make(map[string]interface{})

	json.Unmarshal([]byte(payload), &m)

	if err != nil {
		t.Errorf("%s", err.Error())
	}

	v, ok := m["sparkProperties"].(map[string]interface{})
	if !ok {
		t.Errorf("%s", ok)
	}

	secretProps := map[string]string{
		"spark.yarn.principal": principal,
		"spark.mesos.containerizer": "mesos",
		"spark.mesos.driver.secret.filenames": secretFile,
		"spark.mesos.driver.secret.names": fmt.Sprintf("/%s", secretPath),
	}
	checkProps(v, secretProps, t)
}

func TestPayloadWithSecret(t *testing.T) {
	checkSecret(keytab, keytab, t)
	checkSecret(keytab_prefixed, keytab, t)
}
