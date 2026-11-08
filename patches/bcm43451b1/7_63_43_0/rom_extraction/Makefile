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

NEXMON_PRE_DEDUP = 1
EXTRA_PHONY = dump-rom install-firmware install-original backup-firmware install-backup
include $(NEXMON_ROOT)/patches/common/firmware_patch.mk

gen/ucode.bin gen/ucode_compressed.bin src/ucode_compressed.c src/templateram.c: | init

all: $(RAM_FILE)

gen/memory.ld: $(FW_PATH)/definitions.mk
	@printf "\033[0;31m  GENERATING LINKER FILE\033[0m %s\n" $@
	$(Q)printf "rom : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(ROMSTART) $(ROMSIZE) > $@
	$(Q)printf "ram : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(RAMSTART) $(RAMSIZE) >> $@
	$(Q)printf "patch : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(PATCHSTART) $(PATCHSIZE) >> $@
	$(Q)printf "ucode : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(UCODESTART) $$(($(FP_CONFIG_BASE) - $(UCODESTART))) >> $@
	$(Q)printf "fpconfig : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(FP_CONFIG_BASE) $(FP_CONFIG_SIZE) >> $@

fw_bcmdhd.complete.clean.bin: $(FW_PATH)/$(RAM_FILE) $(FW_PATH)/$(ROM_FILE)
	dd if=$(FW_PATH)/$(ROM_FILE) of=$@ bs=1 status=none conv=notrunc seek=$$(($(ROMSTART)))
	dd if=$< of=$@ bs=1 status=none conv=notrunc seek=$$(($(RAMSTART)))

fw_bcmdhd.complete.bin: $(RAM_FILE) $(FW_PATH)/$(ROM_FILE)
	dd if=$(FW_PATH)/$(ROM_FILE) of=$@ bs=1 status=none conv=notrunc seek=$$(($(ROMSTART)))
	dd if=$< of=$@ bs=1 status=none conv=notrunc seek=$$(($(RAMSTART)))

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

dump-rom: FORCE
	@printf "\033[0;31m  DUMPING ROM TO\033[0m /var/root/romdump.bin\n"
	$(Q)ssh local 'nexutil -g0x602 -l1024 -i -v0x0 -r > /var/root/romdump.bin && for n in {1..447}; do nexutil -g0x602 -l1024 -i -v$$(($$n*1024)) -r >> /var/root/romdump.bin; done'
	@printf "\033[0;31m  DOWNLOADING ROM DUMP\033[0m /var/root/romdump.bin => rom.bin\n"
	$(Q)scp local:/var/root/romdump.bin rom.bin

install-firmware: tempranillo.trx
	@printf "\033[0;31m  COPYING TO PHONE\033[0m %s => /sdcard/%s\n" $< $<
	$(Q)scp tempranillo.trx local:/usr/share/firmware/wifi/C-4345__s-B1/
	@printf "\033[0;31m  RELOADING FIRMWARE\033[0m\n"
	$(Q)ssh local '/usr/libexec/wifiFirmwareLoader -F /usr/share/firmware/wifi/C-4345__s-B1/tempranillo.trx'

install-original: $(FW_PATH)/$(RAM_FILE)
	@printf "\033[0;31m  REMOUNTING /vendor\033[0m\n"
	$(Q)adb shell 'su -c "mount -o rw,remount /vendor"'
	@printf "\033[0;31m  COPYING TO PHONE\033[0m %s => /sdcard/%s\n" $< $<
	$(Q)adb push $< /sdcard/ >> log/adb.log 2>> log/adb.log
	@printf "\033[0;31m  COPYING\033[0m /sdcard/fw_bcmdhd.bin => /vendor/firmware/fw_bcmdhd.bin\n"
	$(Q)adb shell 'su -c "cp /sdcard/fw_bcmdhd.bin /vendor/firmware/fw_bcmdhd.bin"'
	@printf "\033[0;31m  RELOADING FIRMWARE\033[0m\n"
	$(Q)adb shell 'su -c "ifconfig wlan0 down && ifconfig wlan0 up"'

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
	$(Q)rm -fr $(RAM_FILE) obj gen log src/ucode_compressed.c src/templateram.c
