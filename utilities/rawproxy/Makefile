APP_ABI ?= armeabi-v7a arm64-v8a

GIT_VERSION := $(shell git describe --abbrev=4 --dirty --always --tags)

all: deps FORCE
	touch rawproxy.c
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
	rm -f fuzz_radiotap fuzz_radiotap_fuzzer fuzz_radiotap_afl

install: libs/armeabi-v7a/rawproxy
	adb push $< /sdcard/
	adb shell 'su -c "mount -o rw,remount /system"'
	adb shell 'su -c "cp /sdcard/rawproxy /system/bin/rawproxy"'

# Fuzz harness for radiotap parsing (rawproxy.c:166, 0xFFFF pcap)
# Builds: native gcc, clang+libFuzzer, afl-gcc, and sanitizers
fuzz_radiotap: fuzz_radiotap.c
	$(CC) -DTEST_HARNESS -O2 -Wall -o $@ $<
	./$@

fuzz_radiotap_fuzzer: fuzz_radiotap.c
	clang -fsanitize=fuzzer,address,undefined -O1 -g -o $@ $< 2>/dev/null || echo "libFuzzer not available, skipping"

fuzz_radiotap_afl: fuzz_radiotap.c
	afl-gcc -O1 -g -o $@ $< 2>/dev/null || echo "afl-gcc not available, skipping"

fuzz: fuzz_radiotap
	@echo "Fuzz smoke passed"

sanitize: fuzz_radiotap.c rawproxy.c
	$(CC) -fsanitize=address,undefined -g -O1 -DTEST_HARNESS -o fuzz_radiotap_sanitize fuzz_radiotap.c
	./fuzz_radiotap_sanitize
	$(CC) -fsanitize=address,undefined -g -O1 -DVERSION=\"test\" -DUSE_LIBPCAP -I../libpcap -c rawproxy.c -o /tmp/rawproxy_sanitize.o

FORCE:
