all: install

clean:
	rm -rf build

build:
	mkdir -p build/libs build/zip-content/example-script-option
	cp -r contents resources plugin.yaml build/zip-content/example-script-option
	cd build/zip-content; zip -r example-script-option.zip *
	mv build/zip-content/example-script-option.zip build/libs

