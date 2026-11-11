# ndk-build writes local/<abi>/libcrypto.a and removes each .o before compiling
# it. utilities/aircrack-ng and utilities/tcpdump also invoke this makefile,
# so two ndk-builds can run at once and llvm-ar fails with
# "x509name.o: No such file or directory". flock keeps a single archiver.
# local/.built.stamp is the file those callers wait on.
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
