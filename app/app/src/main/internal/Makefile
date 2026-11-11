APP_ABI ?= armeabi-v7a

all: FORCE
	$(MAKE) -C jni APP_ABI=$(APP_ABI)
	cp libs/$(APP_ABI)/libnexmonpentestsuite.so ../libs/$(APP_ABI)/

clean: FORCE
	rm -rf libs
	rm -rf local
	rm -rf obj

FORCE:


.PHONY: all clean