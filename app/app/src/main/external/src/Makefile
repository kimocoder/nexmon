APP_ABI ?= armeabi-v7a

SUBDIRS := $(wildcard */.)
SUBCLEAN = $(addsuffix .clean,$(SUBDIRS))

all: $(SUBDIRS)

$(SUBDIRS):
	$(MAKE) -C $@ APP_ABI=$(APP_ABI)

clean: $(SUBCLEAN)

$(SUBCLEAN): %.clean:
	$(MAKE) -C $* clean
	rm -f ../../libs/*/*.so
	rm -f ../../libs/*/*.a


.PHONY: all $(SUBDIRS) clean $(SUBCLEAN)