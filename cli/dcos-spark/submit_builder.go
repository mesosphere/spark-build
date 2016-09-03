package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/mesosphere/dcos-commons/cli"
	"gopkg.in/alecthomas/kingpin.v2"
	"log"
	"net/url"
	"os"
	"regexp"
	"strings"
)

var keyWhitespaceValPattern = regexp.MustCompile("(.+)\\s+(.+)")
var backslashNewlinePattern = regexp.MustCompile("\\s*\\\\s*\\n\\s+")

type sparkVal struct {
	flagName string
	propName string
	desc string
	s string // used by string vals
	b bool // used by bool vals
}
func (f *sparkVal) flag(section *kingpin.Application) *kingpin.FlagClause {
	return section.Flag(f.flagName, fmt.Sprintf("%s (%s)", f.desc, f.propName))
}
func newSparkVal(flagName, propName, desc string) *sparkVal {
	return &sparkVal{flagName, propName, desc, "", false}
}

type sparkArgs struct {
	mainClass string

	propertiesFile string
	properties map[string]string

	boolVals []*sparkVal
	stringVals []*sparkVal

	appJar *url.URL
	appArgs []string
}

/*
Relevant files:
- http://arturmkrtchyan.com/apache-spark-hidden-rest-api
- https://github.com/apache/spark/blob/master/launcher/src/main/java/org/apache/spark/launcher/SparkSubmitOptionParser.java
- https://github.com/apache/spark/blob/master/core/src/main/scala/org/apache/spark/deploy/SparkSubmitArguments.scala
- https://github.com/apache/spark/blob/master/core/src/main/scala/org/apache/spark/deploy/SparkSubmit.scala

To get POST requests from spark-submit:
- Open spark-2.0.0/conf/log4j.properties.template => set "DEBUG" => write as "log4j.properties"
- $ SPARK_JAVA_OPTS="-Dlog4j.debug=true -Dlog4j.configuration=log4j.properties ..." ./spark-2.0.0/bin/spark-submit ...

Unsupported flags, omitted here:

managed by us, user cannot change:
- deployMode:             --deploy-mode <client|cluster> (spark.submit.deployMode/DEPLOY_MODE)
- master:                 --master mesos://host:port (spark.master/MASTER)
officially unsupported in DC/OS Spark docs:
- pyFiles:                --py-files many.zip,python.egg,files.py (spark.submit.pyFiles)
client mode only? doesn't seem to be used in POST call at all:
- proxyUser:              --proxy-user SOMENAME
client mode only (downloads jars to local system):
- ivyRepoPath:            (spark.jars.ivy)
- packages:               --packages maven,coordinates,for,jars (spark.jars.packages)
- packagesExclusions:     --exclude-packages groupId:artifactId,toExclude:fromClasspath (spark.jars.excludes)
- repositories:           --repositories additional.remote,repositories.to.search
yarn only:
- archives:               --archives
- executorCores:          --executor-cores NUM (spark.executor.cores/SPARK_EXECUTOR_CORES)
- keytab:                 --keytab (spark.yarn.keytab)
- numExecutors:           --num-executors (spark.executor.instances)
- principal:              --principal (spark.yarn.principal)
- queue:                  --queue (spark.yarn.queue)
*/
func sparkSubmitArgSetup() (*kingpin.Application, *sparkArgs) {
	submit := kingpin.New("","")
	submit.HelpFlag.Short('h').Hidden()
	submit.UsageTemplate(`<flags> <jar> [args]
{{if .Context.Flags}}
Flags:
{{.Context.Flags|FlagsToTwoColumns|FormatTwoColumns}}
{{end}}
{{if .Context.Args}}
Args:
{{.Context.Args|ArgsToTwoColumns|FormatTwoColumns}}
{{end}}
`)

	args := &sparkArgs{"", "", make(map[string]string), make([]*sparkVal, 0), make([]*sparkVal, 0), new(url.URL), make([]string, 0)}

	submit.Flag("class", "Your application's main class (for Java / Scala apps). (REQUIRED)").Required().StringVar(&args.mainClass) // note: spark-submit can autodetect, but only for file://local.jar
	submit.Flag("properties-file", "Path to file containing whitespace-separated Spark property defaults.").PlaceHolder("PATH").ExistingFileVar(&args.propertiesFile)
	submit.Flag("conf", "Custom Spark configuration properties.").Short('D').PlaceHolder("PROP=VALUE").StringMapVar(&args.properties)

	val := newSparkVal("supervise", "spark.driver.supervise", "If given, restarts the driver on failure.")
	val.flag(submit).BoolVar(&val.b)
	args.boolVals = append(args.boolVals, val)

	val = newSparkVal("name", "spark.app.name", "A name for your application")
	val.flag(submit).StringVar(&val.s)
	args.stringVals = append(args.stringVals, val)

	val = newSparkVal("driver-cores", "spark.driver.cores", "Cores for driver.")
	val.flag(submit).Default("1").StringVar(&val.s)
	args.stringVals = append(args.stringVals, val)

	val = newSparkVal("driver-memory", "spark.driver.memory", "Memory for driver (e.g. 1000M, 2G).")
	val.flag(submit).Default("1G").Envar("SPARK_DRIVER_MEMORY").StringVar(&val.s)
	args.stringVals = append(args.stringVals, val)

	val = newSparkVal("driver-class-path", "spark.driver.extraClassPath", "Extra class path entries to pass to the driver. Note that jars added with --jars are automatically included in the classpath.")
	val.flag(submit).StringVar(&val.s)
	args.stringVals = append(args.stringVals, val)

	val = newSparkVal("driver-java-options", "spark.driver.extraJavaOptions", "Extra Java options to pass to the driver.")
	val.flag(submit).StringVar(&val.s)
	args.stringVals = append(args.stringVals, val)

	val = newSparkVal("driver-library-path", "spark.driver.extraLibraryPath", "Extra library path entries to pass to the driver.")
	val.flag(submit).StringVar(&val.s)
	args.stringVals = append(args.stringVals, val)

	val = newSparkVal("executor-memory", "spark.executor.memory", "Memory per executor (e.g. 1000M, 2G)")
	val.flag(submit).Default("1G").Envar("SPARK_EXECUTOR_MEMORY").StringVar(&val.s)
	args.stringVals = append(args.stringVals, val)

	val = newSparkVal("total-executor-cores", "spark.cores.max", "Total cores for all executors.")
	val.flag(submit).StringVar(&val.s)
	args.stringVals = append(args.stringVals, val)

	val = newSparkVal("files", "spark.files", "Comma-separated list of file URLs to be placed in the working directory of each executor.")
	val.flag(submit).StringVar(&val.s)
	args.stringVals = append(args.stringVals, val)

	val = newSparkVal("jars", "spark.jars", "Comma-separated list of jar URLs to include on the driver and executor classpaths.")
	val.flag(submit).StringVar(&val.s)
	args.stringVals = append(args.stringVals, val)

	submit.Arg("jar", "Application jar to be run").Required().URLVar(&args.appJar)
	submit.Arg("args", "Application arguments").StringsVar(&args.appArgs)

	return submit, args
}

