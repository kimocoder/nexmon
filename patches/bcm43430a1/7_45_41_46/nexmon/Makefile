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

NEXMON_BUILD_DRIVER = 1
EXTRA_PHONY = backup-firmware install-firmware install-remote-firmware
include $(NEXMON_ROOT)/patches/common/firmware_patch.mk

gen/dummy.idc gen/ucode.asm gen/ucode.bin gen/ucode_compressed.bin src/ucode_compressed.c src/templateram.c: | init

all: $(RAM_FILE) brcmfmac.ko

gen/memory.ld: $(FW_PATH)/definitions.mk
	@printf "\033[0;31m  GENERATING LINKER FILE\033[0m %s\n" $@
	$(Q)printf "rom : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(ROMSTART) $(ROMSIZE) > $@
	$(Q)printf "ram : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(RAMSTART) $(RAMSIZE) >> $@
	$(Q)printf "patch : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(PATCHSTART) $(PATCHSIZE) >> $@
	$(Q)printf "ucode : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(UCODESTART) $$(($(UCODESIZE) - $(PATCHSIZE))) >> $@
	$(Q)printf "fpconfig : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(FP_CONFIG_BASE) $(FP_CONFIG_SIZE) >> $@

gen/dummy.idc: $(RAM_FILE)
	@printf "\033[0;31m  GENERATING IDC FILE\033[0m gen/nexmon.pre => %s\n" $@
	$(Q)cat gen/nexmon.pre | gawk 'BEGIN { printf "#import <idc.idc>\n\nstatic main() {\n" } { if (!seen[$$0]++ && $$2 == "DUMMY") { printf "\tMakeName(%s,\"%s\");\n",$$1,$$4 }; } END { printf "}\n" }' > $@

###################################################################
# ucode compression related
###################################################################

gen/ucode.asm: $(FW_PATH)/ucode.bin
	$(NEXMON_ROOT)/buildtools/b43-unified/disassembler/b43-dasm $< $@ --arch 15 --format raw-le32
#	$(NEXMON_ROOT)/buildtools/b43-unified/debug/b43-beautifier --asmfile $@ --defs $(NEXMON_ROOT)/buildtools/b43-unified/debug/include > tmp && mv tmp $@

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

backup-firmware:
ifeq ($(shell uname -m),$(filter $(shell uname -m), armv6l armv7l aarch64))
	$(Q)cp /lib/firmware/brcm/brcmfmac43430-sdio.bin brcmfmac43430-sdio.bin.orig
	$(Q)cp /lib/firmware/brcm/brcmfmac43430-sdio.clm_blob brcmfmac43430-sdio.clm_blob 2>/dev/null || true
	$(Q)cp /lib/firmware/brcm/brcmfmac43430-sdio.raspberrypi,3-model-b.clm_blob brcmfmac43430-sdio.raspberrypi,3-model-b.clm_blob 2>/dev/null || true
else
	$(warning Warning: Cannot backup the original firmware on this arch.)
endif

install-firmware: brcmfmac43430-sdio.bin brcmfmac.ko
ifeq ($(shell uname -m),$(filter $(shell uname -m), armv6l armv7l aarch64))
	@printf "\033[0;31m  COPYING\033[0m brcmfmac43430-sdio.bin => /lib/firmware/brcm/brcmfmac43430-sdio.bin\n"
	$(Q)cp brcmfmac43430-sdio.bin /lib/firmware/brcm/brcmfmac43430-sdio.bin
	$(Q)rm -rf /lib/firmware/brcm/brcmfmac43430-sdio.clm_blob
	$(Q)rm -rf /lib/firmware/brcm/brcmfmac43430-sdio.raspberrypi,3-model-b.clm_blob
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
	$(warning Warning: Cannot install firmware on this arch., bcm43430-sdio.bin needs to be copied manually into /lib/firmware/brcm/ on your RPI3)
endif

install-remote-firmware: brcmfmac43430-sdio.bin brcmfmac.ko
	@printf "\033[0;31m  COPYING\033[0m brcmfmac43430-sdio.bin => /lib/firmware/brcm/brcmfmac43430-sdio.bin\n"
	$(Q)sshpass -p nexmon scp brcmfmac43430-sdio.bin root@192.168.1.231:/lib/firmware/brcm/brcmfmac43430-sdio.bin
#ifeq ($(shell sshpass -p nexmon ssh root@192.168.1.231 'lsmod | grep "^brcmfmac" | wc -l'), 1)
	@if [ `sshpass -p nexmon ssh root@192.168.1.231 'lsmod | grep "^brcmfmac" | wc -l'` -eq 1 ]; then \
		printf "\033[0;31m  UNLOADING\033[0m brcmfmac\n"; \
		sshpass -p nexmon ssh root@192.168.1.231 'rmmod brcmfmac'; \
	fi
#endif
ifneq ("$(wildcard $(DRIVER_FOLDER_NAME)/brcmfmac.ko)", "")
	$(Q)sshpass -p nexmon ssh root@192.168.1.231 'modprobe brcmutil'
	@printf "\033[0;31m  RELOADING\033[0m brcmfmac\n"
	$(Q)sshpass -p nexmon ssh root@192.168.1.231 'insmod $(DRIVER_FOLDER_NAME)/brcmfmac.ko'
else
	$(warning Warning: Driver not compiled)
endif

clean-firmware: FORCE
	@printf "\033[0;31m  CLEANING\033[0m\n"
	$(Q)rm -fr $(RAM_FILE) obj gen log src/ucode_compressed.c src/templateram.c ucode_compressed.bin
