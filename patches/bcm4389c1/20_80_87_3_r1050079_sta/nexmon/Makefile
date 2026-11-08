NEXMON_ROOT ?= $(abspath ../../../..)
include ../version.mk
include $(FW_PATH)/definitions.mk

LOCAL_SRCS=$(wildcard src/*.c) src/ucode0_compressed.c src/ucode1_compressed.c src/ucode2_compressed.c src/templateram0.c src/templateram1.c src/templateram2.c src/templateram3.c
COMMON_SRCS=$(NEXMON_ROOT)/patches/common/ucode_compression_code.c $(NEXMON_ROOT)/patches/common/objmem.c $(NEXMON_ROOT)/patches/common/helper.c $(NEXMON_ROOT)/patches/common/wrapper.c
FW_SRCS=$(wildcard $(FW_PATH)/*.c)

DATETIME := $(shell date -u +'%b %e %Y %T')

CFLAGS = \
	-fno-strict-aliasing \
	-DBCMPKTIDMAP=1 \
	-DWLC_UCODE_WRITE_BL_HOOK_ADDR=$(WLC_UCODE_WRITE_BL_HOOK_ADDR) \
	-DMMU_PROTECT_ON_BL_ADDR=$(MMU_PROTECT_ON_BL_ADDR) \
	-DHNDRTE_RECLAIM_3_END_PTR_0=$(HNDRTE_RECLAIM_3_END_PTR_0) \
	-DHNDRTE_RECLAIM_3_END_PTR_1=$(HNDRTE_RECLAIM_3_END_PTR_1) \
	-DHNDRTE_RECLAIM_3_END_PTR_2=$(HNDRTE_RECLAIM_3_END_PTR_2) \
	-DFP_CONFIG_BASE=$(FP_CONFIG_BASE) \
	-DTEMPLATERAM0START_PTR=$(TEMPLATERAM0START_PTR) \
	-DTEMPLATERAM1START_PTR=$(TEMPLATERAM1START_PTR) \
	-DTEMPLATERAM2START_PTR=$(TEMPLATERAM2START_PTR) \
	-DTEMPLATERAM3START_PTR=$(TEMPLATERAM3START_PTR) \
	-DPATCHSTART=$(PATCHSTART) \
	-DUCODE0START_PTR=$(UCODE0START_PTR) \
	-DUCODE0SIZE_PTR=$(UCODE0SIZE_PTR) \
	-DUCODE1START_PTR=$(UCODE1START_PTR) \
	-DUCODE1SIZE_PTR=$(UCODE1SIZE_PTR) \
	-DUCODE2START_PTR=$(UCODE2START_PTR) \
	-DUCODE2SIZE_PTR=$(UCODE2SIZE_PTR) \
	-DVERSION_PTR_1=$(VERSION_PTR_1) \
	-DVERSION_PTR_2=$(VERSION_PTR_2) \
	-DVERSION_PTR_3=$(VERSION_PTR_3) \
	-DVERSION_PTR_4=$(VERSION_PTR_4) \
	-DDATETIME_PTR=$(DATETIME_PTR) \
	-DDATETIME=\""$(DATETIME)"\" \
	-Wno-unused-function

NEXMON_PRE_DEDUP = 1
FLASHPATCHES_AWK = flashpatches.bcm4389.mk.awk
EXTRA_PHONY = backup-firmware install-firmware
include $(NEXMON_ROOT)/patches/common/firmware_patch.mk

gen/ucode0.bin gen/ucode1.bin gen/ucode2.bin gen/ucode0_compressed.bin gen/ucode1_compressed.bin gen/ucode2_compressed.bin src/ucode0_compressed.c src/ucode1_compressed.c src/ucode2_compressed.c src/templateram0.c src/templateram1.c src/templateram2.c src/templateram3.c: | init

all: nexmon-magisk.zip

nexmon-magisk/system/vendor/firmware/wifi:
	@printf "\033[0;32m  CREATING\033[0m magisk module structure %s\n" $@
	$(Q)mkdir -p $@

nexmon-magisk/system/bin:
	@printf "\033[0;32m  CREATING\033[0m magisk module structure %s\n" $@
	$(Q)mkdir -p $@

$(NEXMON_ROOT)/utilities/nexutil/libs/arm64-v8a/nexutil: $(NEXMON_ROOT)/utilities/nexutil
	@printf "\033[0;32m  BUILDING\033[0m nexutil %s\n" $@
	$(Q)$(MAKE) APP_ABI=arm64-v8a -C $<

nexmon-magisk/system/bin/nexutil: $(NEXMON_ROOT)/utilities/nexutil/libs/arm64-v8a/nexutil nexmon-magisk/system/bin
	@printf "\033[0;32m  COPYING\033[0m nexutil %s\n" $@
	$(Q)cp $(NEXMON_ROOT)/utilities/nexutil/libs/arm64-v8a/nexutil $@

nexmon-magisk.zip: $(RAM_FILE) nexmon-magisk nexmon-magisk/system/bin/nexutil nexmon-magisk/system/vendor/firmware/wifi
	@printf "\033[0;32m  BUILDING\033[0m magisk module %s (details: log/magisk.log)\n" $@
	$(Q)cp $< nexmon-magisk/system/vendor/firmware/wifi/
	$(Q)cd nexmon-magisk && zip -r -Z deflate ../$@ * 2>&1 > ../log/magisk.log && cd ..

gen/memory.ld: $(FW_PATH)/definitions.mk
	@printf "\033[0;32m  GENERATING LINKER FILE\033[0m %s\n" $@
	$(Q)printf "rom : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(ROMSTART) $(ROMSIZE) > $@
	$(Q)printf "ram : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(RAMSTART) $(RAMSIZE) >> $@
	$(Q)printf "ucode : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(UCODEREGIONSTART) $(UCODEREGIONSIZE) >> $@
	$(Q)printf "patch : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(PATCHSTART) $(PATCHSIZE) >> $@
	$(Q)printf "fpconfig : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(FP_CONFIG_BASE) $(FP_CONFIG_SIZE) >> $@

###################################################################
# ucode compression related
###################################################################

gen/ucode0.bin: $(FW_PATH)/ucode0.bin
	@printf "\033[0;32m  COPYING FIRST UCODE\033[0m %s => %s\n" $< $@
	$(Q)cp $< $@

gen/ucode1.bin: $(FW_PATH)/ucode1.bin
	@printf "\033[0;32m  COPYING SECOND UCODE\033[0m %s => %s\n" $< $@
	$(Q)cp $< $@

gen/ucode2.bin: $(FW_PATH)/ucode2.bin
	@printf "\033[0;32m  COPYING THIRD UCODE\033[0m %s => %s\n" $< $@
	$(Q)cp $< $@

gen/ucode0_compressed.bin: gen/ucode0.bin
	@printf "\033[0;32m  COMPRESSING FIRST UCODE\033[0m %s => %s\n" $< $@
	$(Q)$(ZLIBFLATE) < $< > $@

gen/ucode1_compressed.bin: gen/ucode1.bin
	@printf "\033[0;32m  COMPRESSING SECOND UCODE\033[0m %s => %s\n" $< $@
	$(Q)$(ZLIBFLATE) < $< > $@

gen/ucode2_compressed.bin: gen/ucode2.bin
	@printf "\033[0;32m  COMPRESSING THIRD UCODE\033[0m %s => %s\n" $< $@
	$(Q)$(ZLIBFLATE) < $< > $@

src/ucode0_compressed.c: gen/ucode0_compressed.bin
	@printf "\033[0;32m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

src/ucode1_compressed.c: gen/ucode1_compressed.bin
	@printf "\033[0;32m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

src/ucode2_compressed.c: gen/ucode2_compressed.bin
	@printf "\033[0;32m  GENERATING C FILE\033[0m %s => %s\n" $< $@
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

src/templateram3.c: $(FW_PATH)/templateram3.bin
	@printf "\033[0;32m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

###################################################################

backup-firmware:
	@printf "\033[0;32m  BACKING UP\033[0m /vendor/firmware/wifi/%s => %s.backup\n" $(RAM_FILE) $(RAM_FILE).backup
	$(Q)adb shell 'su -c "cp /vendor/firmware/wifi/$(RAM_FILE) /sdcard/$(RAM_FILE).backup"' 2>&1 >> log/adb.log
	$(Q)adb pull "/sdcard/$(RAM_FILE).backup" "$(RAM_FILE).backup" 2>&1 >> log/adb.log

install-firmware: nexmon-magisk.zip
	@printf "\033[0;32m  COPYING TO PHONE\033[0m %s => /sdcard/%s\n" $< $<
	$(Q)adb push $< /sdcard/ >> log/adb.log 2>> log/adb.log
	@printf "\033[0;32m  INSTALLING\033[0m /sdcard/%s using Magisk\033[0m\n" $<
	$(Q)adb shell 'su -c "magisk --install-module /sdcard/$<"' 2>&1 >> log/adb.log
	@printf "\033[0;33m  ANDROID REBOOT REQUIRED\033[0m run: adb reboot\033[0m\n" $<
	$(Q)-bash -c 'read -p "Reboot attached device now?(y/N)" adbreboot; [[ $${adbreboot,,} == "y" ]] && adb reboot'

clean-firmware: FORCE
	@printf "\033[0;32m  CLEANING\033[0m\n"
	$(Q)rm -fr $(RAM_FILE) obj gen log src/ucode0_compressed.c src/ucode1_compressed.c src/ucode2_compressed.c src/templateram0.c src/templateram1.c src/templateram2.c src/templateram3.c nexmon-magisk.zip nexmon-magisk/system
