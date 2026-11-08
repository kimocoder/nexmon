#!/bin/bash
set -euo pipefail
if [ $# -ne 2 ]; then echo "getsectionaddr.sh: usage: $0 <section> <elf>" >&2; exit 1; fi
# Use CC's objdump if CC ends in gcc, else fallback to host objdump
if [ -n "${CC:-}" ] && [ "$CC" != "${CC%gcc}" ]; then
    OBJDUMP="${CC%gcc}objdump"
else
    OBJDUMP="objdump"
fi
if ! command -v "$OBJDUMP" >/dev/null 2>&1; then
    OBJDUMP="objdump"
fi
ADDR=$("$OBJDUMP" -h "$2" 2>/dev/null | awk -v sec="$1" '$2 == sec { print $4 }' | head -n 1)
if [ -n "$ADDR" ]; then
    printf "%s\n" "$ADDR"
fi
