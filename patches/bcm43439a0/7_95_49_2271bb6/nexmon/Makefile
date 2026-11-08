NEXMON_ROOT ?= $(abspath ../../../..)
include ../version.mk
include $(FW_PATH)/definitions.mk

LOCAL_SRCS=$(wildcard src/*.c) src/ucode_compressed.c src/templateram.c
COMMON_SRCS=$(wildcard $(NEXMON_ROOT)/patches/common/*.c)
FW_SRCS=$(wildcard $(FW_PATH)/*.c)

FW_WRAPPER_FILE=w43439A0_7_95_49_00_combined.h

CFLAGS = \
	-DWLC_UCODE_WRITE_BL_HOOK_ADDR=$(WLC_UCODE_WRITE_BL_HOOK_ADDR) \
	-DHNDRTE_RECLAIM_0_END_PTR=$(HNDRTE_RECLAIM_0_END_PTR) \
	-DTEMPLATERAMSTART_PTR=$(TEMPLATERAMSTART_PTR) \
	-DPATCHSTART=$(PATCHSTART) \
	-DUCODESIZE=$(UCODESIZE) \
	-DVERSION_PTR_1=$(VERSION_PTR_1) \
	-DVERSION_PTR_2=$(VERSION_PTR_2) \
	-DVERSION_PTR_3=$(VERSION_PTR_3)

include $(NEXMON_ROOT)/patches/common/firmware_patch.mk

gen/ucode.asm gen/ucode.bin gen/ucode_compressed.bin src/ucode_compressed.c src/templateram.c: | init

all: $(RAM_FILE) $(FW_WRAPPER_FILE)

gen/memory.ld: $(FW_PATH)/definitions.mk
	@printf "\033[0;31m  GENERATING LINKER FILE\033[0m %s\n" $@
	$(Q)printf "rom : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(ROMSTART) $(ROMSIZE) > $@
	$(Q)printf "ram : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(RAMSTART) $(RAMSIZE) >> $@
	$(Q)printf "patch : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(PATCHSTART) $(PATCHSIZE) >> $@
	$(Q)printf "ucode : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(UCODESTART) $$(($(UCODESIZE) - $(PATCHSIZE))) >> $@
	$(Q)printf "fpconfig : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(FP_CONFIG_BASE) $(FP_CONFIG_SIZE) >> $@

$(FW_WRAPPER_FILE): $(RAM_FILE) $(FW_PATH)/clm.bin
	@printf "\033[0;31m  GENERATING C STYLE FIRMWARE FILE\033[0m %s\n" $@
	@$(Q)FW_LEN=$$(stat -c %s "$<");CLM_LEN=$$(stat -c %s "$(FW_PATH)/clm.bin");HEX_COMB=$$(cat "$<" <(dd if=/dev/zero bs=1 count=$$(((($$FW_LEN + 511) & ~511) - $$FW_LEN)) conv=notrunc status=none) "$(FW_PATH)/clm.bin" | xxd -i);printf "static const unsigned char fw_combined[] CYW43_RESOURCE_ATTRIBUTE = {\n$$HEX_COMB\n};\n#define CYW43_WIFI_FW_LEN ($$FW_LEN)\n#define CYW43_CLM_LEN ($$CLM_LEN)\nconst uintptr_t fw_data = (uintptr_t)&fw_combined[0];" > $@

###################################################################
# ucode compression related
###################################################################

gen/ucode.asm: $(FW_PATH)/ucode.bin
	$(NEXMON_ROOT)/buildtools/b43-unified/disassembler/b43-dasm $< $@ --arch 15 --format raw-le32

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

clean-firmware: FORCE
	@printf "\033[0;31m  CLEANING\033[0m\n"
	$(Q)rm -fr $(RAM_FILE) $(FW_WRAPPER_FILE) obj gen log src/ucode_compressed.c src/templateram.c ucode_compressed.bin
