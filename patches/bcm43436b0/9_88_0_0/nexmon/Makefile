NEXMON_ROOT ?= $(abspath ../../../..)
include ../version.mk
include $(FW_PATH)/definitions.mk

LOCAL_SRCS=$(wildcard src/*.c) src/ucode_compressed.c src/templateram.c
COMMON_SRCS=$(wildcard $(NEXMON_ROOT)/patches/common/*.c)
FW_SRCS=$(wildcard $(FW_PATH)/*.c)

CFLAGS = \
	-DWLC_UCODE_WRITE_BL_HOOK_ADDR=$(WLC_UCODE_WRITE_BL_HOOK_ADDR) \
	-DHNDRTE_RECLAIM_0_END_PTR=$(HNDRTE_RECLAIM_0_END_PTR) \
	-DTEMPLATERAMSTART_PTR=$(TEMPLATERAMSTART_PTR) \
	-DPATCHSTART=$(PATCHSTART) \
	-DUCODESIZE=$(UCODESIZE)

FLASHPATCHES_AWK = flashpatches.bcm43596.mk.awk
EXTRA_PHONY = backup-firmware install-firmware
include $(NEXMON_ROOT)/patches/common/firmware_patch.mk

gen/dummy.idc gen/ucode.asm gen/ucode.bin gen/ucode_compressed.bin src/ucode_compressed.c src/templateram.c: | init

all: $(RAM_FILE)

gen/memory.ld: $(FW_PATH)/definitions.mk
	@printf "\033[0;31m  GENERATING LINKER FILE\033[0m %s\n" $@
	$(Q)printf "rom : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(ROMSTART) $(ROMSIZE) > $@
	$(Q)printf "ram : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(RAMSTART) $(RAMSIZE) >> $@
	$(Q)printf "patch : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(PATCHSTART) $(PATCHSIZE) >> $@
	$(Q)printf "ucode : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $$(($(UCODESTART) - 4)) $$(($(PATCHSTART) - $(UCODESTART))) >> $@
	$(Q)printf "fpconfig : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(FP_CONFIG_BASE) $(FP_CONFIG_SIZE) >> $@

gen/dummy.idc: $(RAM_FILE)
	@printf "\033[0;31m  GENERATING IDC FILE\033[0m gen/nexmon.pre => %s\n" $@
	$(Q)cat gen/nexmon.pre | gawk 'BEGIN { printf "#import <idc.idc>\n\nstatic main() {\n" } { if (!seen[$$0]++ && $$2 == "DUMMY") { printf "\tMakeName(%s,\"%s\");\n",$$1,$$4 }; } END { printf "}\n" }' > $@

###################################################################
# ucode compression related
###################################################################

gen/ucode.asm: $(FW_PATH)/ucode.bin
	$(NEXMON_ROOT)/buildtools/b43/disassembler/b43-dasm $< $@ --arch 15 --format raw-le32
#	$(NEXMON_ROOT)/buildtools/b43/debug/b43-beautifier --asmfile $@ --defs $(NEXMON_ROOT)/buildtools/b43/debug/include > tmp && mv tmp $@

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

backup-firmware:
ifeq ($(shell uname -m),$(filter $(shell uname -m), armv6l armv7l aarch64))
	cp /lib/firmware/brcm/$(RAM_FILE) $(RAM_FILE).orig
else
	$(warning Warning: Cannot backup the original firmware on this arch.)
endif

install-firmware: $(RAM_FILE)
	@printf "\033[0;31m  REMOUNTING /vendor\033[0m\n"
	$(Q)adb shell 'su -c "mount -o rw,remount /vendor"'
	@printf "\033[0;31m  COPYING TO PHONE\033[0m %s => /sdcard/%s\n" $< $<
	$(Q)adb push $< /sdcard/ >> log/adb.log 2>> log/adb.log
	@printf "\033[0;31m  COPYING\033[0m /sdcard/$(RAM_FILE) => /vendor/firmware/$(RAM_FILE)\n"
	$(Q)adb shell 'su -c "cp /sdcard/$(RAM_FILE) /vendor/firmware/$(RAM_FILE)"'
	@printf "\033[0;31m  RELOADING FIRMWARE\033[0m\n"
	$(Q)adb shell 'su -c "ifconfig wlan0 down && ifconfig wlan0 up"'

clean-firmware: FORCE
	@printf "\033[0;31m  CLEANING\033[0m\n"
	$(Q)rm -fr $(RAM_FILE) obj gen log src/ucode_compressed.c src/templateram.c ucode_compressed.bin
