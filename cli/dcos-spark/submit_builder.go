package main

import (
	"bufio"
	"bytes"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/mesosphere/dcos-commons/cli/client"
	"github.com/mesosphere/dcos-commons/cli/config"
	"gopkg.in/alecthomas/kingpin.v3-unstable"
	"io/ioutil"
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
	desc     string
	s        string // used by string vals
	b        bool   // used by bool vals
}

func (f *sparkVal) flag(section *kingpin.Application) *kingpin.Clause {
	return section.Flag(f.flagName, fmt.Sprintf("%s (%s)", f.desc, f.propName))
}
func newSparkVal(flagName, propName, desc string) *sparkVal {
	return &sparkVal{flagName, propName, desc, "", false}
}

type sparkArgs struct {
	mainClass 			string
	kerberosPrincipal 	string
	keytabSecretPath	string
	tgtSecretPath		string
	tgtSecretValue		string
	propertiesFile    	string
	properties        	map[string]string

	boolVals   			[]*sparkVal
	stringVals 			[]*sparkVal

	app		  			*url.URL
	appArgs 			[]string

	isScala				bool
	isPython			bool
	isR					bool
}

func NewSparkArgs() *sparkArgs {
	return &sparkArgs{
		"",
		"",
		"",
		"",
		"",
		"",
		make(map[string]string),
		make([]*sparkVal, 0),
		make([]*sparkVal, 0),
		new(url.URL),
		make([]string, 0),
		false,
		false,
		false}
}

/*
Relevant files:
- http://arturmkrtchyan.com/apache-spark-hidden-rest-api
stock spark:
- https://github.com/apache/spark/blob/master/launcher/src/main/java/org/apache/spark/launcher/SparkSubmitOptionParser.java
- https://github.com/apache/spark/blob/master/core/src/main/scala/org/apache/spark/deploy/SparkSubmitArguments.scala
- https://github.com/apache/spark/blob/master/core/src/main/scala/org/apache/spark/deploy/SparkSubmit.scala
patched spark (adds kerberos support for Mesos):
- https://github.com/mesosphere/spark/blob/custom-master/launcher/src/main/java/org/apache/spark/launcher/SparkSubmitOptionParser.java
- https://github.com/mesosphere/spark/blob/custom-master/core/src/main/scala/org/apache/spark/deploy/SparkSubmitArguments.scala
- https://github.com/mesosphere/spark/blob/custom-master/core/src/main/scala/org/apache/spark/deploy/SparkSubmit.scala

To get POST requests from spark-submit:
- Open spark-2.0.0/conf/log4j.properties.template => set "DEBUG" => write as "log4j.properties"
- $ SPARK_JAVA_OPTS="-Dlog4j.debug=true -Dlog4j.configuration=log4j.properties ..." ./spark-2.0.0/bin/spark-submit ...

Supported in mesosphere/spark patchset, but not in stock spark (yarn only there):
- principal:              --principal (spark.yarn.principal, spark.hadoop.yarn.resourcemanager.principal)
- tgt:                    --tgt (spark.mesos.kerberos.tgt => spark.mesos.kerberos.tgtBase64) - may not be set while keytab is set
- keytab:                 --keytab (spark.yarn.keytab => spark.mesos.kerberos.keytabBase64) - may not be set while tgt is set

Unsupported flags, omitted here:

managed by us, user cannot change:
- deployMode:             --deploy-mode <client|cluster> (spark.submit.deployMode/DEPLOY_MODE)
- master:                 --master mesos://host:port (spark.master/MASTER)
python is officially supported in DC/OS Spark docs:
- pyFiles:                --py-files many.zip,python.egg,files.py (spark.submit.pyFiles)
appears to be client mode only? doesn't seem to be used in POST submit call at all:
- proxyUser:              --proxy-user SOMENAME
client mode only (downloads jars to local system, wouldn't work for POST call):
- ivyRepoPath:            (spark.jars.ivy)
- packages:               --packages maven,coordinates,for,jars (spark.jars.packages)
- packagesExclusions:     --exclude-packages groupId:artifactId,toExclude:fromClasspath (spark.jars.excludes)
- repositories:           --repositories additional.remote,repositories.to.search
yarn only (note: principal/tgt/keytab are supported in patched spark):
- archives:               --archives
- executorCores:          --executor-cores NUM (spark.executor.cores/SPARK_EXECUTOR_CORES)
- numExecutors:           --num-executors (spark.executor.instances)
- queue:                  --queue (spark.yarn.queue)
*/
func sparkSubmitArgSetup() (*kingpin.Application, *sparkArgs) {
	submit := kingpin.New("", "")
	submit.GetFlag("help").Short('h')
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

	args := NewSparkArgs()

	submit.Flag("class", "Your application's main class (for Java / Scala apps). (REQUIRED)").
		StringVar(&args.mainClass) // note: spark-submit can autodetect, but only for file://local.jar
	submit.Flag("properties-file", "Path to file containing whitespace-separated Spark property defaults.").
		PlaceHolder("PATH").ExistingFileVar(&args.propertiesFile)
	submit.Flag("conf", "Custom Spark configuration properties.").
		PlaceHolder("PROP=VALUE").StringMapVar(&args.properties)
	submit.Flag("kerberos-principal", "Principal to be used to login to KDC.").
		PlaceHolder("user@REALM").Default("").StringVar(&args.kerberosPrincipal)
	submit.Flag("keytab-secret-path", "path to Keytab in secret store to be used in the Spark drivers").
		PlaceHolder("/mykeytab").Default("").StringVar(&args.keytabSecretPath)
	submit.Flag("tgt-secret-path", "Path to ticket granting ticket (TGT) in secret store to be used " +
		"in the Spark drivers").PlaceHolder("/mytgt").Default("").StringVar(&args.tgtSecretPath)
	submit.Flag("tgt-secret-value", "Value of TGT to be used in the drivers, must be base64 encoded").
		Default("").StringVar(&args.tgtSecretValue)

	submit.Flag("isR", "Force using SparkR").Default("false").BoolVar(&args.isR)
	submit.Flag("isPython", "Force using Python").Default("false").BoolVar(&args.isPython)

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

	val = newSparkVal("py-files", "spark.submit.pyFiles", "Add .py, .zip or .egg files to " +
		"be distributed with your application. If you depend on multiple Python files we recommend packaging them " +
		"into a .zip or .egg.")
	val.flag(submit).StringVar(&val.s)
	args.stringVals = append(args.stringVals, val)

	submit.Arg("jar", "Application jar to be run").Required().URLVar(&args.app)
	submit.Arg("args", "Application arguments").StringsVar(&args.appArgs)

	return submit, args
}

