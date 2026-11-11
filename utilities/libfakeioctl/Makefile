APP_ABI ?= armeabi-v7a arm64-v8a
LIBNEXIO_ABI := $(firstword $(APP_ABI))
LIBNEXIO := ../libnexio/local/$(LIBNEXIO_ABI)/libnexio.a

all: $(LIBNEXIO) Android.mk fakeioctl.c
	$(NDK_ROOT)/ndk-build NDK_APPLICATION_MK=`pwd`/Application.mk NDK_APP_OUT=. TARGET_PLATFORM=android-21 APP_ABI='$(APP_ABI)'

$(LIBNEXIO): FORCE
	$(MAKE) -C ../libnexio APP_ABI='$(APP_ABI)'

install: libs/armeabi-v7a/libfakeioctl.so libs/arm64-v8a/libfakeioctl.so
	adb shell 'su -c "mount -o rw,remount /system"'
	adb push libs/armeabi-v7a/libfakeioctl.so /sdcard/
	adb shell 'su -c "cp /sdcard/libfakeioctl.so /system/lib/libfakeioctl.so"'
	adb push libs/arm64-v8a/libfakeioctl.so /sdcard/
	adb shell 'su -c "cp /sdcard/libfakeioctl.so /system/lib64/libfakeioctl.so"'

clean:
	rm -Rf libs
	rm -Rf local

FORCE:
.PHONY: all clean install FORCE