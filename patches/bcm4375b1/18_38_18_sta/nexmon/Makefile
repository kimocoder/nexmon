NEXMON_ROOT ?= $(abspath ../../../..)
include ../version.mk
include $(FW_PATH)/definitions.mk

LOCAL_SRCS=$(wildcard src/*.c) src/ucode1_compressed.c src/ucode2_compressed.c src/templateram0.c src/templateram1.c src/templateram2.c
COMMON_SRCS=$(wildcard $(NEXMON_ROOT)/patches/common/*.c)
FW_SRCS=$(wildcard $(FW_PATH)/*.c)

CFLAGS = \
	-fno-strict-aliasing \
	-DWLC_UCODE_WRITE_BL_HOOK_ADDR=$(WLC_UCODE_WRITE_BL_HOOK_ADDR) \
	-DUCODE1START_PTR=$(UCODE1START_PTR) \
	-DUCODE1SIZE_PTR=$(UCODE1SIZE_PTR) \
	-DUCODE2START_PTR=$(UCODE2START_PTR) \
	-DUCODE2SIZE_PTR=$(UCODE2SIZE_PTR) \
	-DHNDRTE_RECLAIM_0_END_PTR=$(HNDRTE_RECLAIM_0_END_PTR) \
	-DTEMPLATERAMSTART0_PTR=$(TEMPLATERAMSTART0_PTR) \
	-DTEMPLATERAMSTART1_PTR=$(TEMPLATERAMSTART1_PTR) \
	-DTEMPLATERAMSTART2_PTR=$(TEMPLATERAMSTART2_PTR) \
	-DVASIPSTART_PTR=$(VASIPSTART_PTR) \
	-DFP_CONFIG_ORIGBASE=$(FP_CONFIG_ORIGBASE) \
	-DFP_CONFIG_ORIGEND=$(FP_CONFIG_ORIGEND) \
	-DPATCHSTART=$(PATCHSTART) \
	-DUCODESIZE=$(UCODESIZE)

NEXMON_PRE_DEDUP = 1
FLASHPATCHES_AWK = flashpatches.bcm4375.mk.awk
EXTRA_PHONY = dump-rom install-firmware install-remote install-remote2
include $(NEXMON_ROOT)/patches/common/firmware_patch.mk

gen/ucode1.asm gen/ucode2.asm gen/ucode1.bin gen/ucode2.bin gen/ucode1_compressed.bin gen/ucode2_compressed.bin src/ucode1_compressed.c src/ucode2_compressed.c src/templateram0.c src/templateram1.c src/templateram2.c src/vasip.c: | init

all: $(RAM_FILE)

gen/memory.ld: $(FW_PATH)/definitions.mk
	@printf "\033[0;31m  GENERATING LINKER FILE\033[0m %s\n" $@
	$(Q)printf "rom : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(ROMSTART) $(ROMSIZE) > $@
	$(Q)printf "ram : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(RAMSTART) $(RAMSIZE) >> $@
	$(Q)printf "patch : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(PATCHSTART) $(PATCHSIZE) >> $@
	$(Q)printf "ucode : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(UCODE1START) $$(($(FP_CONFIG_BASE) - $(UCODE1START))) >> $@
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

gen/ucode1.asm: $(FW_PATH)/ucode1.bin
	$(NEXMON_ROOT)/buildtools/b43-unified/disassembler/b43-dasm $< $@ --arch 15 --format raw-le32
	$(NEXMON_ROOT)/buildtools/b43-unified/debug/b43-beautifier --asmfile $@ --defs $(NEXMON_ROOT)/buildtools/b43-unified/debug/include > $@.tmp && mv $@.tmp $@

gen/ucode2.asm: $(FW_PATH)/ucode2.bin
	$(NEXMON_ROOT)/buildtools/b43-unified/disassembler/b43-dasm $< $@ --arch 15 --format raw-le32
	$(NEXMON_ROOT)/buildtools/b43-unified/debug/b43-beautifier --asmfile $@ --defs $(NEXMON_ROOT)/buildtools/b43-unified/debug/include > $@.tmp && mv $@.tmp $@

ifneq ($(wildcard src/ucode1.asm), )
gen/ucode1.bin: src/ucode1.asm
	@printf "\033[0;31m  ASSEMBLING UCODE\033[0m %s => %s\n" $< $@

ifneq ($(wildcard $(NEXMON_ROOT)/buildtools/b43-unified/assembler/b43-asm.bin), )
	$(Q)PATH=$(PATH):$(NEXMON_ROOT)/buildtools/b43-unified/assembler $(NEXMON_ROOT)/buildtools/b43-unified/assembler/b43-asm $< $@ --format raw-le32
else
	$(error Warning: please compile b43-asm.bin first)
endif

else
gen/ucode1.bin: $(FW_PATH)/ucode1.bin
	@printf "\033[0;31m  COPYING UCODE\033[0m %s => %s\n" $< $@
	$(Q)cp $< $@
endif

ifneq ($(wildcard src/ucode2.asm), )
gen/ucode2.bin: src/ucode2.asm
	@printf "\033[0;31m  ASSEMBLING UCODE\033[0m %s => %s\n" $< $@

ifneq ($(wildcard $(NEXMON_ROOT)/buildtools/b43-unified/assembler/b43-asm.bin), )
	$(Q)PATH=$(PATH):$(NEXMON_ROOT)/buildtools/b43-unified/assembler $(NEXMON_ROOT)/buildtools/b43-unified/assembler/b43-asm $< $@ --format raw-le32
else
	$(error Warning: please compile b43-asm.bin first)
endif

else
gen/ucode2.bin: $(FW_PATH)/ucode2.bin
	@printf "\033[0;31m  COPYING UCODE\033[0m %s => %s\n" $< $@
	$(Q)cp $< $@
endif

gen/ucode1_compressed.bin: gen/ucode1.bin
	@printf "\033[0;31m  COMPRESSING UCODE1\033[0m %s => %s\n" $< $@
	$(Q)$(ZLIBFLATE) < $< > $@

gen/ucode2_compressed.bin: gen/ucode2.bin
	@printf "\033[0;31m  COMPRESSING UCODE2\033[0m %s => %s\n" $< $@
	$(Q)$(ZLIBFLATE) < $< > $@

src/ucode1_compressed.c: gen/ucode1_compressed.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

src/ucode2_compressed.c: gen/ucode2_compressed.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

src/templateram0.c: $(FW_PATH)/templateram0.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

src/templateram1.c: $(FW_PATH)/templateram1.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

src/templateram2.c: $(FW_PATH)/templateram2.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

src/vasip.c: $(FW_PATH)/vasip.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

###################################################################

dump-rom: FORCE
	@printf "\033[0;31m  DUMPING ROM TO\033[0m /var/root/romdump.bin\n"
	adb shell "su -c 'nexutil -g0x602 -l1024 -i -v0x0 -r'" > rom.bin && for n in {1..1343}; do adb shell "su -c 'nexutil -g0x602 -l1024 -i -v$$(($$n*1024)) -r'" >> rom.bin; done

install-firmware: $(RAM_FILE)
	@printf "\033[0;31m  REMOUNTING /system\033[0m\n"
	$(Q)adb shell 'su -c "mount -o rw,remount /system"'
	@printf "\033[0;31m  COPYING TO PHONE\033[0m %s => /sdcard/%s\n" $< $<
	$(Q)adb push $< /sdcard/ >> log/adb.log 2>> log/adb.log
	@printf "\033[0;31m  COPYING\033[0m /sdcard/$(RAM_FILE) => /vendor/etc/wifi/$(RAM_FILE)\n"
	$(Q)adb shell 'su -c "cp /sdcard/$(RAM_FILE) /vendor/etc/wifi/$(RAM_FILE)"'
	@printf "\033[0;31m  RELOADING FIRMWARE\033[0m\n"
	$(Q)adb shell 'su -c "ifconfig wlan0 down && ifconfig wlan0 up"'

install-remote: $(RAM_FILE)
	scp $(RAM_FILE) 51.254.39.142:~
	ssh 51.254.39.142 "cp bcmdhd_sta.bin_b1 /data/tmpfs/"
#	ssh 51.254.39.142 "unchroot /data/tmpfs/install"

install-remote2: $(RAM_FILE)
	scp $(RAM_FILE) 51.254.39.142_:~
	ssh 51.254.39.142_ "cp bcmdhd_sta.bin_b1 /data/tmpfs/"
#	ssh 51.254.39.142_ "unchroot /data/tmpfs/install"

clean-firmware: FORCE
	@printf "\033[0;31m  CLEANING\033[0m\n"
	$(Q)rm -fr $(RAM_FILE) obj gen log src/ucode1_compressed.c src/ucode2_compressed.c src/templateram0.c src/templateram1.c src/templateram2.c src/vasip.c
