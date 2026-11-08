# Shared firmware-patch build rules for all Nexmon firmware patch Makefiles.
#
# Expected variables set by the caller before including this file:
#   LOCAL_SRCS                  - patch C sources (including generated src/*.c)
#   COMMON_SRCS                 - shared C sources under patches/common/
#   FW_SRCS                     - firmware-specific C sources under $(FW_PATH)/
#   CFLAGS                      - target-specific preprocessor defines & compiler flags
#
# Optional configuration variables (set before including this file):
#   NEXMON_FW_TARGET            - output firmware filename (default: $(RAM_FILE))
#   NEXMON_FIRMWARE_ONLY_TARGET - prerequisite of firmware-only (default: $(NEXMON_FW_TARGET))
#   NEXMON_PRE_DEDUP            - set to 1 to generate deduplicated gen/nexmon2.pre
#                                 prioritizing patch objects over wrapper/flashpatches
#   USE_FLASHPATCHES            - set to 0 if target has no flashpatches (default: 1)
#   APPLY_FLASHPATCHES          - set to 0 to skip running gen/flashpatches.mk (default: $(USE_FLASHPATCHES))
#   FLASHPATCHES_AWK            - awk generator under buildtools/scripts/ (default: flashpatches.mk.awk)
#   NEXMON_LDFLAGS              - extra flags passed to $(CC)ld for gen/patch.elf
#   NEXMON_CUSTOM_FW_RULES      - set to 1 if caller defines custom gen/nexmon.mk and firmware assembly rules
#   NEXMON_BUILD_DRIVER         - set to 1 to enable brcmfmac.ko build and clean rules (default: 0)
#   CLEAN_EXTRA                 - extra paths removed by `make clean`
#   EXTRA_PHONY                 - extra target names added to .PHONY

SHELL = /bin/bash
.DEFAULT_GOAL := all
.DELETE_ON_ERROR:

-include $(NEXMON_ROOT)/patches/common/nexmon_lazy.mk
KBUILD_EXTRA_SYMV ?= $(if $(SYMVERS_SUPPLEMENT),KBUILD_EXTRA_SYMBOLS=$(SYMVERS_SUPPLEMENT))
NEXMON_UNAME_M ?= $(shell uname -m)
NEXMON_UNAME_R ?= $(shell uname -r)

NEXMON_FW_TARGET ?= $(RAM_FILE)
NEXMON_FIRMWARE_ONLY_TARGET ?= $(NEXMON_FW_TARGET)
NEXMON_PRE_DEDUP ?= 0
USE_FLASHPATCHES ?= 1
APPLY_FLASHPATCHES ?= $(USE_FLASHPATCHES)
FLASHPATCHES_AWK ?= flashpatches.mk.awk
NEXMON_CUSTOM_FW_RULES ?= 0
NEXMON_BUILD_DRIVER ?= 0

OBJS = $(sort $(addprefix obj/,$(notdir $(LOCAL_SRCS:.c=.o)) $(notdir $(COMMON_SRCS:.c=.o)) $(notdir $(FW_SRCS:.c=.o))))
PREFILES = $(OBJS:.o=.pre)

# Auto-generated header dependencies (-MMD/-MP below). Without these a change to
# a shared header (patches/include, ./include, or the firmware headers) would
# not rebuild the affected objects and stale .o files would be silently reused.
DEPS = $(OBJS:.o=.d)
-include $(DEPS)

NEXMON_COMMON_CFLAGS = \
	-fplugin=$(CCPLUGIN) \
	-fplugin-arg-nexmon-objfile=obj/$*.o \
	-fplugin-arg-nexmon-prefile=obj/$*.pre.tmp \
	-fplugin-arg-nexmon-chipver=$(NEXMON_CHIP_NUM) \
	-fplugin-arg-nexmon-fwver=$(NEXMON_FW_VERSION_NUM) \
	-DNEXMON_CHIP=$(NEXMON_CHIP) \
	-DNEXMON_FW_VERSION=$(NEXMON_FW_VERSION) \
	-DGIT_VERSION=\"$(GIT_VERSION)\" \
	-DBUILD_NUMBER=\"$$(cat BUILD_NUMBER)\" \
	-Wall -Werror -O2 -nostdlib -nostartfiles -ffreestanding -mthumb -march=$(NEXMON_ARCH) \
	-ffunction-sections -fdata-sections \
	-MMD -MP \
	-I$(NEXMON_ROOT)/patches/include \
	-Iinclude \
	-I$(FW_PATH)

