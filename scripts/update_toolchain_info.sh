#!/usr/bin/env bash
#
# Nexmon Toolchain Information Script
# Displays current toolchain versions and checks for updates
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Nexmon Toolchain Information${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NEXMON_ROOT="$(dirname "$SCRIPT_DIR")"

print_header

# Check current toolchain
echo -e "${BLUE}Current Toolchain:${NC}"
print_info "GCC ARM None EABI 5.4 (2016q2)"
print_info "Release Date: June 2016"
print_warning "Toolchain is 8+ years old"
echo ""

# Check if toolchains exist
echo -e "${BLUE}Installed Toolchains:${NC}"
for toolchain_dir in "$NEXMON_ROOT/buildtools"/gcc-arm-none-eabi-*; do
    if [ -d "$toolchain_dir" ]; then
        toolchain_name=$(basename "$toolchain_dir")
        print_success "$toolchain_name"

        # Try to get version
        gcc_bin="$toolchain_dir/bin/arm-none-eabi-gcc"
        if [ -x "$gcc_bin" ]; then
            version=$("$gcc_bin" --version 2>/dev/null | head -1 || echo "Unknown")
            echo "  Version: $version"
        fi
    fi
done
echo ""

# Platform-specific toolchain
echo -e "${BLUE}Platform Detection:${NC}"
OS=$(uname -s)
ARCH=$(uname -m)
print_info "OS: $OS"
print_info "Architecture: $ARCH"
echo ""

case "$OS" in
    Darwin)
        print_info "Toolchain: gcc-arm-none-eabi-5_4-2016q2-osx"
        ;;
    Linux)
        case "$ARCH" in
            x86_64)
                print_info "Toolchain: gcc-arm-none-eabi-5_4-2016q2-linux-x86"
                ;;
            armv7l|armv6l|aarch64)
                print_info "Toolchain: gcc-arm-none-eabi-5_4-2016q2-linux-armv7l"
                ;;
        esac
        ;;
esac
echo ""

# Recommendations
echo -e "${BLUE}Recommendations:${NC}"
print_warning "Consider updating to a newer toolchain for:"
echo "  - Better optimization"
echo "  - Improved C11/C++14 support"
echo "  - Security fixes"
echo "  - Bug fixes"
echo ""
print_info "Potential alternatives:"
echo "  - GCC ARM 8.x (2018-2019)"
echo "  - GCC ARM 10.x (2020-2021)"
echo "  - GCC ARM 12.x (2022+)"
echo ""
print_warning "Note: Changing toolchain may require:"
echo "  - Recompilation of all patches"
echo "  - Testing on all supported devices"
echo "  - Potential code adjustments"
echo ""
