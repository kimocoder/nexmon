LOCAL_PATH := $(call my-dir)
UTILITIES_PATH := $(LOCAL_PATH)/../../../../../../../utilities
COWPATTY_PATH := $(UTILITIES_PATH)/cowpatty

include $(CLEAR_VARS)
LOCAL_MODULE := cowpatty
LOCAL_SRC_FILES :=\
	$(COWPATTY_PATH)/md5.c\
	src/cowpatty.c\
	$(COWPATTY_PATH)/sha1.c\
	$(COWPATTY_PATH)/utils.c\
	src/infomessage.c

LOCAL_CFLAGS:=-g -O3 -mfpu=neon -Wall -Wextra -Wno-unused-but-set-variable -Wno-unused-parameter\
	-fPIC -DANDROID -DOS_ANDROID -DLinux -DOPENSSL

LOCAL_C_INCLUDES := $(COWPATTY_PATH)
LOCAL_STATIC_LIBRARIES := libpcap libcrypto libssl
include $(BUILD_SHARED_LIBRARY)


include $(CLEAR_VARS)
LOCAL_MODULE := libssl
LOCAL_SRC_FILES := $(UTILITIES_PATH)/libssl/local/$(TARGET_ARCH_ABI)/libssl.a
LOCAL_EXPORT_C_INCLUDES := $(UTILITIES_PATH)/boringssl/include
include $(PREBUILT_STATIC_LIBRARY)


include $(CLEAR_VARS)
LOCAL_MODULE := libcrypto
LOCAL_SRC_FILES := $(UTILITIES_PATH)/libcrypto/local/$(TARGET_ARCH_ABI)/libcrypto.a
LOCAL_EXPORT_C_INCLUDES := $(UTILITIES_PATH)/boringssl/include
include $(PREBUILT_STATIC_LIBRARY)


include $(CLEAR_VARS)
LOCAL_MODULE := libpcap
LOCAL_SRC_FILES := $(LOCAL_PATH)/../libpcap/local/$(TARGET_ARCH_ABI)/libpcap.a
LOCAL_EXPORT_C_INCLUDES := $(UTILITIES_PATH)/libpcap
include $(PREBUILT_STATIC_LIBRARY)
