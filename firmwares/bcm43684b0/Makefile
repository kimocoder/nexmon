SUBDIRS = $(dir $(wildcard */definitions.mk))

all: $(SUBDIRS)

$(SUBDIRS): FORCE
ifneq (,$(wildcard $(addprefix $@, Makefile)))
	@printf "\033[0;31m  EXECUTING MAKE FOR FIRMWARE VERSION\033[0m %s\n" $@
	$(Q)$(MAKE) -C $@
endif

clean: FORCE
	@printf "\033[0;31m  CLEANING FIRMWARE VERSIONS\033[0m\n"
	$(Q)for dir in $(SUBDIRS); do if [ -f $$dir/Makefile ]; then $(MAKE) -C $$dir clean || exit 1; fi; done

FORCE:
