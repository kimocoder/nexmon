#!/usr/bin/env bash
#
# hwcheck_monitor_injection.sh - live monitor-mode and frame-injection check
# for the Nexmon/brcmfmac BCM43455 on a Raspberry Pi (or similar).
#
# What it does
#   1. Prints kernel, platform, brcmfmac module, firmware and interface stats.
#   2. Creates a monitor vif, verifies RX capture and channel switching.
#   3. Recreates the monitor vif (fresh TX state) and injects probe requests
#      with a unique SSID, counting them on an independent receiver.
#   4. Exercises the monitor guard paths (second monitor, type change, scans).
#   5. Restores the interfaces and prints a PASS/FAIL/SKIP summary.
#
# The independent receiver is optional. It is auto-detected as a wireless
# interface on a different wiphy; if none is available (or --no-sniffer is
# given), injection is still exercised but the on-air check is SKIPped and
# only the driver TX counters are reported.
#
# Requires: root, iw, ip, tcpdump, python3 + scapy, ethtool (optional),
#           nexutil (optional, for firmware capability readout).
#
# Examples
#   sudo ./hwcheck_monitor_injection.sh
#   sudo ./hwcheck_monitor_injection.sh --iface wlan0 --channel 1 --count 30
#   sudo ./hwcheck_monitor_injection.sh --sniffer wlan1 --log /tmp/mon.log
#
set -u

IFACE="${IFACE:-wlan0}"
MON="${MON:-${IFACE}mon}"
CHANNEL="${CHANNEL:-1}"
COUNT="${COUNT:-20}"
AIR_MIN="${AIR_MIN:-1}"
SNIFFER="${SNIFFER:-auto}"
NO_SNIFFER=0
LOGDIR="${LOGDIR:-$(cd "$(dirname "$0")" && pwd)/.local-notes}"
LOGFILE=""

PASS=0
FAIL=0
SKIP=0

usage() {
	sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
	exit 0
}

while [ $# -gt 0 ]; do
	case "$1" in
		--iface) IFACE="$2"; MON="${IFACE}mon"; shift 2 ;;
		--mon) MON="$2"; shift 2 ;;
		--channel) CHANNEL="$2"; shift 2 ;;
		--count) COUNT="$2"; shift 2 ;;
		--sniffer) SNIFFER="$2"; shift 2 ;;
		--no-sniffer) NO_SNIFFER=1; SNIFFER=""; shift ;;
		--log) LOGFILE="$2"; shift 2 ;;
		--help|-h) usage ;;
		*) echo "unknown option: $1" >&2; usage ;;
	esac
done

[ "$(id -u)" -eq 0 ] || { echo "must run as root" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TMPDIR="$(mktemp -d /tmp/nexmon-moninj.XXXXXX)"
if [ -z "$LOGFILE" ]; then
	mkdir -p "$LOGDIR"
	LOGFILE="$LOGDIR/monitor-injection-$(date +%Y%m%d-%H%M%S).log"
fi
mkdir -p "$(dirname "$LOGFILE")"
touch "$LOGFILE"
exec > >(tee -a "$LOGFILE") 2>&1

section() { printf '\n\033[1m=== %s ===\033[0m\n' "$*"; }
pass() { PASS=$((PASS + 1)); printf '  [PASS] %s\n' "$*"; }
fail() { FAIL=$((FAIL + 1)); printf '  [FAIL] %s\n' "$*"; }
skip() { SKIP=$((SKIP + 1)); printf '  [SKIP] %s\n' "$*"; }
note() { printf '  [info] %s\n' "$*"; }

MON_CREATED=0
SNIFFER_ORIG_TYPE=""
SNIFFER_ORIG_CHAN=""
BG_PIDS=""

cleanup() {
	trap - EXIT INT TERM
	for p in $BG_PIDS; do kill "$p" 2>/dev/null; done
	wait 2>/dev/null
	if [ "$MON_CREATED" -eq 1 ]; then
		ip link set "$MON" down 2>/dev/null
		iw dev "$MON" del 2>/dev/null
	fi
	iw dev "$IFACE" set type managed 2>/dev/null
	ip link set "$IFACE" up 2>/dev/null
	if [ -n "$SNIFFER" ] && [ -n "$SNIFFER_ORIG_TYPE" ]; then
		ip link set "$SNIFFER" down 2>/dev/null
		iw dev "$SNIFFER" set type "$SNIFFER_ORIG_TYPE" 2>/dev/null
		iw dev "$SNIFFER" set channel "$SNIFFER_ORIG_CHAN" 2>/dev/null
		ip link set "$SNIFFER" up 2>/dev/null
	fi
	rm -rf "$TMPDIR"
}
trap cleanup EXIT INT TERM

find_nexutil() {
	for c in "$SCRIPT_DIR/utilities/nexutil/nexutil" /usr/local/bin/nexutil "$(command -v nexutil 2>/dev/null)"; do
		[ -n "$c" ] && [ -x "$c" ] && { echo "$c"; return 0; }
	done
	return 1
}

pcap_count() {
	python3 - "$1" <<'PY'
import sys
from scapy.all import rdpcap
print(len(rdpcap(sys.argv[1])))
PY
}

pcap_count_ssid() {
	python3 - "$1" "$2" <<'PY'
import sys
from scapy.all import rdpcap, Dot11ProbeReq, Dot11Elt
pcap, ssid = sys.argv[1], sys.argv[2].encode()
n = 0
try:
    pkts = rdpcap(pcap)
except Exception:
    print(0); raise SystemExit
for p in pkts:
    if p.haslayer(Dot11ProbeReq) and p.haslayer(Dot11Elt):
        e = p.getlayer(Dot11Elt)
        if e.ID == 0 and bytes(e.info) == ssid:
            n += 1
print(n)
PY
}

send_probe_rtap() {
	python3 - "$1" "$2" "$3" <<'PY'
import sys
from scapy.all import RadioTap, Dot11, Dot11ProbeReq, Dot11Elt, sendp
iface, ssid, count = sys.argv[1], sys.argv[2], int(sys.argv[3])
pkt = (RadioTap() /
       Dot11(type=0, subtype=4, addr1="ff:ff:ff:ff:ff:ff",
             addr2="02:11:22:33:44:55", addr3="ff:ff:ff:ff:ff:ff") /
       Dot11ProbeReq() / Dot11Elt(ID="SSID", info=ssid))
sendp(pkt, iface=iface, count=count, inter=0.02, verbose=False)
PY
}

mon_channel() {
	iw dev "$MON" info 2>/dev/null | sed -n 's/.*channel \([0-9][0-9]*\).*/\1/p' | head -1
}

recreate_monitor() {
	if [ "$MON_CREATED" -eq 1 ]; then
		ip link set "$MON" down 2>/dev/null
		iw dev "$MON" del 2>/dev/null
		MON_CREATED=0
	fi
	ip link set "$IFACE" up 2>/dev/null
	if iw dev "$IFACE" interface add "$MON" type monitor 2>/dev/null; then
		MON_CREATED=1
		ip link set "$MON" up 2>/dev/null
		ip link set "$IFACE" down 2>/dev/null
		iw dev "$MON" set channel "$CHANNEL" 2>/dev/null
		return 0
	fi
	return 1
}

sniffer_ready() {
	[ -z "$SNIFFER" ] && return 1
	ip link set "$SNIFFER" up 2>/dev/null
	iw dev "$SNIFFER" set channel "$CHANNEL" 2>/dev/null
	if [ "$(iw dev "$SNIFFER" info 2>/dev/null | sed -n 's/.*channel \([0-9][0-9]*\).*/\1/p' | head -1)" != "$CHANNEL" ]; then
		# mac80211 refuses a channel change while the vif is up
		ip link set "$SNIFFER" down 2>/dev/null
		iw dev "$SNIFFER" set channel "$CHANNEL" 2>/dev/null
		ip link set "$SNIFFER" up 2>/dev/null
	fi
	[ "$(iw dev "$SNIFFER" info 2>/dev/null | sed -n 's/.*channel \([0-9][0-9]*\).*/\1/p' | head -1)" = "$CHANNEL" ]
}

# ---------------------------------------------------------------------------
section "KERNEL / PLATFORM"
uname -a
[ -r /proc/device-tree/model ] && note "model: $(tr -d '\0' < /proc/device-tree/model)"
note "kernel: $(uname -r)"

section "BCM DRIVER / FIRMWARE"
if command -v ethtool >/dev/null 2>&1; then
	ethtool -i "$IFACE" 2>&1
fi
note "module version:    $(modinfo -F version brcmfmac 2>/dev/null)"
note "module srcversion: $(cat /sys/module/brcmfmac/srcversion 2>/dev/null)"
note "module vermagic:   $(modinfo -F vermagic brcmfmac 2>/dev/null)"
dmesg | grep -E "Firmware: BCM|brcmf_c_preinit_dcmds" | tail -1

section "WLAN0 / PHY CAPABILITIES"
iw dev "$IFACE" info 2>&1
PHY="$(iw dev "$IFACE" info 2>/dev/null | awk '/wiphy/{print $2; exit}')"
if [ -n "$PHY" ]; then
	note "monitor mode in wiphy: $(iw phy "phy$PHY" info 2>/dev/null | sed -n '/Supported interface modes/,/^$/p' | grep -c monitor)"
fi
NEX="$(find_nexutil || true)"
if [ -n "$NEX" ]; then
	"$NEX" -I "$IFACE" --capabilities 2>&1 || note "nexutil capabilities query failed"
fi

section "INTERFACE STATS (before)"
ip -s link show "$IFACE"
if command -v ethtool >/dev/null 2>&1; then
	ethtool -S "$IFACE" 2>/dev/null | grep -iE "packets|errors|dropped|tx|rx" | head -20
fi

# ---------------------------------------------------------------------------
section "MONITOR: create / RX capture"
if recreate_monitor; then
	pass "monitor vif $MON created and up"
	note "$(ip -d link show "$MON" | sed -n '2p' | cut -c1-140)"
	note "promisc flag: $(ip -d link show "$MON" | grep -o 'promiscuity [0-9]*' || true)"

	RX_PCAP="$TMPDIR/rx.pcap"
	timeout 15 tcpdump -i "$MON" -c 5 -w "$RX_PCAP" -q >/dev/null 2>&1
	RX_N="$(pcap_count "$RX_PCAP" 2>/dev/null || echo 0)"
	if [ "${RX_N:-0}" -ge 1 ]; then
		pass "monitor RX captured $RX_N frames"
		tcpdump -r "$RX_PCAP" -c 1 -e 2>/dev/null | cut -c1-110 | sed 's/^/  /'
	else
		fail "monitor RX captured no frames"
	fi
else
	fail "could not create monitor vif $MON"
fi

section "MONITOR: channel switching"
for ch in 1 6 11 36 44 48; do
	iw dev "$MON" set channel "$ch" >/dev/null 2>&1
	rc=$?
	got="$(mon_channel)"
	if [ "$rc" -eq 0 ] && [ "$got" = "$ch" ]; then
		pass "hop to channel $ch (readback $got)"
	else
		fail "hop to channel $ch (rc=$rc readback=${got:-none})"
	fi
done

# ---------------------------------------------------------------------------
section "INJECTION: unique probe requests ($COUNT frames on channel $CHANNEL)"
# A fresh monitor avoids the post-retune TX wedge.
recreate_monitor >/dev/null 2>&1
iw dev "$MON" set channel "$CHANNEL" >/dev/null 2>&1
SSID="NEXMON-TEST-$(date +%s)-$$"

SNIFF_OK=0
if [ "$NO_SNIFFER" -eq 0 ] && [ -n "$SNIFFER" ]; then
	if [ "$SNIFFER" = "auto" ]; then
		IFACE_PHY="$(iw dev "$IFACE" info 2>/dev/null | awk '/wiphy/{print $2; exit}')"
		for dev in $(iw dev 2>/dev/null | awk '/Interface/{print $2}'); do
			[ "$dev" = "$IFACE" ] && continue
			dphy="$(iw dev "$dev" info 2>/dev/null | awk '/wiphy/{print $2; exit}')"
			[ "$dphy" = "$IFACE_PHY" ] && continue
			SNIFFER="$dev"
			break
		done
	fi
	if [ -n "$SNIFFER" ]; then
		SNIFFER_ORIG_TYPE="$(iw dev "$SNIFFER" info 2>/dev/null | awk '/type/{print $2; exit}')"
		SNIFFER_ORIG_CHAN="$(iw dev "$SNIFFER" info 2>/dev/null | sed -n 's/.*channel \([0-9][0-9]*\).*/\1/p' | head -1)"
		if [ "$SNIFFER_ORIG_TYPE" != "monitor" ]; then
			ip link set "$SNIFFER" down 2>/dev/null
			iw dev "$SNIFFER" set type monitor 2>/dev/null
			ip link set "$SNIFFER" up 2>/dev/null
		fi
		if sniffer_ready; then
			BG="$TMPDIR/bg.pcap"
			timeout 4 tcpdump -i "$SNIFFER" -w "$BG" -q >/dev/null 2>&1
			BG_N="$(pcap_count "$BG" 2>/dev/null || echo 0)"
			if [ "${BG_N:-0}" -ge 1 ]; then
				SNIFF_OK=1
				note "receiver $SNIFFER on channel $CHANNEL (background frames: $BG_N)"
			else
				note "receiver $SNIFFER sees no background frames on channel $CHANNEL - air check skipped"
			fi
		else
			note "receiver $SNIFFER could not be tuned to channel $CHANNEL - air check skipped"
		fi
	fi
fi

MON_PCAP="$TMPDIR/inj-mon.pcap"
SNIFF_PCAP="$TMPDIR/inj-air.pcap"
rm -f "$MON_PCAP" "$SNIFF_PCAP"
TX_BEFORE="$(cat "/sys/class/net/$MON/statistics/tx_packets" 2>/dev/null || echo 0)"
( timeout 12 tcpdump -i "$MON" -w "$MON_PCAP" -q >/dev/null 2>&1 ) & BG_PIDS="$BG_PIDS $!"
if [ "$SNIFF_OK" -eq 1 ]; then
	( timeout 12 tcpdump -i "$SNIFFER" -w "$SNIFF_PCAP" -q >/dev/null 2>&1 ) & BG_PIDS="$BG_PIDS $!"
fi
sleep 2
send_probe_rtap "$MON" "$SSID" "$COUNT"
sleep 2
for p in $BG_PIDS; do kill "$p" 2>/dev/null; done
wait 2>/dev/null
BG_PIDS=""
TX_AFTER="$(cat "/sys/class/net/$MON/statistics/tx_packets" 2>/dev/null || echo 0)"

LOCAL_N="$(pcap_count_ssid "$MON_PCAP" "$SSID")"
note "ssid: $SSID"
note "driver TX packets: $TX_BEFORE -> $TX_AFTER (delta $((TX_AFTER - TX_BEFORE)))"
note "local monitor copies: $LOCAL_N"

if [ "$SNIFF_OK" -eq 1 ]; then
	AIR_N="$(pcap_count_ssid "$SNIFF_PCAP" "$SSID")"
	note "over-the-air copies on $SNIFFER: $AIR_N / $COUNT"
	if [ "${AIR_N:-0}" -ge "$AIR_MIN" ]; then
		pass "injection reached the air ($AIR_N/$COUNT)"
	else
		fail "injection not observed on air ($AIR_N/$COUNT)"
	fi
else
	skip "on-air verification (no independent receiver on channel $CHANNEL)"
	if [ "$((TX_AFTER - TX_BEFORE))" -ge "$COUNT" ]; then
		pass "driver accepted all $COUNT injected frames (TX counter)"
	else
		fail "driver accepted only $((TX_AFTER - TX_BEFORE))/$COUNT injected frames"
	fi
fi

section "MONITOR: guard paths"
ip link set "$IFACE" up 2>/dev/null
iw dev "$IFACE" interface add "${MON}2" type monitor >/dev/null 2>&1
rc=$?
[ "$rc" -ne 0 ] && pass "second monitor refused (rc=$rc)" || fail "second monitor was not refused"
iw dev "${MON}2" del >/dev/null 2>&1

iw dev "$IFACE" set type monitor >/dev/null 2>&1
rc=$?
[ "$rc" -ne 0 ] && pass "type change refused while monitor exists (rc=$rc)" || fail "type change was not refused"

timeout 15 iw dev "$MON" scan >/dev/null 2>&1
rc=$?
[ "$rc" -ne 0 ] && pass "scan on monitor refused (rc=$rc)" || fail "scan on monitor was not refused"

timeout 15 iw dev "$IFACE" scan >/dev/null 2>&1
rc=$?
[ "$rc" -ne 0 ] && pass "scan on $IFACE refused while monitor exists (rc=$rc)" || fail "scan on $IFACE was not refused"

# ---------------------------------------------------------------------------
section "INTERFACE STATS (after injection)"
ip -s link show "$MON" 2>/dev/null
note "wlan0 counters: rx=$(cat /sys/class/net/$IFACE/statistics/rx_packets 2>/dev/null) tx=$(cat /sys/class/net/$IFACE/statistics/tx_packets 2>/dev/null) rx_err=$(cat /sys/class/net/$IFACE/statistics/rx_errors 2>/dev/null) tx_err=$(cat /sys/class/net/$IFACE/statistics/tx_errors 2>/dev/null)"

section "SUMMARY"
printf '  PASS=%d  FAIL=%d  SKIP=%d\n' "$PASS" "$FAIL" "$SKIP"
printf '  log: %s\n' "$LOGFILE"
if [ "$FAIL" -eq 0 ]; then
	printf '\n  RESULT: OK\n'
	exit 0
else
	printf '\n  RESULT: FAILED (%d)\n' "$FAIL"
	exit 1
fi