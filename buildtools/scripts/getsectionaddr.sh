#!/bin/bash
set -euo pipefail
if [ $# -ne 2 ]; then echo "getsectionaddr.sh: usage: $0 <section> <elf>" >&2; exit 1; fi
# Resolve objdump matching CC prefix or fallback to host/arm-none-eabi objdump
OBJDUMP="objdump"
if [ -n "${CC:-}" ]; then
    if [ "$CC" != "${CC%gcc}" ]; then
        CANDIDATE="${CC%gcc}objdump"
    elif [ "$CC" != "${CC%-}" ]; then
        CANDIDATE="${CC}objdump"
    else
        CANDIDATE="${CC}-objdump"
    fi
    if command -v "$CANDIDATE" >/dev/null 2>&1; then
        OBJDUMP="$CANDIDATE"
    elif command -v "arm-none-eabi-objdump" >/dev/null 2>&1; then
        OBJDUMP="arm-none-eabi-objdump"
    fi
elif command -v "arm-none-eabi-objdump" >/dev/null 2>&1; then
    OBJDUMP="arm-none-eabi-objdump"
fi
if ! command -v "$OBJDUMP" >/dev/null 2>&1; then
    OBJDUMP="objdump"
fi
ADDR=$("$OBJDUMP" -h "$2" 2>/dev/null | awk -v sec="$1" '$2 == sec { print $4 }' | head -n 1)
if [ -n "$ADDR" ]; then
    printf "%s\n" "$ADDR"
fi
