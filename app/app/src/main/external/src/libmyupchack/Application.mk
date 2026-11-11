APP_BUILD_SCRIPT := Android.mk
APP_STL := c++_static
APP_ABI := armeabi-v7a
APP_PLATFORM := android-21
APP_PROJECT_PATH := $(shell pwd)


# Legacy C sources predate C17: keep implicit declarations a warning and
# allow tentative definitions in more than one translation unit.
APP_CFLAGS += -Wno-error=implicit-function-declaration -Wno-error=implicit-int -fcommon