func sparkSubmitHelp() string {
	app, _ := sparkSubmitArgSetup()
	var buf bytes.Buffer
	writer := bufio.NewWriter(&buf)
	app.Writers(writer, writer)
	app.Usage(make([]string, 0))
	writer.Flush()
	return buf.String()
}

func prepareBase64Secret(secretPath string, isEncoded bool) string {
	ss := strings.Split(secretPath, "/")
	s := ss[len(ss) - 1]  // The secret file without any slashes
	// TODO document how secret formatting works w.r.t decoding
	// secrets with __dcos_base64__ will be decoded by mesos or spark
	if strings.HasPrefix(s, "__dcos_base64__") || strings.HasSuffix(s, "base64") {
		// if we have the .base64, maintain the whole thing spark-env will decode it
		return strings.TrimPrefix(s, "__dcos_base64__")
	}
	if isEncoded {
		return s + ".base64"
	} else {
		return s
	}
}

func addArgsForFileBasedSecret(args *sparkArgs, secretPath, property string) {
	args.properties["spark.mesos.driver.secret.name"] = secretPath
	args.properties[property] = prepareBase64Secret(secretPath, false)
	args.properties["spark.mesos.driver.secret.filename"] = prepareBase64Secret(secretPath, true)
}

func setupKerberosAuthArgs(args *sparkArgs) error {
	args.properties["spark.mesos.containerizer"] = "mesos"
	if args.keytabSecretPath != "" {  // using keytab secret
		addArgsForFileBasedSecret(args, args.keytabSecretPath, "spark.yarn.keytab")
		return nil
	}
	if args.tgtSecretPath != "" {  // using tgt secret
		addArgsForFileBasedSecret(args, args.tgtSecretPath, "spark.mesos.driverEnv.KRB5CCNAME")
		return nil
	}
	if args.tgtSecretValue != "" {  // using secret by value
		args.properties["spark.mesos.driver.secret.value"] = args.tgtSecretValue
		args.properties["spark.mesos.driverEnv.KRB5CCNAME"] = "tgt"
		args.properties["spark.mesos.driver.secret.filename"] = "tgt.base64"
		return nil
	}
	return errors.New(fmt.Sprintf("Unable to add Kerberos args, got args %s", args))
}

