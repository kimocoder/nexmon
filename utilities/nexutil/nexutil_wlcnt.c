#include "nexutil_wlcnt.h"

#include <endian.h>
#include <stdint.h>
#include <string.h>

#include <wlcnt.h>
#include <nexioctls.h>

#ifndef WLC_GET_VAR
#define WLC_GET_VAR 262
#endif

#define WL_CNT_MIN_LEN 8

int
nexutil_read_wl_counters(nexutil_ioctl_fn ioctl_fn, struct nexio *nexio,
                         void *buf, size_t len)
{
    int ret;

    if (!ioctl_fn || !buf || len < sizeof("counters"))
        return -1;

    /*
     * Prefer the stock "counters" iovar: it is available on most firmware,
     * including builds that do not implement the custom ioctl. Trying the
     * custom ioctl first on those builds makes the driver log a failed DCMD
     * on every run.
     */
    memset(buf, 0, len);
    memcpy(buf, "counters", sizeof("counters"));

    ret = ioctl_fn(nexio, WLC_GET_VAR, buf, (int) len, false);
    if (ret >= 0)
        return ret;

    /* Fall back to the Nexmon ioctl for firmware without the iovar. */
    memset(buf, 0, len);

    return ioctl_fn(nexio, NEX_GET_WL_CNT, buf, (int) len, false);
}

int
nexutil_print_wl_counters(const void *buf, size_t buflen, FILE *out, FILE *err)
{
    const unsigned char *p = buf;
    uint16_t version, length;
    size_t i, words;
    size_t names = sizeof(wl_cnt_varname) / sizeof(wl_cnt_varname[0]);
    size_t descriptions = sizeof(wl_cnt_description) / sizeof(wl_cnt_description[0]);

    if (!buf || !out || buflen < WL_CNT_MIN_LEN)
        return -1;

    memcpy(&version, p, sizeof(version));
    memcpy(&length, p + sizeof(version), sizeof(length));
    version = le16toh(version);
    length = le16toh(length);

    fprintf(out, "version: %u\n", version);
    fprintf(out, "length: %u\n", length);

    if (length < WL_CNT_MIN_LEN || length > buflen) {
        if (err)
            fprintf(err, "ERR: invalid wl counter length %u (buffer %zu)\n",
                    length, buflen);
        return -1;
    }

    if (version < WL_CNT_T_VERSION && err)
        fprintf(err, "WARN: wl_cnt v%u predates the v%d field table; "
                "names may not match the firmware layout\n",
                version, WL_CNT_T_VERSION);

    words = length / sizeof(uint32_t);
    for (i = 1; i < words; i++) {
        uint32_t value;

        memcpy(&value, p + i * sizeof(value), sizeof(value));
        value = le32toh(value);

        if (i < names && i < descriptions && wl_cnt_varname[i] && wl_cnt_description[i])
            fprintf(out, "%s: %u (%s)\n", wl_cnt_varname[i], value,
                    wl_cnt_description[i]);
        else
            fprintf(out, "field_%zu: %u\n", i, value);
    }

    if (length > sizeof(wl_cnt_t))
        fprintf(out, "note: wl_cnt v%u is %u bytes; the v%d table decodes "
                "the first %zu bytes\n", version, length, WL_CNT_T_VERSION,
                sizeof(wl_cnt_t));

    return 0;
}