NEXMON_EFFECTIVE_CFLAGS = $(NEXMON_COMMON_CFLAGS) $(filter-out -fplugin%,$(CFLAGS))

firmware-only: $(NEXMON_FIRMWARE_ONLY_TARGET)

init: check-nexmon-setup-env
	$(Q)mkdir -p obj gen log
	$(Q)if ! test -f BUILD_NUMBER; then echo 0 > BUILD_NUMBER; fi
# By default every build increments BUILD_NUMBER and rebuilds version.o. Keep
# this explicit rather than touching a source while make is checking its mtime.
# Set NEXMON_FREEZE_BUILD_NUMBER=1 to keep the number fixed and only rebuild
# version.o when its inputs actually changed.
ifndef NEXMON_FREEZE_BUILD_NUMBER
	$(Q)echo $$(($$(cat BUILD_NUMBER) + 1)) > BUILD_NUMBER
endif
	$(Q)$(MAKE) -s -f $(NEXMON_ROOT)/patches/common/header.mk

ifndef NEXMON_FREEZE_BUILD_NUMBER
ifneq ($(filter obj/version.o,$(OBJS)),)
obj/version.o obj/version.pre: FORCE
endif
endif

# Ensure gen/ exists before memory.ld or linker/patch rules run concurrently.
gen/memory.ld gen/nexmon.ld gen/nexmon.mk gen/patch.elf: | init
ifeq ($(USE_FLASHPATCHES),1)
gen/flashpatches.ld gen/flashpatches.mk: | init
endif

ifeq ($(NEXMON_BUILD_DRIVER),1)
brcmfmac.ko: check-nexmon-setup-env
ifneq ("$(wildcard $(DRIVER_FOLDER_NAME))", "")
ifeq ($(NEXMON_UNAME_M),$(filter $(NEXMON_UNAME_M), armv6l armv7l))
	@printf "\033[0;31m  BUILDING DRIVER for kernel $(KERNEL_VERSION)\033[0m brcmfmac_$(KERNEL_VERSION).y-nexmon/brcmfmac.ko (details: log/driver.log)\n" $@
	$(Q)mkdir -p log
	$(Q)KBUILD_MODPOST_WARN=1 $(MAKE) -C /lib/modules/$(NEXMON_UNAME_R)/build M=$(DRIVER_FOLDER_NAME) $(KBUILD_EXTRA_SYMV) >log/driver.log
else ifeq ($(NEXMON_UNAME_M),$(filter $(NEXMON_UNAME_M), aarch64))
	@printf "\033[0;31m  BUILDING DRIVER for kernel $(KERNEL_VERSION)\033[0m brcmfmac_$(KERNEL_VERSION).y-nexmon/brcmfmac.ko (details: log/driver.log)\n" $@
	$(Q)mkdir -p log
	$(Q)ARCH="arm64" KBUILD_MODPOST_WARN=1 $(MAKE) -C /lib/modules/$(NEXMON_UNAME_R)/build M=$(DRIVER_FOLDER_NAME) $(KBUILD_EXTRA_SYMV) >log/driver.log
else
	$(warning Warning: Driver can not be compiled on this platform, execute the make command on a Raspberry Pi)
endif
else
	$(warning Warning: Driver for kernel $(KERNEL_VERSION) not found)
endif
endif

# A multi-target pattern rule produces the object and its plugin metadata in
# one invocation, including when an old build has objects but no .pre files.
# The plugin appends, so start with an empty private file and publish it only
# after successful compilation. No compiler rewrites another object's metadata.
define compile_object
	@printf "\033[0;31m  COMPILING\033[0m %s => obj/$*.o (details: log/compiler.log)\n" $<
	$(Q): > obj/$*.pre.tmp
	$(Q)$(CC)gcc $(NEXMON_EFFECTIVE_CFLAGS) -c $< -o obj/$*.o >>log/compiler.log && mv obj/$*.pre.tmp obj/$*.pre
