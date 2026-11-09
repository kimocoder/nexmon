#ifndef INFOMESSAGE_H_
#define INFOMESSAGE_H_

#include <jni.h>

#define UPDATE_ERROR 1
#define UPDATE_SUCCESS 2
#define UPDATE_RUNNING 3

extern JavaVM* jvm;

void cleanup_info_message(JNIEnv *env);

extern char info_buffer[1024];

void info_message_thread(char* mes, int reason, JNIEnv* env);

void info_message(char* mes, int reason);


void setup_info_message(JNIEnv* env, jobject obj, jmethodID mid, int myid);

#endif