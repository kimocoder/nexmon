APP_ABI ?= armeabi-v7a arm64-v8a

all: FORCE
	$(NDK_ROOT)/ndk-build NDK_APPLICATION_MK=`pwd`/Application.mk NDK_APP_OUT=. TARGET_PLATFORM=android-21 APP_ABI='$(APP_ABI)'

install:
	@echo "nothing to install ..."

clean:
	rm -Rf libs
	rm -Rf local

FORCE:
.PHONY: all clean install FORCE