func sparkSubmitHelp() string {
	app, _ := sparkSubmitArgSetup()
	var buf bytes.Buffer
	writer := bufio.NewWriter(&buf)
	app.UsageWriter(writer)
	app.Usage(make([]string, 0))
	writer.Flush()
	return buf.String()
}

func cleanUpSubmitArgs(argsStr string, boolVals []*sparkVal) []string {
	// clean up any instances of shell-style escaped newlines: "arg1\\narg2" => "arg1 arg2"
	argsCleaned := strings.TrimSpace(backslashNewlinePattern.ReplaceAllLiteralString(argsStr, " "))
	// HACK: spark-submit uses '--arg val' by convention, while kingpin only supports '--arg=val'.
	//       translate the former into the latter for kingpin to parse.
	args := strings.Split(argsCleaned, " ")
	argsEquals := make([]string, 0)
	i := 0
ARGLOOP:
	for i < len(args) {
		arg := args[i]
		if !strings.HasPrefix(arg, "-") {
			// looks like we've exited the flags entirely, and are now at the jar and/or args.
			// any arguments without a dash at the front should've been joined to preceding keys.
			// flush the rest and exit.
			for i < len(args) {
				arg = args[i]
				argsEquals = append(argsEquals, arg)
				i += 1
			}
			break
		}
		// join this arg to the next arg if...:
		// 1. we're not at the last arg in the array
		// 2. we start with "--"
		// 3. we don't already contain "=" (already joined)
		// 4. we aren't a boolean value (no val to join)
		if i < len(args) - 1 && strings.HasPrefix(arg, "--") && !strings.Contains(arg, "=") {
			// check for boolean:
			for _, boolVal := range(boolVals) {
				if boolVal.flagName == arg[2:] {
					argsEquals = append(argsEquals, arg)
					i += 1
					continue ARGLOOP
				}
			}
			// merge this --key against the following val to get --key=val
			argsEquals = append(argsEquals, arg + "=" + args[i+1])
			i += 2
		} else {
			// already joined or at the end, pass through:
			argsEquals = append(argsEquals, arg)
			i += 1
		}
	}
	if cli.Verbose {
		fmt.Printf("Translated arguments: '%s'\n", argsEquals)
	}
	return argsEquals
}

func getValsFromPropertiesFile(path string) map[string]string {
	vals := make(map[string]string)
	if len(path) == 0 {
		return vals
	}

	file, err := os.Open(path)
	if err != nil {
		log.Fatal(err)
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if len(line) == 0 {
			continue
		}
		if line[0] == '#' {
			continue
		}
		result := keyWhitespaceValPattern.FindStringSubmatch(line)
		if len(result) == 0 {
			continue
		}
		vals[result[1]] = result[2]
	}
	return vals
}

