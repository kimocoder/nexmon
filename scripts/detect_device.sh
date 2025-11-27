#!/usr/bin/env bash
#
# Nexmon Automatic Device Detection
# Detects WiFi chip and suggests appropriate firmware patch
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║        Nexmon Automatic Device Detection              ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
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
    echo -e "${CYAN}ℹ${NC} $1"
}

# Detect Raspberry Pi model
detect_raspberry_pi() {
    if [ ! -f /proc/device-tree/model ]; then
        return 1
    fi
    
    local model=$(cat /proc/device-tree/model 2>/dev/null | tr -d '\0')
    
    echo -e "\n${BLUE}Raspberry Pi Detected:${NC}"
    print_info "Model: $model"
    
    case "$model" in
        *"Raspberry Pi 3 Model B Plus"*|*"Raspberry Pi 4"*|*"Raspberry Pi 5"*)
            print_success "Chip: bcm43455c0"
            echo ""
            print_info "Recommended firmware patches:"
            echo "  • patches/bcm43455c0/7_45_206/nexmon/ (Raspberry Pi OS)"
            echo "  • patches/bcm43455c0/7_45_189/nexmon/ (Older kernels)"
            echo "  • patches/bcm43455c0/7_45_154/nexmon/ (Legacy)"
            return 0
            ;;
        *"Raspberry Pi 3 Model B"*|*"Raspberry Pi Zero W"*)
            print_success "Chip: bcm43430a1"
            echo ""
            print_info "Recommended firmware patches:"
            echo "  • patches/bcm43430a1/7_45_41_46/nexmon/ (Recommended)"
            echo "  • patches/bcm43430a1/7_45_41_26/nexmon/ (Legacy)"
            return 0
            ;;
        *"Raspberry Pi Zero 2"*)
            print_success "Chip: bcm43436b0"
            echo ""
            print_info "Recommended firmware patch:"
            echo "  • patches/bcm43436b0/9_88_4_65/nexmon/"
            return 0
            ;;
        *)
            print_warning "Unknown Raspberry Pi model"
            return 1
            ;;
    esac
}

# Detect Android device
detect_android() {
    if ! command -v getprop &> /dev/null; then
        return 1
    fi
    
    echo -e "\n${BLUE}Android Device Detected:${NC}"
    
    local manufacturer=$(getprop ro.product.manufacturer 2>/dev/null || echo "Unknown")
    local model=$(getprop ro.product.model 2>/dev/null || echo "Unknown")
    local device=$(getprop ro.product.device 2>/dev/null || echo "Unknown")
    
    print_info "Manufacturer: $manufacturer"
    print_info "Model: $model"
    print_info "Device: $device"
    
    # Try to detect chip from known devices
    case "$device" in
        hammerhead)
            print_success "Detected: Nexus 5"
            print_success "Chip: bcm4339"
            echo ""
            print_info "Firmware patch:"
            echo "  • patches/bcm4339/6_37_34_43/nexmon/"
            return 0
            ;;
        shamu)
            print_success "Detected: Nexus 6"
            print_success "Chip: bcm4356"
            echo ""
            print_info "Firmware patch:"
            echo "  • patches/bcm4356/7_35_101_5_sta/nexmon/"
            return 0
            ;;
        angler)
            print_success "Detected: Nexus 6P"
            print_success "Chip: bcm4358"
            echo ""
            print_info "Firmware patches:"
            echo "  • patches/bcm4358/7_112_300_14_sta/nexmon/ (Android 8.0)"
            echo "  • patches/bcm4358/7_112_201_3_sta/nexmon/ (Android 7.1.2)"
            echo "  • patches/bcm4358/7_112_200_17_sta/nexmon/ (Android 7)"
            return 0
            ;;
        *)
            print_warning "Device not in known database"
            print_info "Check /vendor/firmware/ for firmware files"
            return 1
            ;;
    esac
}

