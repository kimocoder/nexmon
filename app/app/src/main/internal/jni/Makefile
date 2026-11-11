APP_ABI ?= armeabi-v7a

# NDK r30 installs into local/<abi> because Application.mk sets
# APP_PROJECT_PATH; older NDKs used libs/<abi>. Accept either.
all: FORCE
	$(NDK_ROOT)/ndk-build NDK_APPLICATION_MK=`pwd`/Application.mk NDK_APP_OUT=. TARGET_PLATFORM=android-21 APP_ABI=$(APP_ABI)
	@if [ -d libs/$(APP_ABI) ]; then \
		cp libs/$(APP_ABI)/*.so ../libs/$(APP_ABI)/; \
	else \
		cp local/$(APP_ABI)/*.so ../libs/$(APP_ABI)/; \
	fi

clean:
	rm -rf local

FORCE:

.PHONY: all clean