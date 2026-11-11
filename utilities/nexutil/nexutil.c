/***************************************************************************
 *                                                                         *
 *          ###########   ###########   ##########    ##########           *
 *         ############  ############  ############  ############          *
 *         ##            ##            ##   ##   ##  ##        ##          *
 *         ##            ##            ##   ##   ##  ##        ##          *
 *         ###########   ####  ######  ##   ##   ##  ##    ######          *
 *          ###########  ####  #       ##   ##   ##  ##    #    #          *
 *                   ##  ##    ######  ##   ##   ##  ##    #    #          *
 *                   ##  ##    #       ##   ##   ##  ##    #    #          *
 *         ############  ##### ######  ##   ##   ##  ##### ######          *
 *         ###########    ###########  ##   ##   ##   ##########           *
 *                                                                         *
 *            S E C U R E   M O B I L E   N E T W O R K I N G              *
 *                                                                         *
 * This file is part of NexMon.                                            *
 *                                                                         *
 * Copyright (c) 2016 NexMon Team                                          *
 *                                                                         *
 * NexMon is free software: you can redistribute it and/or modify          *
 * it under the terms of the GNU General Public License as published by    *
 * the Free Software Foundation, either version 3 of the License, or       *
 * (at your option) any later version.                                     *
 *                                                                         *
 * NexMon is distributed in the hope that it will be useful,               *
 * but WITHOUT ANY WARRANTY; without even the implied warranty of          *
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the           *
 * GNU General Public License for more details.                            *
 *                                                                         *
 * You should have received a copy of the GNU General Public License       *
 * along with NexMon. If not, see <http://www.gnu.org/licenses/>.          *
 *                                                                         *
 **************************************************************************/

#define _XOPEN_SOURCE 700
#define _DEFAULT_SOURCE
#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>
#include <argp-extern.h>
#include <string.h>
#include <ctype.h>
#include <byteswap.h>
#include <endian.h>

#include <sys/types.h>
#include <sys/socket.h>
#include <unistd.h>
#include <sys/param.h> // for MIN macro

#include <sys/ioctl.h>
#include <arpa/inet.h>
#include <signal.h>
#include <time.h>
#ifdef BUILD_ON_RPI
#include <linux/if.h>
#else
#include <net/if.h>
#endif
#include <stdbool.h>
#define TYPEDEF_BOOL
#include <errno.h>

#include <nexioctls.h>
#include <capabilities.h>

typedef uint32_t uint;

#include <typedefs.h>
#include <bcmwifi_channels.h>
#include <b64.h>

#include "nexutil_capabilities.h"
#include "nexutil_wlcnt.h"

#if ANDROID
#include <sys/system_properties.h>
#endif

#define HEXDUMP_COLS 16

#define IPADDR(a,b,c,d) ((d) << 24 | (c) << 16 | (b) << 8 | (a))

#include <libnexio.h>

char            *ifname = "wlan0";
unsigned char   set_monitor = 0;
unsigned char   set_monitor_value = 0;
unsigned char   get_monitor = 0;
unsigned char   set_promisc = 0;
unsigned char   set_promisc_value = 0;
unsigned char   get_promisc = 0;
unsigned char   set_scansuppress = 0;
unsigned char   set_scansuppress_value = 0;
unsigned char   get_scansuppress = 0;
unsigned char   set_securitycookie = 0;
unsigned int    set_securitycookie_value = 0;
unsigned char   get_securitycookie = 0;
unsigned int    use_udp_tunneling = 0; // contains the securtiy cookie
unsigned int    txip = IPADDR(192,168,222,255);
unsigned int    custom_cmd = 0;
signed char     custom_cmd_set = -1;
unsigned int    custom_cmd_buf_len = 4;
unsigned char   custom_cmd_buf_len_set = false;
void            *custom_cmd_buf = NULL;
char            *custom_cmd_value = NULL;
unsigned char   get_chanspec = 0;
unsigned char   set_chanspec = 0;
char            *set_chanspec_value = NULL;
unsigned char   custom_cmd_value_int = false;
unsigned char   custom_cmd_value_base64 = false;
unsigned char   raw_output = false;
unsigned char   base64_output = false;
unsigned int    dump_objmem_addr = 0;
unsigned char   dump_objmem = false;
unsigned char   disassociate = false;
unsigned char   dump_wl_cnt = false;
unsigned char   revinfo = false;
unsigned char   get_capabilities = false;
unsigned char   nonblock = false;
unsigned char   read_shm = false;
unsigned int    read_shm_offset = 0;
unsigned char   write_shm = false;
unsigned char   write_shm_requested = false;
unsigned char   write_shm_offset_set = false;
unsigned int    write_shm_offset = 0;
unsigned int    write_shm_val = 0;
unsigned char   read_templ = false;
unsigned int    read_templ_offset = 0;
unsigned char   write_templ = false;
unsigned char   write_templ_requested = false;
unsigned char   write_templ_offset_set = false;
unsigned int    write_templ_offset = 0;
unsigned int    write_templ_val = 0;
unsigned char   dump_templ = false;
unsigned int    dump_templ_offset = 0;

#define MAX_HOP_CHANNELS 256

struct hop_config {
    uint32_t chanspecs[MAX_HOP_CHANNELS];
    int count;
    unsigned int interval_ms;
    unsigned int hop_count;
    bool enabled;
};

static struct hop_config hop_cfg = {
    .chanspecs = { 0 },
    .count = 0,
    .interval_ms = 250,
    .hop_count = 0,
    .enabled = false,
};

static unsigned char quiet = 0;
static volatile sig_atomic_t g_hopper_stop = 0;

static void
hopper_sig_handler(int sig)
{
    (void) sig;
    g_hopper_stop = 1;
}

