GIT_VERSION := $(shell git describe --abbrev=4 --dirty --always --tags)
USE_VENDOR_CMD := 0

# Build natively with gcc only when running on an Arm host building for itself.
# On an aarch64 host the NDK cross-toolchain (NDK_NATIVE_HOST_ARCH, exported by
# the top-level utilities Makefile / setup_env.sh) means we are cross-compiling
# for Android, so take the ndk-build path just like an x86_64 host. This keeps
# nexutil consistent with libnexio/libargp, which it links against.
NATIVE_BUILD := $(filter $(shell uname -m),armv6l armv7l aarch64)
ifdef NDK_NATIVE_HOST_ARCH
NATIVE_BUILD :=
endif
ifdef APP_ABI
NATIVE_BUILD :=
endif

LIBNEXIO_ABI := $(if $(APP_ABI),$(if $(filter all,$(APP_ABI)),arm64-v8a,$(firstword $(APP_ABI))),arm64-v8a)
LIBNEXIO := ../libnexio/local/$(LIBNEXIO_ABI)/libnexio.a
LIBARGP := ../libargp/local/$(LIBNEXIO_ABI)/libargp.a

ifeq ($(NATIVE_BUILD),)
all: $(LIBNEXIO) $(LIBARGP) Android.mk nexutil.c FORCE
	$(NDK_ROOT)/ndk-build NDK_APPLICATION_MK=`pwd`/Application.mk NDK_APP_OUT=. TARGET_PLATFORM=android-21 GIT_VERSION=$(GIT_VERSION) $(if $(APP_ABI),APP_ABI=$(APP_ABI))
else
all: nexutil
endif

ifeq ($(NATIVE_BUILD),)
libs/armeabi-v7a/nexutil libs/arm64-v8a/nexutil: $(LIBNEXIO) $(LIBARGP) Android.mk nexutil.c FORCE
	touch nexutil.c
	$(NDK_ROOT)/ndk-build NDK_APPLICATION_MK=`pwd`/Application.mk NDK_APP_OUT=. TARGET_PLATFORM=android-21 GIT_VERSION=$(GIT_VERSION) $(if $(APP_ABI),APP_ABI=$(APP_ABI))
else
nexutil: nexutil.c ../libnexio/libnexio.a FORCE
ifeq ($(USE_VENDOR_CMD),1)
	gcc -static -o nexutil nexutil.c bcmutils.c bcmwifi_channels.c b64-encode.c b64-decode.c -DUSE_VENDOR_CMD -DBUILD_ON_RPI -DVERSION=\"$(GIT_VERSION)\" -I. -I./include -I../../patches/include -I../libnexio -L../libnexio/ -lnexio -I../libargp $(shell pkg-config --cflags --libs libnl-3.0 libnl-genl-3.0) -lpthread
else
	gcc -std=gnu11 -fcommon -static -o nexutil nexutil.c nexutil_capabilities.c bcmutils.c bcmwifi_channels.c b64-encode.c b64-decode.c -DBUILD_ON_RPI -DVERSION=\"$(GIT_VERSION)\" -DUSE_NETLINK -I. -I./include -I../../patches/include -I../libnexio -L../libnexio/ -lnexio -I../libargp
endif
endif

$(LIBARGP) ../libargp/local/armeabi/libargp.a: FORCE
	$(MAKE) -C ../libargp $(if $(APP_ABI),APP_ABI=$(APP_ABI))

$(LIBNEXIO) ../libnexio/local/armeabi/libnexio.a ../libnexio/libnexio.a: FORCE
	$(MAKE) -C ../libnexio $(if $(APP_ABI),APP_ABI=$(APP_ABI))

ifeq ($(NATIVE_BUILD),)
install: libs/armeabi-v7a/nexutil
	adb push $< /sdcard/
	adb shell 'su -c "mount -o rw,remount /system"'
	adb shell 'su -c "cp /sdcard/nexutil /system/bin/nexutil"'
	adb shell 'su -c "chmod +x /system/bin/nexutil"'

install64: libs/arm64-v8a/nexutil
	adb push $< /sdcard/
	adb shell 'su -c "mount -o rw,remount /system"'
	adb shell 'su -c "cp /sdcard/nexutil /system/bin/nexutil"'
	adb shell 'su -c "chmod +x /system/bin/nexutil"'
else
install: nexutil
	cp $< /usr/bin/
endif

clean:
	rm -Rf libs
	rm -Rf local

FORCE:
	
