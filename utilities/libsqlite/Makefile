APP_ABI ?= armeabi-v7a arm64-v8a

all: FORCE
	$(NDK_ROOT)/ndk-build NDK_APPLICATION_MK=`pwd`/Application.mk NDK_APP_OUT=. TARGET_PLATFORM=android-21 APP_ABI='$(APP_ABI)'

clean:
	rm -Rf libs
	rm -Rf local

install:
	@echo "nothing to install ..."

FORCE:
.PHONY: all clean install FORCE