static int
parse_hop_channels(const char *arg, struct hop_config *cfg)
{
    if (!arg || !*arg || !cfg)
        return -1;

    cfg->count = 0;
    char *copy = strdup(arg);
    if (!copy)
        return -1;

    char *saveptr = NULL;
    char *token = strtok_r(copy, ",; \t", &saveptr);
    while (token && cfg->count < MAX_HOP_CHANNELS) {
        while (*token == ' ' || *token == '\t') token++;
        char *end = token + strlen(token) - 1;
        while (end > token && (*end == ' ' || *end == '\t')) {
            *end = '\0';
            end--;
        }
        if (!*token) {
            token = strtok_r(NULL, ",; \t", &saveptr);
            continue;
        }

        if (strcasecmp(token, "2g") == 0 || strcasecmp(token, "2.4g") == 0) {
            for (int ch = 1; ch <= 13 && cfg->count < MAX_HOP_CHANNELS; ch++) {
                char ch_s[8];
                snprintf(ch_s, sizeof(ch_s), "%d", ch);
                uint32_t cs = wf_chspec_aton(ch_s);
                if (cs && cs != INVCHANSPEC)
                    cfg->chanspecs[cfg->count++] = cs;
            }
        } else if (strcasecmp(token, "5g") == 0) {
            static const uint8_t ch5g[] = {
                36, 40, 44, 48, 52, 56, 60, 64,
                100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140,
                149, 153, 157, 161, 165
            };
            for (size_t i = 0; i < sizeof(ch5g) && cfg->count < MAX_HOP_CHANNELS; i++) {
                char ch_s[8];
                snprintf(ch_s, sizeof(ch_s), "%d", ch5g[i]);
                uint32_t cs = wf_chspec_aton(ch_s);
                if (cs && cs != INVCHANSPEC)
                    cfg->chanspecs[cfg->count++] = cs;
            }
        } else if (strcasecmp(token, "all") == 0) {
            for (int ch = 1; ch <= 13 && cfg->count < MAX_HOP_CHANNELS; ch++) {
                char ch_s[8];
                snprintf(ch_s, sizeof(ch_s), "%d", ch);
                uint32_t cs = wf_chspec_aton(ch_s);
                if (cs && cs != INVCHANSPEC)
                    cfg->chanspecs[cfg->count++] = cs;
            }
            static const uint8_t ch5g[] = {
                36, 40, 44, 48, 52, 56, 60, 64,
                100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140,
                149, 153, 157, 161, 165
            };
            for (size_t i = 0; i < sizeof(ch5g) && cfg->count < MAX_HOP_CHANNELS; i++) {
                char ch_s[8];
                snprintf(ch_s, sizeof(ch_s), "%d", ch5g[i]);
                uint32_t cs = wf_chspec_aton(ch_s);
                if (cs && cs != INVCHANSPEC)
                    cfg->chanspecs[cfg->count++] = cs;
            }
        } else {
            char *range_sep = strstr(token, "..");
            int sep_len = 2;
            if (!range_sep) {
                range_sep = strchr(token, '-');
                sep_len = 1;
            }
            if (range_sep && range_sep != token && isdigit((unsigned char)*(range_sep - 1)) && isdigit((unsigned char)*(range_sep + sep_len))) {
                *range_sep = '\0';
                int start_ch = atoi(token);
                int end_ch = atoi(range_sep + sep_len);
                if (start_ch > 0 && end_ch >= start_ch && end_ch <= 250) {
                    for (int ch = start_ch; ch <= end_ch && cfg->count < MAX_HOP_CHANNELS; ch++) {
                        char ch_s[8];
                        snprintf(ch_s, sizeof(ch_s), "%d", ch);
                        uint32_t cs = wf_chspec_aton(ch_s);
                        if (cs && cs != INVCHANSPEC)
                            cfg->chanspecs[cfg->count++] = cs;
                    }
                } else {
                    free(copy);
                    return -1;
                }
            } else {
                uint32_t cs = 0;
                if (token[0] == '0' && (token[1] == 'x' || token[1] == 'X')) {
                    cs = (uint32_t)strtoul(token, NULL, 16);
                } else {
                    cs = wf_chspec_aton(token);
                    if (cs == 0 || cs == INVCHANSPEC) {
                        char *ep = NULL;
                        long ch = strtol(token, &ep, 10);
                        if (ep != token && *ep == '\0' && ch > 0 && ch <= 250) {
                            char ch_s[8];
                            snprintf(ch_s, sizeof(ch_s), "%ld", ch);
                            cs = wf_chspec_aton(ch_s);
                        }
                    }
                }
                if (cs == 0 || cs == INVCHANSPEC) {
                    free(copy);
                    return -1;
                }
                cfg->chanspecs[cfg->count++] = cs;
            }
        }
        token = strtok_r(NULL, ",; \t", &saveptr);
    }
    free(copy);
    return (cfg->count > 0) ? 0 : -1;
}

const char *argp_program_version = VERSION;
const char *argp_program_bug_address = "<mschulz@seemoo.tu-darmstadt.de>";

static char doc[] = "nexutil -- a program to control a nexmon firmware for broadcom chips.";

static struct argp_option options[] = {
    {"interface-name", 'I', "CHAR", 0, "Set interface name (default: wlan0)"},
    {"monitor", 'm', "INT", OPTION_ARG_OPTIONAL, "Set/Get monitor mode"},
    {"promisc", 'p', "INT", OPTION_ARG_OPTIONAL, "Set/Get promiscuous mode"},
    {"scansuppress", 'c', "INT", OPTION_ARG_OPTIONAL, "Set/Get scan suppress setting to avoid scanning"},
    {"disassociate", 'd', 0, 0, "Disassociate from access point"},
    {"get-custom-cmd", 'g', "INT", 0, "Get custom command, e.g. 107 for WLC_GET_VAR"},
    {"set-custom-cmd", 's', "INT", 0, "Set custom command, e.g. 108 for WLC_SET_VAR"},
    {"custom-cmd-buf-len", 'l', "INT", 0, "Custom command buffer length (default: 4)"},
    {"custom-cmd-value", 'v', "CHAR/INT", 0, "Initialization value for the buffer used by custom command"},
    {"custom-cmd-value-int", 'i', 0, 0, "Define that custom-cmd-value should be interpreted as integer"},
    {"custom-cmd-value-base64", 'b', 0, 0, "Define that custom-cmd-value should be interpreted as base64 string"},
    {"base64-output", 'R', 0, 0, "Write base64 encoded strings to stdout instead of hex dumping"},
    {"raw-output", 'r', "INT", OPTION_ARG_OPTIONAL, "Write raw output to stdout, or read D11 SHM at offset INT"},
    {"dump-wl_cnt", 'w', "INT", OPTION_ARG_OPTIONAL, "Dump WL counters (custom ioctl or 'counters' iovar), or write D11 SHM at offset INT"},
    {"read-shm", 'S', "INT", OPTION_ARG_OPTIONAL, "Read D11 SHM register at offset INT (host memory-mapped)"},
    {"write-shm", 'W', "INT=VAL", OPTION_ARG_OPTIONAL, "Write D11 SHM register (offset=val, or offset with -v)"},
    {"read-template", 'T', "INT", OPTION_ARG_OPTIONAL, "Read D11 template RAM at offset INT (host memory-mapped)"},
    {"write-template", 'Y', "INT=VAL", OPTION_ARG_OPTIONAL, "Write D11 template RAM (offset=val, or -Y offset val)"},
    {"dump-template", 'M', "INT", OPTION_ARG_OPTIONAL, "Dump D11 template RAM table (offset, default: 0)"},
    {"dump-objmem", 'o', "INT", 0, "Dumps objmem at addr INT"},
    {"chanspec", 'k', "CHAR/INT", OPTION_ARG_OPTIONAL, "Set chanspec either as integer (e.g., 0x1001, set -i) or as string (e.g., 64/80)."},
    {"nonblock", 'n', 0, 0, "Non-blocking channel hopping mode (sub-2ms fast hop)"},
    {"hop", 'H', "CHANNELS", 0, "Channel hopper: comma-separated list of channels/chanspecs (e.g. 1,6,11 or 1-13 or 2g or 5g)"},
    {"interval", 't', "MS", 0, "Channel hopper dwell interval in milliseconds (default: 250 ms)"},
    {"hop-count", 'C', "INT", 0, "Channel hopper iteration count (default: 0 = loop indefinitely)"},
    {"quiet", 'q', 0, 0, "Quiet mode (suppress per-hop output)"},
    {"security-cookie", 'x', "INT", OPTION_ARG_OPTIONAL, "Set/Get security cookie"},
    {"use-udp-tunneling", 'X', "INT", 0, "Use UDP tunneling with security cookie INT"},
    {"broadcast-ip", 'B', "CHAR", 0, "Broadcast IP to use for UDP tunneling (default: 192.168.222.255)"},
    {"revinfo", 'V', 0, 0, "Dump revision information of the Wi-Fi chip"},
    {"capabilities", 'G', 0, 0, "Print firmware capabilities (monitor, radiotap, injection)"},
    { 0 }
};

static int last_optional_opt = 0;

static unsigned char
parse_uchar_range(const char *arg, int min_val, int max_val, const char *name, struct argp_state *state)
{
    char *endptr = NULL;
    long val;

    errno = 0;
    val = strtol(arg, &endptr, 0);
    if (endptr == arg || *endptr != '\0' || errno != 0 || val < min_val || val > max_val) {
        fprintf(stderr, "ERR: invalid %s value '%s' (valid range: %d..%d)\n",
                name, arg, min_val, max_val);
        argp_error(state, "invalid %s value '%s' (valid range: %d..%d)",
                   name, arg, min_val, max_val);
    }
    return (unsigned char) val;
}

