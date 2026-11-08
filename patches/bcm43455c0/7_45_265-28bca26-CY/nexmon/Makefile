NEXMON_ROOT ?= $(abspath ../../../..)
include ../version.mk
include $(FW_PATH)/definitions.mk

LOCAL_SRCS=$(wildcard src/*.c) src/ucode_compressed.c src/templateram.c
COMMON_SRCS=$(wildcard $(NEXMON_ROOT)/patches/common/*.c)
FW_SRCS=$(wildcard $(FW_PATH)/*.c)

CFLAGS= \
	-DWLC_UCODE_WRITE_BL_HOOK_ADDR=$(WLC_UCODE_WRITE_BL_HOOK_ADDR) \
	-DHNDRTE_RECLAIM_0_END_PTR=$(HNDRTE_RECLAIM_0_END_PTR) \
	-DTEMPLATERAMSTART_PTR=$(TEMPLATERAMSTART_PTR) \
	-DPATCHSTART=$(PATCHSTART) \
	-DUCODESIZE=$(UCODESIZE) \
	-DVERSION_PTR_1=$(VERSION_PTR_1) \
	-DVERSION_PTR_2=$(VERSION_PTR_2) \
	-DVERSION_PTR_3=$(VERSION_PTR_3) \
	-DVERSION_PTR_4=$(VERSION_PTR_4) \
	-DDATE_PTR=$(DATE_PTR) \
	-DTIME_PTR=$(TIME_PTR) \
	-std=gnu11 -Wno-unused-variable -Wno-unused-function -fno-align-functions

NEXMON_BUILD_DRIVER = 1
EXTRA_PHONY = backup-firmware install-firmware
include $(NEXMON_ROOT)/patches/common/firmware_patch.mk

all: $(RAM_FILE) brcmfmac.ko

# These can be requested directly or built concurrently with the objects.
gen/ucode.asm gen/ucode.bin gen/ucode_compressed.bin \
src/ucode_compressed.c src/templateram.c: | init

gen/memory.ld: $(FW_PATH)/definitions.mk
	@printf "\033[0;31m  GENERATING LINKER FILE\033[0m %s\n" $@
	$(Q)printf "rom : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(ROMSTART) $(ROMSIZE) > $@
	$(Q)printf "ram : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(RAMSTART) $(RAMSIZE) >> $@
	$(Q)printf "patch : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(PATCHSTART) $(PATCHSIZE) >> $@
	$(Q)printf "ucode : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $$(($(UCODESTART) - 4)) $$(($(FP_CONFIG_BASE) - $(UCODESTART) + 4)) >> $@
	$(Q)printf "fpconfig : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(FP_CONFIG_BASE) $(FP_CONFIG_SIZE) >> $@

###################################################################
# ucode compression related
###################################################################

gen/ucode.asm: $(FW_PATH)/ucode.bin
	@printf "\033[0;31m  DISASSEMBLING UCODE\033[0m %s => %s\n" $< $@
	$(Q)$(NEXMON_ROOT)/buildtools/b43-unified/disassembler/b43-dasm $< $@ --arch 15 --format raw-le32
	$(Q)$(NEXMON_ROOT)/buildtools/b43-unified/debug/b43-beautifier --asmfile $@ --defs $(NEXMON_ROOT)/buildtools/b43-unified/debug/include > $@.tmp && mv $@.tmp $@

ifneq ($(wildcard src/ucode.asm), )
gen/ucode.bin: src/ucode.asm
	@printf "\033[0;31m  ASSEMBLING UCODE\033[0m %s => %s\n" $< $@

ifneq ($(wildcard $(NEXMON_ROOT)/buildtools/b43-unified/assembler/b43-asm.bin), )
	$(Q)PATH="$(PATH):$(NEXMON_ROOT)/buildtools/b43-unified/assembler" $(NEXMON_ROOT)/buildtools/b43-unified/assembler/b43-asm $< $@ --format raw-le32
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

backup-firmware:
ifeq ($(shell uname -m),$(filter $(shell uname -m), armv6l armv7l aarch64))
	cp /lib/firmware/brcm/$(RAM_FILE) $(RAM_FILE).orig
else
	$(warning Warning: Cannot backup the original firmware on this arch.)
endif

install-firmware: $(RAM_FILE) brcmfmac.ko
ifeq ($(shell uname -m),$(filter $(shell uname -m), armv6l armv7l aarch64))
	@printf "\033[0;31m  COPYING\033[0m %s => /lib/firmware/nexmon/%s\n" $(RAM_FILE) $(RAM_FILE)
	$(Q)mkdir -p /lib/firmware/nexmon
	$(Q)cp $(RAM_FILE) /lib/firmware/nexmon/$(RAM_FILE)
	@printf "\033[0;31m  SETTING UP ALTERNATIVE\033[0m cyfmac43455-sdio.bin to /lib/firmware/nexmon/%s\n" $(RAM_FILE)
	$(Q)update-alternatives --install /lib/firmware/cypress/cyfmac43455-sdio.bin cyfmac43455-sdio.bin /lib/firmware/nexmon/$(RAM_FILE) 30
	$(Q)update-alternatives --set cyfmac43455-sdio.bin /lib/firmware/nexmon/$(RAM_FILE)
ifneq ("$(wildcard $(DRIVER_FOLDER_NAME)/brcmfmac.ko)", "")
	@for module in $$(lsmod | grep "^brcmfmac" | awk '{print $$1}'); do \
		printf "\033[0;31m  UNLOADING\033[0m $$module\n"; \
		rmmod $$module; \
	done
	$(Q)modprobe brcmutil
	@printf "\033[0;31m  RELOADING\033[0m brcmfmac\n"
	$(Q)insmod $(DRIVER_FOLDER_NAME)/brcmfmac.ko
else
	$(warning Warning: Driver not compiled)
endif
else
	$(warning Warning: Cannot install firmware on this arch, $(RAM_FILE) needs to be manually installed on your Raspberry Pi)
endif

clean-firmware: FORCE
	@printf "\033[0;31m  CLEANING\033[0m\n"
	$(Q)rm -fr $(RAM_FILE) obj gen log src/ucode_compressed.c src/templateram.c
