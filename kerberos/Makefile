SHELL = /bin/bash
ORG = mesosphere

all: build

.PHONY: build
build:
	docker build -t $(ORG)/test-kdc .

push:
	docker push $(ORG)/test-kdc

deploy:
	@if ! dcos marathon app show /kdc &>/dev/null; then \
		dcos marathon app add marathon.json; \
	else \
		echo "Marathon app /kdc already deployed.";  \
	fi

test:
	./test.sh

clean:
	dcos marathon app remove /kdc || true
	dcos package uninstall hdfs || true
	dcos package uninstall spark || true