static unsigned int
parse_uint(const char *arg, const char *name, struct argp_state *state)
{
    char *endptr = NULL;
    unsigned long val;

    errno = 0;
    val = strtoul(arg, &endptr, 0);
    if (endptr == arg || *endptr != '\0' || errno != 0 || val > 0xFFFFFFFFUL) {
        fprintf(stderr, "ERR: invalid %s '%s'\n", name, arg);
        argp_error(state, "invalid %s '%s'", name, arg);
    }
    return (unsigned int) val;
}

/* Parse a numeric value without argp state, for options resolved after the
 * command line has been read (e.g. -W OFFSET -v VALUE in either order). */
static unsigned int
parse_uint_value(const char *arg, const char *name)
{
    char *endptr = NULL;
    unsigned long val;

    errno = 0;
    val = strtoul(arg, &endptr, 0);
    if (endptr == arg || *endptr != '\0' || errno != 0 || val > 0xFFFFFFFFUL) {
        fprintf(stderr, "ERR: invalid %s '%s'\n", name, arg);
        exit(EXIT_FAILURE);
    }
    return (unsigned int) val;
}

static error_t
parse_opt(int key, char *arg, struct argp_state *state)
{
    switch (key) {
        case ARGP_KEY_INIT:
            last_optional_opt = 0;
            break;

        case 'I': {
            if (strlen(arg) >= IFNAMSIZ) {
                fprintf(stderr, "ERR: interface name '%s' too long (max %d)\n", arg, IFNAMSIZ-1);
                exit(EXIT_FAILURE);
            }
            ifname = arg;
            last_optional_opt = 0;
            break;
        }

        case 'm':
            if (arg) {
                set_monitor = true;
                set_monitor_value = parse_uchar_range(arg, 0, 255, "monitor mode", state);
                last_optional_opt = 0;
            } else {
                get_monitor = true;
                last_optional_opt = 'm';
            }
            break;

        case 'p':
            if (arg) {
                set_promisc = true;
                set_promisc_value = parse_uchar_range(arg, 0, 1, "promisc", state);
                last_optional_opt = 0;
            } else {
                get_promisc = true;
                last_optional_opt = 'p';
            }
            break;

        case 'c':
            if (arg) {
                set_scansuppress = true;
                set_scansuppress_value = parse_uchar_range(arg, 0, 1, "scansuppress", state);
                last_optional_opt = 0;
            } else {
                get_scansuppress = true;
                last_optional_opt = 'c';
            }
            break;

        case 'd':
            disassociate = true;
            last_optional_opt = 0;
            break;

        case 'g': {
            char *endptr = NULL;
            long v;
            errno = 0;
            v = strtol(arg, &endptr, 0);
            if (endptr == arg || *endptr != '\0' || errno != 0 || v < 0 || v > INT_MAX) {
                fprintf(stderr, "ERR: invalid custom command '%s'\n", arg);
                exit(EXIT_FAILURE);
            }
            custom_cmd_set = false;
            custom_cmd = (unsigned int) v;
            last_optional_opt = 0;
            break;
        }

        case 's': {
            char *endptr = NULL;
            long v;
            errno = 0;
            v = strtol(arg, &endptr, 0);
            if (endptr == arg || *endptr != '\0' || errno != 0 || v < 0 || v > INT_MAX) {
                fprintf(stderr, "ERR: invalid custom command '%s'\n", arg);
                exit(EXIT_FAILURE);
            }
            custom_cmd_set = true;
            custom_cmd = (unsigned int) v;
            last_optional_opt = 0;
            break;
        }
        
        case 'l':
            {
                char *endptr = NULL;
                long v = strtol(arg, &endptr, 0);
                /* reject zero, negative, non-numeric, or oversized lengths: the
                 * value later sizes malloc() and is passed to nex_ioctl(int len),
                 * so a zero/negative/huge value would fail or wrap downstream. */
                if (endptr == arg || *endptr != '\0' || v < 1 || v > 0x100000) {
                    fprintf(stderr, "ERR: invalid -l length '%s' (expected 1..1048576)\n", arg);
                    exit(EXIT_FAILURE);
                }
                custom_cmd_buf_len = (unsigned int) v;
                custom_cmd_buf_len_set = true;
                last_optional_opt = 0;
            }
            break;

        case 'k':
            if (arg) {
                set_chanspec = true;
                set_chanspec_value = arg;
                last_optional_opt = 0;
            } else {
                get_chanspec = true;
                last_optional_opt = 'k';
            }
            break;

        case 'n':
            nonblock = true;
            last_optional_opt = 0;
            break;

        case 'v':
            custom_cmd_value = arg;
            last_optional_opt = 0;
            break;

        case 'i':
            if (!custom_cmd_value_base64)
                custom_cmd_value_int = true;
            else
                argp_error(state, "you can only either use base64 (-b) or integer (-i) encoding");
            last_optional_opt = 0;
            break;

        case 'b':
            if (!custom_cmd_value_int)
                custom_cmd_value_base64 = true;
            else
                argp_error(state, "you can only either use base64 (-b) or integer (-i) encoding");
            last_optional_opt = 0;
            break;

        case 'S':
            if (arg) {
                read_shm = true;
                read_shm_offset = parse_uint(arg, "shm offset", state);
                last_optional_opt = 0;
            } else {
                read_shm = true;
                last_optional_opt = 'S';
            }
            break;

        case 'r':
            if (arg) {
                read_shm = true;
                read_shm_offset = parse_uint(arg, "shm offset", state);
                last_optional_opt = 0;
            } else {
                if (base64_output)
                    argp_error(state, "you can only either use base64 (-R) or raw (-r) output");
                raw_output = true;
                last_optional_opt = 'r';
            }
            break;

        case 'R':
            if (!raw_output)
                base64_output = true;
            else
                argp_error(state, "you can only either use base64 (-R) or raw (-r) output");
            last_optional_opt = 0;
            break;

        case 'T':
            read_templ = true;
            if (arg) {
                read_templ_offset = parse_uint(arg, "template offset", state);
                last_optional_opt = 0;
            } else {
                read_templ_offset = 0;
                last_optional_opt = 'T';
            }
            break;

        case 'M':
            dump_templ = true;
            if (arg) {
                dump_templ_offset = parse_uint(arg, "template dump offset", state);
                last_optional_opt = 0;
            } else {
                dump_templ_offset = 0;
                last_optional_opt = 'M';
            }
            break;

        case 'Y': {
            if (arg) {
                char *eq = strpbrk(arg, "=,:");
                if (eq) {
                    *eq = '\0';
                    write_templ_offset = parse_uint(arg, "template offset", state);
                    write_templ_val = parse_uint(eq + 1, "template value", state);
                    write_templ = true;
                    last_optional_opt = 0;
                } else {
                    write_templ_offset = parse_uint(arg, "template offset", state);
                    write_templ_offset_set = true;
                    if (custom_cmd_value) {
                        write_templ_val = parse_uint(custom_cmd_value, "template value", state);
                        write_templ = true;
                        last_optional_opt = 0;
                    } else {
                        last_optional_opt = 'Y';
                    }
                }
            } else {
                write_templ_requested = true;
                last_optional_opt = 'Y';
            }
            break;
        }

        case 'o': {
            char *endptr = NULL;
            unsigned long v;
            errno = 0;
            v = strtoul(arg, &endptr, 0);
            if (endptr == arg || *endptr != '\0' || errno != 0 || v > 0xFFFFFFFFUL) {
                fprintf(stderr, "ERR: invalid objmem addr '%s'\n", arg);
                exit(EXIT_FAILURE);
            }
            dump_objmem_addr = (unsigned int) v;
            dump_objmem = true;
            last_optional_opt = 0;
            break;
        }

        case 'W':
        case 'w': {
            if (arg) {
                char *eq = strpbrk(arg, "=,:");
                if (eq) {
                    *eq = '\0';
                    write_shm_offset = parse_uint(arg, "shm offset", state);
                    write_shm_val = parse_uint(eq + 1, "shm value", state);
                    write_shm = true;
                    last_optional_opt = 0;
                } else {
                    write_shm_offset = parse_uint(arg, "shm offset", state);
                    write_shm_offset_set = true;
                    if (custom_cmd_value) {
                        write_shm_val = parse_uint(custom_cmd_value, "shm value", state);
                        write_shm = true;
                        last_optional_opt = 0;
                    } else {
                        last_optional_opt = key;
                    }
                }
            } else {
                if (key == 'w')
                    dump_wl_cnt = true;
                else
                    write_shm_requested = true;
                last_optional_opt = key;
            }
            break;
        }

        case 'x':
            if (use_udp_tunneling != 0)
                argp_error(state, "You cannot use -x in combination with -X");
            if (arg) {
                set_securitycookie = true;
                set_securitycookie_value = parse_uint(arg, "security cookie", state);
                last_optional_opt = 0;
            } else {
                get_securitycookie = true;
                last_optional_opt = 'x';
            }
            break;

        case 'X':
            if (set_securitycookie || get_securitycookie)
                argp_error(state, "You cannot use -x in combination with -X");
            use_udp_tunneling = parse_uint(arg, "security cookie", state);
            if (use_udp_tunneling == 0)
                argp_error(state, "You need to use a security cookie different from 0");
            last_optional_opt = 0;
            break;

        case 'B':
            if (arg) {
                struct in_addr addr;
                if (inet_pton(AF_INET, arg, &addr) != 1) {
                    fprintf(stderr, "ERR: invalid broadcast IP address '%s'\n", arg);
                    argp_error(state, "invalid broadcast IP address '%s'", arg);
                }
                txip = addr.s_addr;
            }
            last_optional_opt = 0;
            break;

        case 'V':
            revinfo = true;
            last_optional_opt = 0;
            break;
        case 'G':
            get_capabilities = true;
            last_optional_opt = 0;
            break;
        case 'H':
            if (arg) {
                if (parse_hop_channels(arg, &hop_cfg) < 0) {
                    fprintf(stderr, "ERR: invalid hop channels '%s'\n", arg);
                    exit(EXIT_FAILURE);
                }
                hop_cfg.enabled = true;
                last_optional_opt = 0;
            }
            break;
        case 't':
            if (arg) {
                unsigned int val = parse_uint(arg, "interval", state);
                if (val == 0 || val > 600000) {
                    fprintf(stderr, "ERR: invalid interval '%s' (valid range: 1..600000 ms)\n", arg);
                    exit(EXIT_FAILURE);
                }
                hop_cfg.interval_ms = val;
                last_optional_opt = 0;
            }
            break;
        case 'C':
            if (arg) {
                hop_cfg.hop_count = parse_uint(arg, "hop-count", state);
                last_optional_opt = 0;
            }
            break;
        case 'q':
            quiet = 1;
            last_optional_opt = 0;
            break;

        case ARGP_KEY_ARG:
            switch (last_optional_opt) {
                case 'k':
                    get_chanspec = false;
                    set_chanspec = true;
                    set_chanspec_value = arg;
                    last_optional_opt = 0;
                    break;
                case 'm':
                    get_monitor = false;
                    set_monitor = true;
                    set_monitor_value = parse_uchar_range(arg, 0, 255, "monitor mode", state);
                    last_optional_opt = 0;
                    break;
                case 'p':
                    get_promisc = false;
                    set_promisc = true;
                    set_promisc_value = parse_uchar_range(arg, 0, 1, "promisc", state);
                    last_optional_opt = 0;
                    break;
                case 'c':
                    get_scansuppress = false;
                    set_scansuppress = true;
                    set_scansuppress_value = parse_uchar_range(arg, 0, 1, "scansuppress", state);
                    last_optional_opt = 0;
                    break;
                case 'x':
                    get_securitycookie = false;
                    set_securitycookie = true;
                    set_securitycookie_value = parse_uint(arg, "security cookie", state);
                    last_optional_opt = 0;
                    break;
                case 'S':
                    read_shm = true;
                    read_shm_offset = parse_uint(arg, "shm offset", state);
                    last_optional_opt = 0;
                    break;
                case 'r':
                    raw_output = false;
                    read_shm = true;
                    read_shm_offset = parse_uint(arg, "shm offset", state);
                    last_optional_opt = 0;
                    break;
                case 'W':
                case 'w': {
                    dump_wl_cnt = false;
                    char *eq = strpbrk(arg, "=,:");
                    if (eq) {
                        *eq = '\0';
                        write_shm_offset = parse_uint(arg, "shm offset", state);
                        write_shm_val = parse_uint(eq + 1, "shm value", state);
                        write_shm = true;
                        last_optional_opt = 0;
                    } else if (!write_shm_offset_set) {
                        write_shm_offset = parse_uint(arg, "shm offset", state);
                        write_shm_offset_set = true;
                        if (custom_cmd_value) {
                            write_shm_val = parse_uint(custom_cmd_value, "shm value", state);
                            write_shm = true;
                            last_optional_opt = 0;
                        } else {
                            last_optional_opt = 'w';
                        }
                    } else {
                        write_shm_val = parse_uint(arg, "shm value", state);
                        write_shm = true;
                        last_optional_opt = 0;
                    }
                    break;
                }
                case 'T':
                    read_templ = true;
                    read_templ_offset = parse_uint(arg, "template offset", state);
                    last_optional_opt = 0;
                    break;
                case 'M':
                    dump_templ = true;
                    dump_templ_offset = parse_uint(arg, "template dump offset", state);
                    last_optional_opt = 0;
                    break;
                case 'Y': {
                    char *eq = strpbrk(arg, "=,:");
                    if (eq) {
                        *eq = '\0';
                        write_templ_offset = parse_uint(arg, "template offset", state);
                        write_templ_val = parse_uint(eq + 1, "template value", state);
                        write_templ = true;
                        last_optional_opt = 0;
                    } else if (!write_templ_offset_set) {
                        write_templ_offset = parse_uint(arg, "template offset", state);
                        write_templ_offset_set = true;
                        if (custom_cmd_value) {
                            write_templ_val = parse_uint(custom_cmd_value, "template value", state);
                            write_templ = true;
                            last_optional_opt = 0;
                        } else {
                            last_optional_opt = 'Y';
                        }
                    } else {
                        write_templ_val = parse_uint(arg, "template value", state);
                        write_templ = true;
                        last_optional_opt = 0;
                    }
                    break;
                }
                default:
                    return ARGP_ERR_UNKNOWN;
            }
            break;

        case ARGP_KEY_END:
        case ARGP_KEY_SUCCESS:
            last_optional_opt = 0;
            break;

        default:
            return ARGP_ERR_UNKNOWN;
    }

    return 0;
}

