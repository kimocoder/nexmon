#ifndef MOCK_JNI_H
#define MOCK_JNI_H
#include <stddef.h>
typedef int jint;
typedef unsigned char jboolean;
typedef void *jobject;
typedef jobject jstring;
typedef void *jmethodID;
typedef const struct JNINativeInterface_ *JNIEnv;
typedef const struct JNIInvokeInterface_ *JavaVM;
#define JNI_OK 0
#define JNI_ERR (-1)
#define JNI_EDETACHED (-2)
#define JNI_VERSION_1_6 0x00010006
struct JNINativeInterface_ {
 jint (*GetJavaVM)(JNIEnv *, JavaVM **);
 jobject (*NewGlobalRef)(JNIEnv *, jobject);
 void (*DeleteGlobalRef)(JNIEnv *, jobject);
 jobject (*NewLocalRef)(JNIEnv *, jobject);
 void (*DeleteLocalRef)(JNIEnv *, jobject);
 jstring (*NewStringUTF)(JNIEnv *, const char *);
 void (*CallVoidMethod)(JNIEnv *, jobject, jmethodID, ...);
 jboolean (*ExceptionCheck)(JNIEnv *);
 void (*ExceptionClear)(JNIEnv *);
};
struct JNIInvokeInterface_ {
 jint (*GetEnv)(JavaVM *, void **, jint);
#ifdef __ANDROID__
 jint (*AttachCurrentThread)(JavaVM *, JNIEnv **, void *);
#else
 jint (*AttachCurrentThread)(JavaVM *, void **, void *);
#endif
 jint (*DetachCurrentThread)(JavaVM *);
};
#endif
