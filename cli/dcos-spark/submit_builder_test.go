package main

import (
	"encoding/json"
	"fmt"
	"github.com/stretchr/testify/suite"
	"os"
	"testing"
)

const image = "mesosphere/spark"
const driverCores = "1"
const maxCores = "1"
const driverMemory = "512M"
const appJar = "http://spark-example.jar"
const mainClass = "org.apache.spark.examples.SparkPi"
const principal = "client@local"
const keytabPrefixed = "__dcos_base64__keytab"
const keytab = "keytab"
const sparkAuthSecret = "spark-auth-secret"
const marathonAppId = "spark-app"
var marathonConfig = map[string]interface{}{ "app": map[string]interface{}{ "id": marathonAppId }}

type CliTestSuite struct {
	suite.Suite
}

func (suite *CliTestSuite) SetupSuite() {
	// buildSubmitJson performs an internal lookup against core.ssl_verify to configure spark.ssl.noCertVerification:
	os.Setenv("DCOS_SSL_VERIFY", "false")
	// buildSubmitJson also fetches the service URL to configure spark.master:
	os.Setenv("DCOS_URL", "https://fake-url")
}
func TestCliTestSuite(t *testing.T) {
	suite.Run(t, new(CliTestSuite))
}

// test spaces
func (suite *CliTestSuite) TestCleanUpSubmitArgs() {
	_, args := sparkSubmitArgSetup()
	inputArgs := "--conf    spark.app.name=kerberosStreaming   --conf spark.cores.max=8"
	submitArgs, _ := cleanUpSubmitArgs(inputArgs, args.boolVals)
	if "--conf=spark.app.name=kerberosStreaming" != submitArgs[0] {
		suite.T().Errorf("Failed to reduce spaces while cleaning submit args.")
	}

	if "--conf=spark.cores.max=8" != submitArgs[1] {
		suite.T().Errorf("Failed to reduce spaces while cleaning submit args.")
	}
}

// test scopts pattern for app args when have full submit args
func (suite *CliTestSuite) TestScoptAppArgs() {
	_, args := sparkSubmitArgSetup()
	inputArgs := `--driver-cores 1 --conf spark.cores.max=1 --driver-memory 512M
  --class org.apache.spark.examples.SparkPi http://spark-example.jar --input1 value1 --input2 value2`
	submitArgs, appFlags := cleanUpSubmitArgs(inputArgs, args.boolVals)

	if "--input1" != appFlags[0] {
		suite.T().Errorf("Failed to parse app args.")
	}
	if "value1" != appFlags[1] {
		suite.T().Errorf("Failed to parse app args.")
	}

	if "--driver-memory=512M" != submitArgs[2] {
		suite.T().Errorf("Failed to parse submit args..")
	}
	if "http://spark-example.jar" != submitArgs[4] {
		suite.T().Errorf("Failed to parse submit args..")
	}
}

func createCommand(inputArgs, dockerImage string) SparkCommand {
	return SparkCommand{
		"subId",
		inputArgs,
		dockerImage,
		make(map[string]string),
		false,
		false,
		0,
		"",
		"",
		"",
		0.0,
		0.0,
		0,
		false,
		false,
	}
}

func (suite *CliTestSuite) TestPayloadSimple() {
	inputArgs := fmt.Sprintf(
		"--driver-cores %s "+
			"--conf spark.cores.max=%s "+
			"--driver-memory %s "+
			"--class %s "+
			"%s --input1 value1 --input2 value2", driverCores, maxCores, driverMemory, mainClass, appJar)

	cmd := createCommand(inputArgs, image)
	payload, err := buildSubmitJson(&cmd, marathonConfig)

	m := make(map[string]interface{})

	json.Unmarshal([]byte(payload), &m)

	if err != nil {
		suite.T().Errorf("%s", err.Error())
	}

	if m["appResource"] != "http://spark-example.jar" {
		suite.T().Errorf("App resource incorrect, got %s, should be http://", m["appResource"])
	}

	if m["mainClass"] != mainClass {
		suite.T().Errorf("mainClass should be %s got %s", mainClass, m["mainClass"])
	}

	stringProps := map[string]string{
		"spark.driver.cores": driverCores,
		"spark.cores.max": maxCores,
		"spark.mesos.executor.docker.forcePullImage": "true",
		"spark.mesos.executor.docker.image": image,
		"spark.mesos.task.labels": fmt.Sprintf("DCOS_SPACE:%s", marathonAppId),
		"spark.ssl.noCertVerification": "true",
		"spark.executor.memory": "1G", // default
		"spark.submit.deployMode": "cluster",
		"spark.mesos.driver.labels": fmt.Sprintf("DCOS_SPACE:%s", marathonAppId),
		"spark.driver.memory": driverMemory,
		"spark.jars": appJar,
	}

	v, ok := m["sparkProperties"].(map[string]interface{})
	if !ok {
		suite.T().Errorf("%+v", ok)
	}

	suite.checkProps(v, stringProps)
}

