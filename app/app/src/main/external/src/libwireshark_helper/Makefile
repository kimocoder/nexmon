APP_ABI ?= armeabi-v7a

# prebuildlibs/ holds 2017-era Wireshark/glib/gettext static archives built for
# 32-bit ARM. They cannot be linked into an arm64-v8a build, and NDK r30 no
# longer knows the old `armeabi` ABI, so armeabi-v7a is the only usable target.
ifneq ($(APP_ABI),armeabi-v7a)
$(error libwireshark_helper supports APP_ABI=armeabi-v7a only; prebuildlibs/ are 32-bit ARM, see app/MODERNIZATION.md)
endif

all: Android.mk ../libpcap/local/$(APP_ABI)/libpcap.a prebuildlibs/libwireshark.a
	$(NDK_ROOT)/ndk-build NDK_APPLICATION_MK=`pwd`/Application.mk NDK_APP_OUT=. TARGET_PLATFORM=android-21 APP_ABI=$(APP_ABI)
	cp libs/$(APP_ABI)/*.so ../../../libs/$(APP_ABI)

prebuildlibs/libwireshark.a: prebuildlibs/libwireshark.tar.gz
	cd prebuildlibs && tar xfvz libwireshark.tar.gz

../libpcap/local/$(APP_ABI)/libpcap.a: FORCE
	cd ../libpcap && $(MAKE) APP_ABI=$(APP_ABI)

clean:
	rm -Rf libs
	rm -Rf local

FORCE: