#include <assert.h>
#include <stdarg.h>
#include "infomessage.h"
static int detached, attaches, detaches, globals, locals, calls, fail_attach, fail_global, fail_local, fail_string, exception, get_error;
static int reenter, throw_callback;
static JNIEnv env;
static JavaVM vm;
static jint getvm(JNIEnv *e, JavaVM **v) { (void)e; *v=&vm; return JNI_OK; }
static jint getenv_mock(JavaVM *v, void **e, jint version) { (void)v; assert(version==JNI_VERSION_1_6); *e=&env; return get_error ? JNI_ERR : detached ? JNI_EDETACHED : JNI_OK; }
#ifdef __ANDROID__
#define ENV_OUT JNIEnv **
#else
#define ENV_OUT void **
#endif
static jint attach(JavaVM *v, ENV_OUT e, void *args) { (void)v;(void)args; if(fail_attach)return JNI_ERR; attaches++; *e=&env; return JNI_OK; }
static jint detach(JavaVM *v) { (void)v; detaches++; return JNI_OK; }
static jobject global(JNIEnv *e,jobject o) { (void)e; if(fail_global)return NULL; globals++;return o; }
static void delglobal(JNIEnv *e,jobject o) { (void)e;(void)o; globals--;assert(globals>=0); }
static jobject local(JNIEnv *e,jobject o) { (void)e;if(fail_local)return NULL;locals++;return o; }
static void dellocal(JNIEnv *e,jobject o) { (void)e;(void)o;locals--;assert(locals>=0); }
static jstring string(JNIEnv *e,const char *s) { (void)e;(void)s;if(fail_string)return NULL;locals++;return (jstring)3; }
static void call(JNIEnv *e,jobject o,jmethodID m,...) { (void)e;(void)o;(void)m;calls++; if(reenter) { assert(locals>0); cleanup_info_message(&env); assert(!globals); } if(throw_callback) exception=1; }
static jboolean check(JNIEnv *e) { (void)e;return exception; }
static void clear(JNIEnv *e) { (void)e;exception=0; }
static const struct JNINativeInterface_ native={.GetJavaVM=getvm,.NewGlobalRef=global,.DeleteGlobalRef=delglobal,.NewLocalRef=local,.DeleteLocalRef=dellocal,.NewStringUTF=string,.CallVoidMethod=call,.ExceptionCheck=check,.ExceptionClear=clear};
static const struct JNIInvokeInterface_ invoke={.GetEnv=getenv_mock,.AttachCurrentThread=attach,.DetachCurrentThread=detach};
static void setup(void) {
#ifdef COW
setup_info_message(&env,(jobject)1,(jmethodID)2,42);
#else
setup_info_message(&env,(jobject)1,(jmethodID)2,(jmethodID)4,42);
#endif
}
int main(void) {
 env=&native;vm=&invoke;
 info_message("before setup",1);assert(!calls);
 setup();setup();assert(globals==1);
 info_message("attached",1);assert(calls==1&&!attaches&&!detaches&&!locals);
 detached=1;info_message("worker",1);assert(calls==2&&attaches==1&&detaches==1&&!locals);
 fail_attach=1;info_message("fail",1);assert(calls==2&&attaches==1);fail_attach=0;
 get_error=1;info_message("fail",1);assert(calls==2);get_error=0;
 fail_local=1;info_message("fail",1);assert(calls==2&&!locals);fail_local=0;
 fail_string=1;info_message("fail",1);assert(calls==2&&!locals);fail_string=0;
 fail_global=1;setup();assert(globals==1);fail_global=0;
 exception=1;info_message("exception",1);assert(!exception&&calls==2);
#ifndef COW
 info_message_stats(1,2);assert(calls==3);
#endif
 cleanup_info_message(&env);cleanup_info_message(&env);assert(!globals);
 info_message("after cleanup",1);assert(!locals&&attaches==detaches);
 setup();assert(globals==1);reenter=1;throw_callback=1;info_message("reentrant",1);assert(!globals&&!locals&&!exception);reenter=0;throw_callback=0;
 setup();cleanup_info_message(&env);assert(!globals);
 return 0;
}
