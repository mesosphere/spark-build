#!/bin/bash

curl -s -k -o /dev/null -w "%{http_code}" -L https://$(hostname):$PORT2
