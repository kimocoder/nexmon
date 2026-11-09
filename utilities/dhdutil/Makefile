NATIVE_BUILD ?= $(if $(NDK_ROOT),,1)

ifeq ($(NATIVE_BUILD),1)
all: dhdutil

dhdutil: dhdu.c dhdu_linux.c bcmutils.c miniopt.c FORCE
	gcc -std=gnu11 -fcommon -static -o dhdutil dhdu.c dhdu_linux.c bcmutils.c miniopt.c -I. -I./include -I../../patches/include

else
all: libs/armeabi/dhdutil

libs/armeabi/dhdutil: *.c *.h Android.mk FORCE
	$(NDK_ROOT)/ndk-build NDK_APPLICATION_MK=`pwd`/Application.mk NDK_APP_OUT=. TARGET_PLATFORM=android-21
endif

install: libs/armeabi/dhdutil
	adb push $< /sdcard/
	adb shell 'su -c "mount -o rw,remount /system"'
	adb shell 'su -c "cp /sdcard/dhdutil /system/bin/dhdutil"'
	adb shell 'su -c "chmod +x /system/bin/dhdutil"'

clean:
	rm -Rf libs
	rm -Rf local
	rm -f dhdutil

FORCE:
.PHONY: all clean install FORCE
