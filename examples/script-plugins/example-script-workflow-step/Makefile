all: install

clean:
	rm -rf build

build:
	mkdir -p build/libs build/zip-content/example-script-workflow-step
	cp -r contents resources plugin.yaml build/zip-content/example-script-workflow-step
	cd build/zip-content; zip -r example-script-workflow-step.zip *
	mv build/zip-content/example-script-workflow-step.zip build/libs

