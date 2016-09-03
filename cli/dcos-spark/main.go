package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"github.com/mesosphere/dcos-commons/cli"
	"gopkg.in/alecthomas/kingpin.v2"
	"log"
	"strings"
)

func main() {
	app, err := cli.NewApp("0.1.0", "Mesosphere", "CLI for launching/accessing Spark jobs")
	if err != nil {
		log.Fatalf(err.Error())
	}

	cli.HandleCommonFlags(app, "spark", "Spark DC/OS CLI Module")
	handleCommands(app)

	// Omit modname:
	kingpin.MustParse(app.Parse(cli.GetArguments()))
}

type SparkCommand struct {
	submissionId string

	submitArgs        string
	submitDockerImage string
	submitEnv         map[string]string

	statusSkipMessage bool

	logFollow bool
	logLines  uint
	logFile   string
}

func (cmd *SparkCommand) runSubmit(c *kingpin.ParseContext) error {
	jsonPayload, err := submitJson(cmd.submitArgs, cmd.submitDockerImage, cmd.submitEnv)
	if err != nil {
		return err
	}
	httpResponse := cli.HTTPPostJSON(
		fmt.Sprintf("/v1/submissions/create/%s", cmd.submissionId), jsonPayload)

	responseBytes := cli.GetResponseBytes(httpResponse)
	responseJson := make(map[string]interface{})
	err = json.Unmarshal(responseBytes, &responseJson)
	if err != nil {
		return err
	}

	err = checkSparkJSONResponse(responseJson)
	if err != nil {
		// Failure! Print the raw message:
		cli.PrintJSONBytes(responseBytes, httpResponse.Request)
		return err
	}

	// Success! Print the submissionId value:
	idObj, ok := responseJson["submissionId"]
	if ok {
		idString, ok := idObj.(string)
		if ok {
			// Match the older Python CLI's output:
			fmt.Printf("Run job succeeded. Submission id: %s\n", idString)
		} else {
			log.Printf("Failed to convert 'submissionId' field value to string: %s", responseJson)
		}
	} else {
		log.Printf("Failed to extract 'submissionId' field from JSON response: %s", responseJson)
	}
	return nil
}

func (cmd *SparkCommand) runStatus(c *kingpin.ParseContext) error {
	httpResponse := cli.HTTPGet(fmt.Sprintf("/v1/submissions/status/%s", cmd.submissionId))
	responseBytes := cli.GetResponseBytes(httpResponse)
	cli.PrintJSONBytes(responseBytes, httpResponse.Request)
	responseJson := make(map[string]interface{})
	err := json.Unmarshal(responseBytes, &responseJson)
	if err != nil {
		return err
	}

	if !cmd.statusSkipMessage {
		// Additionally, attempt to pretty-print the 'message' content, if any.
		// This is populated when the task has finished.
		messageObj, ok := responseJson["message"]
		if ok {
			messageString, ok := messageObj.(string)
			if ok {
				fmt.Printf("\nMessage:\n%s", messageString)
			} else {
				log.Printf("Failed to convert 'message' field value to string")
			}
		}
	}

	return checkSparkJSONResponse(responseJson)
}

func (cmd *SparkCommand) runLog(c *kingpin.ParseContext) error {
	args := []string{"task", "log", "--completed"}
	if cmd.logFollow {
		args = append(args, "--follow")
	}
	if cmd.logLines != 0 {
		args = append(args, fmt.Sprintf("--lines=%d", cmd.logLines))
	}
	args = append(args, cmd.submissionId)
	if len(cmd.logFile) != 0 {
		args = append(args, cmd.logFile)
	}
	result, err := cli.RunCLICommand(args...)
	// Always print output from CLI, which may contain user-facing errors (like 'log file not found'):
	fmt.Printf("%s\n", strings.TrimRight(result, "\n"))
	return err
}

func (cmd *SparkCommand) runKill(c *kingpin.ParseContext) error {
	httpResponse := cli.HTTPPost(fmt.Sprintf("/v1/submissions/kill/%s", cmd.submissionId))
	responseBytes := cli.GetResponseBytes(httpResponse)
	cli.PrintJSONBytes(responseBytes, httpResponse.Request)
	responseJson := make(map[string]interface{})
	err := json.Unmarshal(responseBytes, &responseJson)
	if err != nil {
		return err
	}
	return checkSparkJSONResponse(responseJson)
}

func (cmd *SparkCommand) runWebui(c *kingpin.ParseContext) error {
	// Hackish: Create the request we WOULD make, and print the resulting URL:
	fmt.Printf("%s\n", cli.CreateHTTPRequest("GET", "/ui").URL.String())
	return nil
}

func handleCommands(app *kingpin.Application) {
	cmd := &SparkCommand{submitEnv: make(map[string]string)}

	run := app.Command("run", "Submits a new Spark job ala 'spark-submit'").Action(cmd.runSubmit)

	run.Flag("submit-args", fmt.Sprintf("Arguments matching what would be sent to 'spark-submit': %s", sparkSubmitHelp())).Required().PlaceHolder("ARGS").StringVar(&cmd.submitArgs)
	run.Flag("docker-image", "Docker image to run the job within").StringVar(&cmd.submitDockerImage)
	run.Flag("env", "Environment variable(s) to pass into the Spark job.").Short('E').PlaceHolder("ENVKEY=ENVVAL").StringMapVar(&cmd.submitEnv)

	status := app.Command("status", "Retrieves the status of a submitted Spark job").Action(cmd.runStatus)
	status.Flag("skip-message", "Omit the additional printout of the 'message' field").BoolVar(&cmd.statusSkipMessage)
	status.Arg("submission-id", "The ID of the Spark job").Required().StringVar(&cmd.submissionId)

	log := app.Command("log", "Retrieves a log file from a submitted Spark job").Action(cmd.runLog)
	log.Flag("follow", "Dynamically update the log").BoolVar(&cmd.logFollow)
	log.Flag("lines_count", "Print the last N lines.").Default("10").UintVar(&cmd.logLines) //TODO "lines"?
	log.Flag("file", "Specify the sandbox file to print.").Default("stdout").StringVar(&cmd.logFile)
	log.Arg("submission-id", "The ID of the Spark job").Required().StringVar(&cmd.submissionId)

	kill := app.Command("kill", "Aborts a submitted Spark job").Action(cmd.runKill)
	kill.Arg("submission-id", "The ID of the Spark job").Required().StringVar(&cmd.submissionId)

	app.Command("webui", "Returns the Spark Web UI URL").Action(cmd.runWebui)
}

func checkSparkJSONResponse(responseJson map[string]interface{}) error {
	// Parse out the 'success' value returned by Spark, to ensure that we return an error code when success=false:
	successObj, ok := responseJson["success"]
	if !ok {
		return errors.New("Missing 'success' field in response JSON")
	}
	successBool, ok := successObj.(bool)
	if !ok {
		return errors.New(fmt.Sprintf("Unable to convert 'success' field in response JSON to boolean: %s", successObj))
	}
	if !successBool {
		return errors.New("Spark returned success=false")
	}
	return nil
}