func getStringFromTree(m map[string]interface{}, path []string) (string, error) {
	if len(path) == 0 {
		return "", errors.New(fmt.Sprintf("empty path, nothing to navigate in: %s", m))
	}
	obj, ok := m[path[0]]
	if !ok {
		return "", errors.New(fmt.Sprintf("unable to find key '%s' in map: %s", path[0], m))
	}
	if len(path) == 1 {
		ret, ok := obj.(string)
		if !ok {
			return "", errors.New(fmt.Sprintf("unable to cast map value '%s' (for key '%s') as string: %s", obj, path[0], m))
		}
		return ret, nil
	} else {
		next, ok := obj.(map[string]interface{})
		if !ok {
			return "", errors.New(fmt.Sprintf("unable to cast map value '%s' (for key '%s') as string=>object map: %s", obj, path[0], m))
		}
		return getStringFromTree(next, path[1:])
	}
}

func submitJson(argsStr string, dockerImage string, submitEnv map[string]string) (string, error) {
	// first, import any values in the provided properties file (space separated "key val")
	// then map applicable envvars
	// then parse all -Dprop.key=propVal, and all --conf prop.key=propVal
	// then map flags

	submit, args := sparkSubmitArgSetup()

	kingpin.MustParse(submit.Parse(cleanUpSubmitArgs(argsStr, args.boolVals)))

	for _, boolVal := range(args.boolVals) {
		if boolVal.b {
			args.properties[boolVal.propName] = "true"
		}
	}
	for _, stringVal := range(args.stringVals) {
		if len(stringVal.s) != 0 {
			args.properties[stringVal.propName] = stringVal.s
		}
	}

	for k, v := range(getValsFromPropertiesFile(args.propertiesFile)) {
		// populate value if not already present (due to envvars or args):
		_, ok := args.properties[k]
		if !ok {
			args.properties[k] = v
		}
	}

	// insert/overwrite some default properties:
	args.properties["spark.submit.deployMode"] = "cluster"
	if (strings.EqualFold(cli.OptionalCLIConfigValue("core.ssl_verify"), "false")) {
		args.properties["spark.ssl.noCertVerification"] = "true"
	}
	sparkMasterURL := cli.CreateURL("", "")
	if sparkMasterURL.Scheme == "http" {
		sparkMasterURL.Scheme = "mesos"
	} else if sparkMasterURL.Scheme == "https" {
		sparkMasterURL.Scheme = "mesos-ssl"
	} else {
		log.Fatalf("Unsupported protocol '%s': %s", sparkMasterURL.Scheme, sparkMasterURL.String())
	}
	args.properties["spark.master"] = sparkMasterURL.String()

	// copy appResource to front of 'spark.jars' data:
	jars, ok := args.properties["spark.jars"]
	if !ok || len(jars) == 0 {
		args.properties["spark.jars"] = args.appJar.String()
	} else {
		args.properties["spark.jars"] = fmt.Sprintf("%s,%s", args.appJar.String(), jars)
	}

	// if spark.app.name is missing, set it to mainClass
	_, ok = args.properties["spark.app.name"]
	if !ok {
		args.properties["spark.app.name"] = args.mainClass
	}

	// fetch the spark task definition from Marathon:
	url := cli.CreateURL("replaceme", "")
	url.Path = fmt.Sprintf("/marathon/v2/apps/%s", cli.ServiceName)
	responseBytes := cli.GetResponseBytes(cli.CheckHTTPResponse(cli.HTTPQuery(cli.CreateHTTPURLRequest("GET", url, "", ""))))

	responseJson := make(map[string]interface{})
	err := json.Unmarshal(responseBytes, &responseJson)
	if err != nil {
		return "", err
	}

	docker_image, err := getStringFromTree(responseJson, []string{"app", "container", "docker", "image"})
	if err != nil {
		return "", err
	}
	args.properties["spark.mesos.executor.docker.image"] = docker_image
	hdfs_config_url, err := getStringFromTree(responseJson, []string{"app", "labels", "SPARK_HDFS_CONFIG_URL"})
	if err == nil && len(hdfs_config_url) != 0 { // fail silently: it's normal for this to be unset
		hdfs_config_url = strings.TrimRight(hdfs_config_url, "/")
		args.properties["spark.mesos.uris"] = fmt.Sprintf(
			"%s/hdfs-site.xml,%s/core-site.xml", hdfs_config_url, hdfs_config_url)
	}

	jsonMap := map[string]interface{} {
		"action": "CreateSubmissionRequest",
		"appArgs": args.appArgs,
		"appResource": args.appJar.String(),
		"clientSparkVersion": "2.0.0",
		"environmentVariables": submitEnv,
		"mainClass": args.mainClass,
		"sparkProperties": args.properties,
	}
	jsonPayload, err := json.Marshal(jsonMap)
	if err != nil {
		return "", err
	}
	return string(jsonPayload), nil
}
