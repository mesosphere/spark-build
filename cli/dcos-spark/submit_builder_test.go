package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/suite"
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
const sparkAuthSecretPath = "path/to/spark-auth-secret"
const marathonAppId = "spark-app"

var marathonConfig = map[string]interface{}{"app": map[string]interface{}{"id": marathonAppId}}

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
func (suite *CliTestSuite) TestTransformSubmitArgs() {
	_, args := sparkSubmitArgSetup()
	inputArgs := "--conf    spark.app.name=kerberosStreaming   --conf spark.cores.max=8 main.jar 100"
	submitArgs, _ := transformSubmitArgs(inputArgs, args.boolVals)
	if "--conf=spark.app.name=kerberosStreaming" != submitArgs[0] {
		suite.T().Errorf("Failed to reduce spaces while cleaning submit args.")
	}

	if "--conf=spark.cores.max=8" != submitArgs[1] {
		suite.T().Errorf("Failed to reduce spaces while cleaning submit args.")
	}
}

func (suite *CliTestSuite) TestTransformSubmitArgsWithMulitpleValues() {
	_, args := sparkSubmitArgSetup()
	inputArgs := "--conf spark.driver.extraJavaOptions='-XX:+PrintGC -Dparam1=val1 -Dparam2=val2' main.py 100"
	expected := "--conf=spark.driver.extraJavaOptions=-XX:+PrintGC -Dparam1=val1 -Dparam2=val2"
	actual, _ := transformSubmitArgs(inputArgs, args.boolVals)
	assert.Equal(suite.T(), expected, actual[0])
}

func (suite *CliTestSuite) TestTransformSubmitArgsWithSpecialCharacters() {
	_, args := sparkSubmitArgSetup()
	inputArgs := "--conf spark.driver.extraJavaOptions='-Dparam1=\"val 1?\" -Dparam2=val\\ 2! -Dmulti.dot.param3=\"val\\ 3\" -Dpath=$PATH' main.py 100"
	expected := "--conf=spark.driver.extraJavaOptions=-Dparam1=\"val 1?\" -Dparam2=val\\ 2! -Dmulti.dot.param3=\"val\\ 3\" -Dpath=$PATH"
	actual, _ := transformSubmitArgs(inputArgs, args.boolVals)
	assert.Equal(suite.T(), expected, actual[0])
}

func (suite *CliTestSuite) TestTransformSubmitArgsConfsAlreadyHasEquals() {
	_, args := sparkSubmitArgSetup()
	inputArgs := "--conf=spark.driver.extraJavaOptions='-Dparam1=val1' main.py 100"
	expected := "--conf=spark.driver.extraJavaOptions=-Dparam1=val1"
	actual, _ := transformSubmitArgs(inputArgs, args.boolVals)
	assert.Equal(suite.T(), expected, actual[0])
}

func (suite *CliTestSuite) TestTransformSubmitArgsMultilines() {
	_, args := sparkSubmitArgSetup()
	inputArgs := `--conf spark.driver.extraJavaOptions='-XX:+PrintGC -XX:+PrintGCTimeStamps' \
	--supervise --driver-memory 1g \
	main.py 100`
	expected := []string{"--conf=spark.driver.extraJavaOptions=-XX:+PrintGC -XX:+PrintGCTimeStamps", "--supervise", "--driver-memory=1g", "main.py"}
	actual, _ := transformSubmitArgs(inputArgs, args.boolVals)
	assert.Equal(suite.T(), expected, actual)
}

func (suite *CliTestSuite) TestProcessJarsFlag() {
	_, args := sparkSubmitArgSetup()
	inputArgs := "--conf spark.cores.max=8 --jars=http://one.jar app/jars/main.jar 100"
	expected := []string{"--conf=spark.cores.max=8",
		"--jars=http://one.jar",
		"--conf=spark.mesos.uris=http://one.jar",
		"--conf=spark.driver.extraClassPath=" + mesosSandboxPath + "/one.jar",
		"--conf=spark.executor.extraClassPath=" + mesosSandboxPath + "/one.jar",
		"app/jars/main.jar"}
	actual, _ := transformSubmitArgs(inputArgs, args.boolVals)
	assert.Equal(suite.T(), expected, actual)
}

func (suite *CliTestSuite) TestProcessMultiJarsFlag() {
	_, args := sparkSubmitArgSetup()
	inputArgs := "--conf spark.cores.max=8 --jars=http://one.jar,http://two.jar main.jar 100"
	expected := []string{"--conf=spark.cores.max=8",
		"--jars=http://one.jar,http://two.jar",
		"--conf=spark.mesos.uris=http://one.jar,http://two.jar",
		"--conf=spark.driver.extraClassPath=" + mesosSandboxPath + "/one.jar:" + mesosSandboxPath + "/two.jar",
		"--conf=spark.executor.extraClassPath=" + mesosSandboxPath + "/one.jar:" + mesosSandboxPath + "/two.jar",
		"main.jar"}
	actual, _ := transformSubmitArgs(inputArgs, args.boolVals)
	assert.Equal(suite.T(), expected, actual)
}

