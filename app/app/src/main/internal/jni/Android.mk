LOCAL_PATH:=$(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := myandroidlogger
LOCAL_SRC_FILES := ../../libs/$(TARGET_ARCH_ABI)/libandroidlogger.so
include $(PREBUILT_SHARED_LIBRARY)

include $(CLEAR_VARS)
LOCAL_MODULE := myairdecap-ng
LOCAL_SRC_FILES := ../../libs/$(TARGET_ARCH_ABI)/libmyairdecap-ng.so
include $(PREBUILT_SHARED_LIBRARY)

include $(CLEAR_VARS)
LOCAL_MODULE := myfakeauth
LOCAL_SRC_FILES := ../../libs/$(TARGET_ARCH_ABI)/libmyfakeauth.so
include $(PREBUILT_SHARED_LIBRARY)

include $(CLEAR_VARS)
LOCAL_MODULE := myaircrackwep
LOCAL_SRC_FILES := ../../libs/$(TARGET_ARCH_ABI)/libmyaircrackwep.so
include $(PREBUILT_SHARED_LIBRARY)

include $(CLEAR_VARS)
LOCAL_MODULE := mylibpcap
LOCAL_SRC_FILES := ../../libs/$(TARGET_ARCH_ABI)/libpcap.a
LOCAL_SHARED_LIBRARIES:=myandroidlogger
include $(PREBUILT_STATIC_LIBRARY)

include $(CLEAR_VARS)
LOCAL_MODULE := authflood
LOCAL_SRC_FILES := ../../libs/$(TARGET_ARCH_ABI)/libauthflood.so
include $(PREBUILT_SHARED_LIBRARY)

include $(CLEAR_VARS)
LOCAL_MODULE := beaconflood
LOCAL_SRC_FILES := ../../libs/$(TARGET_ARCH_ABI)/libbeaconflood.so
include $(PREBUILT_SHARED_LIBRARY)

include $(CLEAR_VARS)
LOCAL_MODULE := countermeasures
LOCAL_SRC_FILES := ../../libs/$(TARGET_ARCH_ABI)/libcountermeasures.so
include $(PREBUILT_SHARED_LIBRARY)

include $(CLEAR_VARS)
LOCAL_MODULE := wids
LOCAL_SRC_FILES := ../../libs/$(TARGET_ARCH_ABI)/libwids.so
include $(PREBUILT_SHARED_LIBRARY)

include $(CLEAR_VARS)
LOCAL_MODULE := ivstools
LOCAL_SRC_FILES := ../../libs/$(TARGET_ARCH_ABI)/libmyivstools.so
include $(PREBUILT_SHARED_LIBRARY)

include $(CLEAR_VARS)
LOCAL_MODULE := upchack
LOCAL_SRC_FILES := ../../libs/$(TARGET_ARCH_ABI)/libmyupchack.so
include $(PREBUILT_SHARED_LIBRARY)

#include $(CLEAR_VARS)
#LOCAL_MODULE := reaver
#LOCAL_SRC_FILES := ../../libs/$(TARGET_ARCH_ABI)/libreaver.so
#include $(PREBUILT_SHARED_LIBRARY)

include $(CLEAR_VARS)
LOCAL_MODULE := cowpatty
LOCAL_SRC_FILES := ../../libs/$(TARGET_ARCH_ABI)/libcowpatty.so
include $(PREBUILT_SHARED_LIBRARY)


include $(CLEAR_VARS)
LOCAL_MODULE:= nexmonpentestsuite
LOCAL_SRC_FILES := wrapper_pentestsuite.c
LOCAL_STATIC_LIBRARIES:=mylibpcap
LOCAL_SHARED_LIBRARIES:=myairdecap-ng myfakeauth myaircrackwep authflood beaconflood countermeasures wids ivstools upchack cowpatty
include $(BUILD_SHARED_LIBRARY)