endef

obj/%.o obj/%.pre: src/%.c | init
	$(compile_object)

obj/%.o obj/%.pre: $(NEXMON_ROOT)/patches/common/%.c | init
	$(compile_object)

obj/%.o obj/%.pre: $(FW_PATH)/%.c | init
	$(compile_object)

# Merge only the current source set, in a stable order, once all compilers have
# finished. FORCE also handles removed sources; unchanged metadata keeps its
# timestamp so a frozen incremental build need not regenerate linker scripts.
gen/nexmon.pre: $(OBJS) $(PREFILES) FORCE | init
	$(Q)cat $(PREFILES) > $@.tmp
	$(Q)if cmp -s $@.tmp $@; then rm -f $@.tmp; else mv $@.tmp $@; fi

ifeq ($(NEXMON_PRE_DEDUP),1)
NEXMON_PRE_INPUT := gen/nexmon2.pre

gen/nexmon2.pre: gen/nexmon.pre | init
	@printf "\033[0;31m  PREPARING\033[0m %s => %s\n" $< $@
	$(Q)gawk ' \
		$$3 == "obj/flashpatches.o" || $$3 == "obj/wrapper.o" || $$3 == "obj/local_wrapper.o" { low[++n] = $$0; next } \
		{ if (!($$1 ~ /^0x/) || !seen[$$1]++) print } \
		END { for (i = 1; i <= n; i++) { split(low[i], f); if (!(f[1] ~ /^0x/) || !seen[f[1]]++) print low[i] } } \
	' $< > $@.tmp && mv $@.tmp $@
else
NEXMON_PRE_INPUT := gen/nexmon.pre
endif

gen/nexmon.ld: $(NEXMON_PRE_INPUT)
	@printf "\033[0;31m  GENERATING LINKER FILE\033[0m %s => %s\n" $< $@
	$(Q)sort $< | gawk -f $(NEXMON_ROOT)/buildtools/scripts/nexmon.ld.awk > $@

ifeq ($(USE_FLASHPATCHES),1)
gen/flashpatches.ld: $(NEXMON_PRE_INPUT)
	@printf "\033[0;31m  GENERATING LINKER FILE\033[0m %s => %s\n" $< $@
	$(Q)sort $< | gawk -f $(NEXMON_ROOT)/buildtools/scripts/flashpatches.ld.awk > $@

gen/flashpatches.mk: $(NEXMON_PRE_INPUT) $(FW_PATH)/definitions.mk
	@printf "\033[0;31m  GENERATING MAKE FILE\033[0m %s => %s\n" $< $@
	$(Q)gawk \
		-v fp_data_base=$(FP_DATA_BASE) \
		-v fp_data_last=$(FP_DATA_LAST) \
		-v fp_config_base=$(FP_CONFIG_BASE) \
		-v fp_data_end_ptr=$(FP_DATA_END_PTR) \
		-v fp_data_last_ptr=$(FP_DATA_LAST_PTR) \
		-v fp_config_first_entry_ptr=$(FP_CONFIG_FIRST_ENTRY_PTR) \
		-v fp_config_base_ptr_1=$(FP_CONFIG_BASE_PTR_1) \
		-v fp_config_base_ptr_1_2=$(FP_CONFIG_BASE_PTR_1_2) \
		-v fp_config_end_ptr_1=$(FP_CONFIG_END_PTR_1) \
		-v fp_config_base_ptr_2=$(FP_CONFIG_BASE_PTR_2) \
		-v fp_config_end_ptr_2=$(FP_CONFIG_END_PTR_2) \
		-v fp_config_base_ptr_3=$(FP_CONFIG_BASE_PTR_3) \
		-v fp_config_end_ptr_3=$(FP_CONFIG_END_PTR_3) \
		-v fp_config_base_ptr_4=$(FP_CONFIG_BASE_PTR_4) \
		-v fp_config_end_ptr_4=$(FP_CONFIG_END_PTR_4) \
		-v fp_config_end_ptr_5=$(FP_CONFIG_END_PTR_5) \
		-v ramstart=$(RAMSTART) \
		-v out_file=$(NEXMON_FW_TARGET) \
		-v src_file=gen/patch.elf \
		-f $(NEXMON_ROOT)/buildtools/scripts/$(FLASHPATCHES_AWK) $< > $@

