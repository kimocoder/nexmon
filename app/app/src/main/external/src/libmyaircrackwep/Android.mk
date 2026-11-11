# These helpers are forks of aircrack-ng 1.x and use its pre-1.7 API (globals
# opt/wep, struct pcap_pkthdr.tv_sec, its own pcap.h/version.h, struct ivs2_*).
# utilities/aircrack-ng tracks 1.7 for the CLI tools, so the JNI helpers build
# against the vendored snapshot in external/aircrack-legacy/ instead.
LOCAL_PATH := $(call my-dir)
AIRCRACK_NG_PATH := $(LOCAL_PATH)/../../aircrack-legacy

AIRCRACK_CFLAGS := -g -W -Wall -O3 -DANDROID -D_REVISION=0 \
	-Wno-unused-but-set-variable -Wno-array-bounds -Wno-unused-parameter -Wno-unused-variable \
	-D__int8_t_defined -fPIC -DANDROID -DOS_ANDROID -DLinux -DHAVE_SQLITE

ifeq ($(TARGET_ARCH_ABI),armeabi-v7a)
AIRCRACK_CFLAGS += -mfloat-abi=softfp -mfpu=neon -march=armv7 -DSIMD_CORE
endif

# bionic only declares fseeko()/ftello() with a 64-bit off_t from API 24; with
# _FILE_OFFSET_BITS=64 libc++'s <fstream> (linecount.cpp) does not compile.
ifneq ($(TARGET_PLATFORM),android-21)
AIRCRACK_CFLAGS += -D_FILE_OFFSET_BITS=64
endif

include $(CLEAR_VARS)
LOCAL_MODULE := myaircrackwep
LOCAL_SRC_FILES := \
	src/myaircrackwep.c \
	$(AIRCRACK_NG_PATH)/crypto.c \
	$(AIRCRACK_NG_PATH)/common.c \
	$(AIRCRACK_NG_PATH)/uniqueiv.c \
	$(AIRCRACK_NG_PATH)/simd-intrinsics.c \
	$(AIRCRACK_NG_PATH)/cpuid.c \
	$(AIRCRACK_NG_PATH)/memory.c \
	$(AIRCRACK_NG_PATH)/wpapsk.c \
	$(AIRCRACK_NG_PATH)/linecount.cpp \
	$(AIRCRACK_NG_PATH)/aircrack-ptw-lib.c

LOCAL_C_INCLUDES := $(LOCAL_PATH)/src $(AIRCRACK_NG_PATH) $(AIRCRACK_NG_PATH)/include
LOCAL_CFLAGS := $(AIRCRACK_CFLAGS)
LOCAL_SHARED_LIBRARIES := libandroidlogger
LOCAL_STATIC_LIBRARIES := libssl libcrypto libosdep libsqlite libpcap
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
LOCAL_MODULE := libsqlite
LOCAL_SRC_FILES := $(LOCAL_PATH)/../../../../../../../utilities/libsqlite/local/$(TARGET_ARCH_ABI)/libsqlite.a
LOCAL_EXPORT_C_INCLUDES := $(LOCAL_PATH)/../../../../../../../utilities/libsqlite
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