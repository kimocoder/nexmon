# Nexmon comparison: `seemoo-lab/master` → `kimocoder/master`

This report covers the live [GitHub comparison](https://github.com/seemoo-lab/nexmon/compare/master...kimocoder:nexmon:master), resolved through both remote branches and examined using the underlying Git diff and individual patches.

This is a **large downstream fork**, not a small feature patch: it adds driver support through Linux 7.4, new firmware monitor/injection support, CSI and D11 hardware interfaces, extensive security fixes, new Python tooling, Android modernization, and major vendored dependency updates.

## 1. Exact comparison scope

- **Base:** [`68720406f54ff16cad28fd3c51f2392aefad9fb7`](https://github.com/seemoo-lab/nexmon/commit/68720406f54ff16cad28fd3c51f2392aefad9fb7)  
  `README: updating list of supported devices … Pixel 9 …`  
  Committed 2026-09-24.
- **Head:** [`302401ceaf0425853c4a53e18198235612c7d93d`](https://github.com/kimocoder/nexmon/commit/302401ceaf0425853c4a53e18198235612c7d93d)  
  `Merge pull request #4 from kimocoder/monitor-injection-k7.2`  
  Committed 2026-11-04.
- **Merge base:** exactly the upstream base commit.
- **Relationship:** **141 commits ahead, 0 behind**. No upstream-only commits need merging into the fork.
- **Rename-aware diff:** **38,312 files**, approximately **15.86 million insertions** and **4.92 million deletions**.
- With rename detection disabled, the raw diff expands to **39,050 files**, **16,089,953 insertions**, and **5,149,367 deletions**.

The huge numbers are primarily caused by replacing complete vendored projects such as Wireshark, gettext, GLib, libxml2, BoringSSL, ISL, and MPFR. They do **not** represent 38,000 hand-modified Nexmon files.

# 2. Linux `brcmfmac` driver changes

## Driver matrix

The comparison modifies **375 files under `patches/driver`**.

Existing driver trees updated:

- `4.4`
- `4.9`
- `4.14`
- `4.19`
- `5.4`
- `5.10`
- `5.15`
- `6.1`
- `6.2`
- `6.6`

Four complete new driver trees are added, each containing 65 files:

- `brcmfmac_6.18.y-nexmon`
- `brcmfmac_7.2.y-nexmon`
- `brcmfmac_7.3.y-nexmon`
- `brcmfmac_7.4.y-nexmon`

The final tree therefore contains **14 Nexmon driver versions**.

All new ports remain **monolithic**: one `brcmfmac.ko` contains the vendor logic rather than adopting upstream’s split into `brcmfmac-{cyw,bca,wcc}.ko`.

## Kernel 6.18 port

Based on the `jayofelony/nexmon` 6.12-derived tree.

Technical API migrations include:

- `del_timer_sync()` → `timer_delete_sync()`.
- `from_timer()` → `timer_container_of()`.
- Multi-radio/MLO cfg80211 signature changes:
  - `set_wiphy_params` gains `radio_idx`.
  - `set_tx_power` gains `radio_idx`.
  - `get_tx_power` gains `radio_idx` and `link_id`.
  - `set_monitor_channel` gains a `net_device` argument.
- Cypress SDIO identifier renamed to `SDIO_DEVICE_ID_BROADCOM_43752`.

See `patches/driver/brcmfmac_6.18.y-nexmon/PORTING_NOTES.md`.

## Kernel 7.2 port

Based on the 6.18 port.

Changes include:

- Kernel 7.1 cfg80211 operations move from `struct net_device *` to `struct wireless_dev *` for:
  - station retrieval/dump;
  - key add/delete/get;
  - default management key;
  - station add/change/delete.
- Compatibility macros preserve one function body across API versions:
  - `BRCMF_OP_NDEV_ARG`
  - `BRCMF_OP_NDEV`
  - `BRCMF_OP_NDEV_PASS`
- `remain_on_channel` gains the 7.2 `rx_addr` argument; it is accepted but ignored because this driver does not implement per-link receive addresses.
- Removed-kernel-`strncpy()` call sites become `strscpy()`.
- Driver Makefile uses `$(src)` instead of a hard-coded `NEXMON_ROOT`.

See `patches/driver/brcmfmac_7.2.y-nexmon/PORTING_NOTES.md`.

## Kernel 7.3 port

- cfg80211 preassigns management cookies:
  - `u64 *cookie` output parameters become plain `u64 cookie` inputs for `mgmt_tx` and `remain_on_channel`.
- Adds SDPCM control-path deadlock prevention:
  - reserves two `TXCTL_CREDITS`;
  - excludes those credits from TX-glom batch calculations;
  - polls interrupt/pending-frame status when a control frame lacks credits;
  - retriggers the DPC while control frames are pending;
  - prevents bus sleep while control traffic is outstanding.
- Adds monitor-mode recovery after SDIO resets:
  - saves monitor interface name and active chanspec;
  - recreates the monitor interface from a workqueue after bus restart;
  - restores the previous channel;
  - handles NetworkManager/udev re-upping `wlan0` during recovery.

See `patches/driver/brcmfmac_7.3.y-nexmon/PORTING_NOTES.md`.

## Kernel 7.4 port

- `add_key`, `del_key`, and `get_key` migrate from a Boolean `pairwise` argument to `enum nl80211_key_type`.
- Includes the newer P2P-detach and bounded-NVRAM fixes described below.
- Module version becomes `7.4.0-nexmon`.

One documentation inconsistency remains: the README’s supported-kernel list mentions 7.3 but not the newly added 7.4 tree.

# 3. New driver capabilities

These advanced features are principally implemented in the **7.3 and 7.4 trees**, not retroactively in every older driver.

## Fast channel hopping

New commands in `nexmon_ioctls.h`:

```c
#define NEX_GET_CHANSPEC_OVERRIDE 418
#define NEX_SET_CHANSPEC_OVERRIDE 419
```

The SET path:

- Accepts a 16-bit chanspec, with a 32-bit compatibility form.
- Calls `brcmf_fil_iovar_int_set(..., "chanspec", cs)` directly.
- Updates Nexmon’s saved monitor chanspec.
- Bypasses the normal cfg80211 association/regulatory-scan path.
- Returns a four-byte `"ACK\0"` Netlink response.
- Reports regulatory rejection separately when firmware returns `-EBADE`.

The GET path returns the saved override or queries the firmware’s current `chanspec`.

The corresponding firmware ioctl hook exists for **BCM43455c0 7.45.265**, translating the commands into `WLC_GET_VAR`/`WLC_SET_VAR` on `"chanspec"`.

The code describes this as “sub-2ms”; the comparison includes hardware-check scripts, but the source diff alone does not establish that timing on every device.

## 64-bit radiotap TSF timestamps

The driver now:

- Reads the 32-bit hardware TSF/mactime value.
- Tracks transitions from the upper half of the 32-bit range to the lower half.
- Increments a software high word on rollover.
- Emits a 64-bit little-endian `IEEE80211_RADIOTAP_TSFT`.
- Falls back to `ktime_get_boottime_ns()/1000` when no initialized hardware timestamp is available.
- Expands an existing firmware radiotap TSF low word in `brcmf_rx_hdrpull()` when safe to modify the skb.

Firmware monitor mode performs equivalent mactime rollover tracking.

## Generic Netlink CSI streaming

A new Generic Netlink family is registered:

- Family: `nexmon_csi`
- Version: `1`
- Multicast group: `csi`
- Command: `NEXMON_CSI_CMD_SAMPLE`
- Attributes:
  - raw CSI bytes;
  - 64-bit timestamp in microseconds;
  - interface index.

The RX path recognizes:

- IPv4/UDP;
- destination port `5500`;
- Nexmon magic `0x11111111`;
- an 18-byte-minimum CSI payload.

When listeners exist, the driver consumes the original packet and multicasts it through Generic Netlink, legacy Netlink, or both. Otherwise, normal UDP receive processing continues.

Despite the commit’s “zero-copy” name, the implementation allocates Netlink skbs and copies the CSI payload into them. The practical optimization is bypassing normal UDP broadcast delivery and reducing network-stack/socket flooding—not literal end-to-end zero-copy.

## Direct D11 SHM, register, and Template RAM access

New ioctl commands:

```text
426  NEX_WRITE_TEMPLATE_RAM
429  NEX_READ_TEMPLATE_RAM
430  NEX_READ_D11_SHM
431  NEX_WRITE_D11_SHM
```

SHM request structure:

```c
struct nex_d11_shm_req {
    uint32_t offset;
    uint32_t val;
    uint16_t width;   /* 2 or 4 bytes */
    uint16_t is_reg;
};
```

Supported address modes:

- D11 SHM around `0xE8004000`;
- D11 registers around `0x18001000`;
- raw backplane addresses;
- Template RAM through the template request structure.

The SDIO implementation:

- Wakes the bus and triggers the DPC.
- Claims the SDIO host.
- Performs aligned 32-bit backend reads.
- Extracts 16-bit halves where requested.
- Returns values through Netlink.

Template RAM adds:

- A request with a **1,024-byte data buffer**.
- Register-indirect access through D11 registers `0x130/0x134`.
- Optional direct-backplane access at `0x18001800`.
- Standard offsets for ACK, null, QoS-null, RTS, beacon, and probe-response templates.

`nexutil` gains corresponding read/write/dump options, and the Python SDK exposes the same operations.

# 4. Driver security and reliability fixes

## Netlink ioctl hardening

The custom Nexmon Netlink path now:

- Requires `CAP_NET_ADMIN` for DCMD execution.
- Validates `nlmsg` and `nexudp_ioctl_header` lengths.
- Rejects undersized and oversized payloads.
- Handles non-linear skbs using linearization or an allocated copy.
- Corrects promiscuous-command routing to `WLC_GET_PROMISC=9` and `WLC_SET_PROMISC=10`.
- Routes channel commands to the primary interface where appropriate.
- Holds RTNL and device references while resolving interfaces.
- Frees copied frames and drops device references on all exits.

## BCDC response validation

BCDC receive handling now checks:

- Minimum response/header sizes.
- Available payload against the requested output buffer.
- Returned command ID against the issued command.
- Returned interface index against the expected interface.
- Malformed responses return protocol errors instead of copying unchecked data.

## cfg80211 and P2P

- Validates `chandef` and `chandef->chan` in `get_channel`.
- Backports P2P-device removal synchronization:
  - takes RTNL and wiphy locks;
  - rechecks the interface list;
  - avoids double-unregistration and `LIST_POISON2` crashes during teardown.
- Handles action-frame abort before a P2P device VIF exists.
- Avoids dereferencing absent `saved_ie`.
- Uses monotonically increasing atomic nonzero management packet IDs, avoiding firmware TX-completion collisions.

## Msgbuf/DMA

- Validates flowring IDs before indexing arrays.
- Rejects invalid IDs during TX status and flowring creation/deletion.
- Finalizes invalid TX skbs rather than leaking them.
- Stores the correct DMA direction instead of leaving packet IDs bidirectional:
  - `DMA_TO_DEVICE`
  - `DMA_FROM_DEVICE`

## NVRAM and firmware capabilities

- Replaces unbounded NVRAM comment scanning with `strnchr()`/`memchr()` bounded by remaining input.
- Matches capability names only at complete token boundaries, preventing `sae` from matching `sae_ext`.
- Adds external-SAE support:
  - `BRCMF_FEAT_SAE_EXT`;
  - both `sae_ext` and Cypress `extsae`;
  - `NL80211_FEATURE_SAE`;
  - PSK-offload fallback for userspace-hosted SAE.
- Prefers the OTP country code over an NVRAM default where supported.

## SDIO/PCIe/power behavior

- Frees the temporary SDIO control-read buffer on error paths.
- Continues PCIe D3 power-off when no WoWL ACK arrives; preserves the fatal timeout behavior when WoWL is enabled.
- Inserts `smp_mb__after_atomic()` between the 802.1X pending-count decrement and waitqueue check, preventing lost EAPOL completion wakeups.
- Sets `pm2_sleep_ret` to **2,000 ms** in older driver trees.
- Logs firmware event, status, and 802.11 reason code on connection failure.
- Declares the BCM43456 CLM blob correctly so initramfs tooling includes regulatory data.

# 5. Firmware patch changes

## New BCM43455c0 7.45.265 support

A complete patch target is added under:

`patches/bcm43455c0/7_45_265-28bca26-CY/nexmon`

It includes monitor mode, injection, ioctls, radiotap output, version handling, linker layout, build validation, and patch code.

The firmware source is Cypress `cyfmac43455-sdio-standard.bin`:

- Version `7.45.265 (28bca26 CY)`
- CRC `68bafb8c`
- Firmware date 2023-08-29.

The port derives addresses from the closely related `7.45.234_4ca95bb_CY` lineage rather than simply using numerically adjacent firmware.

### Monitor receive path

- Hooks the `wl_monitor` call site at `0x1A7604`.
- Removes the six-byte PLCP header.
- Constructs radiotap containing:
  - 64-bit TSF;
  - flags;
  - data rate;
  - channel frequency and band/encoding;
  - signal and noise.
- Makes monitor output modes mutually exclusive, avoiding multiple submissions/pulls of one skb.
- Honors `MONITOR_DROP_FRM` before delivery.
- Checks available headroom before modifying packets.
- Duplicates A-MSDU packets with additional radiotap headroom.
- Retains a stability-related A-MSDU branch patch.

### Injection path

- Parses radiotap `it_len` as an unsigned 16-bit little-endian value rather than a signed byte.
- Rejects malformed headers and runt frames before `skb_pull()`.
- Extracts the radiotap rate and chooses valid defaults:
  - 6 Mbps on 5 GHz;
  - 2 Mbps on 2.4 GHz.
- Allocates **202 bytes of TX headroom** for D11AC transmit metadata.
- Uses the hardware reference SCB and discards packets if none exists.
- Uses `wlc_sendctl()` rather than the older D11N-style direct FIFO path.
- Adds a naked-assembly guard in `wlc_send_q` to free packets with null SCBs rather than data-aborting.
- Includes diagnostic ioctls/counters for injection, DMA, MAC, and SCB state.

### SDIO batch ownership fix

A significant later fix processes the entire SDIO `PKTLINK` list rather than only its head:

- Uses the packet-ID map at `0x1986C0`.
- Saves each next pointer.
- Clears the link field.
- Injects or normally transmits every packet.

Previously, remaining pooled packets could be lost, eventually closing the SDPCM receive window.

### Radio-state handling

Monitor injection setup now:

- Suppresses scanning.
- Disables MPC and PM.
- Restores transmit power.
- Clears the relevant hardware suspend/mute state.
- Avoids an unmatched `wlc_enable_mac()` during setup, preserving MAC suspend bookkeeping.

## Other firmware targets

- **7.45.206:** monitor/injection path repaired with corrected TX-header handling, function addresses, packet guards, and injection behavior.
- **BCM43430a1 7.45.98:** adds recovered addresses for DMA, memory, monitor, transmit, and related wrappers. Notably, the correct `memcpy` address avoids the previous no-op stub.
- **BCM43436b0:** enables flash-patch slot 25.
- Wrapper correction changes a mislabeled BCM4358 ROM address to BCM4356.
- Numerous sibling targets receive the same radiotap-length, allocation-failure, runt-frame, packet-ownership, and monitor-UAF fixes.

## Shared firmware hardening

- `argprintf()` gains:
  - null/invalid-buffer checks;
  - recursion suppression;
  - clamped `vsnprintf()` accounting;
  - no pointer advancement beyond the output buffer.
- Radiotap iterator:
  - supports newer HE/EHT field definitions;
  - handles extended bitmaps without unaligned word accesses;
  - validates vendor-namespace lengths;
  - prevents integer-wrap/bounds bypasses.
- UDP tunnel and helper code gain allocation, length, initialization, and concurrency fixes.

# 6. Userspace utility changes

## `libnexio`

A public `libnexio.h` is introduced; `struct nexio` becomes opaque instead of being independently redeclared by consumers.

Other changes:

- Centralized `nex_free()` for sockets, ifreq, Netlink socket, and callbacks.
- Constructor failure cleanup.
- UDP/Netlink reply-length validation before copying.
- Negative-length and allocation-failure rejection.
- Netlink TX/RX share one connected socket, allowing replies to the authenticated sender port ID.
- Optional interface-to-ifindex mapping through `nex_init_netlink_ifname()`.
- Netlink callback ownership corrected.
- Error callbacks and receive-error handling prevent hangs.
- Close-on-exec and safer buffer allocation are added.

## `libnexmon` and `libfakeioctl`

- Use the shared libnexio interface.
- Resolve libc symbols lazily as well as in the constructor.
- Reject negative/out-of-range file descriptors before indexing arrays.
- Validate AF_PACKET address type and length.
- Clear descriptor state on `close()` to prevent stale injection routing after FD reuse.
- Correct LP64 ioctl request types and socket-flag handling.
- Add allocation and monitor-bitmask checks.

## `nexutil`

Notable changes:

- Custom buffer lengths restricted to `0..1 MiB`.
- Integer writes require at least four bytes.
- Missing `-v` with integer mode is rejected.
- Oversized base64 payloads are rejected instead of silently truncated.
- objmem tail writes require a complete word.
- Firmware version parsing is bounded.
- 6 GHz 80 MHz channel-table length now uses the correct array.
- Chanspec get/set validates responses and errors.
- Monitor/promiscuous/cookie ioctl failures produce nonzero exit status.
- Handles are released on exit.
- New D11 SHM/template options are added.

## `rawproxy` / `rawproxyreverse`

- Radiotap length must fit within captured bytes.
- Correct payload length is used after stripping radiotap.
- Socket creation/bind/send errors are checked properly.
- Negative `recvfrom()` results never reach `pcap_inject()`.
- `MSG_TRUNC` detects oversized datagrams.
- Reverse proxy binds to loopback.
- A packed, fixed **16-byte `pcap_pkthdr32`** wire format replaces architecture-dependent `pcap_pkthdr` serialization.
- Port validation, `SO_REUSEADDR`, parent-death handling, and signal handling are improved.

## Other native tools

- `dhdutil`: structure initialization, null/bounds checks, bounded strings, FD lifecycle, and `/proc` parsing fixes.
- `wireless_tools`: parsing switches to reentrant `strtok_r()`.
- Compiler-warning fixes are applied across b43 tools, socat, aircrack-ng, mdk4, and other utilities.

# 7. New Python and host tooling

## `pynexmon` 0.2.0

Added under `python/pynexmon`, packaged through `pyproject.toml`; Python 3.9+.

`NexmonDevice` uses `ctypes` and `libnexio` to provide:

- raw ioctls;
- monitor and promiscuous mode;
- chanspec conversion/get/set;
- capabilities and revision information;
- disassociation;
- D11 SHM/register/template reads and writes.

CSI support includes:

- 18-byte header parsing;
- complex I/Q samples;
- amplitudes and phases;
- optional NumPy arrays;
- JSON/dictionary output;
- UDP reception;
- Generic Netlink family/group resolution;
- automatic Netlink → UDP fallback.

## `nexfirmware.py`

A new 2,771-line firmware management CLI with:

- `detect`
- `reverse` / `analyze`
- `pull`
- `put`
- `restore`
- `edit`

Capabilities include:

- active chip/driver/firmware detection;
- RAM/ROM map inference;
- ARM/Thumb disassembly through Capstone;
- microcode extraction;
- strings/binwalk integration;
- flash-patch analysis;
- firmware installation and stock restoration;
- backup and driver reload;
- atomic file writes;
- path-traversal and destination-name checks;
- compressed firmware input, including zstandard.

## Other added tools

- `monitor-mode.sh`: locked, idempotent monitor setup/teardown; handles NetworkManager, wpa_supplicant, regulatory state, channel changes, and failure recovery.
- `nexmon_crash_decoder.py`: firmware trap/crash decoding and address-region analysis.
- `nexbench.py`: injection benchmarks for probe, beacon, null, QoS-null, RTS, and CTS frames.
- `benchmark_multiframe.py`: multi-frame benchmark variant.
- `hwcheck_channel_hopping.py` and `hwcheck_nonblock.py`: hardware-oriented channel-hopping and nonblocking checks.
- Thirteen audit/report artifacts are added under `audits/`.

# 8. Android application changes

## Toolchain

- Android Gradle Plugin: **2.3.2 → 7.4.2**.
- Gradle wrapper: **3.3 → 7.6.4**.
- `jcenter()` → `google()` and `mavenCentral()`.
- `compile` dependency syntax → `implementation`.
- Java compatibility: **7 → 8**.
- compileSdk: **23 → 28**.
- minSdk: **23 → 24**.
- Gradle targetSdk: **23 → 28**.
- Native ABI set: `armeabi` → `armeabi-v7a arm64-v8a`.
- STL: `stlport_static` → `c++_static`.
- Floating libsuperuser dependency is pinned.
- Remains on legacy Android Support libraries rather than migrating to AndroidX.

The manifest still says targetSdk 24 while Gradle says 28; the Gradle configuration is the effective build setting.

## Security and JNI fixes

- Adds a signature-level `INTERNAL_BROADCAST` permission.
- Gates attack, monitor, frame, and AP receivers with it.
- Makes `AttackInstanceReceiver` non-exported.
- Shell-quotes paths used in privileged firmware/tool commands.
- Replaces world-writable `chmod 777` extracted binaries with owner-only permissions.
- Rejects unknown or malformed attack payloads.
- Moves native dissection pointers from 32-bit `int` to 64-bit `long`/`jlong`.
- Replaces variable-length stack arrays with checked heap allocation.
- Releases JNI strings on early exits.
- Uses `JavaVM`, global class references, and thread attach/detach correctly in the frame sender.
- Replaces mdk3 integration with mdk4.

# 9. Build system, tests, and CI

## Build orchestration

- Bare top-level `make` now sources `setup_env.sh` and reexecutes Make.
- Adds `utilities`, architecture-specific `utilities-*`, `all-*`, `update`, `check`, `test`, and `clean` targets.
- Recursive invocations use `$(MAKE)` and propagate failures correctly.
- Firmware patch builds gain deterministic build-number controls.
- `setup_env.sh` auto-detects ARM versus ARM64 and kernel7/kernel8.
- Adds native AArch64 GCC 15.3 toolchain support with legacy-GCC fallback.
- Adds ARMHF compatibility-library handling.
- Android NDK auto-detection targets **NDK r30 final or newer**.
- Adds recovery of missing built-in kernel symbols from `.vmlinux.export.c` into `KBUILD_EXTRA_SYMBOLS`.
- GCC plugin fixes cover `SET_DECL_ALIGN`, declaration-specific text sections, alignment, and modern compiler compatibility.
- Extractors gain integer-range, allocation, file-I/O, and bounds checks.
- Flash-patch slot checks and atomic define-cache writes fix parallel-build failures.

## Tests

The comparison adds **22 test files with 211 test methods**, covering:

- firmware Makefiles and recursive builds;
- base64;
- BCDC responses;
- chanspec conversion;
- CSI and Netlink;
- libnexio;
- nexutil CLI;
- firmware management;
- radiotap fuzz cases;
- crash decoding;
- kernel symvers;
- monitor-mode scripts;
- Tier 1–3 security regressions.

Many driver/firmware tests are source-pattern or build-artifact checks; they do not replace testing on physical Broadcom hardware.

## GitHub Actions

Two workflows are added:

- `ci.yml`
  - Ruff and ShellCheck;
  - native utilities and extractor builds;
  - unit tests;
  - BCM43455c0 7.45.265 firmware build and mandatory validation;
  - ASan/UBSan builds;
  - radiotap and hardening tests.
- `check-updates.yml`
  - weekly vendored-dependency check;
  - JSON report artifact.

The test and CI definitions were inspected; hardware tests were not independently run, and the commit messages’ historical “all tests passed” statements are not treated as verification of the current environment.

# 10. Final vendored dependency state

The dominant bulk of the diff comes from these replacements/additions:

```text
aircrack-ng       1.7
BoringSSL         0.20260813.0
c-ares            1.34.9
cowpatty          4.8
gettext           1.0
GLib              2.90.1
iperf             2.2.1
iperf3            3.22
iw                6.17
argp              20260115 snapshot
libffi            3.8.0
libgcrypt         1.12.4
libgpg-error      1.61
libiconv          1.19.1
libnl             3.12.0
libpcap           1.11.0
SQLite            3.54.1
libxml2           2.15.4
mdk4              4.2        (replaces mdk3)
PCRE2             10.49
socat             2.0.0-b9
tcpdump           4.99.7
Wireshark         5.1.0rc0
zlib              1.3.2
ISL               0.28
MPFR              4.2.2
```

Legacy ISL 0.10 and MPFR 3.1.4 sources are retained under `buildtools/legacy/` because the bundled GCC 5.4.1 firmware toolchain still requires those older ABIs.

# Bottom line

The fork’s meaningful Nexmon-specific work is concentrated in roughly:

- **512 files under `patches/`**;
- **30 files under `firmwares/`**;
- **49 Android files**;
- new Python/host tooling;
- **22 test files and two CI workflows**.

Everything else is dominated by wholesale third-party source updates. Technically, the largest advances are the **7.45.265 monitor/injection port**, **Linux 6.18–7.4 support**, **Netlink security hardening**, **CSI streaming**, **fast chanspec override**, **direct D11 access**, and the extensive cross-tree driver/firmware reliability backports.
