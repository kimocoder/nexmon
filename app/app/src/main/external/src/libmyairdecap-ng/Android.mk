# Pre-1.7 aircrack-ng API snapshot, see libmyaircrackwep/Android.mk.
LOCAL_PATH := $(call my-dir)
AIRCRACK_NG_PATH := $(LOCAL_PATH)/../../aircrack-legacy

AIRCRACK_CFLAGS := -g -W -Wall -O3 -DANDROID -D_REVISION=0 \
	-Wno-unused-but-set-variable -Wno-array-bounds -Wno-unused-parameter -Wno-unused-variable \
	-D__int8_t_defined -fPIC -DANDROID -DOS_ANDROID -DLinux

ifneq ($(TARGET_PLATFORM),android-21)
AIRCRACK_CFLAGS += -D_FILE_OFFSET_BITS=64
endif

include $(CLEAR_VARS)
LOCAL_MODULE := myairdecap-ng
LOCAL_SRC_FILES := \
	src/myairdecap-ng.c \
	$(AIRCRACK_NG_PATH)/crypto.c \
	$(AIRCRACK_NG_PATH)/common.c

LOCAL_C_INCLUDES := $(LOCAL_PATH)/src $(AIRCRACK_NG_PATH) $(AIRCRACK_NG_PATH)/include
LOCAL_CFLAGS := $(AIRCRACK_CFLAGS)
LOCAL_SHARED_LIBRARIES := libandroidlogger
LOCAL_STATIC_LIBRARIES := libssl libcrypto libosdep libpcap
include $(BUILD_SHARED_LIBRARY)


include $(CLEAR_VARS)
LOCAL_MODULE := libssl
LOCAL_SRC_FILES := $(LOCAL_PATH)/../../../../../../../utilities/libssl/local/$(TARGET_ARCH_ABI)/libssl.a
LOCAL_EXPORT_C_INCLUDES := $(LOCAL_PATH)/../../../../../../../utilities/boringssl/include
include $(PREBUILT_STATIC_LIBRARY)


include $(CLEAR_VARS)
LOCAL_MODULE := libcrypto
LOCAL_SRC_FILES := $(LOCAL_PATH)/../../../../../../../utilities/libcrypto/local/$(TARGET_ARCH_ABI)/libcrypto.a
LOCAL_EXPORT_C_INCLUDES := $(LOCAL_PATH)/../../../../../../../utilities/boringssl/include
include $(PREBUILT_STATIC_LIBRARY)


include $(CLEAR_VARS)
LOCAL_MODULE := libosdep
LOCAL_SRC_FILES := $(LOCAL_PATH)/../../../../../../../utilities/libosdep/local/$(TARGET_ARCH_ABI)/libosdep.a
LOCAL_EXPORT_C_INCLUDES := $(LOCAL_PATH)/../../../../../../../utilities/libosdep/src
include $(PREBUILT_STATIC_LIBRARY)


include $(CLEAR_VARS)
LOCAL_MODULE := libpcap
LOCAL_SRC_FILES := $(LOCAL_PATH)/../libpcap/local/$(TARGET_ARCH_ABI)/libpcap.a
LOCAL_EXPORT_C_INCLUDES := $(LOCAL_PATH)/../../../../../../../utilities/libpcap
include $(PREBUILT_STATIC_LIBRARY)


include $(CLEAR_VARS)
LOCAL_MODULE := libandroidlogger
LOCAL_SRC_FILES := ../libandroidlogger/libs/$(TARGET_ARCH_ABI)/libandroidlogger.so
LOCAL_C_INCLUDES := ../libandroidlogger
include $(PREBUILT_SHARED_LIBRARY)