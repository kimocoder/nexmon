# Nexutil for Android and Raspberry Pi 3
* For Android: make sure to export `NDK_ROOT` properly
* compile: `make`
* install: `make install`

## WL counters

`nexutil -I <iface> -w` dumps the firmware `wl_cnt_t` block. It first tries the
Nexmon `NEX_GET_WL_CNT` ioctl and, on firmware where that is not implemented,
falls back to Broadcom's stock `counters` iovar (`WLC_GET_VAR`). No firmware
patch is required for the fallback.

The decoder accepts v9 and newer append-only layouts. If the firmware reports a
larger block (for example v10 on BCM43455c0 7.45.265), the known v9 fields are
named and newer tail words are printed as `field_<n>`.