# nexmon brcmfmac driver — kernel 7.3 port

Base: `brcmfmac_7.2.y-nexmon`. Stays monolithic (no upstream fwvid vendor
split): one `brcmfmac.ko` carries all vendor logic, and the stock
`brcmfmac-{cyw,bca,wcc}.ko` are neither needed nor requested.

## Changes made to port 7.2 -> 7.3

### Kernel 7.3: cfg80211 cookie output to input conversion
Kernel 7.3 converted the `u64 *cookie` output parameter to a plain `u64 cookie`
input parameter in `remain_on_channel` and `mgmt_tx` ops across `cfg80211_ops`,
as cfg80211 now pre-assigns the cookie value before invoking drivers.

- `cfg80211.c`: `brcmf_cfg80211_mgmt_tx()` accepts `u64 cookie` (version-guarded
  with `#if LINUX_VERSION_CODE >= KERNEL_VERSION(7,3,0)`).
- `p2p.c` / `p2p.h`: `brcmf_p2p_remain_on_channel()` accepts `u64 cookie`
  instead of `u64 *cookie` on `>= 7.3.0` and stores it into
  `p2p->remain_on_channel_cookie`.

### Kernel 7.3 upstream driver fixes & updates
- `sdio.c`: Declared CLM blob for 43456 (`BRCMF_FW_CLM_DEF(43456, "brcmfmac43456-sdio")`)
  matching upstream modinfo metadata.
- `sdio.c`: Fixed potential buffer leak in `brcmf_sdio_read_control()` on error paths
  by calling `vfree(buf)`.
- `p2p.c`: Handled action frame abort gracefully when device vif is not yet
  allocated (`vif = p2p->bss_idx[P2PAPI_BSSCFG_PRIMARY].vif` fallback), and guarded
  against NULL dereference of `saved_ie` in `brcmf_p2p_send_action_frame()`.
- `msgbuf.c`: Validated `flow_ring_id` boundaries via `brcmf_msgbuf_get_flowid()`
  to prevent array underflow/overflow, and properly stored DMA direction in
  `brcmf_msgbuf_init_pktids()`.
- `common.c`: Updated `MODULE_VERSION` to `"7.3.0-nexmon"`.

## Build (aarch64)

    ARCH=arm64 make -C /lib/modules/$(uname -r)/build \
        M=/root/nexmon/patches/driver/brcmfmac_7.3.y-nexmon modules

Or via nexmon, which selects this directory automatically from `uname -r`:
`make -C patches/bcm43455c0/7_45_234_4ca95bb_CY/nexmon brcmfmac.ko`

## vermagic note
Matches the running `7.3.0-rc2-v8-16k+` kernel tree.