func (suite *CliTestSuite) TestProcessMultiJarsFlagWithSpace() {
	_, args := sparkSubmitArgSetup()
	inputArgs := "--conf spark.cores.max=8 --jars http://one.jar,http://two.jar main.jar 100"
	expected := []string{"--conf=spark.cores.max=8",
		"--jars=http://one.jar,http://two.jar",
		"--conf=spark.mesos.uris=http://one.jar,http://two.jar",
		"--conf=spark.driver.extraClassPath=" + mesosSandboxPath + "/one.jar:" + mesosSandboxPath + "/two.jar",
		"--conf=spark.executor.extraClassPath=" + mesosSandboxPath + "/one.jar:" + mesosSandboxPath + "/two.jar",
		"main.jar"}
	actual, _ := transformSubmitArgs(inputArgs, args.boolVals)
	assert.Equal(suite.T(), expected, actual)
}

func (suite *CliTestSuite) TestProcessPackagesFlag() {
	_, args := sparkSubmitArgSetup()
	inputArgs := "--conf spark.cores.max=8 --packages=groupid:artifactid:version app/packages/main.jar 100"
	expected := []string{"--conf=spark.cores.max=8",
		"--packages=groupid:artifactid:version",
		"--conf=spark.jars.ivy=" + mesosSandboxPath + "/.ivy2",
		"app/packages/main.jar"}
	actual, _ := transformSubmitArgs(inputArgs, args.boolVals)
	assert.Equal(suite.T(), expected, actual)
}

func (suite *CliTestSuite) TestProcessMultiPackagesFlag() {
	_, args := sparkSubmitArgSetup()
	inputArgs := "--conf spark.cores.max=8 --packages=groupid1:artifactid1:version1,groupid2:artifactid2:version2 app/packages/main.jar 100"
	expected := []string{"--conf=spark.cores.max=8",
		"--packages=groupid1:artifactid1:version1,groupid2:artifactid2:version2",
		"--conf=spark.jars.ivy=" + mesosSandboxPath + "/.ivy2",
		"app/packages/main.jar"}
	actual, _ := transformSubmitArgs(inputArgs, args.boolVals)
	assert.Equal(suite.T(), expected, actual)
}

func (suite *CliTestSuite) TestProcessMultiPackagesFlagWithSpace() {
	_, args := sparkSubmitArgSetup()
	inputArgs := "--conf spark.cores.max=8 --packages groupid1:artifactid1:version1,groupid2:artifactid2:version2 app/packages/main.jar 100"
	expected := []string{"--conf=spark.cores.max=8",
		"--packages=groupid1:artifactid1:version1,groupid2:artifactid2:version2",
		"--conf=spark.jars.ivy=" + mesosSandboxPath + "/.ivy2",
		"app/packages/main.jar"}
	actual, _ := transformSubmitArgs(inputArgs, args.boolVals)
	assert.Equal(suite.T(), expected, actual)
}

func (suite *CliTestSuite) TestIsSparkApp() {
	assert.True(suite.T(), isSparkApp("mainApp.jar"))
	assert.True(suite.T(), isSparkApp("pythonFile.py"))
	assert.True(suite.T(), isSparkApp("file.R"))
	assert.False(suite.T(), isSparkApp("app.c"))
	assert.False(suite.T(), isSparkApp("randomFlag"))
}

