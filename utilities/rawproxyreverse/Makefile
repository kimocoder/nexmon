APP_ABI ?= armeabi-v7a arm64-v8a

GIT_VERSION := $(shell git describe --abbrev=4 --dirty --always --tags)

all: deps FORCE
	touch rawproxyreverse.c
	$(NDK_ROOT)/ndk-build NDK_APPLICATION_MK=`pwd`/Application.mk NDK_APP_OUT=. TARGET_PLATFORM=android-21 APP_ABI='$(APP_ABI)' GIT_VERSION=$(GIT_VERSION)

deps: FORCE
	$(MAKE) -C ../libargp APP_ABI='$(APP_ABI)'
	$(MAKE) -C ../libpcap APP_ABI='$(APP_ABI)'

../libargp/local/armeabi-v7a/libargp.a: FORCE
	cd ../libargp && $(MAKE) APP_ABI='$(APP_ABI)'

../libpcap/local/armeabi-v7a/libpcap.a: FORCE
	cd ../libpcap && $(MAKE) APP_ABI='$(APP_ABI)'

clean:
	rm -Rf libs
	rm -Rf local
	rm -f /tmp/rawproxyreverse_sanitize.o

sanitize: rawproxyreverse.c
	$${CC:-gcc} $${CFLAGS:-} -fsanitize=address,undefined -g -O1 -DVERSION=\"test\" -I../libargp -I../libpcap -c rawproxyreverse.c -o /tmp/rawproxyreverse_sanitize.o

install: libs/armeabi-v7a/rawproxyreverse
	adb push $< /sdcard/
	adb shell 'su -c "mount -o rw,remount /system"'
	adb shell 'su -c "cp /sdcard/rawproxyreverse /system/bin/rawproxyreverse"'

FORCE:
