dist:
	bin/dist.sh

docker: dist
	bin/docker.sh

test:
	bin/test.sh

.PHONY: dist docker test