// test scopts pattern for app args when have full submit args
func (suite *CliTestSuite) TestScoptAppArgs() {
	_, args := sparkSubmitArgSetup()
	inputArgs := `--driver-cores 1 --conf spark.cores.max=1 --driver-memory 512M
  --class org.apache.spark.examples.SparkPi http://spark-example.jar --input1 value1 --input2 value2`
	submitArgs, appFlags := transformSubmitArgs(inputArgs, args.boolVals)

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
			"--conf spark.driver.extraJavaOptions='-XX:+PrintGC -Dparam1=val1 -Dparam2=val2' "+
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
		"spark.driver.cores":                         driverCores,
		"spark.cores.max":                            maxCores,
		"spark.mesos.executor.docker.forcePullImage": "true",
		"spark.mesos.executor.docker.image":          image,
		"spark.mesos.task.labels":                    fmt.Sprintf("DCOS_SPACE:%s", marathonAppId),
		"spark.ssl.noCertVerification":               "true",
		"spark.executor.memory":                      "1G", // default
		"spark.submit.deployMode":                    "cluster",
		"spark.mesos.driver.labels":                  fmt.Sprintf("DCOS_SPACE:%s", marathonAppId),
		"spark.driver.memory":                        driverMemory,
		"spark.driver.extraJavaOptions":              "-XX:+PrintGC -Dparam1=val1 -Dparam2=val2",
		"spark.jars":                                 appJar,
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
		"spark.driver.cores":                         driverCores,
		"spark.cores.max":                            maxCores,
		"spark.mesos.executor.docker.forcePullImage": "false",
		"spark.mesos.executor.docker.image":          "other",
		"spark.mesos.task.labels":                    fmt.Sprintf("DCOS_SPACE:%s", marathonAppId),
		"spark.ssl.noCertVerification":               "true",
		"spark.executor.memory":                      "1G", // default
		"spark.submit.deployMode":                    "cluster",
		"spark.mesos.driver.labels":                  fmt.Sprintf("DCOS_SPACE:%s", marathonAppId),
		"spark.driver.memory":                        driverMemory,
		"spark.jars":                                 appJar,
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
			"--kerberos-principal %s "+
			"--keytab-secret-path /%s "+
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
		"spark.yarn.principal":                principal,
		"spark.mesos.containerizer":           "mesos",
		"spark.mesos.driver.secret.filenames": secretFile,
		"spark.mesos.driver.secret.names":     fmt.Sprintf("/%s", secretPath),
	}
	suite.checkProps(v, secretProps)
}

func (suite *CliTestSuite) TestPayloadWithSecret() {
	suite.checkSecret(keytab, keytab)
	suite.checkSecret(keytabPrefixed, keytab)
}

func (suite *CliTestSuite) TestSaslSecret() {
	inputArgs := fmt.Sprintf(
		"--executor-auth-secret %s "+
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
		"spark.authenticate":                      "true",
		"spark.mesos.containerizer":               "mesos",
		"spark.authenticate.enableSaslEncryption": "true",
		"spark.authenticate.secret":               sparkAuthSecret,
		"spark.executorEnv._SPARK_AUTH_SECRET":    sparkAuthSecret,
	}

	v, ok := m["sparkProperties"].(map[string]interface{})
	if !ok {
		suite.T().Errorf("%+v", ok)
	}

	suite.checkProps(v, stringProps)
}

func (suite *CliTestSuite) TestSaslFileBasedSecret() {
	inputArgs := fmt.Sprintf(
		"--executor-auth-secret-path /%s "+
			"--class %s "+
			"%s --input1 value1 --input2 value2", sparkAuthSecretPath, mainClass, appJar)

	_, sparkAuthSecretFile := filepath.Split(fmt.Sprintf("/%s", sparkAuthSecretPath))
	cmd := createCommand(inputArgs, image)
	payload, err := buildSubmitJson(&cmd, marathonConfig)

	m := make(map[string]interface{})

	json.Unmarshal([]byte(payload), &m)

	if err != nil {
		suite.T().Errorf("%s", err.Error())
	}

	stringProps := map[string]string{
		"spark.authenticate":                        "true",
		"spark.mesos.containerizer":                 "mesos",
		"spark.authenticate.enableSaslEncryption":   "true",
		"spark.authenticate.secret.file":            sparkAuthSecretFile,
		"spark.executorEnv._SPARK_AUTH_SECRET_FILE": sparkAuthSecretFile,
		"spark.mesos.driver.secret.filenames":       sparkAuthSecretFile,
		"spark.mesos.driver.secret.names":           fmt.Sprintf("/%s", sparkAuthSecretPath),
		"spark.mesos.executor.secret.filenames":     sparkAuthSecretFile,
		"spark.mesos.executor.secret.names":         fmt.Sprintf("/%s", sparkAuthSecretPath),
	}

	v, ok := m["sparkProperties"].(map[string]interface{})
	if !ok {
		suite.T().Errorf("%+v", ok)
	}

	suite.checkProps(v, stringProps)
}

func (suite *CliTestSuite) TestPackagesFlag() {
	sparkPackages := "group.one.id:artifact-one-id:version.one,group.two.id:artifact-two-id:version.two"
	inputArgs := fmt.Sprintf(
		"--packages %s --class %s %s --input1 value1 --input2 value2",
		sparkPackages, mainClass, appJar)

	cmd := createCommand(inputArgs, image)
	payload, err := buildSubmitJson(&cmd, marathonConfig)

	jsonMap := make(map[string]interface{})

	json.Unmarshal([]byte(payload), &jsonMap)

	if err != nil {
		suite.T().Errorf("%s", err.Error())
	}

	stringProps := map[string]string{
		"spark.jars.ivy":      mesosSandboxPath + "/.ivy2",
		"spark.jars.packages": sparkPackages,
	}

	sparkProps, ok := jsonMap["sparkProperties"].(map[string]interface{})
	if !ok {
		suite.T().Errorf("%+v", ok)
	}

	suite.checkProps(sparkProps, stringProps)
}
