#!/usr/bin/env bash
#
# List all supported devices and firmware versions
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NEXMON_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Nexmon Supported Devices and Firmware Versions"
echo "=============================================="
echo ""

if [ ! -d "$NEXMON_ROOT/patches" ]; then
    echo "Error: patches directory not found"
    exit 1
fi

cd "$NEXMON_ROOT/patches"

for chip_dir in bcm*/; do
    if [ -d "$chip_dir" ]; then
        chip=$(basename "$chip_dir")
        echo "Chip: $chip"

        for fw_dir in "$chip_dir"*/; do
            if [ -d "$fw_dir" ]; then
                fw_version=$(basename "$fw_dir")

                # Check for nexmon subdirectory
                if [ -d "$fw_dir/nexmon" ]; then
                    echo "  ├─ Firmware: $fw_version"

                    # Check capabilities if patch.c exists
                    if [ -f "$fw_dir/nexmon/src/patch.c" ]; then
                        caps=$(grep -o "NEX_CAP_[A-Z_]*" "$fw_dir/nexmon/src/patch.c" 2>/dev/null | sort -u || true)
                        if [ -n "$caps" ]; then
                            echo "  │  Capabilities:"
                            echo "$caps" | while read -r cap; do
                                echo "  │    - $cap"
                            done
                        fi
                    fi
                fi
            fi
        done
        echo ""
    fi
done

echo "=============================================="
echo "Total chips supported: $(find . -maxdepth 1 -type d -name "bcm*" | wc -l)"
echo ""
