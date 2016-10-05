all: env test packages

clean:
	bin/clean.sh

env: clean
	bin/env.sh

test:
	bin/test.sh

packages:
	bin/packages.sh

binary: env
	pyinstaller binary/binary.spec

.PHONY: binary
