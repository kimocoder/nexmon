APP_ABI ?= armeabi-v7a arm64-v8a
IPERF3_ABI := $(firstword $(APP_ABI))

all: FORCE
	$(NDK_ROOT)/ndk-build NDK_APPLICATION_MK=`pwd`/Application.mk NDK_APP_OUT=. TARGET_PLATFORM=android-21 APP_ABI='$(APP_ABI)'

install: libs/$(IPERF3_ABI)/iperf3
	adb push $< /sdcard/
	adb shell 'su -c "mount -o rw,remount /system"'
	adb shell 'su -c "cp /sdcard/iperf3 /system/bin/iperf3"'
	adb shell 'su -c "chmod +x /system/bin/iperf3"'

clean:
	rm -Rf libs
	rm -Rf local

FORCE:
.PHONY: all clean install FORCE
