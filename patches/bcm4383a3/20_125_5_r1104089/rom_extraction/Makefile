NEXMON_ROOT ?= $(abspath ../../../..)
include ../version.mk
include $(FW_PATH)/definitions.mk

LOCAL_SRCS=$(wildcard src/*.c) src/ucode0_compressed.c src/ucode1_compressed.c src/templateram0.c src/templateram1.c src/templateram2.c 
COMMON_SRCS=$(NEXMON_ROOT)/patches/common/ucode_compression_code.c $(NEXMON_ROOT)/patches/common/objmem.c $(NEXMON_ROOT)/patches/common/argprintf.c $(NEXMON_ROOT)/patches/common/wrapper.c
FW_SRCS=$(wildcard $(FW_PATH)/*.c)

DATETIME := $(shell date -u +'%b %e %Y %T')

CFLAGS = \
	-fno-strict-aliasing \
	-DWLC_UCODE_WRITE_BL_HOOK_ADDR=$(WLC_UCODE_WRITE_BL_HOOK_ADDR) \
	-DRECLAIM_3_END_PTR_0=$(RECLAIM_3_END_PTR_0) \
	-DMPU_PROTECT_ON_BL_ADDR=$(MPU_PROTECT_ON_BL_ADDR) \
	-DFP_CONFIG_ORIGEND=$(FP_CONFIG_ORIGEND) \
	-DFP_CONFIG_ORIGBASE=$(FP_CONFIG_ORIGBASE) \
	-DFP_CONFIG_END=$(FP_CONFIG_END) \
	-DPATCHSTART=$(PATCHSTART) \
	-DPATCHEND=$(PATCHEND) \
	-DTINFLATE_OUTPUT_SIZE=$(TINFLATE_OUTPUT_SIZE) \
	-DUCODE0START_PTR=$(UCODE0START_PTR) \
	-DUCODE0SIZE_PTR=$(UCODE0SIZE_PTR) \
	-DUCODE1START_PTR=$(UCODE1START_PTR) \
	-DUCODE1SIZE_PTR=$(UCODE1SIZE_PTR) \
	-DTEMPLATERAM0START_PTR=$(TEMPLATERAM0START_PTR) \
	-DTEMPLATERAM1START_PTR=$(TEMPLATERAM1START_PTR) \
	-DTEMPLATERAM2START_PTR=$(TEMPLATERAM2START_PTR) \
	-DFP_CONFIG_BASE_PTR_1=$(FP_CONFIG_BASE_PTR_1) \
	-DFP_CONFIG_END_PTR_1=$(FP_CONFIG_END_PTR_1) \
	-DFP_CONFIG_BASE_PTR_2=$(FP_CONFIG_BASE_PTR_2) \
	-DFP_CONFIG_END_PTR_2=$(FP_CONFIG_END_PTR_2) \
	-DFP_CONFIG_BASE_PTR_3=$(FP_CONFIG_BASE_PTR_3) \
	-DFP_CONFIG_END_PTR_3=$(FP_CONFIG_END_PTR_3) \
	-DFP_CONFIG_BASE_PTR_4=$(FP_CONFIG_BASE_PTR_4) \
	-DFP_CONFIG_END_PTR_4=$(FP_CONFIG_END_PTR_4) \
	-DFP_CONFIG_END_PTR_5=$(FP_CONFIG_END_PTR_5) \
	-DFP_CONFIG_FIRST_ENTRY_PTR=$(FP_CONFIG_FIRST_ENTRY_PTR) \
	-DMPU_RESTRICTION_ADDR1=$(MPU_RESTRICTION_ADDR1) \
	-DMPU_RESTRICTION_ADDR2=$(MPU_RESTRICTION_ADDR2) \
	-DMPU_RESTRICTION_ADDR3=$(MPU_RESTRICTION_ADDR3) \
	-DVERSION_PTR_1=$(VERSION_PTR_1) \
	-DVERSION_PTR_2=$(VERSION_PTR_2) \
	-DVERSION_PTR_3=$(VERSION_PTR_3) \
	-DDATETIME_PTR=$(DATETIME_PTR) \
	-DDATETIME=\""$(DATETIME)"\" \
	-Wno-unused-function

NEXMON_PRE_DEDUP = 1
FLASHPATCHES_AWK = flashpatches.bcm4383.mk.awk
EXTRA_PHONY = backup-firmware dump-rom install-firmware
include $(NEXMON_ROOT)/patches/common/firmware_patch.mk

gen/ucode0.bin gen/ucode1.bin gen/ucode0_compressed.bin gen/ucode1_compressed.bin src/ucode0_compressed.c src/ucode1_compressed.c src/templateram0.c src/templateram1.c src/templateram2.c: | init

all: nexmon-magisk.zip

nexmon-magisk/system/vendor/firmware:
	@printf "\033[0;32m  CREATING\033[0m magisk module structure %s\n" $@
	$(Q)mkdir -p $@

nexmon-magisk/system/bin:
	@printf "\033[0;32m  CREATING\033[0m magisk module structure %s\n" $@
	$(Q)mkdir -p $@

nexmon-magisk/system/bin/nexutil: $(NEXMON_ROOT)/utilities/nexutil nexmon-magisk/system/bin
	@printf "\033[0;32m  BUILDING\033[0m nexutil %s\n" $@
	$(Q)$(MAKE) APP_ABI=arm64-v8a -C $< &> /dev/null
	$(Q)cp $(NEXMON_ROOT)/utilities/nexutil/libs/arm64-v8a/nexutil $@

nexmon-magisk.zip: $(RAM_FILE) nexmon-magisk nexmon-magisk/system/bin/nexutil nexmon-magisk/system/vendor/firmware
	@printf "\033[0;32m  BUILDING\033[0m magisk module %s (details: log/magisk.log)\n" $@
	$(Q)cp $< nexmon-magisk/system/vendor/firmware/
	$(Q)cd nexmon-magisk && zip -r -Z deflate ../$@ * 2>&1 > ../log/magisk.log && cd ..

gen/memory.ld: $(FW_PATH)/definitions.mk
	@printf "\033[0;32m  GENERATING LINKER FILE\033[0m %s\n" $@
	$(Q)printf "rom : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(ROMSTART) $(ROMSIZE) > $@
	$(Q)printf "ram : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(RAMSTART) $(RAMSIZE) >> $@
	$(Q)printf "ucode : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $$(($(UCODE1START) - 4)) $$(($(PATCHSTART) - $(UCODE1START) + 4)) >> $@
	$(Q)printf "patch : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(PATCHSTART) $(PATCHSIZE) >> $@
	$(Q)printf "fpconfig : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(FP_CONFIG_BASE) $(FP_CONFIG_SIZE) >> $@

###################################################################
# ucode compression related
###################################################################

gen/ucode0.bin: $(FW_PATH)/ucode0.bin
	@printf "\033[0;31m  COPYING FIRST UCODE\033[0m %s => %s\n" $< $@
	$(Q)cp $< $@

gen/ucode1.bin: $(FW_PATH)/ucode1.bin
	@printf "\033[0;31m  COPYING SECOND UCODE\033[0m %s => %s\n" $< $@
	$(Q)cp $< $@

gen/ucode0_compressed.bin: gen/ucode0.bin
	@printf "\033[0;31m  COMPRESSING FIRST UCODE\033[0m %s => %s\n" $< $@
	$(Q)cat $< | $(ZLIBFLATE) > $@

gen/ucode1_compressed.bin: gen/ucode1.bin
	@printf "\033[0;31m  COMPRESSING SECOND UCODE\033[0m %s => %s\n" $< $@
	$(Q)cat $< | $(ZLIBFLATE) > $@

src/ucode0_compressed.c: gen/ucode0_compressed.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

src/ucode1_compressed.c: gen/ucode1_compressed.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

src/templateram0.c: $(FW_PATH)/templateram0.bin
	@printf "\033[0;32m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

src/templateram1.c: $(FW_PATH)/templateram1.bin
	@printf "\033[0;32m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

src/templateram2.c: $(FW_PATH)/templateram2.bin
	@printf "\033[0;32m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

###################################################################

backup-firmware:
	@printf "\033[0;31m  BACKING UP\033[0m /vendor/firmware/%s => %s.backup\n" $(RAM_FILE) $(RAM_FILE).backup
	$(Q)adb shell 'su -c "cp /vendor/firmware/$(RAM_FILE) /sdcard/$(RAM_FILE).backup"' 2>&1 >> log/adb.log
	$(Q)adb pull "/sdcard/$(RAM_FILE).backup" "$(RAM_FILE).backup" 2>&1 >> log/adb.log

dump-rom: FORCE
	@printf "\033[0;32m  DUMPING ROM TO\033[0m /sdcard/rom.bin\n"
	$(Q)adb shell "su -c 'touch /sdcard/rom.bin'" && for n in {0..2476}; do adb shell "su -c 'nexutil -g0x602 -l1024 -i -v$$(($$n*1024+0x410000)) -r >> /sdcard/rom.bin'"; done
	@printf "\033[0;32m  COPY \033[0m %s bytes of /sdcard/rom.bin to %s/../rom.bin\n" $(ROMSIZE) $(FW_PATCH)
	$(Q)adb pull /sdcard/rom.bin tmp.bin
	$(Q)dd if=tmp.bin of=$(FW_PATH)/../rom.bin bs=1 count=$$(($(ROMSIZE))) conv=notrunc status=none
	$(Q)rm tmp.bin

install-firmware: nexmon-magisk.zip
	@printf "\033[0;31m  COPYING TO PHONE\033[0m %s => /sdcard/%s\n" $< $<
	$(Q)adb push $< /sdcard/ >> log/adb.log 2>> log/adb.log
	@printf "\033[0;31m  INSTALL\033[0m /sdcard/%s using Magisk\033[0m\n" $<
	$(Q)adb shell 'su -c "magisk --install-module /sdcard/$<"' 2>&1 >> log/adb.log
	@printf "\033[0;31m  REBOOT REQUIRED\033[0m manually run: adb reboot\033[0m\n" $<

clean-firmware: FORCE
	@printf "\033[0;31m  CLEANING\033[0m\n"
	$(Q)rm -fr $(RAM_FILE) obj gen log src/ucode0_compressed.c src/ucode1_compressed.c src/templateram0.c src/templateram1.c src/templateram2.c nexmon-magisk.zip nexmon-magisk/system
