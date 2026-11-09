#include <jni.h>
#include <pthread.h>
#include "infomessage.h"

JavaVM *jvm;
char info_buffer[1024];
static JavaVM *callback_vm;
static jobject callback_obj;
static jmethodID callback_mid, callback_stats;
static int callback_id;
static pthread_mutex_t callback_lock = PTHREAD_MUTEX_INITIALIZER;

/* JNIEnv belongs to a thread; only JavaVM may be cached across threads. */
static JNIEnv *callback_env(JavaVM **vm, int *attached) {
    JNIEnv *env = NULL;
    jint status;
    *attached = 0;
    pthread_mutex_lock(&callback_lock);
    *vm = callback_vm;
    pthread_mutex_unlock(&callback_lock);
    if (!*vm) return NULL;
    status = (**vm)->GetEnv(*vm, (void **)&env, JNI_VERSION_1_6);
    if (status == JNI_EDETACHED) {
#ifdef __ANDROID__
        if ((**vm)->AttachCurrentThread(*vm, &env, NULL) != JNI_OK)
#else
        if ((**vm)->AttachCurrentThread(*vm, (void **)&env, NULL) != JNI_OK)
#endif
            return NULL;
        *attached = 1;
    } else if (status != JNI_OK) return NULL;
    return env;
}

static void callback_done(JavaVM *vm, JNIEnv *env, int attached) {
    if (attached) {
        /* A native-created attachment has no Java caller to receive exceptions. */
        if ((*env)->ExceptionCheck(env)) (*env)->ExceptionClear(env);
        (*vm)->DetachCurrentThread(vm);
    }
}

static void dispatch(char *mes, int reason, int rate, int amount, int stats) {
    JavaVM *vm;
    int attached, id;
    jobject obj = NULL;
    jmethodID mid;
    jstring text;
    JNIEnv *env = callback_env(&vm, &attached);
    if (!env) return;
    if ((*env)->ExceptionCheck(env)) goto done;
    /* Pin a local reference before releasing the lock. Setup/cleanup can then
     * replace the global reference without invalidating an in-flight callback.
     * Never hold the lock across Java code (callbacks can reenter setup). */
    pthread_mutex_lock(&callback_lock);
    mid = stats ? callback_stats : callback_mid;
    id = callback_id;
    if (callback_obj && mid) obj = (*env)->NewLocalRef(env, callback_obj);
    pthread_mutex_unlock(&callback_lock);
    if (!obj) goto done;
    if (stats) {
        (*env)->CallVoidMethod(env, obj, mid, (jint)rate, (jint)amount, (jint)id);
    } else {
        text = (*env)->NewStringUTF(env, mes ? mes : "");
        if (text) {
            (*env)->CallVoidMethod(env, obj, mid, text, (jint)reason, (jint)id);
            (*env)->DeleteLocalRef(env, text);
        }
    }
    (*env)->DeleteLocalRef(env, obj);
done:
    callback_done(vm, env, attached);
}

void info_message_thread(char *mes, int reason, JNIEnv *env) {
    /* Resolve the current thread even for legacy workers supplying an env. */
    (void)env;
    info_message(mes, reason);
}

void info_message(char *mes, int reason) {
    dispatch(mes, reason, 0, 0, 0);
}


void cleanup_info_message(JNIEnv *env) {
    jobject old;
    if (!env) return;
    pthread_mutex_lock(&callback_lock);
    old = callback_obj;
    callback_obj = NULL;
    callback_mid = callback_stats = NULL;
    pthread_mutex_unlock(&callback_lock);
    if (old) (*env)->DeleteGlobalRef(env, old);
}

void setup_info_message(JNIEnv* env, jobject obj, jmethodID mid, int myid) {
    JavaVM *vm = NULL;
    jobject replacement, old;
    if (!env || !obj || !mid || (*env)->ExceptionCheck(env)) return;
    if ((*env)->GetJavaVM(env, &vm) != JNI_OK || !vm) return;
    replacement = (*env)->NewGlobalRef(env, obj);
    if (!replacement) return;
    pthread_mutex_lock(&callback_lock);
    old = callback_obj;
    callback_vm = vm;
    jvm = vm; /* Retained for existing explicitly attached worker threads. */
    callback_obj = replacement;
    callback_mid = mid;
    callback_stats = NULL;
    callback_id = myid;
    pthread_mutex_unlock(&callback_lock);
    if (old) (*env)->DeleteGlobalRef(env, old);
}
