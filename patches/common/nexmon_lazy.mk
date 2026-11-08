# Common lazy probes for nexmon Makefiles — included by patches/common/firmware_patch.mk.
# Skips git and kernel-symvers probes when every requested goal is clean*, while keeping
# KERNEL_VERSION and DRIVER_FOLDER_NAME populated so `make clean` still cleans the driver
# and `make clean all` still populates GIT_VERSION and SYMVERS_SUPPLEMENT.
ifndef NEXMON_LAZY_MK_INCLUDED
NEXMON_LAZY_MK_INCLUDED := 1

NEXMON_UNAME_M := $(shell uname -m)
NEXMON_UNAME_R := $(shell uname -r)
KERNEL_VERSION := $(shell printf '%s\n' "$(NEXMON_UNAME_R)" | sed 's/\([0-9]\+\.[0-9]\+\)\..*/\1/')
DRIVER_FOLDER_NAME := $(NEXMON_ROOT)/patches/driver/brcmfmac_$(KERNEL_VERSION).y-nexmon

ifeq ($(if $(MAKECMDGOALS),$(filter-out clean%,$(MAKECMDGOALS)),all),)
GIT_VERSION ?=
SYMVERS_SUPPLEMENT :=
else
ifeq ($(origin GIT_VERSION),undefined)
GIT_VERSION := $(shell git -C "$(NEXMON_ROOT)" describe --abbrev=4 --dirty --always --tags 2>/dev/null)
endif
SYMVERS_SUPPLEMENT := $(shell "$(NEXMON_ROOT)/buildtools/scripts/kernel-symvers-supplement.sh" "/lib/modules/$(NEXMON_UNAME_R)/build" 2>/dev/null)
endif

# A kernel tree whose Module.symvers lacks the vmlinux built-in exports makes
# modpost fail an out-of-tree module with hundreds of "undefined" symbols,
# module_layout among them, even though every source file compiles. Recover the
# missing rows from the kernel's own .vmlinux.export.c.
KBUILD_EXTRA_SYMV := $(if $(SYMVERS_SUPPLEMENT),KBUILD_EXTRA_SYMBOLS=$(SYMVERS_SUPPLEMENT))

endif
