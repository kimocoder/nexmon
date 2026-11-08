SUBDIRS = $(dir $(wildcard */Makefile))

all: $(SUBDIRS)

$(SUBDIRS): FORCE
	@printf "\033[0;31m  EXECUTING MAKE FOR CHIP VERSION\033[0m %s\n" $@
	$(Q)$(MAKE) -C $@

clean: FORCE
	@printf "\033[0;31m  CLEANING CHIP VERSIONS\033[0m\n"
	$(Q)for dir in $(SUBDIRS); do if [ -f $$dir/Makefile ]; then $(MAKE) -C $$dir clean || exit 1; fi; done

FORCE:
