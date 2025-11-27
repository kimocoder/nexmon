#!/usr/bin/env bash
#
# Nexmon Firmware Version Checker
# Helps identify if your device's firmware is supported
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Nexmon Firmware Version Checker${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Detect platform
detect_platform() {
    local os=$(uname -s)
    local arch=$(uname -m)
    
    echo -e "\n${BLUE}Platform Detection:${NC}"
    print_info "Operating System: $os"
    print_info "Architecture: $arch"
    
    case "$os" in
        Linux)
            if [ -f /proc/device-tree/model ]; then
                local model=$(cat /proc/device-tree/model 2>/dev/null | tr -d '\0')
                print_info "Device Model: $model"
            fi
            ;;
        Darwin)
            print_info "macOS detected"
            ;;
    esac
}

# Check for WiFi chip
check_wifi_chip() {
    echo -e "\n${BLUE}WiFi Chip Detection:${NC}"
    
    if command -v lspci &> /dev/null; then
        local pci_wifi=$(lspci | grep -i "network\|wireless\|wifi" || true)
        if [ -n "$pci_wifi" ]; then
            print_info "PCI WiFi devices:"
            echo "$pci_wifi" | while read -r line; do
                echo "  $line"
            done
        fi
    fi
    
    # Check dmesg for Broadcom
    if command -v dmesg &> /dev/null && [ -r /var/log/dmesg ] || [ -r /proc/kmsg ]; then
        local broadcom=$(dmesg 2>/dev/null | grep -i "brcm\|broadcom" | head -5 || true)
        if [ -n "$broadcom" ]; then
            print_info "Broadcom references in dmesg:"
            echo "$broadcom" | while read -r line; do
                echo "  $line"
            done
        fi
    fi
}

# Check firmware version
check_firmware_version() {
    echo -e "\n${BLUE}Firmware Version Check:${NC}"
    
    # Check for brcmfmac
    if command -v modinfo &> /dev/null; then
        if modinfo brcmfmac &> /dev/null; then
            print_success "brcmfmac driver found"
            local driver_version=$(modinfo brcmfmac | grep "^version:" | awk '{print $2}')
            if [ -n "$driver_version" ]; then
                print_info "Driver version: $driver_version"
            fi
        else
            print_warning "brcmfmac driver not found"
        fi
    fi
    
    # Check firmware files
    local fw_paths=(
        "/lib/firmware/brcm"
        "/system/vendor/firmware"
        "/vendor/firmware"
    )
    
    for fw_path in "${fw_paths[@]}"; do
        if [ -d "$fw_path" ]; then
            print_info "Firmware directory found: $fw_path"
            local fw_files=$(find "$fw_path" -name "brcmfmac*.bin" 2>/dev/null || true)
            if [ -n "$fw_files" ]; then
                echo "$fw_files" | while read -r file; do
                    echo "  $(basename "$file")"
                done
            fi
        fi
    done
}

# Check if chip is supported
check_support() {
    echo -e "\n${BLUE}Checking Nexmon Support:${NC}"
    
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local nexmon_root="$(dirname "$script_dir")"
    
    if [ -d "$nexmon_root/patches" ]; then
        print_success "Nexmon patches directory found"
        print_info "Supported chips:"
        
        for chip_dir in "$nexmon_root/patches"/bcm*/; do
            if [ -d "$chip_dir" ]; then
                local chip=$(basename "$chip_dir")
                local fw_count=$(find "$chip_dir" -mindepth 1 -maxdepth 1 -type d | wc -l)
                echo "  - $chip ($fw_count firmware versions)"
            fi
        done
    else
        print_warning "Not running from Nexmon directory"
        print_info "Clone from: https://github.com/seemoo-lab/nexmon"
    fi
}

# Check kernel version
check_kernel() {
    echo -e "\n${BLUE}Kernel Information:${NC}"
    
    local kernel_version=$(uname -r)
    print_info "Kernel version: $kernel_version"
    
    # Extract major.minor
    local kernel_major_minor=$(echo "$kernel_version" | grep -oE '^[0-9]+\.[0-9]+')
    
    # Check if driver patch exists
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local nexmon_root="$(dirname "$script_dir")"
    
    if [ -d "$nexmon_root/patches/driver" ]; then
        local driver_dir="$nexmon_root/patches/driver/brcmfmac_${kernel_major_minor}.y-nexmon"
        if [ -d "$driver_dir" ]; then
            print_success "Nexmon driver patch available for kernel $kernel_major_minor.y"
        else
            print_warning "No Nexmon driver patch for kernel $kernel_major_minor.y"
            print_info "Available driver patches:"
            for driver in "$nexmon_root/patches/driver"/brcmfmac_*; do
                if [ -d "$driver" ]; then
                    echo "  - $(basename "$driver")"
                fi
            done
        fi
    fi
}

# Check dependencies
check_dependencies() {
    echo -e "\n${BLUE}Build Dependencies Check:${NC}"
    
    local deps=("git" "make" "gcc" "gawk" "flex" "bison")
    local missing=()
    
    for dep in "${deps[@]}"; do
        if command -v "$dep" &> /dev/null; then
            print_success "$dep installed"
        else
            print_error "$dep not found"
            missing+=("$dep")
        fi
    done
    
    if [ ${#missing[@]} -gt 0 ]; then
        echo ""
        print_warning "Missing dependencies: ${missing[*]}"
        print_info "Install with: sudo apt-get install ${missing[*]}"
    fi
}

# Main function
main() {
    print_header
    detect_platform
    check_wifi_chip
    check_firmware_version
    check_kernel
    check_support
    check_dependencies
    
    echo ""
}

# Run main function
main "$@"