static struct argp argp = { options, parse_opt, 0, doc };

/* source: http://grapsus.net/blog/post/Hexadecimal-dump-in-C */
void
hexdump(void *mem, unsigned int len)
{
    unsigned int i, j;
    
    for(i = 0; i < len + ((len % HEXDUMP_COLS) ? (HEXDUMP_COLS - len % HEXDUMP_COLS) : 0); i++) {
        if (i % HEXDUMP_COLS == 0) {
                printf("0x%06x: ", i);
        }

        if(i < len) {
            printf("%02x ", 0xFF & ((char*)mem)[i]);
        } else {
            printf("   ");
        }

        if(i % HEXDUMP_COLS == (HEXDUMP_COLS - 1)) {
            for(j = i - (HEXDUMP_COLS - 1); j <= i; j++) {
                if(j >= len) {
                    putchar(' ');
                } else if(isprint((unsigned char)((char*)mem)[j])) {
                    putchar(0xFF & ((char*)mem)[j]);        
                } else {
                        putchar('.');
                }
            }
            putchar('\n');
        }
    }
}

static void
ioctl_alarm_handler(int sig)
{
    (void) sig;
    const char msg[] = "ERR: ioctl timed out after 10s (firmware wedged, SDIO -110? check dmesg)\n";
    (void) write(STDERR_FILENO, msg, sizeof(msg) - 1);
    _exit(124);
}