func (suite *CliTestSuite) TestPayloadCustomImageNoExecutor() {
	inputArgs := fmt.Sprintf(
		"--driver-cores %s "+
			"--conf spark.mesos.executor.docker.image=other "+
			"--conf spark.mesos.executor.docker.forcePullImage=false "+
			"--conf spark.cores.max=%s "+
			"--driver-memory %s "+
			"--class %s "+
			"%s --input1 value1 --input2 value2", driverCores, maxCores, driverMemory, mainClass, appJar)

	cmd := createCommand(inputArgs, "")
	payload, err := buildSubmitJson(&cmd, marathonConfig)

	m := make(map[string]interface{})

	json.Unmarshal([]byte(payload), &m)

	if err != nil {
		suite.T().Errorf("%s", err.Error())
	}

	if m["appResource"] != "http://spark-example.jar" {
		suite.T().Errorf("App resource incorrect, got %s, should be http://", m["appResource"])
	}

	if m["mainClass"] != mainClass {
		suite.T().Errorf("mainClass should be %s got %s", mainClass, m["mainClass"])
	}

	stringProps := map[string]string{
		"spark.driver.cores": driverCores,
		"spark.cores.max": maxCores,
		"spark.mesos.executor.docker.forcePullImage": "false",
		"spark.mesos.executor.docker.image": "other",
		"spark.mesos.task.labels": fmt.Sprintf("DCOS_SPACE:%s", marathonAppId),
		"spark.ssl.noCertVerification": "true",
		"spark.executor.memory": "1G", // default
		"spark.submit.deployMode": "cluster",
		"spark.mesos.driver.labels": fmt.Sprintf("DCOS_SPACE:%s", marathonAppId),
		"spark.driver.memory": driverMemory,
		"spark.jars": appJar,
	}

	v, ok := m["sparkProperties"].(map[string]interface{})
	if !ok {
		suite.T().Errorf("%+v", ok)
	}

	suite.checkProps(v, stringProps)
}

func (suite *CliTestSuite) checkProps(obs map[string]interface{}, expected map[string]string) {
	for prop, value := range expected {
		setting, contains := obs[prop]
		if !contains {
			suite.T().Errorf("Should have property %s", prop)
		}
		if setting != value {
			suite.T().Errorf("config %s should be %s, got %s", prop, value, setting)
		}
	}
}

func (suite *CliTestSuite) checkSecret(secretPath, secretFile string) {
	inputArgs := fmt.Sprintf(
		"--driver-cores %s "+
			"--kerberos-principal %s " +
			"--keytab-secret-path /%s " +
			"--conf spark.cores.max=%s "+
			"--driver-memory %s "+
			"--class %s "+
			"%s --input1 value1 --input2 value2",
		driverCores, principal, secretPath, maxCores, driverMemory, mainClass, appJar)

	cmd := createCommand(inputArgs, image)
	payload, err := buildSubmitJson(&cmd, marathonConfig)

	m := make(map[string]interface{})

	json.Unmarshal([]byte(payload), &m)

	if err != nil {
		suite.T().Errorf("%s", err.Error())
	}

	v, ok := m["sparkProperties"].(map[string]interface{})
	if !ok {
		suite.T().Errorf("%+v", ok)
	}

	secretProps := map[string]string{
		"spark.yarn.principal": principal,
		"spark.mesos.containerizer": "mesos",
		"spark.mesos.driver.secret.filenames": secretFile,
		"spark.mesos.driver.secret.names": fmt.Sprintf("/%s", secretPath),
	}
	suite.checkProps(v, secretProps)
}

func (suite *CliTestSuite) TestPayloadWithSecret() {
	suite.checkSecret(keytab, keytab)
	suite.checkSecret(keytabPrefixed, keytab)
}

func (suite *CliTestSuite) TestSaslSecret() {
	inputArgs := fmt.Sprintf(
		"--executor-auth-secret /%s " +
			"--class %s "+
			"%s --input1 value1 --input2 value2", sparkAuthSecret, mainClass, appJar)


	cmd := createCommand(inputArgs, image)
	payload, err := buildSubmitJson(&cmd, marathonConfig)

	m := make(map[string]interface{})

	json.Unmarshal([]byte(payload), &m)

	if err != nil {
		suite.T().Errorf("%s", err.Error())
	}

	stringProps := map[string]string{
		"spark.authenticate": "true",
		"spark.mesos.containerizer": "mesos",
		"spark.authenticate.enableSaslEncryption": "true",
		"spark.authenticate.secret": "spark_shared_secret",
		"spark.executorEnv._SPARK_AUTH_SECRET": "spark_shared_secret",
		"spark.mesos.driver.secret.filenames": sparkAuthSecret,
		"spark.mesos.driver.secret.names": fmt.Sprintf("/%s", sparkAuthSecret),
	}

	v, ok := m["sparkProperties"].(map[string]interface{})
	if !ok {
		suite.T().Errorf("%+v", ok)
	}

	suite.checkProps(v, stringProps)
}
