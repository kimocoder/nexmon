NEXMON_ROOT ?= $(abspath ../../../..)
include ../version.mk
include $(FW_PATH)/definitions.mk

ifndef NEXMON_SETUP_ENV
$(error run 'source setup_env.sh' first in the repository\'s root directory)
endif

LOCAL_SRCS=$(wildcard src/*.c) \
src/d11ucode_mu129_compressed.c \
src/d11ucodex_mu129_compressed.c \
src/d11ucode_mu129_1_compressed.c \
src/d11ucodex_mu129_1_compressed.c \
src/d11ucode_btcxmu129_1_compressed.c \
src/d11ucodex_btcxmu129_1_compressed.c \
src/d11ucode_mu129_2_compressed.c \
src/d11ucodex_mu129_2_compressed.c \
src/d11ucode_btcxmu129_2_compressed.c \
src/d11ucodex_btcxmu129_2_compressed.c

COMMON_SRCS=$(wildcard $(NEXMON_ROOT)/patches/common/*.c)
FW_SRCS=$(wildcard $(FW_PATH)/*.c)

DATE := $(shell date -u +'%b %e %Y')
TIME := $(shell date -u +'%T')

CFLAGS = \
	-fno-strict-aliasing \
	-DRECLAIM_END_PTR=$(RECLAIM_END_PTR) \
	-DPATCHSTART=$(PATCHSTART) \
	-DWLC_BMAC_PROCESS_UCODE_SR_BL_HOOK_ADDR=$(WLC_BMAC_PROCESS_UCODE_SR_BL_HOOK_ADDR) \
	-DWLC_UCODE_WRITE_BL_HOOK_0_ADDR=$(WLC_UCODE_WRITE_BL_HOOK_0_ADDR) \
	-DWLC_UCODE_WRITE_BL_HOOK_1_ADDR=$(WLC_UCODE_WRITE_BL_HOOK_1_ADDR) \
	-DWLC_UCODE_WRITE_BL_HOOK_2_ADDR=$(WLC_UCODE_WRITE_BL_HOOK_2_ADDR) \
	-DWLC_UCODE_WRITE_BL_HOOK_3_ADDR=$(WLC_UCODE_WRITE_BL_HOOK_3_ADDR) \
	-DWLC_UCODE_WRITE_BL_HOOK_4_ADDR=$(WLC_UCODE_WRITE_BL_HOOK_4_ADDR) \
	-DWLC_UCODEX_WRITE_BL_HOOK_ADDR=$(WLC_UCODEX_WRITE_BL_HOOK_ADDR) \
	-DUCODE0START_PTR=$(UCODE0START_PTR) \
	-DUCODE0SIZE_PTR=$(UCODE0SIZE_PTR) \
	-DUCODEX0START_PTR=$(UCODEX0START_PTR) \
	-DUCODEX0SIZE_PTR=$(UCODEX0SIZE_PTR) \
	-DUCODE1START_PTR=$(UCODE1START_PTR) \
	-DUCODE1SIZE_PTR=$(UCODE1SIZE_PTR) \
	-DUCODEX1START_PTR=$(UCODEX1START_PTR) \
	-DUCODEX1SIZE_PTR=$(UCODEX1SIZE_PTR) \
	-DUCODEBT1START_PTR=$(UCODEBT1START_PTR) \
	-DUCODEBT1SIZE_PTR=$(UCODEBT1SIZE_PTR) \
	-DUCODEXBT1START_PTR=$(UCODEXBT1START_PTR) \
	-DUCODEXBT1SIZE_PTR=$(UCODEXBT1SIZE_PTR) \
	-DUCODE2START_PTR=$(UCODE2START_PTR) \
	-DUCODE2SIZE_PTR=$(UCODE2SIZE_PTR) \
	-DUCODEX2START_PTR=$(UCODEX2START_PTR) \
	-DUCODEX2SIZE_PTR=$(UCODEX2SIZE_PTR) \
	-DUCODEBT2START_PTR=$(UCODEBT2START_PTR) \
	-DUCODEBT2SIZE_PTR=$(UCODEBT2SIZE_PTR) \
	-DUCODEXBT2START_PTR=$(UCODEXBT2START_PTR) \
	-DUCODEXBT2SIZE_PTR=$(UCODEXBT2SIZE_PTR) \
	-DVERSION_PTR_1=$(VERSION_PTR_1) \
	-DVERSION_PTR_2=$(VERSION_PTR_2) \
	-DVERSION_PTR_3=$(VERSION_PTR_3) \
	-DVERSION_PTR_4=$(VERSION_PTR_4) \
	-DDATE_PTR=$(DATE_PTR) \
	-DDATE=\""$(DATE)"\" \
	-DTIME_PTR=$(TIME_PTR) \
	-DTIME=\""$(TIME)"\" \
	-Wno-unused-function

NEXMON_PRE_DEDUP = 1
USE_FLASHPATCHES = 0
EXTRA_PHONY = copy-firmware load-firmware
include $(NEXMON_ROOT)/patches/common/firmware_patch.mk

gen/d11ucode_btcxmu129_1.bin gen/d11ucode_btcxmu129_1_compressed.bin src/d11ucode_btcxmu129_1_compressed.c gen/d11ucode_btcxmu129_2.bin gen/d11ucode_btcxmu129_2_compressed.bin src/d11ucode_btcxmu129_2_compressed.c gen/d11ucode_mu129_1.bin gen/d11ucode_mu129_1_compressed.bin src/d11ucode_mu129_1_compressed.c gen/d11ucode_mu129_2.bin gen/d11ucode_mu129_2_compressed.bin src/d11ucode_mu129_2_compressed.c gen/d11ucode_mu129.bin gen/d11ucode_mu129_compressed.bin src/d11ucode_mu129_compressed.c gen/d11ucodex_btcxmu129_1.bin gen/d11ucodex_btcxmu129_1_compressed.bin src/d11ucodex_btcxmu129_1_compressed.c gen/d11ucodex_btcxmu129_2.bin gen/d11ucodex_btcxmu129_2_compressed.bin src/d11ucodex_btcxmu129_2_compressed.c gen/d11ucodex_mu129_1.bin gen/d11ucodex_mu129_1_compressed.bin src/d11ucodex_mu129_1_compressed.c gen/d11ucodex_mu129_2.bin gen/d11ucodex_mu129_2_compressed.bin src/d11ucodex_mu129_2_compressed.c gen/d11ucodex_mu129.bin gen/d11ucodex_mu129_compressed.bin src/d11ucodex_mu129_compressed.c: | init

all: $(RAM_FILE)

gen/memory.ld: $(FW_PATH)/definitions.mk
	@printf "\033[0;31m  GENERATING LINKER FILE\033[0m %s\n" $@
	$(Q)printf "ram : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(RAMSTART) $(RAMSIZE) > $@
	$(Q)printf "ucode : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(UCODEBT1START) $$(($(PATCHSTART) - $(UCODEBT1START))) >> $@
	$(Q)printf "patch : ORIGIN = 0x%08x, LENGTH = 0x%08x\n" $(PATCHSTART) $(PATCHSIZE) >> $@

###################################################################
# ucode compression related
###################################################################

gen/d11ucode_btcxmu129_1.bin: $(FW_PATH)/d11ucode_btcxmu129_1.bin
	@printf "\033[0;31m  COPYING UCODE\033[0m %s => %s\n" $< $@
	$(Q)cp $< $@

gen/d11ucode_btcxmu129_1_compressed.bin: gen/d11ucode_btcxmu129_1.bin
	@printf "\033[0;31m  COMPRESSING UCODE\033[0m %s => %s\n" $< $@
	$(Q)$(ZLIBFLATE) < $< > $@

src/d11ucode_btcxmu129_1_compressed.c: gen/d11ucode_btcxmu129_1_compressed.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

gen/d11ucode_btcxmu129_2.bin: $(FW_PATH)/d11ucode_btcxmu129_2.bin
	@printf "\033[0;31m  COPYING UCODE\033[0m %s => %s\n" $< $@
	$(Q)cp $< $@

gen/d11ucode_btcxmu129_2_compressed.bin: gen/d11ucode_btcxmu129_2.bin
	@printf "\033[0;31m  COMPRESSING UCODE\033[0m %s => %s\n" $< $@
	$(Q)$(ZLIBFLATE) < $< > $@

src/d11ucode_btcxmu129_2_compressed.c: gen/d11ucode_btcxmu129_2_compressed.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

gen/d11ucode_mu129_1.bin: $(FW_PATH)/d11ucode_mu129_1.bin
	@printf "\033[0;31m  COPYING UCODE\033[0m %s => %s\n" $< $@
	$(Q)cp $< $@

gen/d11ucode_mu129_1_compressed.bin: gen/d11ucode_mu129_1.bin
	@printf "\033[0;31m  COMPRESSING UCODE\033[0m %s => %s\n" $< $@
	$(Q)$(ZLIBFLATE) < $< > $@

src/d11ucode_mu129_1_compressed.c: gen/d11ucode_mu129_1_compressed.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

gen/d11ucode_mu129_2.bin: $(FW_PATH)/d11ucode_mu129_2.bin
	@printf "\033[0;31m  COPYING UCODE\033[0m %s => %s\n" $< $@
	$(Q)cp $< $@

gen/d11ucode_mu129_2_compressed.bin: gen/d11ucode_mu129_2.bin
	@printf "\033[0;31m  COMPRESSING UCODE\033[0m %s => %s\n" $< $@
	$(Q)$(ZLIBFLATE) < $< > $@

src/d11ucode_mu129_2_compressed.c: gen/d11ucode_mu129_2_compressed.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

gen/d11ucode_mu129.bin: $(FW_PATH)/d11ucode_mu129.bin
	@printf "\033[0;31m  COPYING UCODE\033[0m %s => %s\n" $< $@
	$(Q)cp $< $@

gen/d11ucode_mu129_compressed.bin: gen/d11ucode_mu129.bin
	@printf "\033[0;31m  COMPRESSING UCODE\033[0m %s => %s\n" $< $@
	$(Q)$(ZLIBFLATE) < $< > $@

src/d11ucode_mu129_compressed.c: gen/d11ucode_mu129_compressed.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

gen/d11ucodex_btcxmu129_1.bin: $(FW_PATH)/d11ucodex_btcxmu129_1.bin
	@printf "\033[0;31m  COPYING UCODE\033[0m %s => %s\n" $< $@
	$(Q)cp $< $@

gen/d11ucodex_btcxmu129_1_compressed.bin: gen/d11ucodex_btcxmu129_1.bin
	@printf "\033[0;31m  COMPRESSING UCODE\033[0m %s => %s\n" $< $@
	$(Q)$(ZLIBFLATE) < $< > $@

src/d11ucodex_btcxmu129_1_compressed.c: gen/d11ucodex_btcxmu129_1_compressed.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

gen/d11ucodex_btcxmu129_2.bin: $(FW_PATH)/d11ucodex_btcxmu129_2.bin
	@printf "\033[0;31m  COPYING UCODE\033[0m %s => %s\n" $< $@
	$(Q)cp $< $@

gen/d11ucodex_btcxmu129_2_compressed.bin: gen/d11ucodex_btcxmu129_2.bin
	@printf "\033[0;31m  COMPRESSING UCODE\033[0m %s => %s\n" $< $@
	$(Q)$(ZLIBFLATE) < $< > $@

src/d11ucodex_btcxmu129_2_compressed.c: gen/d11ucodex_btcxmu129_2_compressed.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

gen/d11ucodex_mu129_1.bin: $(FW_PATH)/d11ucodex_mu129_1.bin
	@printf "\033[0;31m  COPYING UCODE\033[0m %s => %s\n" $< $@
	$(Q)cp $< $@

gen/d11ucodex_mu129_1_compressed.bin: gen/d11ucodex_mu129_1.bin
	@printf "\033[0;31m  COMPRESSING UCODE\033[0m %s => %s\n" $< $@
	$(Q)$(ZLIBFLATE) < $< > $@

src/d11ucodex_mu129_1_compressed.c: gen/d11ucodex_mu129_1_compressed.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

gen/d11ucodex_mu129_2.bin: $(FW_PATH)/d11ucodex_mu129_2.bin
	@printf "\033[0;31m  COPYING UCODE\033[0m %s => %s\n" $< $@
	$(Q)cp $< $@

gen/d11ucodex_mu129_2_compressed.bin: gen/d11ucodex_mu129_2.bin
	@printf "\033[0;31m  COMPRESSING UCODE\033[0m %s => %s\n" $< $@
	$(Q)$(ZLIBFLATE) < $< > $@

src/d11ucodex_mu129_2_compressed.c: gen/d11ucodex_mu129_2_compressed.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

gen/d11ucodex_mu129.bin: $(FW_PATH)/d11ucodex_mu129.bin
	@printf "\033[0;31m  COPYING UCODE\033[0m %s => %s\n" $< $@
	$(Q)cp $< $@

gen/d11ucodex_mu129_compressed.bin: gen/d11ucodex_mu129.bin
	@printf "\033[0;31m  COMPRESSING UCODE\033[0m %s => %s\n" $< $@
	$(Q)$(ZLIBFLATE) < $< > $@

src/d11ucodex_mu129_compressed.c: gen/d11ucodex_mu129_compressed.bin
	@printf "\033[0;31m  GENERATING C FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "#pragma NEXMON targetregion \"ucode\"\n\n" > $@
	$(Q)cd $(dir $<) && xxd -i $(notdir $<) >> $(shell pwd)/$@

###################################################################

copy-firmware: $(RAM_FILE)
ifneq ($(strip $(SSHPASS)),)
ifneq ($(strip $(SSHUSER)),)
ifneq ($(strip $(SSHADDRESS)),)
	@printf "\033[0;31m  COPYING\033[0m %s to %s:/jffs/%s\n" $(RAM_FILE) $(SSHADDRESS) $(RAM_FILE)
	@SSHPASS=$(SSHPASS) sshpass -e ssh $(SSHUSER)@$(SSHADDRESS) '/usr/sbin/socat -u TCP-LISTEN:65535,reuseaddr OPEN:/jffs/$(RAM_FILE),creat'& sleep 1; socat -u FILE:$(RAM_FILE) TCP:$(SSHADDRESS):65535
else
	$(error No SSH address given. Set with SSHADDRESS=<address> when calling make)
endif
else
	$(error No SSH user given. Set with SSHUSER=<ssh username> when calling make)
endif
else
	$(error No SSH password given. Set with SSHPASS=<ssh password> when calling make)
endif

load-firmware:
ifneq ($(strip $(SSHPASS)),)
ifneq ($(strip $(SSHUSER)),)
ifneq ($(strip $(SSHADDRESS)),)
	@printf "\033[0;31m  CHECKING FILE EXISTENCE\033[0m %s:/jffs/%s\n" $(SSHADDRESS) $(RAM_FILE)
	@SSHPASS=$(SSHPASS) sshpass -e ssh $(SSHUSER)@$(SSHADDRESS) '[ -s /jffs/$(RAM_FILE) ]' || (echo Error: $(SSHADDRESS):/jffs/$(RAM_FILE) does not exist. Run \'make copy-firmware\' first.; exit 1)
	@printf "\033[0;31m  UNLOADING\033[0m dhd module\n"
	@SSHPASS=$(SSHPASS) sshpass -e ssh $(SSHUSER)@$(SSHADDRESS) '/sbin/rmmod dhd; /bin/usleep 200000'
	@printf "\033[0;31m  LOADING\033[0m dhd module\n"
	@SSHPASS=$(SSHPASS) sshpass -e ssh $(SSHUSER)@$(SSHADDRESS) '/sbin/insmod $$(/usr/bin/find /lib/modules -name dhd.ko) firmware_path=/jffs/$(RAM_FILE) instance_base=1 dhd_msg_level=0x400001'
	@printf "\033[0;31m  RECONFIGURING\033[0m interfaces\n"
	@SSHPASS=$(SSHPASS) sshpass -e ssh $(SSHUSER)@$(SSHADDRESS) '/sbin/restart_wireless >/dev/null 2>/dev/null'
	@SSHPASS=$(SSHPASS) sshpass -e ssh $(SSHUSER)@$(SSHADDRESS) '/bin/brctl delif br0 eth7'
else
	$(error No SSH address given. Set with SSHADDRESS=<address> when calling make)
endif
else
	$(error No SSH user given. Set with SSHUSER=<ssh username> when calling make)
endif
else
	$(error No SSH password given. Set with SSHPASS=<ssh password> when calling make)
endif

clean-firmware:
	@printf "\033[0;31m  CLEANING\033[0m\n"
	$(Q)rm -fr $(RAM_FILE) obj gen log src/d11ucode_mu129_compressed.c src/d11ucodex_mu129_compressed.c src/d11ucode_mu129_1_compressed.c src/d11ucodex_mu129_1_compressed.c src/d11ucode_btcxmu129_1_compressed.c src/d11ucodex_btcxmu129_1_compressed.c src/d11ucode_mu129_2_compressed.c src/d11ucodex_mu129_2_compressed.c src/d11ucode_btcxmu129_2_compressed.c src/d11ucodex_btcxmu129_2_compressed.c
