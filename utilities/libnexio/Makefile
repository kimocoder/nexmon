GIT_VERSION := $(shell git describe --abbrev=4 --dirty --always --tags)
USE_VENDOR_CMD := 0
CC ?= gcc
AR ?= ar
CFLAGS ?=
LDFLAGS ?=

# Build natively with gcc only when running on an Arm host building for itself.
# On an aarch64 host the NDK cross-toolchain (NDK_NATIVE_HOST_ARCH, exported by
# the top-level utilities Makefile / setup_env.sh) means we are cross-compiling
# for Android, so take the ndk-build path just like an x86_64 host -- otherwise
# the Android consumers (e.g. libfakeioctl) would not find local/<abi>/*.a.
ifndef NATIVE_BUILD
NATIVE_BUILD := $(filter $(shell uname -m),armv6l armv7l aarch64)
ifdef NDK_NATIVE_HOST_ARCH
NATIVE_BUILD :=
endif
ifdef APP_ABI
NATIVE_BUILD :=
endif
endif

ifeq ($(NATIVE_BUILD),)
TARGET_ABI := $(if $(APP_ABI),$(if $(filter all,$(APP_ABI)),arm64-v8a,$(firstword $(APP_ABI))),arm64-v8a)
TARGET_LIB := local/$(TARGET_ABI)/libnexio.a

.PHONY: all

all: $(TARGET_LIB) libnexio.a

$(TARGET_LIB): Android.mk Application.mk libnexio.c libnexio.h
	mkdir -p local
	flock local $(NDK_ROOT)/ndk-build NDK_APPLICATION_MK=`pwd`/Application.mk NDK_APP_OUT=. TARGET_PLATFORM=android-21 $(if $(APP_ABI),APP_ABI=$(APP_ABI))
	@if [ -f local/$(TARGET_ABI)/libnexio.a ]; then \
		cp -f local/$(TARGET_ABI)/libnexio.a ./libnexio.a; \
	elif [ -f local/armeabi-v7a/libnexio.a ]; then \
		cp -f local/armeabi-v7a/libnexio.a ./libnexio.a; \
	fi

local/%/libnexio.a: Android.mk Application.mk libnexio.c libnexio.h
	mkdir -p local
	flock local $(NDK_ROOT)/ndk-build NDK_APPLICATION_MK=`pwd`/Application.mk NDK_APP_OUT=. TARGET_PLATFORM=android-21 APP_ABI=$*
	@if [ -f $@ ]; then \
		cp -f $@ ./libnexio.a; \
	fi

libnexio.a: $(TARGET_LIB)
	@if [ -f $(TARGET_LIB) ]; then \
		cp -f $(TARGET_LIB) ./libnexio.a; \
	fi
else
libnexio.a: libnexio.c
ifeq ($(USE_VENDOR_CMD),1)
	$(CC) $(CFLAGS) -fPIC -c libnexio.c -o libnexio.o -DUSE_VENDOR_CMD -DVERSION=\"$(GIT_VERSION)\" -I../../patches/include $(shell pkg-config --cflags --libs libnl-3.0 libnl-genl-3.0 2>/dev/null)
else
	$(CC) $(CFLAGS) -std=gnu11 -fcommon -fPIC -c libnexio.c -o libnexio.o -DBUILD_ON_RPI -DVERSION=\"$(GIT_VERSION)\" -I../../patches/include
	$(CC) $(CFLAGS) $(LDFLAGS) -shared -fPIC -std=gnu11 -fcommon -DBUILD_ON_RPI -DVERSION=\"$(GIT_VERSION)\" -I../nexutil/include -I../../patches/include libnexio.c ../nexutil/bcmwifi_channels.c ../nexutil/bcmutils.c -o libnexio.so
endif
	$(AR) rcs libnexio.a libnexio.o
endif

sanitize: libnexio.c
	$(CC) $(CFLAGS) -fsanitize=address,undefined -g -O1 -fPIC -c libnexio.c -o libnexio_sanitize.o -I../../patches/include
	$(AR) rcs libnexio_sanitize.a libnexio_sanitize.o

clean:
	rm -Rf libs
	rm -Rf local libnexio.o libnexio.a libnexio.so libnexio_sanitize.a libnexio_sanitize.o

install:
	@echo "nothing to install ..."
