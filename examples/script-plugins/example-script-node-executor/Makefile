all: install

clean:
	rm -rf build

build:
	mkdir -p build/libs build/zip-content/example-script-node-executor
	cp -r contents resources plugin.yaml build/zip-content/example-script-node-executor
	cd build/zip-content; zip -r example-script-node-executor.zip *
	mv build/zip-content/example-script-node-executor.zip build/libs

