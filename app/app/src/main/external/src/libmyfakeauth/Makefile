APP_ABI ?= armeabi-v7a

UTILITIES_PATH=../../../../../../../utilities/

all: libs/$(APP_ABI)/libmyfakeauth.so
	cd libs/$(APP_ABI)/ && cp *.so ../../../../../libs/$(APP_ABI)

libs/$(APP_ABI)/libmyfakeauth.so: Android.mk $(UTILITIES_PATH)/libsqlite/local/$(APP_ABI)/libsqlite.a $(UTILITIES_PATH)/libcrypto/local/$(APP_ABI)/libcrypto.a $(UTILITIES_PATH)/libssl/local/$(APP_ABI)/libssl.a ../../../../../../../utilities/libosdep/local/$(APP_ABI)/libosdep.a
	$(NDK_ROOT)/ndk-build NDK_APPLICATION_MK=`pwd`/Application.mk NDK_APP_OUT=. TARGET_PLATFORM=android-21 APP_ABI=$(APP_ABI)

$(UTILITIES_PATH)/libosdep/local/$(APP_ABI)/libosdep.a: FORCE
	cd $(UTILITIES_PATH)/libosdep && $(MAKE) APP_ABI=$(APP_ABI)

$(UTILITIES_PATH)/libsqlite/local/$(APP_ABI)/libsqlite.a: FORCE
	cd $(UTILITIES_PATH)/libsqlite && $(MAKE) APP_ABI=$(APP_ABI)

$(UTILITIES_PATH)/libssl/local/$(APP_ABI)/libssl.a: FORCE
	cd $(UTILITIES_PATH)/libssl && $(MAKE) APP_ABI=$(APP_ABI)

$(UTILITIES_PATH)/libcrypto/local/$(APP_ABI)/libcrypto.a: FORCE
	cd $(UTILITIES_PATH)/libcrypto && $(MAKE) APP_ABI=$(APP_ABI)
	
FORCE:

clean:
	rm -Rf libs
	rm -Rf local
