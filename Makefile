dist:
	bin/dist.sh

docker: dist
	bin/docker.sh

universe:
	bin/universe.sh

test:
	bin/test.sh

.PHONY: dist docker test universe
