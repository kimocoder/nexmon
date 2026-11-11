#!/bin/sh
# Smoke-test nexmon binaries on a live API 21 device or emulator.
#
#   buildtools/scripts/android_smoke_test.sh BINARY [BINARY...]
#
# Each binary is pushed to /data/local/tmp and started there. A binary that
# cannot load (wrong ABI, or a libc symbol newer than the device) fails with
# "CANNOT LINK EXECUTABLE"; that, a missing file, or exit status 126/127 is
# treated as a failure. Usage errors from the program itself are fine: the point
# is that the loader and the API-21 libc accept the binary.
set -eu

if [ "$#" -eq 0 ]; then
    echo "usage: $0 BINARY [BINARY...]" >&2
    exit 2
fi

api=$(adb shell getprop ro.build.version.sdk | tr -d '\r')
abi=$(adb shell getprop ro.product.cpu.abi | tr -d '\r')
echo "device: API $api, primary ABI $abi"
if [ "$api" != "21" ]; then
    echo "FAIL: expected an API 21 device, got API $api" >&2
    exit 1
fi

status=0
for binary in "$@"; do
    [ -f "$binary" ] || { echo "FAIL: $binary does not exist" >&2; status=1; continue; }
    name=$(basename "$binary")
    remote="/data/local/tmp/$name"
    adb push "$binary" "$remote" >/dev/null
    adb shell "chmod 755 $remote"

    rc=0
    output=$(adb shell "$remote </dev/null 2>&1") || rc=$?
    case "$output" in
        *"CANNOT LINK EXECUTABLE"*|*"not found"*|*"Permission denied"*)
            echo "FAIL: $name: $output" >&2
            status=1
            continue
            ;;
    esac
    if [ "$rc" -eq 126 ] || [ "$rc" -eq 127 ]; then
        echo "FAIL: $name exited $rc: $output" >&2
        status=1
        continue
    fi
    echo "ok: $name"
    adb shell "rm -f $remote"
done

exit "$status"