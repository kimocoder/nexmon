NEXMON_ROOT ?= $(abspath ../../../..)
FW_PATH=$(NEXMON_ROOT)/firmwares/bcm4330/5_90_100_41_sta
include $(FW_PATH)/definitions.mk

HEADER_SRCS=$(wildcard $(NEXMON_ROOT)/patches/include/*.h) $(wildcard $(FW_PATH)/.h)
LOCAL_SRCS=$(wildcard src/*.c) src/ucode_compressed.c
COMMON_SRCS=$(wildcard $(NEXMON_ROOT)/patches/common/*.c)
FW_SRCS=$(wildcard $(FW_PATH)/*.c)

CFLAGS =

EXTRA_PHONY = install-firmware backup-firmware install-backup
include $(NEXMON_ROOT)/patches/common/firmware_patch.mk

src/ucode_compressed.c: | init

all: $(RAM_FILE)

gen/memory.ld: $(FW_PATH)/definitions.mk
	@printf "\033[0;31m  GENERATING LINKER FILE\033[0m %s\n" $@
	$(Q)printf "rom : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(ROMSTART) $(ROMSIZE) > $@
	$(Q)printf "ram : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(RAMSTART) $(RAMSIZE) >> $@
	$(Q)printf "patch : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(PATCHSTART) $(PATCHSIZE) >> $@
	$(Q)printf "ucode : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(UCODESTART) $$(($(FP_CONFIG_BASE) - $(UCODESTART))) >> $@
	$(Q)printf "fpconfig : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(FP_CONFIG_BASE) $(FP_CONFIG_SIZE) >> $@

###################################################################
# ucode compression related
###################################################################

ucode_compressed.bin: $(FW_PATH)/ucode.bin
	@printf "\033[0;31m  COMPRESSING UCODE\033[0m %s => %s\n" $< $@
	$(Q)$(ZLIBFLATE) < $< > $@

src/ucode_compressed.c: ucode_compressed.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)xxd -i $< >> $@

###################################################################

install-firmware: $(RAM_FILE)
	@printf "\033[0;31m  REMOUNTING /system\033[0m\n"
	$(Q)adb shell 'su -c "mount -o rw,remount /system"'
	@printf "\033[0;31m  COPYING TO PHONE\033[0m %s => /sdcard/%s\n" $< $<
	$(Q)adb push $< /sdcard/ >> log/adb.log 2>> log/adb.log
	@printf "\033[0;31m  COPYING\033[0m /sdcard/bcmdhd_sta.bin => /system/etc/wifi/bcmdhd_sta.bin\n"
	$(Q)adb shell 'su -c "cp /sdcard/bcmdhd_sta.bin /system/etc/wifi/bcmdhd_sta.bin"'
	@printf "\033[0;31m  REBOOTING TO RELOAD FIRMWARE\033[0m\n"
	$(Q)adb shell 'reboot'

backup-firmware: FORCE
	adb shell 'su -c "cp /vendor/firmware/fw_bcmdhd.bin /sdcard/fw_bcmdhd.orig.bin"'
	adb pull /sdcard/fw_bcmdhd.orig.bin

install-backup: fw_bcmdhd.orig.bin
	adb shell 'su -c "mount -o rw,remount /system"' && \
	adb push $< /sdcard/ && \
	adb shell 'su -c "cp /sdcard/fw_bcmdhd.bin /vendor/firmware/fw_bcmdhd.bin"'
	adb shell 'su -c "ifconfig wlan0 down && ifconfig wlan0 up"'

clean-firmware: FORCE
	@printf "\033[0;31m  CLEANING\033[0m\n"
	$(Q)rm -fr $(RAM_FILE) obj gen log src/ucode_compressed.c ucode_compressed.bin
