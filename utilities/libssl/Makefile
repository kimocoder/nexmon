# Callers rebuild this library with -j while another ndk-build is already
# compiling it. See libcrypto/Makefile.
APP_ABI ?= armeabi-v7a arm64-v8a

all: FORCE
	mkdir -p local
	flock local $(NDK_ROOT)/ndk-build NDK_APPLICATION_MK=`pwd`/Application.mk NDK_APP_OUT=. TARGET_PLATFORM=android-21 APP_ABI='$(APP_ABI)'
	touch local/.built.stamp

clean:
	rm -Rf libs
	rm -Rf local

install:
	@echo "nothing to install ..."

FORCE:
.PHONY: all clean install FORCE