# Detect chip from dmesg
detect_from_dmesg() {
    if ! command -v dmesg &> /dev/null; then
        return 1
    fi
    
    local dmesg_output=$(dmesg 2>/dev/null | grep -i "brcm\|broadcom" || true)
    
    if [ -z "$dmesg_output" ]; then
        return 1
    fi
    
    echo -e "\n${BLUE}Broadcom WiFi Detected in dmesg:${NC}"
    
    # Try to extract chip info
    if echo "$dmesg_output" | grep -q "43430"; then
        print_success "Chip: bcm43430a1 (likely)"
        echo ""
        print_info "Firmware patches:"
        echo "  • patches/bcm43430a1/7_45_41_46/nexmon/"
        return 0
    elif echo "$dmesg_output" | grep -q "43455"; then
        print_success "Chip: bcm43455c0 (likely)"
        echo ""
        print_info "Firmware patches:"
        echo "  • patches/bcm43455c0/7_45_206/nexmon/"
        return 0
    elif echo "$dmesg_output" | grep -q "4339"; then
        print_success "Chip: bcm4339 (likely)"
        echo ""
        print_info "Firmware patch:"
        echo "  • patches/bcm4339/6_37_34_43/nexmon/"
        return 0
    fi
    
    print_warning "Could not determine exact chip model"
    echo ""
    print_info "dmesg output:"
    echo "$dmesg_output" | head -5
    return 1
}

# Detect from firmware files
detect_from_firmware() {
    local fw_paths=(
        "/lib/firmware/brcm"
        "/vendor/firmware"
        "/system/vendor/firmware"
    )
    
    for fw_path in "${fw_paths[@]}"; do
        if [ -d "$fw_path" ]; then
            local fw_files=$(find "$fw_path" -name "brcmfmac*.bin" 2>/dev/null || true)
            
            if [ -n "$fw_files" ]; then
                echo -e "\n${BLUE}Firmware Files Found:${NC}"
                print_info "Location: $fw_path"
                echo ""
                
                echo "$fw_files" | while read -r file; do
                    local basename=$(basename "$file")
                    echo "  • $basename"
                    
                    # Try to match to known chips
                    case "$basename" in
                        *43430*)
                            echo "    → bcm43430a1 (Raspberry Pi 3/Zero W)"
                            ;;
                        *43455*)
                            echo "    → bcm43455c0 (Raspberry Pi 3+/4)"
                            ;;
                        *43436*)
                            echo "    → bcm43436b0 (Raspberry Pi Zero 2 W)"
                            ;;
                        *4339*)
                            echo "    → bcm4339 (Nexus 5)"
                            ;;
                        *4358*)
                            echo "    → bcm4358 (Nexus 6P)"
                            ;;
                    esac
                done
                return 0
            fi
        fi
    done
    
    return 1
}

# Main detection logic
main() {
    print_header
    
    local detected=0
    
    # Try different detection methods
    if detect_raspberry_pi; then
        detected=1
    elif detect_android; then
        detected=1
    elif detect_from_dmesg; then
        detected=1
    elif detect_from_firmware; then
        detected=1
    fi
    
    if [ $detected -eq 0 ]; then
        echo -e "\n${YELLOW}Could not automatically detect device${NC}"
        echo ""
        print_info "Manual detection steps:"
        echo "  1. Check dmesg: dmesg | grep -i brcm"
        echo "  2. Check firmware: ls /lib/firmware/brcm/"
        echo "  3. Check lspci: lspci | grep -i network"
        echo "  4. See COMPATIBILITY.md for full device list"
        echo ""
        print_info "Or run: ./scripts/check_firmware_version.sh"
    else
        echo ""
        echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║  Next Steps:                                           ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo "1. Navigate to the recommended patch directory"
        echo "2. Run: source setup_env.sh"
        echo "3. Run: make"
        echo "4. Run: make install-firmware"
        echo ""
    fi
}

# Run main function
main "$@"