NEXMON_PATCH_ELF_LDS := patch.ld gen/nexmon.ld gen/flashpatches.ld gen/memory.ld
NEXMON_FW_PATCH_MKS := gen/nexmon.mk gen/flashpatches.mk
else
NEXMON_PATCH_ELF_LDS := patch.ld gen/nexmon.ld gen/memory.ld
NEXMON_FW_PATCH_MKS := gen/nexmon.mk
endif

gen/patch.elf: $(NEXMON_PATCH_ELF_LDS) $(OBJS)
	@printf "\033[0;31m  LINKING OBJECTS\033[0m => %s (details: log/linker.log, log/linker.err)\n" $@
	$(Q)$(CC)ld -T $< -o $@ --gc-sections --print-gc-sections $(NEXMON_LDFLAGS) -M >>log/linker.log 2>>log/linker.err

ifneq ($(NEXMON_CUSTOM_FW_RULES),1)
gen/nexmon.mk: $(NEXMON_PRE_INPUT) gen/patch.elf $(FW_PATH)/definitions.mk
	@printf "\033[0;31m  GENERATING MAKE FILE\033[0m %s => %s\n" $< $@
	$(Q)printf "%s: gen/patch.elf FORCE\n" "$(NEXMON_FW_TARGET)" > $@
	$(Q)sort $< | \
		gawk -v src_file=gen/patch.elf -f $(NEXMON_ROOT)/buildtools/scripts/nexmon.mk.1.awk | \
		gawk -v ramstart=$(RAMSTART) -f $(NEXMON_ROOT)/buildtools/scripts/nexmon.mk.2.awk >> $@
	$(Q)printf "\nFORCE:\n" >> $@
	$(Q)gawk '!a[$$0]++' $@ > $@.tmp && mv $@.tmp $@

$(NEXMON_FW_TARGET): init gen/patch.elf $(FW_PATH)/$(RAM_FILE) $(NEXMON_FW_PATCH_MKS)
	$(Q)cp $(FW_PATH)/$(RAM_FILE) $@
ifeq ($(APPLY_FLASHPATCHES),1)
	@printf "\033[0;31m  APPLYING FLASHPATCHES\033[0m gen/flashpatches.mk => %s (details: log/flashpatches.log)\n" $@
	$(Q)$(MAKE) -f gen/flashpatches.mk >>log/flashpatches.log 2>>log/flashpatches.log
endif
	@printf "\033[0;31m  APPLYING PATCHES\033[0m gen/nexmon.mk => %s (details: log/patches.log)\n" $@
	$(Q)$(MAKE) -f gen/nexmon.mk >>log/patches.log 2>>log/patches.log
endif

check-nexmon-setup-env:
ifndef NEXMON_SETUP_ENV
	$(error run 'source setup_env.sh' first in the repository\'s root directory)
endif

clean: clean-firmware
ifeq ($(NEXMON_BUILD_DRIVER),1)
ifeq ($(NEXMON_UNAME_M),$(filter $(NEXMON_UNAME_M), armv6l armv7l aarch64))
ifneq ("$(wildcard $(DRIVER_FOLDER_NAME))", "")
	@printf "\033[0;31m  CLEANING DRIVER\033[0m\n" $@
	$(Q)$(MAKE) -C /lib/modules/$(NEXMON_UNAME_R)/build M=$(DRIVER_FOLDER_NAME) clean
endif
endif
endif
	$(Q)rm -fr BUILD_NUMBER $(CLEAN_EXTRA)

.PHONY: all firmware-only init check-nexmon-setup-env clean clean-firmware FORCE $(EXTRA_PHONY)

FORCE:
