#ifndef NEXUTIL_WLCNT_H
#define NEXUTIL_WLCNT_H

#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>

struct nexio;

#ifndef NEXUTIL_IOCTL_FN_DEFINED
#define NEXUTIL_IOCTL_FN_DEFINED
typedef int (*nexutil_ioctl_fn)(struct nexio *nexio, int cmd, void *buf, int len, bool set);
#endif

/*
 * Read the firmware's wl_cnt_t counter block.
 *
 * Tries Broadcom's "counters" iovar (WLC_GET_VAR) first and falls back to the
 * Nexmon NEX_GET_WL_CNT ioctl, which only a few firmware patches implement.
 * buf must be at least sizeof(wl_cnt_t) bytes.
 *
 * Returns 0 on success, -1 when neither path works.
 */
int nexutil_read_wl_counters(nexutil_ioctl_fn ioctl_fn, struct nexio *nexio,
                             void *buf, size_t len);

/*
 * Decode and print a wl_cnt_t block. Accepts versions whose layout extends the
 * v9 field table (v9 and v10 are prefix-compatible); newer tail fields are
 * reported as field_<n> instead of being mislabelled.
 *
 * Returns 0 on success, -1 for an invalid header.
 */
int nexutil_print_wl_counters(const void *buf, size_t buflen, FILE *out, FILE *err);

#endif /* NEXUTIL_WLCNT_H */