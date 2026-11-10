all: libs/armeabi/libargp.a

libs/armeabi/libargp.a: Android.mk
	$(NDK_ROOT)/ndk-build NDK_APPLICATION_MK=`pwd`/Application.mk NDK_APP_OUT=. TARGET_PLATFORM=android-21 $(if $(APP_ABI),APP_ABI=$(APP_ABI))

install:
	@echo "nothing to install ..."

clean:
	rm -Rf libs
	rm -Rf local
