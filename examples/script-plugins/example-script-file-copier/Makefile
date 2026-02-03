all: install

clean:
	rm -rf build

build:
	mkdir -p build/libs build/zip-content/example-script-file-copier
	cp -r contents resources plugin.yaml build/zip-content/example-script-file-copier
	cd build/zip-content; zip -r example-script-file-copier.zip *
	mv build/zip-content/example-script-file-copier.zip build/libs

