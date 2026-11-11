#ifndef NEXMON_PTY_COMPAT_H
#define NEXMON_PTY_COMPAT_H

/*
 * socat ships its own glibc openpty() implementation (openpty.c), but bionic's
 * <pty.h> only declares openpty() from API 23. Supply the matching prototype
 * for older platform levels so sycls.c and xio-pty.c compile.
 */
#if defined(__ANDROID__) && __ANDROID_API__ < 23
#include <termios.h>
#include <sys/ioctl.h>

#ifdef __cplusplus
extern "C" {
#endif

int openpty(int *amaster, int *aslave, char *name,
            struct termios *termp, struct winsize *winp);

#ifdef __cplusplus
}
#endif
#endif

#endif /* NEXMON_PTY_COMPAT_H */