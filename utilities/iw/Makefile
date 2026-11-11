APP_ABI ?= armeabi-v7a arm64-v8a
IW_ABI := $(firstword $(APP_ABI))

all: FORCE nl80211-commands.inc
	$(NDK_ROOT)/ndk-build NDK_APPLICATION_MK=`pwd`/Application.mk NDK_APP_OUT=. TARGET_PLATFORM=android-21 APP_ABI='$(APP_ABI)'

# Same generator as upstream iw (requires GNU sed).
nl80211-commands.inc: nl80211.h
	@echo '  GEN  ' $@
	@sed 's%^\tNL80211_CMD_%%;t n;d;:n s%^\([^=]*\),.*%\t[NL80211_CMD_\1] = "\L\1",%;t;d' nl80211.h | grep -v "reserved" > $@.tmp
	@mv $@.tmp $@

install: libs/$(IW_ABI)/iw
	adb push $< /sdcard/
	adb shell 'su -c "mount -o rw,remount /system"'
	adb shell 'su -c "cp /sdcard/iw /system/bin/iw"'
	adb shell 'su -c "chmod +x /system/bin/iw"'

clean:
	rm -Rf libs
	rm -Rf local
	rm -f nl80211-commands.inc.tmp

FORCE:
.PHONY: all clean install FORCE
