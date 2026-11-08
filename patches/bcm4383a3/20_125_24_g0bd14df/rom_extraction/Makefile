NEXMON_ROOT ?= $(abspath ../../../..)
include ../version.mk
include $(FW_PATH)/definitions.mk

LOCAL_SRCS=$(wildcard src/*.c) src/ucode0_compressed.c src/ucode1_compressed.c src/templateram0.c src/templateram1.c src/templateram2.c
COMMON_SRCS=$(NEXMON_ROOT)/patches/common/ucode_compression_code.c $(NEXMON_ROOT)/patches/common/objmem.c $(NEXMON_ROOT)/patches/common/wrapper.c

FW_SRCS=$(wildcard $(FW_PATH)/*.c)

DATETIME := $(shell date -u +'%b %e %Y %T')

CFLAGS = \
	-fno-strict-aliasing \
	-DWLC_UCODE_WRITE_BL_HOOK_ADDR=$(WLC_UCODE_WRITE_BL_HOOK_ADDR) \
	-DHNDRTE_RECLAIM_3_END_PTR=$(HNDRTE_RECLAIM_3_END_PTR) \
	-DTEMPLATERAM0START_PTR=$(TEMPLATERAM0START_PTR) \
	-DTEMPLATERAM1START_PTR=$(TEMPLATERAM1START_PTR) \
	-DTEMPLATERAM2START_PTR=$(TEMPLATERAM2START_PTR) \
	-DPATCHSTART=$(PATCHSTART) \
	-DUCODE0START_PTR=$(UCODE0START_PTR) \
	-DUCODE0SIZE_PTR=$(UCODE0SIZE_PTR) \
	-DUCODE1START_PTR=$(UCODE1START_PTR) \
	-DUCODE1SIZE_PTR=$(UCODE1SIZE_PTR) \
	-DFP_CONFIG_ORIGBASE=$(FP_CONFIG_ORIGBASE) \
	-DFP_CONFIG_ORIGEND=$(FP_CONFIG_ORIGEND) \
	-DVERSION_PTR_1=$(VERSION_PTR_1) \
	-DVERSION_PTR_2=$(VERSION_PTR_2) \
	-DVERSION_PTR_3=$(VERSION_PTR_3) \
	-DVERSION_PTR_4=$(VERSION_PTR_4) \
	-DDATETIME_PTR=$(DATETIME_PTR) \
	-DDATETIME=\""$(DATETIME)"\"

NEXMON_PRE_DEDUP = 1
USE_FLASHPATCHES = 0
NEXMON_LDFLAGS = --no-check-sections
EXTRA_PHONY = backup-firmware dump-rom install-nexutil install-firmware install-all install-magisk
include $(NEXMON_ROOT)/patches/common/firmware_patch.mk

all: $(RAM_FILE)
all: nexmon-magisk.zip
#all:

magisk_root := nexmon-magisk

$(magisk_root):
	$(error Magisk module root directory missing, must be created manually)

$(magisk_root)/system/vendor/firmware: $(magisk_root)
	@printf "\033[0;32m  CREATING\033[0m magisk module structure %s\n" $@
	$(Q)mkdir -p $@

utils_path = $(magisk_root)/system/system_ext/bin/
$(utils_path): $(magisk_root)
	@printf "\033[0;32m  CREATING\033[0m magisk module structure %s\n" $@
	$(Q)mkdir -p $@

$(magisk_root)/customize.sh: $(magisk_root)
	@printf "\033[0;32m  CREATING\033[0m magisk module customize script %s\n" $@
	$(Q)rm -f $@
	$(Q)touch $@

utils_name = nexutil
utils = $(addprefix $(utils_path),$(utils_name))

$(utils) : $(utils_path)%: $(NEXMON_ROOT)/utilities/% $(utils_path) $(magisk_root)/customize.sh
	@printf "\033[0;32m  BUILDING\033[0m %s\n" $@
	$(Q)$(MAKE) APP_ABI=arm64-v8a -C $< >/dev/null
	$(Q)cp $(NEXMON_ROOT)/utilities/$*/libs/arm64-v8a/$* $@
	$(Q)printf "set_perm $$MODPATH/system/bin/%s root root 755\n" $* >> $(magisk_root)/customize.sh

$(magisk_root).zip: $(RAM_FILE) $(magisk_root) $(utils) $(magisk_root)/system/vendor/firmware
	@printf "\033[0;32m  BUILDING\033[0m magisk module %s (details: log/magisk.log)\n" $@
	$(Q)cp $< $(magisk_root)/system/vendor/firmware/
	$(Q)cd $(magisk_root) && zip -r -Z deflate ../$@ * 2>&1 > ../log/magisk.log && cd ..

gen/memory.ld: $(FW_PATH)/definitions.mk
	@printf "\033[0;32m  GENERATING LINKER FILE\033[0m %s\n" $@
	$(Q)printf "rom : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(ROMSTART) $(ROMSIZE) > $@
	$(Q)printf "ram : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(RAMSTART) $(RAMSIZE) >> $@
	$(Q)printf "ucode : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(UCODE1START) $$(($(PATCHSTART) - $(UCODE1START))) >> $@
	$(Q)printf "patch : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(PATCHSTART) $(PATCHSIZE) >> $@

###################################################################
# ucode compression related
###################################################################

gen/ucode%.bin: $(FW_PATH)/ucode%.bin | init
	@printf "\033[0;32m  COPYING UCODE\033[0m %s => %s\n" $< $@
	$(Q)cp $< $@

gen/ucode%_compressed.bin: gen/ucode%.bin | init
	@printf "\033[0;32m  COMPRESSING UCODE\033[0m %s => %s\n" $< $@
	$(Q)cat $< | $(ZLIBFLATE) > $@

src/ucode%_compressed.c: gen/ucode%_compressed.bin | init
	@printf "\033[0;32m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

src/templateram%.c: $(FW_PATH)/templateram%.bin | init
	@printf "\033[0;32m  GENERATING C FILE\033[0m %s => %s\n" $(notdir $<) $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

###################################################################

backup-firmware:
	@printf "\033[0;32m  BACKING UP\033[0m /vendor/firmware/%s => %s.backup\n" $(RAM_FILE) $(RAM_FILE).backup
	$(Q)adb shell 'su -c "cp /vendor/firmware/$(RAM_FILE) /sdcard/$(RAM_FILE).backup"' 2>&1
	$(Q)adb pull "/sdcard/$(RAM_FILE).backup" "$(RAM_FILE).backup" 2>&1
	$(Q)adb shell 'su -c "rm /sdcard/$(RAM_FILE).backup"' 2>&1

dump-rom: FORCE
	@printf "\033[0;31m  DUMPING ROM TO\033[0m /sdcard/rom.bin\n"
	$(Q)adb shell "su -c 'touch /sdcard/rom.bin'" && for n in {0..2304}; do adb shell "su -c 'nexutil -g0x602 -l1024 -i -v$$(($$n*1024+0x00410000)) -r >> /sdcard/rom.bin'"; done
	@printf "\033[0;31m  COPY \033[0m %s bytes of /sdcard/rom.bin to %s/../rom.bin\n" $(ROMSIZE) $(FW_PATH)
	$(Q)adb pull /sdcard/rom.bin tmp.bin
	$(Q)dd if=tmp.bin of=$(FW_PATH)/../rom.bin bs=1 count=$$(($(ROMSIZE))) conv=notrunc status=none
	$(Q)rm tmp.bin

$(NEXMON_ROOT)/utilities/nexutil/libs/arm64-v8a/nexutil: $(NEXMON_ROOT)/utilities/nexutil
	@printf "\033[0;32m  BUILDING\033[0m %s\n" $@
	$(Q)$(MAKE) -C $(NEXMON_ROOT)/utilities/libargp clean >/dev/null
	$(Q)$(MAKE) -C $(NEXMON_ROOT)/utilities/libnexio clean >/dev/null
	$(Q)$(MAKE) -C $< clean >/dev/null
	$(Q)$(MAKE) APP_ABI=arm64-v8a -C $< >/dev/null

install-nexutil: $(NEXMON_ROOT)/utilities/nexutil/libs/arm64-v8a/nexutil 000-install-util-remount.sh
	@printf "\033[0;32m  INSTALLING\033[0m %s\n" $<
	@./000-install-util-remount.sh $<

install-firmware: $(RAM_FILE) 000-install-firmware-bind.sh
	@printf "\033[0;32m  INSTALLING\033[0m %s\n" $<
	@./000-install-firmware-bind.sh $<

install-all: $(RAM_FILE) install-firmware install-nexutil
	@printf "\033[0;32m  INSTALL ALL\033[0m\n"

install-magisk: $(magisk_root).zip
	@printf "\033[0;32m  INSTALLING\033[0m %s\n" $<
	@./000-install-magisk.sh $<

clean-firmware: FORCE
	@printf "\033[0;32m  CLEANING\033[0m\n"
	$(Q)rm -fr $(RAM_FILE) obj gen log src/ucode0_compressed.c src/ucode1_compressed.c src/templateram0.c src/templateram1.c src/templateram2.c $(magisk_root)/system $(magisk_root).zip
