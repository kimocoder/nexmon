#include <endian.h>
#include <stdint.h>

#include <nexioctls.h>
#include <capabilities.h>

#include "nexutil_capabilities.h"

int
nexutil_report_capabilities(nexutil_ioctl_fn ioctl_fn, struct nexio *nexio,
                            FILE *out, FILE *err)
{
    uint32_t caps = 0;
    uint32_t known = NEX_CAP_MONITOR_MODE | NEX_CAP_MONITOR_MODE_RADIOTAP
                   | NEX_CAP_FRAME_INJECTION;

    if (!ioctl_fn || !out || !err)
        return -1;

    if (ioctl_fn(nexio, NEX_GET_CAPABILITIES, &caps, sizeof(caps), false) < 0) {
        fprintf(err, "ERR: could not get capabilities\n");
        return -1;
    }

    caps = le32toh(caps);
    fprintf(out, "capabilities: 0x%x\n", caps);
    fprintf(out, "  monitor mode:    %s\n", (caps & NEX_CAP_MONITOR_MODE) ? "yes" : "no");
    fprintf(out, "  radiotap:        %s\n", (caps & NEX_CAP_MONITOR_MODE_RADIOTAP) ? "yes" : "no");
    fprintf(out, "  frame injection: %s\n", (caps & NEX_CAP_FRAME_INJECTION) ? "yes" : "no");
    if (caps & ~known)
        fprintf(out, "  unknown bits:    0x%x\n", caps & ~known);

    return 0;
}