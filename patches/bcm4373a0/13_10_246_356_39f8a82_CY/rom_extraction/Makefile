NEXMON_ROOT ?= $(abspath ../../../..)
include ../version.mk
include $(FW_PATH)/definitions.mk

LOCAL_SRCS=$(wildcard src/*.c) src/ucode_compressed.c src/templateram.c
COMMON_SRCS=$(NEXMON_ROOT)/patches/common/ucode_compression_code.c $(NEXMON_ROOT)/patches/common/objmem.c $(NEXMON_ROOT)/patches/common/wrapper.c
FW_SRCS=$(wildcard $(FW_PATH)/*.c)

DATE := $(shell date -u +'%b %e %Y')
TIME := $(shell date -u +'%T')

CFLAGS = \
	-fno-strict-aliasing \
	-DWLC_UCODE_WRITE_BL_HOOK_ADDR=$(WLC_UCODE_WRITE_BL_HOOK_ADDR) \
	-DHNDRTE_RECLAIM_3_END_PTR=$(HNDRTE_RECLAIM_3_END_PTR) \
	-DFP_CONFIG_ORIGEND=$(FP_CONFIG_ORIGEND) \
	-DFP_CONFIG_ORIGBASE=$(FP_CONFIG_ORIGBASE) \
	-DTEMPLATERAMSTART_PTR=$(TEMPLATERAMSTART_PTR) \
	-DPATCHSTART=$(PATCHSTART) \
	-DUCODESTART_PTR=$(UCODESTART_PTR) \
	-DUCODESIZE_PTR=$(UCODESIZE_PTR) \
	-DVERSION_PTR_1=$(VERSION_PTR_1) \
	-DVERSION_PTR_2=$(VERSION_PTR_2) \
	-DVERSION_PTR_3=$(VERSION_PTR_3) \
	-DVERSION_PTR_4=$(VERSION_PTR_4) \
	-DDATE_PTR=$(DATE_PTR) \
	-DDATE=\""$(DATE)"\" \
	-DTIME_PTR=$(TIME_PTR) \
	-DTIME=\""$(TIME)"\" \
	-Wno-unused-function

NEXMON_FIRMWARE_ONLY_TARGET = $(FW_FILE)
NEXMON_PRE_DEDUP = 1
USE_FLASHPATCHES = 0
include $(NEXMON_ROOT)/patches/common/firmware_patch.mk

gen/ucode.bin gen/ucode_compressed.bin src/ucode_compressed.c src/templateram.c: | init

all: $(FW_FILE)

$(FW_FILE): $(RAM_FILE)
	@printf "\033[0;32m  EMBEDDING\033[0m %s => %s (details: log/trx.log)\n" $< $@
	$(Q)cp $(FW_PATH)/$(FW_FILE) $(FW_FILE) 2>&1 >> log/trx.log
	$(Q)dd of=$(FW_FILE) if=$(RAM_FILE) bs=1 seek=$$(($(RAM_FILE_OFFSET))) count=$$(($(RAM_FILE_LEN))) conv=notrunc 2>> log/trx.log >> log/trx.log

gen/memory.ld: $(FW_PATH)/definitions.mk
	@printf "\033[0;32m  GENERATING LINKER FILE\033[0m %s\n" $@
	$(Q)printf "rom : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(ROMSTART) $(ROMSIZE) > $@
	$(Q)printf "ram : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(RAMSTART) $(RAMSIZE) >> $@
	$(Q)printf "ucode : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(UCODESTART) $$(($(PATCHSTART) - $(UCODESTART))) >> $@
	$(Q)printf "patch : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(PATCHSTART) $(PATCHSIZE) >> $@

###################################################################
# ucode compression related
###################################################################

gen/ucode.bin: $(FW_PATH)/ucode.bin
	@printf "\033[0;32m  COPYING UCODE\033[0m %s => %s\n" $< $@
	$(Q)cp $< $@

gen/ucode_compressed.bin: gen/ucode.bin
	@printf "\033[0;32m  COMPRESSING UCODE\033[0m %s => %s\n" $< $@
	$(Q)cat $< | $(ZLIBFLATE) > $@

src/ucode_compressed.c: gen/ucode_compressed.bin
	@printf "\033[0;32m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

src/templateram.c: $(FW_PATH)/templateram.bin
	@printf "\033[0;32m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

###################################################################

clean-firmware: FORCE
	@printf "\033[0;32m  CLEANING\033[0m\n"
	$(Q)rm -fr $(FW_FILE) $(RAM_FILE) obj gen log src/ucode_compressed.c src/templateram.c
