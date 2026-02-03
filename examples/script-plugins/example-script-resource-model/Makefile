all: install

clean:
	rm -rf build

build:
	mkdir -p build/libs build/zip-content/example-script-resource-model
	cp -r contents resources plugin.yaml build/zip-content/example-script-resource-model
	cd build/zip-content; zip -r example-script-resource-model.zip *
	mv build/zip-content/example-script-resource-model.zip build/libs