func parseApplicationFile(args *sparkArgs) error {
	appString := args.app.String()
	fs := strings.Split(appString, "/")
	f := fs[len(fs)-1]

	if strings.HasSuffix(appString, ".R") || args.isR {
		if args.mainClass != "" {
			return errors.New("Can only specify main class when using a Scala or Java Spark application")
		}
		log.Printf("Parsing application as R job")
		if args.mainClass != "" {
			return errors.New("Cannot specify a main class for an R job")
		}
		args.isR = true
		args.isPython = false
		args.isScala = false
		args.mainClass = f
		return nil
	}

	if strings.HasSuffix(appString, ".py") || args.isPython {
		if args.mainClass != "" {
			return errors.New("Can only specify main class when using a Scala or Java Spark application")
		}
		log.Printf("Parsing application as Python job")
		if args.mainClass != "" {
			return errors.New("Cannot specify a main class for an python job")
		}
		args.isR = false
		args.isPython = true
		args.isScala = false
		args.mainClass = f
		return nil
	}

	args.isR = false
	args.isPython = false
	args.isScala = true
	return nil
}

func cleanUpSubmitArgs(argsStr string, boolVals []*sparkVal) ([]string, []string) {
	// clean up any instances of shell-style escaped newlines: "arg1\\narg2" => "arg1 arg2"
	argsCleaned := strings.TrimSpace(backslashNewlinePattern.ReplaceAllLiteralString(argsStr, " "))
	// HACK: spark-submit uses '--arg val' by convention, while kingpin only supports '--arg=val'.
	//       translate the former into the latter for kingpin to parse.
	args := strings.Split(argsCleaned, " ")
	argsEquals := make([]string, 0)
	appFlags := make([]string, 0)
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
				if strings.HasPrefix(arg, "-") {
					appFlags = append(appFlags, arg)
				} else {
					argsEquals = append(argsEquals, arg)
				}
				i += 1
			}
			break
		}
		// join this arg to the next arg if...:
		// 1. we're not at the last arg in the array
		// 2. we start with "--"
		// 3. we don't already contain "=" (already joined)
		// 4. we aren't a boolean value (no val to join)
		if i < len(args)-1 && strings.HasPrefix(arg, "--") && !strings.Contains(arg, "=") {
			// check for boolean:
			for _, boolVal := range boolVals {
				if boolVal.flagName == arg[2:] {
					argsEquals = append(argsEquals, arg)
					i += 1
					continue ARGLOOP
				}
			}
			// merge this --key against the following val to get --key=val
			argsEquals = append(argsEquals, arg+"="+args[i+1])
			i += 2
		} else {
			// already joined or at the end, pass through:
			argsEquals = append(argsEquals, arg)
			i += 1
		}
	}
	if config.Verbose {
		log.Printf("Translated spark-submit arguments: '%s'\n", argsEquals)
		log.Printf("Translated application arguments: '%s'\n", appFlags)
	}

	return argsEquals, appFlags
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
		prop := strings.TrimSpace(result[1])
		val := strings.TrimSpace(result[2])
		vals[prop] = val
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

func appendToProperty(propValue, toAppend string, args *sparkArgs) {
	_, contains := args.properties[propValue]
	if !contains {
		args.properties[propValue] = toAppend
	} else {
		args.properties[propValue] += "," + toAppend
	}
}

