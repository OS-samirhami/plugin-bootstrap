all: install

clean:
	rm -rf build

build:
	mkdir -p build/libs build/zip-content/example-ui-plugin
	cp -r resources plugin.yaml build/zip-content/example-ui-plugin
	cd build/zip-content; zip -r example-ui-plugin.zip *
	mv build/zip-content/example-ui-plugin.zip build/libs

