NEXMON_ROOT ?= $(abspath ../../../..)
include ../version.mk
include $(FW_PATH)/definitions.mk

# firmwares/.gitignore excludes rom.bin because dumps are device-specific, so
# the 9_88_0_0 dump is committed next to this target instead of in FW_PATH.
ROM_FILE=$(NEXMON_ROOT)/patches/bcm43436b0/9_88_0_0/rom_extraction/rom.bin

LOCAL_SRCS=$(wildcard src/*.c) src/ucode_compressed.c src/templateram.c
COMMON_SRCS=$(wildcard $(NEXMON_ROOT)/patches/common/*.c)
FW_SRCS=$(wildcard $(FW_PATH)/*.c)

CFLAGS = \
	-fno-strict-aliasing \
	-DWLC_UCODE_WRITE_BL_HOOK_ADDR=$(WLC_UCODE_WRITE_BL_HOOK_ADDR) \
	-DHNDRTE_RECLAIM_0_END_PTR=$(HNDRTE_RECLAIM_0_END_PTR) \
	-DTEMPLATERAMSTART_PTR=$(TEMPLATERAMSTART_PTR) \
	-DPATCHSTART=$(PATCHSTART) \
	-DFP_CONFIG_ORIGBASE=$(FP_CONFIG_ORIGBASE) \
	-DFP_CONFIG_ORIGEND=$(FP_CONFIG_ORIGEND) \
	-DUCODESIZE=$(UCODESIZE)

NEXMON_PRE_DEDUP = 1
FLASHPATCHES_AWK = flashpatches.bcm43596.mk.awk
EXTRA_PHONY = dump-rom install-firmware
include $(NEXMON_ROOT)/patches/common/firmware_patch.mk

gen/ucode.bin gen/ucode_compressed.bin src/ucode_compressed.c src/templateram.c: | init

all: $(RAM_FILE)

gen/memory.ld: $(FW_PATH)/definitions.mk
	@printf "\033[0;31m  GENERATING LINKER FILE\033[0m %s\n" $@
	$(Q)printf "rom : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(ROMSTART) $(ROMSIZE) > $@
	$(Q)printf "ram : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(RAMSTART) $(RAMSIZE) >> $@
	$(Q)printf "patch : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(PATCHSTART) $(PATCHSIZE) >> $@
	$(Q)printf "ucode : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $$(($(UCODESTART) - 4)) $$(($(PATCHSTART) - $(UCODESTART))) >> $@
	$(Q)printf "fpconfig : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(FP_CONFIG_BASE) $(FP_CONFIG_SIZE) >> $@

fw_bcmdhd.complete.clean.bin: $(FW_PATH)/$(RAM_FILE) $(ROM_FILE)
	dd if=$(ROM_FILE) of=$@ bs=1 status=none conv=notrunc seek=$$(($(ROMSTART)))
	dd if=$< of=$@ bs=1 status=none conv=notrunc seek=$$(($(RAMSTART)))

fw_bcmdhd.complete.bin: $(RAM_FILE) $(ROM_FILE)
	dd if=$(ROM_FILE) of=$@ bs=1 status=none conv=notrunc seek=$$(($(ROMSTART)))
	dd if=$< of=$@ bs=1 status=none conv=notrunc seek=$$(($(RAMSTART)))

###################################################################
# ucode compression related
###################################################################

ifneq ($(wildcard src/ucode.asm), )
gen/ucode.bin: src/ucode.asm
	@printf "\033[0;31m  ASSEMBLING UCODE\033[0m %s => %s\n" $< $@

ifneq ($(wildcard $(NEXMON_ROOT)/buildtools/b43/assembler/b43-asm.bin), )
	$(Q)PATH=$(PATH):$(NEXMON_ROOT)/buildtools/b43/assembler $(NEXMON_ROOT)/buildtools/b43/assembler/b43-asm $< $@ --format raw-le32
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
	$(Q)cat $< | $(ZLIBFLATE) > $@

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
	@printf "\033[0;31m  MAKE SURE PATCHED FIRMWARE IS INSTALLED FOR DUMPING\n"
	@printf "\033[0;31m  PLEASE RUN THE FOLLOWING COMMAND THROUGH adb shell\n"
	@printf '\033[0m nexutil -g0x602 -l1024 -i -v$(ROMSTART) -r > /sdcard/rom.bin && for n in `seq 1 581`; do nexutil -g0x602 -l1024 -i -v$$((($$n*1024)+$(ROMSTART))) -r >> /sdcard/rom.bin; done)\n'
	@printf "\033[0;31m  WHEN READY, PULL THE FILE WITH\033[0m adb pull /sdcard/rom.bin\n"

install-firmware: $(RAM_FILE)
	@printf "\033[0;31m  REMOUNTING /vendor\033[0m\n"
	$(Q)adb shell 'su -c "mount -o rw,remount /vendor"'
	@printf "\033[0;31m  COPYING TO WATCH\033[0m %s => /sdcard/%s\n" $< $<
	$(Q)adb push $< /sdcard/ >> log/adb.log 2>> log/adb.log
	@printf "\033[0;31m  COPYING\033[0m /sdcard/$(RAM_FILE) => /vendor/firmware/$(RAM_FILE)\n"
	$(Q)adb shell 'su -c "cp /sdcard/$(RAM_FILE) /vendor/firmware/$(RAM_FILE)"'
	@printf "\033[0;31m  RELOADING FIRMWARE\033[0m\n"
	$(Q)adb shell 'su -c "ifconfig wlan0 down && ifconfig wlan0 up"'

clean-firmware: FORCE
	@printf "\033[0;31m  CLEANING\033[0m\n"
	$(Q)rm -fr $(RAM_FILE) obj gen log src/ucode_compressed.c src/templateram.c ucode_compressed.bin
