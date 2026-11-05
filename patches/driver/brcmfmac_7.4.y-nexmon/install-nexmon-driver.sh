#!/bin/bash
# Build and install the nexmon-patched brcmfmac driver for the running kernel.
#
# The nexmon firmware patch alone is not enough: nexutil needs the patched
# driver (netlink protocol 31).  After a kernel rebuild, the stock brcmfmac
# is loaded again and nexutil fails with EPROTONOSUPPORT (errno 93).  Run
# this script after every kernel build/install to restore the patched driver.
#
# Usage:
#   install-nexmon-driver.sh              # build + install for $(uname -r)
#   install-nexmon-driver.sh --reload     # also unload/reload brcmfmac
#   install-nexmon-driver.sh --check      # verify the running driver is patched
#
# The stock module is preserved as brcmfmac.ko.xz.stock-backup next to the
# install location (kept across runs).  Rollback:
#   cd /lib/modules/$(uname -r)/kernel/drivers/net/wireless/broadcom/brcm80211/brcmfmac
#   rm -f brcmfmac.ko
#   cp brcmfmac.ko.xz.stock-backup brcmfmac.ko.xz && depmod -a
#   modprobe -r brcmfmac && modprobe brcmfmac

set -euo pipefail

RELOAD=0
CHECK=0
for arg in "$@"; do
    case "$arg" in
        --reload) RELOAD=1 ;;
        --check) CHECK=1 ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

KVER="$(uname -r)"
KBASE="$(echo "$KVER" | sed -E 's/^([0-9]+\.[0-9]+)\..*/\1.y/')"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The script lives in the driver directory itself.
if [ "$(basename "$SRC_DIR")" != "brcmfmac_${KBASE}-nexmon" ]; then
    echo "error: running kernel $KVER needs driver sources brcmfmac_${KBASE}-nexmon," >&2
    echo "       but this script lives in $(basename "$SRC_DIR")." >&2
    echo "       Copy it to the matching patches/driver/brcmfmac_${KBASE}-nexmon/ directory." >&2
    exit 1
fi

MODDIR="/lib/modules/${KVER}/kernel/drivers/net/wireless/broadcom/brcm80211/brcmfmac"
BACKUP="${MODDIR}/brcmfmac.ko.xz.stock-backup"

check_driver() {
    python3 -c '
import socket, sys
try:
    s = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, 31)
    s.close()
except OSError as e:
    sys.exit(f"netlink 31 unavailable: {e} — stock brcmfmac is loaded")
' && echo "OK: nexmon netlink protocol 31 is available (patched driver loaded)"
}

if [ "$CHECK" -eq 1 ]; then
    check_driver
    exit $?
fi

BUILD_DIR="/lib/modules/${KVER}/build"
if [ ! -d "$BUILD_DIR" ]; then
    echo "error: no kernel build tree at $BUILD_DIR" >&2
    echo "       Install the kernel headers/build tree for $KVER first." >&2
    exit 1
fi

echo ">> Building brcmfmac_${KBASE}-nexmon for $KVER"
if ! make -C "$BUILD_DIR" M="$SRC_DIR" modules; then
    echo "error: build failed." >&2
    echo "       If modpost fails on missing built-in exports, recover Module.symvers with" >&2
    echo "       /root/nexmon/audits/2026-09-24/recover_builtin_symvers.py first." >&2
    exit 1
fi

if [ ! -f "${SRC_DIR}/brcmfmac.ko" ]; then
    echo "error: ${SRC_DIR}/brcmfmac.ko was not produced" >&2
    exit 1
fi

if ! modinfo "${SRC_DIR}/brcmfmac.ko" | grep -q "vermagic: *${KVER} "; then
    echo "error: built module vermagic does not match $KVER" >&2
    exit 1
fi

echo ">> Installing to $MODDIR"
if [ -f "${MODDIR}/brcmfmac.ko.xz" ] && [ ! -f "$BACKUP" ]; then
    cp -a "${MODDIR}/brcmfmac.ko.xz" "$BACKUP"
    echo "   stock module backed up to $BACKUP"
fi
# Install uncompressed and remove any compressed variant: modprobe then
# unambiguously loads the patched module.
install -m 0644 "${SRC_DIR}/brcmfmac.ko" "${MODDIR}/brcmfmac.ko"
rm -f "${MODDIR}/brcmfmac.ko.xz"
depmod -a "$KVER"
echo "   installed (patched brcmfmac.ko, stock backup preserved)"

if [ "$RELOAD" -eq 1 ]; then
    echo ">> Reloading brcmfmac (wlan interfaces will briefly disappear)"
    modprobe -r brcmfmac_cyw brcmfmac 2>/dev/null || modprobe -r brcmfmac
    modprobe brcmfmac
    sleep 6
    ip link set wlan0 up 2>/dev/null || true
    check_driver
else
    echo ">> Installed.  Reload with --reload, or reboot, to activate."
    echo "   Verify afterwards with: $0 --check"
fi