/* Produce a human-readable string for boardrev */
char *
bcm_brev_str(uint32 brev, char *buf)
{
    if (brev < 0x100)
        snprintf(buf, 8, "%d.%d", (brev & 0xf0) >> 4, brev & 0xf);
    else
        snprintf(buf, 8, "%c%03x", ((brev & 0xf000) == 0x1000) ? 'P' : 'A', brev & 0xfff);

    return (buf);
}

int
main(int argc, char **argv)
{
    struct nexio *nexio;
    int ret;
    int buf = 0;
    int failed = 0;

    argp_parse(&argp, argc, argv, ARGP_IN_ORDER, 0, 0);

    /* -v may appear after the offset, so resolve the value now. */
    if (!write_shm && write_shm_offset_set && custom_cmd_value) {
        write_shm_val = parse_uint_value(custom_cmd_value, "shm value");
        write_shm = true;
    }
    if (!write_templ && write_templ_offset_set && custom_cmd_value) {
        write_templ_val = parse_uint_value(custom_cmd_value, "template value");
        write_templ = true;
    }

    if ((write_shm_requested || write_shm_offset_set) && !write_shm) {
        fprintf(stderr, "ERR: -W/-w offset given without a value "
                "(use -W offset=value or -v VALUE)\n");
        exit(EXIT_FAILURE);
    }
    if ((write_templ_requested || write_templ_offset_set) && !write_templ) {
        fprintf(stderr, "ERR: -Y offset given without a value "
                "(use -Y offset=value or -v VALUE)\n");
        exit(EXIT_FAILURE);
    }

    if (hop_cfg.enabled && set_chanspec) {
        fprintf(stderr, "ERR: cannot combine --chanspec (-k) with --hop (-H)\n");
        exit(EXIT_FAILURE);
    }

    /* Guard against wedged SDIO firmware that blocks ioctl indefinitely */
    signal(SIGALRM, ioctl_alarm_handler);
    alarm(10);

    if (use_udp_tunneling != 0)
        nexio = nex_init_udp(use_udp_tunneling, txip);
    else
#ifdef USE_NETLINK
        nexio = nex_init_netlink_ifname(ifname);
#elif defined(USE_VENDOR_CMD)
        nexio = nex_init_vendor_cmd(ifname);
#else
        nexio = nex_init_ioctl(ifname);
#endif

    if (!nexio) {
        fprintf(stderr, "ERR: could not initialise nexio interface\n");
        exit(EXIT_FAILURE);
    }

    if (set_monitor) {
        buf = set_monitor_value;
        ret = nex_ioctl(nexio, WLC_SET_MONITOR, &buf, 4, true);
        if (ret < 0) {
            fprintf(stderr, "ERR: could not set monitor mode to %d\n", set_monitor_value);
            failed = 1;
        }
    }

    if (set_promisc) {
        buf = set_promisc_value;
        ret = nex_ioctl(nexio, WLC_SET_PROMISC, &buf, 4, true);
        if (ret < 0) {
            fprintf(stderr, "ERR: could not set promiscuous mode to %d\n", set_promisc_value);
            failed = 1;
        }
    }

    if (set_scansuppress) {
        buf = set_scansuppress_value;
        if (set_scansuppress_value)
            ret = nex_ioctl(nexio, WLC_SET_SCANSUPPRESS, &buf, 4, true);
        else
            ret = nex_ioctl(nexio, WLC_SET_SCANSUPPRESS, &buf, 1, true);
        if (ret < 0) {
            fprintf(stderr, "ERR: could not set scan suppress to %d\n", set_scansuppress_value);
            failed = 1;
        }
    }

    if (set_securitycookie) {
        buf = set_securitycookie_value;
        ret = nex_ioctl(nexio, NEX_SET_SECURITYCOOKIE, &buf, 4, true);
        if (ret < 0) {
            fprintf(stderr, "ERR: could not set security cookie\n");
            failed = 1;
        }
    }

    if (get_monitor) {
        ret = nex_ioctl(nexio, WLC_GET_MONITOR, &buf, 4, false);
        if (ret < 0) { fprintf(stderr, "ERR: could not get monitor mode\n"); failed = 1; }
        else printf("monitor: %d\n", buf);
    }

    if (get_promisc) {
        ret = nex_ioctl(nexio, WLC_GET_PROMISC, &buf, 4, false);
        if (ret < 0) { fprintf(stderr, "ERR: could not get promiscuous mode\n"); failed = 1; }
        else printf("promisc: %d\n", buf);
    }

    if (get_scansuppress) {
        ret = nex_ioctl(nexio, WLC_GET_SCANSUPPRESS, &buf, 4, false);
        if (ret < 0) { fprintf(stderr, "ERR: could not get scan suppress\n"); failed = 1; }
        else printf("scansuppress: %d\n", buf);
    }

    if (get_securitycookie) {
        ret = nex_ioctl(nexio, NEX_GET_SECURITYCOOKIE, &buf, 4, false);
        if (ret < 0) { fprintf(stderr, "ERR: could not get security cookie\n"); failed = 1; }
        else printf("securitycookie: %d\n", buf);
    }

    if (get_capabilities) {
        if (nexutil_report_capabilities(nex_ioctl, nexio, stdout, stderr) < 0)
            failed = 1;
    }

    if (get_chanspec) {
        char chanspec_str[CHANSPEC_STR_LEN] = { 0 };
        uint32 cs32 = 0;
        uint16 chanspec = 0;

        /* Try fast-path NEX_GET_CHANSPEC_OVERRIDE first (sub-2ms direct driver/firmware read) */
        ret = nex_ioctl(nexio, NEX_GET_CHANSPEC_OVERRIDE, &cs32, sizeof(cs32), false);
        if (ret == 0 && cs32 != 0) {
            chanspec = (uint16) le32toh(cs32);
        } else {
            /* Fallback to legacy WLC_GET_VAR "chanspec" */
            char charbuf[16] __attribute__((aligned(4))) = "chanspec";
            ret = nex_ioctl(nexio, WLC_GET_VAR, charbuf, 13, false);
            if (ret < 0 || memcmp(charbuf, "chanspec", 8) == 0) {
                fprintf(stderr, "ERR: failed to get chanspec\n");
                failed = 1;
            } else {
                memcpy(&chanspec, charbuf, sizeof(chanspec));
                chanspec = le16toh(chanspec);
            }
        }

        if (!failed) {
            bool is_psc = wf_chspec_is_6g_psc((chanspec_t) chanspec);
            printf("chanspec: 0x%04x, %s%s\n", chanspec,
                   wf_chspec_ntoa_ex(chanspec, chanspec_str),
                   is_psc ? " (6GHz PSC)" : "");
        }
    }

    if (set_chanspec) {
        uint32 cs = 0;
        uint32 cs_le = 0;

        if (custom_cmd_value_int)
            cs = strtoul(set_chanspec_value, NULL, 0);
        else
            cs = wf_chspec_aton(set_chanspec_value);

        if (cs == 0 || cs == INVCHANSPEC) {
            fprintf(stderr, "ERR: invalid chanspec '%s'\n", set_chanspec_value);
            nex_free(nexio);
            return -1;
        } else {
            cs_le = htole32(cs);
            if (nonblock) {
                /* Non-blocking fast channel hop (fire-and-forget sub-2ms) */
                ret = nex_ioctl_nonblock(nexio, NEX_SET_CHANSPEC_OVERRIDE, &cs_le, sizeof(cs_le));
                if (ret < 0) {
                    char chanspec_str[CHANSPEC_STR_LEN] = { 0 };
                    bool is_psc = wf_chspec_is_6g_psc((chanspec_t) cs);
                    fprintf(stderr, "ERR: failed to non-blocking set chanspec 0x%04x (%s%s)\n",
                            cs, wf_chspec_ntoa_ex((chanspec_t) cs, chanspec_str),
                            is_psc ? " [6GHz PSC]" : "");
                    nex_free(nexio);
                    return -1;
                }
            } else {
                /* Try fast-path NEX_SET_CHANSPEC_OVERRIDE first */
                ret = nex_ioctl(nexio, NEX_SET_CHANSPEC_OVERRIDE, &cs_le, sizeof(cs_le), true);
                if (ret < 0) {
                    /* Fallback to legacy WLC_SET_VAR "chanspec" */
                    char charbuf[16] __attribute__((aligned(4))) = "chanspec";
                    memcpy(&charbuf[9], &cs_le, sizeof(cs_le));
                    ret = nex_ioctl(nexio, WLC_SET_VAR, charbuf, 13, true);
                    if (ret < 0) {
                        char chanspec_str[CHANSPEC_STR_LEN] = { 0 };
                        bool is_psc = wf_chspec_is_6g_psc((chanspec_t) cs);
                        fprintf(stderr, "ERR: failed to set chanspec 0x%04x (%s%s)\n",
                                cs, wf_chspec_ntoa_ex((chanspec_t) cs, chanspec_str),
                                is_psc ? " [6GHz PSC]" : "");
                        nex_free(nexio);
                        return -1;
                    }
                }
            }
        }
    }

    if (hop_cfg.enabled) {
        /* Cancel one-off 10-second alarm */
        alarm(0);

        /* Set up signal handlers for graceful exit on SIGINT or SIGTERM */
        struct sigaction sa;
        memset(&sa, 0, sizeof(sa));
        sa.sa_handler = hopper_sig_handler;
        sigemptyset(&sa.sa_mask);
        sigaction(SIGINT, &sa, NULL);
        sigaction(SIGTERM, &sa, NULL);

        if (!quiet) {
            printf("Channel hopper started on %s: %d channels, dwell %u ms%s%s\n",
                   ifname, hop_cfg.count, hop_cfg.interval_ms,
                   nonblock ? " (non-blocking)" : "",
                   hop_cfg.hop_count > 0 ? "" : " (infinite loop)");
            fflush(stdout);
        }

        unsigned int total_hops = 0;
        int idx = 0;

        while (!g_hopper_stop) {
            uint32_t cs = hop_cfg.chanspecs[idx];
            uint32_t cs_le = htole32(cs);
            int hop_ret = 0;

            if (nonblock) {
                hop_ret = nex_ioctl_nonblock(nexio, NEX_SET_CHANSPEC_OVERRIDE, &cs_le, sizeof(cs_le));
            } else {
                alarm(5);
                hop_ret = nex_ioctl(nexio, NEX_SET_CHANSPEC_OVERRIDE, &cs_le, sizeof(cs_le), true);
                if (hop_ret < 0) {
                    char charbuf[16] __attribute__((aligned(4))) = "chanspec";
                    memcpy(&charbuf[9], &cs_le, sizeof(cs_le));
                    hop_ret = nex_ioctl(nexio, WLC_SET_VAR, charbuf, 13, true);
                }
                alarm(0);
            }

            char chanspec_str[CHANSPEC_STR_LEN] = { 0 };
            bool is_psc = wf_chspec_is_6g_psc((chanspec_t) cs);
            const char *cs_desc = wf_chspec_ntoa_ex((chanspec_t) cs, chanspec_str);

            if (hop_ret < 0) {
                fprintf(stderr, "WARN: hop to 0x%04x (%s) failed (err=%d)\n",
                        cs, cs_desc ? cs_desc : "unknown", hop_ret);
            } else if (!quiet) {
                printf("[hop #%u] %s (0x%04x)%s\n",
                       total_hops + 1, cs_desc ? cs_desc : "unknown", cs,
                       is_psc ? " [6GHz PSC]" : "");
                fflush(stdout);
            }

            total_hops++;
            if (hop_cfg.hop_count > 0 && total_hops >= hop_cfg.hop_count)
                break;

            idx = (idx + 1) % hop_cfg.count;

            /* Sleep for dwell interval */
            struct timespec req, rem;
            req.tv_sec = hop_cfg.interval_ms / 1000;
            req.tv_nsec = (long)(hop_cfg.interval_ms % 1000) * 1000000L;
            while (nanosleep(&req, &rem) == -1 && errno == EINTR) {
                if (g_hopper_stop)
                    break;
                req = rem;
            }
        }

        if (!quiet) {
            printf("Channel hopper stopped (%u hops completed)\n", total_hops);
            fflush(stdout);
        }
        nex_free(nexio);
        return 0;
    }

    if (custom_cmd_set != -1) {
        if (!custom_cmd_buf_len_set) {
            if (custom_cmd_set == 1) { // SET command
                if (custom_cmd_value_base64 && custom_cmd_value) {
                    size_t est_len = (strlen(custom_cmd_value) * 3) / 4 + 4;
                    custom_cmd_buf_len = est_len > 4 ? (unsigned int) est_len : 4;
                } else if (custom_cmd_value && !custom_cmd_value_int) {
                    size_t slen = strlen(custom_cmd_value) + 1;
                    custom_cmd_buf_len = slen > 4 ? (unsigned int) slen : 4;
                } else if (custom_cmd_value_int) {
                    custom_cmd_buf_len = sizeof(uint32);
                }
            } else if (custom_cmd_set == 0) { // GET command
                /* For telemetry/structured dumps, 4 bytes truncates almost everything;
                 * default to 256 bytes (or 1024 for known dump commands 511, 512, 514). */
                if (custom_cmd == 511 || custom_cmd == 512 || custom_cmd == 514)
                    custom_cmd_buf_len = 1024;
                else
                    custom_cmd_buf_len = 256;
            }
        }

        custom_cmd_buf = malloc(custom_cmd_buf_len);
        if (!custom_cmd_buf) {
            nex_free(nexio);
            return -1;
        }

        memset(custom_cmd_buf, 0, custom_cmd_buf_len);

        if (custom_cmd_set == 1 && raw_output) { // set command using raw input
            //freopen(NULL, "rb", stdin);
            size_t bytes_read = fread(custom_cmd_buf, 1, custom_cmd_buf_len, stdin);
            if (bytes_read == 0 && ferror(stdin)) {
                fprintf(stderr, "ERR: failed reading from stdin\n");
                free(custom_cmd_buf);
                nex_free(nexio);
                return -1;
            }
        } else {
            if (custom_cmd_value) {
                if (custom_cmd_value_int) {
                    /* writing a 4-byte integer needs a buffer of at least 4 bytes */
                    if (custom_cmd_buf_len < sizeof(uint32)) {
                        fprintf(stderr, "ERR: -v integer needs -l >= 4\n");
                        free(custom_cmd_buf);
                        nex_free(nexio);
                        return -1;
                    }
                    *(uint32 *) custom_cmd_buf = strtoul(custom_cmd_value, NULL, 0);
                } else if (custom_cmd_value_base64) {
                    size_t decoded_len = 0;
                    unsigned char *decoded = b64_decode_ex(custom_cmd_value, strlen(custom_cmd_value), &decoded_len);
                    if (!decoded) {
                        fprintf(stderr, "ERR: base64 decode of -v failed\n");
                        free(custom_cmd_buf);
                        nex_free(nexio);
                        return -1;
                    }
                    /* Auto-resize buffer if user did not specify -l */
                    if (!custom_cmd_buf_len_set && decoded_len > custom_cmd_buf_len) {
                        void *resized = realloc(custom_cmd_buf, decoded_len);
                        if (!resized) {
                            free(decoded);
                            free(custom_cmd_buf);
                            nex_free(nexio);
                            return -1;
                        }
                        custom_cmd_buf = resized;
                        custom_cmd_buf_len = (unsigned int) decoded_len;
                    } else if (decoded_len > custom_cmd_buf_len) {
                        fprintf(stderr,
                                "ERR: base64 payload decodes to %zu bytes but -l is %u; "
                                "refusing to truncate. Re-run with -l %zu.\n",
                                decoded_len, custom_cmd_buf_len, decoded_len);
                        free(decoded);
                        free(custom_cmd_buf);
                        nex_free(nexio);
                        return -1;
                    }
                    memcpy(custom_cmd_buf, decoded, decoded_len);
                    free(decoded);
                } else {
                    strncpy(custom_cmd_buf, custom_cmd_value, custom_cmd_buf_len);
                    if (custom_cmd_buf_len > 0)
                        ((char *) custom_cmd_buf)[custom_cmd_buf_len - 1] = '\0';
                }
            } else {
                /* no -v supplied: there is no integer to write. Requesting an
                 * integer set here would strtoul(NULL) and crash. */
                if (custom_cmd_value_int) {
                    fprintf(stderr, "ERR: -i given without a -v value\n");
                    free(custom_cmd_buf);
                    nex_free(nexio);
                    return -1;
                }
            }
        }

        /* NOTICE: Using SDIO to communicate to the firmware, the maximum CDC message length 
         * is limited to CDC_MAX_MSG_SIZE = ETHER_MAX_LEN = 1518, however only 1502 bytes 
         * arrive in the ioctl function, the rest might be used for the ioctl header.
         */
        if (custom_cmd_buf_len > 1502 && custom_cmd_set)
            fprintf(stderr, "WARN: Using SDIO, the ioctl payload length is limited to 1502 bytes.\n");
        ret = nex_ioctl(nexio, custom_cmd, custom_cmd_buf, custom_cmd_buf_len, custom_cmd_set);
        if (ret < 0) {
            fprintf(stderr, "ERR: custom command ioctl (%d) failed (err=%d)\n", custom_cmd, ret);
            failed = 1;
        } else if (custom_cmd_set == false) {
            if (raw_output) {
                fwrite(custom_cmd_buf, sizeof(char), custom_cmd_buf_len, stdout);
                fflush(stdout);
            } else if (base64_output) {
                char *encoded = b64_encode(custom_cmd_buf, custom_cmd_buf_len);
                if (encoded) {
                    fwrite(encoded, sizeof(char), strlen(encoded), stdout);
                    fputc('\n', stdout);
                    fflush(stdout);
                    free(encoded);
                } else {
                    fprintf(stderr, "ERR: base64 encoding failed\n");
                }
            } else {
                hexdump(custom_cmd_buf, custom_cmd_buf_len);
            }
        }

        free(custom_cmd_buf);
        custom_cmd_buf = NULL;
    }

    if (dump_objmem) {
        custom_cmd_buf = malloc(custom_cmd_buf_len);
        if (!custom_cmd_buf) {
            nex_free(nexio);
            return -1;
        }

        memset(custom_cmd_buf, 0, custom_cmd_buf_len);

        unsigned int *custom_cmd_buf_pos = (unsigned int *) custom_cmd_buf;

        int i = 0;
        for (i = 0; i < (int)(custom_cmd_buf_len / 0x2000); i++) {
            *custom_cmd_buf_pos = dump_objmem_addr + i * 0x2000 / 4;
            if (!raw_output) {
                printf("%p %08x\n", (void *) custom_cmd_buf_pos, *custom_cmd_buf_pos);
            }
            ret = nex_ioctl(nexio, 406, custom_cmd_buf_pos, 0x2000, false);
            if (ret < 0) {
                fprintf(stderr, "ERR: dump_objmem ioctl failed\n");
                failed++;
                break;
            }
            custom_cmd_buf_pos += 0x2000 / 4;
        }
        /* Only seed the address word into the tail if the remainder is at least
         * a full word; a 1-3 byte remainder has no room for the 4-byte write and
         * would overrun the allocation. */
        if (failed == 0 && custom_cmd_buf_len % 0x2000 >= sizeof(unsigned int)) {
            *(unsigned int *) custom_cmd_buf_pos = dump_objmem_addr + i * 0x2000 / 4;
            ret = nex_ioctl(nexio, 406, custom_cmd_buf_pos, custom_cmd_buf_len % 0x2000, false);
            if (ret < 0) {
                fprintf(stderr, "ERR: dump_objmem ioctl failed\n");
                failed++;
            }
        }

        if (failed == 0) {
            if (raw_output) {
                fwrite(custom_cmd_buf, sizeof(char), custom_cmd_buf_len, stdout);
                fflush(stdout);
            } else {
                hexdump(custom_cmd_buf, custom_cmd_buf_len);
            }
        }

        free(custom_cmd_buf);
        custom_cmd_buf = NULL;
    }

    if (read_shm) {
        unsigned int val = 0;
        ret = nex_read_d11_shm(nexio, read_shm_offset, &val);
        if (ret < 0) {
            fprintf(stderr, "ERR: read D11 SHM at 0x%04x failed (err=%d)\n", read_shm_offset, ret);
            failed = 1;
        } else {
            if (raw_output) {
                uint16_t val16 = (uint16_t) val;
                fwrite(&val16, sizeof(val16), 1, stdout);
                fflush(stdout);
            } else {
                printf("D11 SHM [0x%04x]: 0x%04x (%u)\n", read_shm_offset, val, val);
            }
        }
    }

    if (write_shm) {
        ret = nex_write_d11_shm(nexio, write_shm_offset, write_shm_val);
        if (ret < 0) {
            fprintf(stderr, "ERR: write D11 SHM at 0x%04x <= 0x%04x failed (err=%d)\n",
                    write_shm_offset, write_shm_val, ret);
            failed = 1;
        } else {
            printf("D11 SHM [0x%04x] <= 0x%04x: SUCCESS\n", write_shm_offset, write_shm_val);
        }
    }

    if (read_templ) {
        unsigned int val = 0;
        ret = nex_read_d11_templ(nexio, read_templ_offset, &val);
        if (ret < 0) {
            fprintf(stderr, "ERR: read D11 template RAM at 0x%04x failed (err=%d)\n", read_templ_offset, ret);
            failed = 1;
        } else {
            if (raw_output) {
                uint32_t val32 = (uint32_t) val;
                fwrite(&val32, sizeof(val32), 1, stdout);
                fflush(stdout);
            } else {
                printf("D11 TEMPL [0x%04x]: 0x%08x (%u)\n", read_templ_offset, val, val);
            }
        }
    }

    if (write_templ) {
        ret = nex_write_d11_templ(nexio, write_templ_offset, write_templ_val);
        if (ret < 0) {
            fprintf(stderr, "ERR: write D11 template RAM at 0x%04x <= 0x%08x failed (err=%d)\n",
                    write_templ_offset, write_templ_val, ret);
            failed = 1;
        } else {
            printf("D11 TEMPL [0x%04x] <= 0x%08x: SUCCESS\n", write_templ_offset, write_templ_val);
        }
    }

    if (dump_templ) {
        unsigned char tbuf[256];
        unsigned int dump_len = custom_cmd_buf_len_set ? custom_cmd_buf_len : 128;
        if (dump_len > sizeof(tbuf))
            dump_len = sizeof(tbuf);
        memset(tbuf, 0, sizeof(tbuf));
        ret = nex_read_d11_template_ram(nexio, dump_templ_offset, tbuf, dump_len);
        if (ret < 0) {
            fprintf(stderr, "ERR: dump D11 template RAM at 0x%04x len %u failed (err=%d)\n",
                    dump_templ_offset, dump_len, ret);
            failed = 1;
        } else {
            if (raw_output) {
                fwrite(tbuf, 1, dump_len, stdout);
                fflush(stdout);
            } else {
                printf("D11 TEMPLATE RAM DUMP [offset 0x%04x, len %u]:\n", dump_templ_offset, dump_len);
                hexdump(tbuf, dump_len);
            }
        }
    }

    if (disassociate) {
        buf = 1;
        ret = nex_ioctl(nexio, WLC_DISASSOC, &buf, 4, true);
        if (ret < 0) {
            fprintf(stderr, "ERR: disassociate failed (err=%d)\n", ret);
            failed = 1;
        }
    }

    if (dump_wl_cnt) {
        unsigned char cnt_buf[2048] __attribute__((aligned(4)));

        ret = nexutil_read_wl_counters(nex_ioctl, nexio, cnt_buf, sizeof(cnt_buf));
        if (ret < 0) {
            fprintf(stderr, "ERR: failed to get wl counters (err=%d)\n", ret);
            failed = 1;
        } else if (nexutil_print_wl_counters(cnt_buf, sizeof(cnt_buf), stdout, stderr) < 0) {
            failed = 1;
        }
    }

    if (revinfo) {
        typedef struct wlc_rev_info {
            uint        vendorid;   /* PCI vendor id */
            uint        deviceid;   /* device id of chip */
            uint        radiorev;   /* radio revision */
            uint        chiprev;    /* chip revision */
            uint        corerev;    /* core revision */
            uint        boardid;    /* board identifier (usu. PCI sub-device id) */
            uint        boardvendor;    /* board vendor (usu. PCI sub-vendor id) */
            uint        boardrev;   /* board revision */
            uint        driverrev;  /* driver version */
            uint        ucoderev;   /* microcode version */
            uint        bus;        /* bus type */
            uint        chipnum;    /* chip number */
            uint        phytype;    /* phy type */
            uint        phyrev;     /* phy revision */
            uint        anarev;     /* anacore rev */
            uint        chippkg;    /* chip package info */
            uint        nvramrev;   /* nvram revision number */
        } wlc_rev_info_t;

        char b[8];
        char str[17][32] = { 0 };
        wlc_rev_info_t revinfo;
        
        memset(&revinfo, 0, sizeof(revinfo));

        ret = nex_ioctl(nexio, WLC_GET_REVINFO, &revinfo, sizeof(revinfo), false);
        if (ret < 0) {
            fprintf(stderr, "ERR: failed to get revinfo (err=%d)\n", ret);
            failed = 1;
        }

#ifdef ANDROID
        char model_string[PROP_VALUE_MAX + 1];
        __system_property_get("ro.product.model", model_string);
#else
        char model_string[128] = "unknown";
        FILE *f_model = fopen("/sys/firmware/devicetree/base/model", "r");
        if (!f_model)
            f_model = fopen("/proc/device-tree/model", "r");
        if (f_model) {
            if (fgets(model_string, sizeof(model_string), f_model)) {
                model_string[strcspn(model_string, "\r\n")] = '\0';
            }
            fclose(f_model);
        }
#endif
        char fw_ver[256] = "ver\0";
        nex_ioctl(nexio, WLC_GET_VAR, fw_ver, sizeof(fw_ver), false);
        fw_ver[sizeof(fw_ver) - 1] = 0;
        char *fw_ver2 = strstr(fw_ver, "version");
        /* fw_ver is filled from the firmware's WLC_GET_VAR reply, so treat it
         * as untrusted: "version" can match right at the end of the buffer,
         * and fw_ver2 + 8 would then point past the array. The strlen() and
         * the trailing-NUL strip below would read and write out of bounds.
         * Only skip when the result stays inside fw_ver; otherwise fall back
         * to the whole buffer as we do when the marker is absent. */
        if (fw_ver2 != NULL &&
            (size_t)(fw_ver2 - fw_ver) + 8 < sizeof(fw_ver)) {
            fw_ver2 += 8;
            size_t vlen = strlen(fw_ver2);
            if (vlen > 0 && (fw_ver2[vlen - 1] == '\n' || fw_ver2[vlen - 1] == '\r'))
                fw_ver2[vlen - 1] = 0;
        } else {
            fw_ver2 = fw_ver;
        }

        snprintf(str[0], sizeof(str[0]), "0x%x", le32toh(revinfo.vendorid));
        snprintf(str[1], sizeof(str[0]), "0x%x", le32toh(revinfo.deviceid));
        snprintf(str[2], sizeof(str[0]), "0x%x", le32toh(revinfo.radiorev));
        snprintf(str[3], sizeof(str[0]), "0x%x", le32toh(revinfo.chipnum));
        snprintf(str[4], sizeof(str[0]), "0x%x", le32toh(revinfo.chiprev));
        snprintf(str[5], sizeof(str[0]), "0x%x", le32toh(revinfo.chippkg));
        snprintf(str[6], sizeof(str[0]), "0x%x", le32toh(revinfo.corerev));
        snprintf(str[7], sizeof(str[0]), "0x%x", le32toh(revinfo.boardid));
        snprintf(str[8], sizeof(str[0]), "0x%x", le32toh(revinfo.boardvendor));
        snprintf(str[9], sizeof(str[0]), "%s", bcm_brev_str(le32toh(revinfo.boardrev), b));
        snprintf(str[10], sizeof(str[0]), "0x%x", le32toh(revinfo.driverrev));
        snprintf(str[11], sizeof(str[0]), "0x%x", le32toh(revinfo.ucoderev));
        snprintf(str[12], sizeof(str[0]), "0x%x", le32toh(revinfo.bus));
        snprintf(str[13], sizeof(str[0]), "0x%x", le32toh(revinfo.phytype));
        snprintf(str[14], sizeof(str[0]), "0x%x", le32toh(revinfo.phyrev));
        snprintf(str[15], sizeof(str[0]), "0x%x", le32toh(revinfo.anarev));
        snprintf(str[16], sizeof(str[0]), "0x%x", le32toh(revinfo.nvramrev));

#ifdef ANDROID
        printf("platform %s\n", model_string);
#endif
        printf("firmware %s\n", fw_ver2);
        printf("vendorid %s\n", str[0]);
        printf("deviceid %s\n", str[1]);
        printf("radiorev %s\n", str[2]);
        printf("chipnum %s\n", str[3]);
        printf("chiprev %s\n", str[4]);
        printf("chippackage %s\n", str[5]);
        printf("corerev %s\n", str[6]);
        printf("boardid %s\n", str[7]);
        printf("boardvendor %s\n", str[8]);
        printf("boardrev %s\n", str[9]);
        printf("driverrev %s\n", str[10]);
        printf("ucoderev %s\n", str[11]);
        printf("bus %s\n", str[12]);
        printf("phytype %s\n", str[13]);
        printf("phyrev %s\n", str[14]);
        printf("anarev %s\n", str[15]);
        printf("nvramrev %s\n", str[16]);

        printf("\n");
        printf("platform             | firmware                         | vendorid | deviceid | radiorev   | chipnum | chiprev | chippackage | corerev | boardid | boardvendor | boardrev | driverrev | ucoderev  | bus | phytype | phyrev | anarev | nvramrev\n");
        printf("-------------------- | -------------------------------- | -------- | -------- | ---------- | ------- | ------- | ----------- | ------- | ------- | ----------- | -------- | --------- | --------- | --- | ------- | ------ | ------ | --------\n");
        printf("%-20s | %-32s | %8s | %8s | %10s | %7s | %7s | %11s | %7s | %7s | %11s | %8s | %9s | %9s | %3s | %7s | %6s | %6s | %8s\n", 
            model_string, fw_ver2, str[0], str[1], str[2], str[3], str[4], str[5], str[6], str[7], str[8], str[9], str[10], str[11], str[12], str[13], str[14], str[15], str[16]);
    }

    alarm(0);
    nex_free(nexio);
    return failed ? EXIT_FAILURE : 0;
}
