APP_ABI ?= armeabi-v7a

all: Android.mk ../libsender/local/$(APP_ABI)/libsender.a
	$(NDK_ROOT)/ndk-build NDK_APPLICATION_MK=`pwd`/Application.mk NDK_APP_OUT=. TARGET_PLATFORM=android-21 APP_ABI=$(APP_ABI)
	cp libs/$(APP_ABI)/*.so ../../../libs/$(APP_ABI)

../libsender/local/$(APP_ABI)/libsender.a: FORCE
	cd ../libsender && $(MAKE) APP_ABI=$(APP_ABI)

clean:
	rm -Rf libs
	rm -Rf local

FORCE:

