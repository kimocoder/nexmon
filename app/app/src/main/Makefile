UTILITIES_PATH = ../../../../utilities
PATCHES_PATH = ../../../../patches

NDK_ROOT ?= $(shell if [ -n "$$ANDROID_NDK_ROOT" ]; then echo "$$ANDROID_NDK_ROOT"; elif [ -n "$$ANDROID_NDK_HOME" ]; then echo "$$ANDROID_NDK_HOME"; elif [ -n "$$ANDROID_NDK" ]; then echo "$$ANDROID_NDK"; elif [ -d "/opt/android-sdk/ndk/30.0.16248370" ]; then echo "/opt/android-sdk/ndk/30.0.16248370"; elif [ -d "/opt/android-sdk/ndk" ]; then find /opt/android-sdk/ndk -mindepth 1 -maxdepth 1 -type d | sort -V | tail -n 1; fi)
export NDK_ROOT

# ABI for the APK's jniLibs (src/main/libs/<abi>). libwireshark_helper links
# the 2017 prebuilt Wireshark/glib archives in
# external/src/libwireshark_helper/prebuildlibs, which are 32-bit ARM only, so
# arm64-v8a needs those rebuilt first (see app/MODERNIZATION.md).
APP_ABI ?= armeabi-v7a
# assets/nexmon has no per-ABI directory, so the APK ships one set of
# executables. It is taken from this ABI.
ASSET_ABI ?= armeabi-v7a
export APP_ABI ASSET_ABI

all: assets/nexmon assets libs/$(APP_ABI)

assets: \
	assets/nexmon/fw_bcm4330_5_90_100_41_sta.bin \
	assets/nexmon/fw_bcm4339_6_37_34_43.bin \
	assets/nexmon/fw_bcm4358_7_112_200_17_sta.bin \
	assets/nexmon \
	assets/nexmon/rawproxy \
	assets/nexmon/rawproxyreverse \
	assets/nexmon/nc \
	assets/nexmon/iw \
	assets/nexmon/iwconfig \
	assets/nexmon/tcpdump \
	assets/nexmon/aircrack-ng \
	assets/nexmon/dhdutil \
	assets/nexmon/nexutil \
	assets/nexmon/mdk4 \
	assets/nexmon/socat \
	assets/nexmon/libfakeioctl.so \
	FORCE

assets/nexmon: FORCE
	mkdir -p assets/nexmon/

assets/nexmon/fw_bcm4330_5_90_100_41_sta.bin: FORCE
	make -C $(PATCHES_PATH)/bcm4330/5_90_100_41_sta/nexmon
	cp $(PATCHES_PATH)/bcm4330/5_90_100_41_sta/nexmon/bcmdhd_sta.bin $@

assets/nexmon/fw_bcm4339_6_37_34_43.bin: FORCE
	make -C $(PATCHES_PATH)/bcm4339/6_37_34_43/nexmon
	cp $(PATCHES_PATH)/bcm4339/6_37_34_43/nexmon/fw_bcmdhd.bin $@

assets/nexmon/fw_bcm4358_7_112_200_17_sta.bin: FORCE
	make -C $(PATCHES_PATH)/bcm4358/7_112_200_17_sta/nexmon
	cp $(PATCHES_PATH)/bcm4358/7_112_200_17_sta/nexmon/fw_bcmdhd.bin $@

assets/nexmon/rawproxy: FORCE
	make -C $(UTILITIES_PATH)/rawproxy APP_ABI=$(ASSET_ABI)
	cp $(UTILITIES_PATH)/rawproxy/libs/$(ASSET_ABI)/rawproxy $@

assets/nexmon/rawproxyreverse: FORCE
	make -C $(UTILITIES_PATH)/rawproxyreverse APP_ABI=$(ASSET_ABI)
	cp $(UTILITIES_PATH)/rawproxyreverse/libs/$(ASSET_ABI)/rawproxyreverse $@

assets/nexmon/tcpdump: FORCE
	make -C $(UTILITIES_PATH)/tcpdump APP_ABI=$(ASSET_ABI)
	cp $(UTILITIES_PATH)/tcpdump/libs/$(ASSET_ABI)/tcpdump $@

assets/nexmon/dhdutil: FORCE
	make -C $(UTILITIES_PATH)/dhdutil APP_ABI=$(ASSET_ABI)
	cp $(UTILITIES_PATH)/dhdutil/libs/$(ASSET_ABI)/dhdutil $@

assets/nexmon/nexutil: FORCE
	make -C $(UTILITIES_PATH)/nexutil APP_ABI=$(ASSET_ABI)
	cp $(UTILITIES_PATH)/nexutil/libs/$(ASSET_ABI)/nexutil $@

assets/nexmon/mdk4: FORCE
	make -C $(UTILITIES_PATH)/mdk4 APP_ABI=$(ASSET_ABI)
	cp $(UTILITIES_PATH)/mdk4/libs/$(ASSET_ABI)/mdk4 $@

assets/nexmon/libfakeioctl.so: FORCE
	make -C $(UTILITIES_PATH)/libfakeioctl APP_ABI=$(ASSET_ABI)
	cp $(UTILITIES_PATH)/libfakeioctl/libs/$(ASSET_ABI)/libfakeioctl.so $@

assets/nexmon/aircrack-ng: FORCE
	make -C $(UTILITIES_PATH)/aircrack-ng APP_ABI=$(ASSET_ABI)
	cp $(UTILITIES_PATH)/aircrack-ng/libs/$(ASSET_ABI)/* $(dir $@)

assets/nexmon/nc: FORCE
	make -C $(UTILITIES_PATH)/netcat APP_ABI=$(ASSET_ABI)
	cp $(UTILITIES_PATH)/netcat/libs/$(ASSET_ABI)/nc $@

assets/nexmon/iw: FORCE
	make -C $(UTILITIES_PATH)/iw APP_ABI=$(ASSET_ABI)
	cp $(UTILITIES_PATH)/iw/libs/$(ASSET_ABI)/iw $@

assets/nexmon/socat: FORCE
	make -C $(UTILITIES_PATH)/socat APP_ABI=$(ASSET_ABI)
	cp $(UTILITIES_PATH)/socat/libs/$(ASSET_ABI)/socat $@

assets/nexmon/iwconfig: FORCE
	make -C $(UTILITIES_PATH)/wireless_tools APP_ABI=$(ASSET_ABI)
	cp $(UTILITIES_PATH)/wireless_tools/libs/$(ASSET_ABI)/* $(dir $@)

libs/$(APP_ABI): utilities-libs
	mkdir -p $@
	$(MAKE) -C external APP_ABI=$(APP_ABI)
	$(MAKE) -C internal APP_ABI=$(APP_ABI)

# Static libraries from utilities/ that external/src/*/Android.mk links
# against. They are not built by external/ itself, so build them here.
utilities-libs: FORCE
	@for lib in libssl libcrypto libsqlite libosdep; do \
		$(MAKE) -C $(UTILITIES_PATH)/$$lib APP_ABI=$(APP_ABI) || exit 1; \
	done

clean: FORCE
	$(MAKE) -C external clean
	$(MAKE) -C internal clean
	rm -rf libs
	rm -rf assets/nexmon/

FORCE:


.PHONY: all clean