#!/bin/bash
set -euo pipefail
if [ -z "${NEXMON_ROOT:-}" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
    if [ -f "$SCRIPT_DIR/../../setup_env.sh" ]; then
        NEXMON_ROOT="$(cd "$SCRIPT_DIR/../.." >/dev/null 2>&1 && pwd)"
    else
        echo "getdefine.sh: NEXMON_ROOT not set" >&2
        exit 1
    fi
fi
if [ -z "${1:-}" ]; then echo "getdefine.sh: missing define name" >&2; exit 1; fi
# Cache gcc -E per (NEXMON_ROOT, define) to avoid forking gcc for every AT
CACHE_DIR="${TMPDIR:-/tmp}/nexmon-getdefine-$(id -u 2>/dev/null || echo 0)"
mkdir -p "$CACHE_DIR" 2>/dev/null || true
chmod 700 "$CACHE_DIR" 2>/dev/null || true
CACHE_KEY=""
if command -v sha256sum >/dev/null 2>&1; then
    CACHE_KEY=$(printf "%s|%s" "$NEXMON_ROOT" "$1" | sha256sum | cut -d' ' -f1)
else
    CACHE_KEY=$(printf "%s|%s" "$NEXMON_ROOT" "$1" | cksum | tr ' ' '_')
fi
CACHE_FILE="$CACHE_DIR/$CACHE_KEY"
FW_HDR="$NEXMON_ROOT/patches/include/firmware_version.h"
if [ -f "$CACHE_FILE" ] && [ "$CACHE_FILE" -nt "$FW_HDR" ]; then
    cat "$CACHE_FILE"
    exit 0
fi
COMPILER="gcc"
if [ -n "${CC:-}" ]; then
    if command -v "${CC}" >/dev/null 2>&1; then
        COMPILER="${CC}"
    elif command -v "${CC}gcc" >/dev/null 2>&1; then
        COMPILER="${CC}gcc"
    elif command -v gcc >/dev/null 2>&1; then
        COMPILER="gcc"
    fi
fi
OUT=$(printf "#include \"%s/patches/include/firmware_version.h\"\n%s\n" "$NEXMON_ROOT" "$1" | "$COMPILER" -E -x c - 2>/dev/null | tail -n 1)
TMP_FILE=$(mktemp "$CACHE_DIR/.tmp.XXXXXX" 2>/dev/null || mktemp "${TMPDIR:-/tmp}/nexmon-gd.XXXXXX")
trap 'rm -f "$TMP_FILE" 2>/dev/null' EXIT
printf "%s\n" "$OUT" > "$TMP_FILE"
mv -f "$TMP_FILE" "$CACHE_FILE" 2>/dev/null || true
printf "%s\n" "$OUT"
