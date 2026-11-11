APP_ABI ?= armeabi-v7a arm64-v8a

all: deps FORCE
	$(NDK_ROOT)/ndk-build NDK_APPLICATION_MK=`pwd`/Application.mk NDK_APP_OUT=. TARGET_PLATFORM=android-21 APP_ABI='$(APP_ABI)'

deps: FORCE
	$(MAKE) -C ../libosdep APP_ABI='$(APP_ABI)'
	$(MAKE) -C ../libpcap APP_ABI='$(APP_ABI)'

../libosdep/local/armeabi-v7a/libosdep.a: FORCE
	cd ../libosdep && $(MAKE) APP_ABI='$(APP_ABI)'

../libpcap/local/armeabi-v7a/libpcap.a: FORCE
	cd ../libpcap && $(MAKE) APP_ABI='$(APP_ABI)'

clean:
	rm -Rf libs
	rm -Rf local

install: libs/armeabi-v7a/mdk4
	adb push $< /sdcard/
	adb shell 'su -c "mount -o rw,remount /system"'
	adb shell 'su -c "cp /sdcard/mdk4 /system/bin/mdk4"'
	adb shell 'su -c "chmod +x /system/bin/mdk4"'

FORCE:
