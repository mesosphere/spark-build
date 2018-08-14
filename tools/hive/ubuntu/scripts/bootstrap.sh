#!/bin/bash

/usr/sbin/sshd
service apache2 restart

if [[ $1 == "-bash" ]]; then
  /bin/bash
fi

if [[ $1 == "-d" ]]; then
  while true; do sleep 1000; done
fi
