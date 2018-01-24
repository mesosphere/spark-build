package main

import (
	"errors"
	"fmt"
	"log"
)

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

func appendToPropertyIfSet(propValue, toAppend string, args *sparkArgs) {
	_, contains := args.properties[propValue]
	if contains {
		args.properties[propValue] += "," + toAppend
	}
}

func setPropertyToDefaultIfNotSet(args *sparkArgs, prop, setting string) {
	_, contains := args.properties[prop]
	if !contains {
		args.properties[prop] = setting
	}
}

func addPropertyAndWarn(args *sparkArgs, prop, setting string) {
	oldVal, contains := args.properties[prop]
	if contains {
		log.Printf("WARNING: property %s being overwritten with %s (previously %s)",
			prop, setting, oldVal)
	}
	args.properties[prop] = setting
}
