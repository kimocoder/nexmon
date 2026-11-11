# NDK wrapper. Do not replace this with the autotools-generated Makefile
# (Makefile.in / configure); utilities/Makefile invokes `make -C aircrack-ng`
# and expects ndk-build, same as tcpdump/mdk4/nexutil.

APP_ABI ?= armeabi-v7a arm64-v8a

# crypto/*.cc and ssl/*.cc, one directory deep, plus generated err_data.cc.
# sources.mk lists exactly these shapes (see utilities/boringssl/sources.mk).
BORINGSSL_CRYPTO_INPUTS := ../libcrypto/Android.mk ../libcrypto/Application.mk ../boringssl/crypto-sources.mk ../boringssl/sources.mk \
	$(wildcard ../boringssl/crypto/*.cc ../boringssl/crypto/*/*.cc ../boringssl/gen/crypto/*.cc ../boringssl/include/openssl/*.h)
BORINGSSL_SSL_INPUTS := ../libssl/Android.mk ../libssl/Application.mk ../boringssl/ssl-sources.mk ../boringssl/sources.mk \
	$(wildcard ../boringssl/ssl/*.cc ../boringssl/include/openssl/*.h)

all: deps FORCE
	$(NDK_ROOT)/ndk-build NDK_APPLICATION_MK=`pwd`/Application.mk NDK_APP_OUT=. TARGET_PLATFORM=android-21 APP_ABI='$(APP_ABI)'

deps: FORCE
	$(MAKE) -C ../libssl APP_ABI='$(APP_ABI)'
	$(MAKE) -C ../libcrypto APP_ABI='$(APP_ABI)'

../libssl/local/.built.stamp: $(BORINGSSL_SSL_INPUTS)
	$(MAKE) -C ../libssl APP_ABI='$(APP_ABI)'

../libcrypto/local/.built.stamp: $(BORINGSSL_CRYPTO_INPUTS)
	$(MAKE) -C ../libcrypto APP_ABI='$(APP_ABI)'

install: libs/armeabi-v7a/aircrack-ng
	adb push libs/armeabi-v7a/aireplay-ng /sdcard/
	adb shell 'su -c "mount -o rw,remount /system"'
	adb shell 'su -c "cp /sdcard/aireplay-ng /system/bin/aireplay-ng"'
	adb shell 'su -c "chmod +x /system/bin/aireplay-ng"'

clean:
	rm -Rf libs
	rm -Rf local

FORCE:
