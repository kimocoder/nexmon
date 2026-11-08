NEXMON_ROOT ?= $(abspath ../../../..)
include ../version.mk
include $(FW_PATH)/definitions.mk

LOCAL_SRCS=$(wildcard src/*.c) src/ucode_compressed.c src/templateram.c
COMMON_SRCS=$(wildcard $(NEXMON_ROOT)/patches/common/*.c)
FW_SRCS=$(wildcard $(FW_PATH)/*.c)

CFLAGS = \
	-fno-strict-aliasing \
	-DPATCHSTART=$(PATCHSTART) \
	-DUCODESIZE=$(UCODESIZE)

NEXMON_FW_TARGET = fw_bcm43455_hw.bin
NEXMON_PRE_DEDUP = 1
CLEAN_EXTRA = rom.bin
EXTRA_PHONY = dump-rom backup-firmware install-backup
include $(NEXMON_ROOT)/patches/common/firmware_patch.mk

gen/ucode.bin gen/ucode_compressed.bin src/ucode_compressed.c src/templateram.c: | init

all: fw_bcm43455_hw.bin

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

ifneq ($(wildcard src/ucode.asm), )
gen/ucode.bin: src/ucode.asm
	@printf "\033[0;31m  ASSEMBLING UCODE\033[0m %s => %s\n" $< $@

ifneq ($(wildcard $(NEXMON_ROOT)/buildtools/b43-unified/assembler/b43-asm.bin), )
	$(Q)PATH=$(PATH):$(NEXMON_ROOT)/buildtools/b43-unified/assembler $(NEXMON_ROOT)/buildtools/b43-unified/assembler/b43-asm $< $@ --format raw-le32
else
	$(error Warning: please compile b43-asm.bin first)
endif

else
gen/ucode.bin: $(FW_PATH)/ucode.bin
	@printf "\033[0;31m  COPYING UCODE\033[0m %s => %s\n" $< $@
	$(Q)cp $< $@
endif

gen/ucode_compressed.bin: gen/ucode.bin
	@printf "\033[0;31m  COMPRESSING UCODE\033[0m %s => %s\n" $< $@
	$(Q)$(ZLIBFLATE) < $< > $@

src/ucode_compressed.c: gen/ucode_compressed.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

src/templateram.c: $(FW_PATH)/templateram.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

###################################################################

dump-rom: fw_bcm43455_hw.bin
	@printf "\033[0;31m  COPYING TO PHONE\033[0m %s => /sdcard/%s\n" $< $<
	$(Q)adb push $< /sdcard/ >> log/adb.log 2>> log/adb.log
	@printf "\033[0;31m  Stopping wifi service and killing wpa_supplicant\033[0m\n"
	$(Q)adb shell 'su -c "mount -o rw,remount /vendor"'
	$(Q)adb shell 'su -c "/system/bin/svc wifi disable"'
	@printf "\033[0;31m  Killing wpa_supplicant and backup it\033[0m\n"
	$(Q)adb shell 'su -c "killall wpa_supplicant"'
	$(Q)adb shell 'su -c "mv /system/bin/wpa_supplicant /system/bin/wpa_supplicant.backup"'
	$(Q)adb shell 'su -c "killall wpa_supplicant"'
	@printf "\033[0;31m  LOADING FIRMWARE\033[0m /sdcard/fw_bcm43455_hw.bin\n"
	$(Q)adb shell 'su -c "dhdutil download /sdcard/fw_bcm43455_hw.bin"'
	@printf "\033[0;31m  DUMPING ROM\033[0m ROM => /sdcard/rom.bin\n"
	$(Q)adb shell 'su -c "dhdutil membytes -r 0x199000 $(ROMSIZE) > /sdcard/rom.bin"'
	@printf "\033[0;31m  PULLING\033[0m /sdcard/rom.bin => rom.bin\n"
	$(Q)adb pull /sdcard/rom.bin rom.bin
	@printf "\033[0;31m  Restoring wpa_supplicant\033[0m\n"
	$(Q)adb shell 'su -c "mv /system/bin/wpa_supplicant.backup /system/bin/wpa_supplicant"'
	@printf "\033[0;31m  RELOADING PREVIOUS FIRMWARE\033[0m\n"
	$(Q)adb shell 'su -c "ifconfig wlan0 down && ifconfig wlan0 up"'
	@printf "\033[0;31m  COPYING ROM\033[0m rom.bin => $(NEXMON_ROOT)/firmwares/bcm43455/rom.bin\n"
	$(Q)cp rom.bin $(NEXMON_ROOT)/firmwares/bcm43455/rom.bin

backup-firmware: FORCE
	adb shell 'su -c "cp /vendor/firmware/fw_bcm43455_hw.bin /sdcard/fw_bcm43455_hw.orig.bin"'
	adb pull /sdcard/fw_bcm43455_hw.orig.bin

install-backup: fw_bcm43455_hw.orig.bin
	adb shell 'su -c "mount -o rw,remount /system"' && \
	adb push $< /sdcard/ && \
	adb shell 'su -c "cp /sdcard/fw_bcm43455_hw.bin /vendor/firmware/fw_bcm43455_hw.bin"'
	adb shell 'su -c "ifconfig wlan0 down && ifconfig wlan0 up"'

clean-firmware: FORCE
	@printf "\033[0;31m  CLEANING\033[0m\n"
	$(Q)rm -fr fw_bcm43455_hw.bin obj gen log src/ucode_compressed.c src/templateram.c
