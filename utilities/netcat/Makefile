APP_ABI ?= armeabi-v7a arm64-v8a
NETCAT_ABI := $(firstword $(APP_ABI))

all: FORCE
	$(NDK_ROOT)/ndk-build NDK_APPLICATION_MK=`pwd`/Application.mk NDK_APP_OUT=. TARGET_PLATFORM=android-21 APP_ABI='$(APP_ABI)'

install: libs/$(NETCAT_ABI)/nc
	adb push $< /sdcard/
	adb shell 'su -c "mount -o rw,remount /system"'
	adb shell 'su -c "cp /sdcard/nc /system/bin/nc"'
	adb shell 'su -c "chmod +x /system/bin/nc"'

clean:
	rm -Rf libs
	rm -Rf local

FORCE:
.PHONY: all clean install FORCE
