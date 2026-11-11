APP_BUILD_SCRIPT := Android.mk

# Legacy C sources predate C17: keep implicit declarations a warning and
# allow tentative definitions in more than one translation unit.
APP_CFLAGS += -Wno-error=implicit-function-declaration -Wno-error=implicit-int -fcommon

APP_PLATFORM := android-21
