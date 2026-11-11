#ifndef NEXUTIL_CAPABILITIES_H
#define NEXUTIL_CAPABILITIES_H

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

struct nexio;

#ifndef NEXUTIL_IOCTL_FN_DEFINED
#define NEXUTIL_IOCTL_FN_DEFINED
/* Injectable so the no-capability path can be tested without a device. */
typedef int (*nexutil_ioctl_fn)(struct nexio *nexio, int cmd, void *buf, int len, bool set);
#endif

/*
 * Query NEX_GET_CAPABILITIES and print the decoded bits to out.
 * Returns 0 on success, -1 when the ioctl fails (firmware without support).
 */
int nexutil_report_capabilities(nexutil_ioctl_fn ioctl_fn, struct nexio *nexio,
                                FILE *out, FILE *err);

#endif /* NEXUTIL_CAPABILITIES_H */