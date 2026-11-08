NEXMON_ROOT ?= $(abspath ../../../..)
include ../version.mk
include $(FW_PATH)/definitions.mk

LOCAL_SRCS=$(wildcard src/*.c)

CFLAGS = \
	-fno-strict-aliasing \
	-DPATCHSTART=$(PATCHSTART) \
	-DUCODESIZE=$(UCODESIZE)

NEXMON_FW_TARGET = fw_bcmdhd.bin
NEXMON_PRE_DEDUP = 1
USE_FLASHPATCHES = 0
CLEAN_EXTRA = rom.bin
EXTRA_PHONY = dump-rom backup-firmware install-backup
include $(NEXMON_ROOT)/patches/common/firmware_patch.mk

all: fw_bcmdhd.bin

gen/memory.ld: $(FW_PATH)/definitions.mk
	@printf "\033[0;31m  GENERATING LINKER FILE\033[0m %s\n" $@
	$(Q)printf "rom : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(ROMSTART) $(ROMSIZE) > $@
	$(Q)printf "ram : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(RAMSTART) $(RAMSIZE) >> $@
	$(Q)printf "patch : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(PATCHSTART) $(PATCHSIZE) >> $@

dump-rom: fw_bcmdhd.bin
	@printf "\033[0;31m  COPYING TO PHONE\033[0m %s => /sdcard/%s\n" $< $<
	$(Q)adb push $< /sdcard/ >> log/adb.log 2>> log/adb.log
	@printf "\033[0;31m  LOADING FIRMWARE\033[0m /sdcard/fw_bcmdhd.bin\n"
	$(Q)adb shell 'su -c "dhdutil download /sdcard/fw_bcmdhd.bin"'
	@printf "\033[0;31m  DUMPING ROM\033[0m ROM => /sdcard/rom.bin\n"
	$(Q)adb shell 'su -c "dhdutil membytes -r 0x181000 $(ROMSIZE) > /sdcard/rom.bin"'
	@printf "\033[0;31m  PULLING\033[0m /sdcard/rom.bin => rom.bin\n"
	$(Q)adb pull /sdcard/rom.bin rom.bin
	@printf "\033[0;31m  RELOADING PREVIOUS FIRMWARE\033[0m\n"
	$(Q)adb shell 'su -c "ifconfig wlan0 down && ifconfig wlan0 up"'
	@printf "\033[0;31m  COPYING ROM\033[0m rom.bin => $(NEXMON_ROOT)/firmwares/bcm4356/rom.bin\n"
	$(Q)cp rom.bin $(NEXMON_ROOT)/firmwares/bcm4356/rom.bin

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
	$(Q)rm -fr fw_bcmdhd.bin obj gen log