func getBase64Content(path string) string {
	log.Printf("Opening file %s", path)
	data, err := ioutil.ReadFile(path)
	if err != nil {
		log.Fatal(err)
	}

	var encodebuf bytes.Buffer
	encoder := base64.NewEncoder(base64.StdEncoding, &encodebuf)
	encoder.Write(data)
	encoder.Close() // must be called before returning string to ensure flush
	return encodebuf.String()
}

func buildSubmitJson(cmd *SparkCommand) (string, error) {
	// first, import any values in the provided properties file (space separated "key val")
	// then map applicable envvars
	// then parse all -Dprop.key=propVal, and all --conf prop.key=propVal
	// then map flags
	submit, args := sparkSubmitArgSetup()  // setup
	// convert and get application flags, add them to the args passed to the spark app
	submitArgs, appFlags := cleanUpSubmitArgs(cmd.submitArgs, args.boolVals)
	args.appArgs = append(args.appArgs, appFlags...)
	_, err := submit.Parse(submitArgs)

	if err != nil {
		log.Fatalf("Error when parsing --submit-args: %s", err)
	}

	for _, boolVal := range args.boolVals {
		if boolVal.b {
			args.properties[boolVal.propName] = "true"
		}
	}

	for _, stringVal := range args.stringVals {
		if len(stringVal.s) != 0 {
			args.properties[stringVal.propName] = stringVal.s
		}
	}

	for k, v := range getValsFromPropertiesFile(args.propertiesFile) {
		// populate value if not already present (due to envvars or args):
		_, ok := args.properties[k]
		if !ok {
			args.properties[k] = v
		}
	}

	parseApplicationFile(args)

	// insert/overwrite some default properties:
	args.properties["spark.submit.deployMode"] = "cluster"
	if strings.EqualFold(client.OptionalCLIConfigValue("core.ssl_verify"), "false") {
		args.properties["spark.ssl.noCertVerification"] = "true"
	}
	sparkMasterURL := client.CreateServiceURL("", "")
	if sparkMasterURL.Scheme == "http" {
		sparkMasterURL.Scheme = "mesos"
	} else if sparkMasterURL.Scheme == "https" {
		sparkMasterURL.Scheme = "mesos-ssl"
	} else {
		log.Fatalf("Unsupported protocol '%s': %s", sparkMasterURL.Scheme, sparkMasterURL.String())
	}
	args.properties["spark.master"] = sparkMasterURL.String()

	// copy appResource to front of 'spark.jars' data:
	if args.isScala {
		jars, ok := args.properties["spark.jars"]
		if !ok || len(jars) == 0 {
			args.properties["spark.jars"] = args.app.String()
		} else {
			args.properties["spark.jars"] = fmt.Sprintf("%s,%s", args.app.String(), jars)
		}
	}

	// if spark.app.name is missing, set it to mainClass
	_, ok := args.properties["spark.app.name"]
	if !ok {
		args.properties["spark.app.name"] = args.mainClass
	}

	// fetch the spark task definition from Marathon, extract the docker image and HDFS config url:
	url := client.CreateServiceURL("replaceme", "")
	url.Path = fmt.Sprintf("/marathon/v2/apps/%s", config.ServiceName)

	responseBytes, err := client.CheckHTTPResponse(
		client.HTTPQuery(client.CreateHTTPURLRequest("GET", url, "", "", "")))

	responseJson := make(map[string]interface{})
	err = json.Unmarshal(responseBytes, &responseJson)
	if err != nil {
		return "", err
	}

	if config.Verbose {
		log.Printf("Response from Marathon lookup of task '%s':", config.ServiceName)
		prettyJson, err := json.MarshalIndent(responseJson, "", " ")
		if err != nil {
			log.Fatalf("Failed to prettify json (%s): %s", err, responseJson)
		} else {
			fmt.Fprintf(os.Stderr, "%s\n", string(prettyJson))
		}
	}

	// driver image
	_, contains := args.properties["spark.mesos.executor.docker.image"]
	if !contains {
		if cmd.submitDockerImage == "" {
			dispatcher_image, err := getStringFromTree(responseJson, []string{"app", "container", "docker", "image"})
			if err != nil {
				return "", err
			}
			args.properties["spark.mesos.executor.docker.image"] = dispatcher_image
		} else {
			args.properties["spark.mesos.executor.docker.image"] = cmd.submitDockerImage
		}
	}
	log.Printf("Using %s as the image for the driver", args.properties["spark.mesos.executor.docker.image"])

	_, contains = args.properties["spark.mesos.executor.docker.forcePullImage"]
	if !contains {
		log.Printf("Pulling image %s for executors, by default. To bypass set " +
			"spark.mesos.executor.docker.forcePullImage=false", args.properties["spark.mesos.executor.docker.image"])
		args.properties["spark.mesos.executor.docker.forcePullImage"] = "true"
	}

	// DCOS_SPACE
	if cmd.submitDcosSpace == "" { // get the DCOS_SPACE from the marathon app
		dispatcherId, err := getStringFromTree(responseJson, []string{"app", "id"})
		if err != nil {
			return "", err
		}
		cmd.submitDcosSpace = dispatcherId
	}
	log.Printf("Setting DCOS_SPACE to %s", cmd.submitDcosSpace)
	appendToProperty("spark.mesos.driver.labels", fmt.Sprintf("DCOS_SPACE:%s", cmd.submitDcosSpace),
		args)

	// HDFS config
	hdfs_config_url, err := getStringFromTree(responseJson, []string{"app", "labels", "SPARK_HDFS_CONFIG_URL"})
	if err == nil && len(hdfs_config_url) != 0 { // fail silently: it's normal for this to be unset
		hdfs_config_url = strings.TrimRight(hdfs_config_url, "/")
		appendToProperty("spark.mesos.uris",
			fmt.Sprintf("%s/hdfs-site.xml,%s/core-site.xml", hdfs_config_url, hdfs_config_url), args)
	}

	// kerberos configuration (include base64-encoded copy of --keytab OR --tgt):
	if args.kerberosPrincipal != "" {
		if args.keytabSecretPath == "" && args.tgtSecretPath == "" && args.tgtSecretValue == "" {
			return "", errors.New("Need to provide Keytab secret, TGT secret, or TGT value " +
				"with Kerberos principal")
		}

		if args.keytabSecretPath != "" && (args.tgtSecretValue != "" || args.tgtSecretPath != "") {
			return "", errors.New("Keytabs and TGTs cannot be used together")
		}

		if args.tgtSecretPath != "" && args.tgtSecretValue != "" {
			return "", errors.New("Cannot use a TGT-by-value and a TGT-by-secret at the same time")
		}

		log.Printf("Using Kerberos principal %s", args.kerberosPrincipal)
		args.properties["spark.yarn.principal"] = args.kerberosPrincipal
		krb5conf, err := getStringFromTree(responseJson, []string{"app", "env", "SPARK_MESOS_KRB5_CONF_BASE64"})
		if err != nil && krb5conf == "" {
			log.Printf("WARNING: krb5.conf (base64 encoded) could not be extracted from the " +
				"Dispatcher's config")
		}

		if krb5conf != "" {
			_, contains := args.properties["spark.mesos.driverEnv.KRB5_CONFIG_BASE64"]
			if !contains {
				args.properties["spark.mesos.driverEnv.KRB5_CONFIG_BASE64"] = krb5conf
			} else {
				log.Printf("Using user-specified krb5 config")
			}
		}

		err = setupKerberosAuthArgs(args)
		if err != nil {
			return "", err
		}
	}

	jsonMap := map[string]interface{}{
		"action":               "CreateSubmissionRequest",
		"appArgs":              args.appArgs,
		"appResource":          args.app.String(),
		"clientSparkVersion":   "2.0.0",
		"environmentVariables": cmd.submitEnv,
		"mainClass":            args.mainClass,
		"sparkProperties":      args.properties,
	}

	jsonPayload, err := json.Marshal(jsonMap)
	if err != nil {
		return "", err
	}

	if config.Verbose {
		log.Printf("Spark-submit json: %s\n", jsonPayload)
	}

	return string(jsonPayload), nil
}
