#!/usr/bin/env bash
#
# Automated Firmware Extraction Tool
# Extracts firmware from various sources
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     Nexmon Automated Firmware Extraction Tool         ║${NC}"
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
    echo -e "${BLUE}ℹ${NC} $1"
}

usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Automated firmware extraction from various sources.

OPTIONS:
    -s, --source PATH       Source path (device, directory, or file)
    -c, --chip CHIP         Chip model (e.g., bcm43455c0)
    -v, --version VERSION   Firmware version
    -o, --output DIR        Output directory (default: firmwares/)
    -h, --help              Show this help message

EXAMPLES:
    # Extract from connected Android device
    $0 --source adb --chip bcm4339 --version 6_37_34_43

    # Extract from Raspberry Pi
    $0 --source /lib/firmware/brcm --chip bcm43455c0 --version 7_45_206

    # Extract from system image
    $0 --source /path/to/system.img --chip bcm4358 --version 7_112_300_14_sta

EOF
}

# Extract from Android device via ADB
extract_from_adb() {
    local chip=$1
    local version=$2
    local output_dir=$3
    
    print_info "Extracting firmware from Android device via ADB..."
    
    if ! command -v adb &> /dev/null; then
        print_error "ADB not found. Please install Android SDK platform-tools."
        return 1
    fi
    
    # Check device connection
    if ! adb devices | grep -q "device$"; then
        print_error "No Android device connected or unauthorized"
        print_info "Enable USB debugging and authorize this computer"
        return 1
    fi
    
    print_success "Device connected"
    
    # Common firmware paths on Android
    local fw_paths=(
        "/vendor/firmware"
        "/system/vendor/firmware"
        "/system/etc/firmware"
    )
    
    local found=0
    for fw_path in "${fw_paths[@]}"; do
        print_info "Checking $fw_path..."
        
        local files=$(adb shell "ls $fw_path/fw_bcm*.bin 2>/dev/null" || true)
        if [ -n "$files" ]; then
            print_success "Found firmware files in $fw_path"
            
            mkdir -p "$output_dir"
            
            echo "$files" | while read -r file; do
                local basename=$(basename "$file")
                print_info "Pulling $basename..."
                adb pull "$file" "$output_dir/" 2>/dev/null || true
            done
            
            found=1
            break
        fi
    done
    
    if [ $found -eq 0 ]; then
        print_warning "No firmware files found on device"
        return 1
    fi
    
    print_success "Firmware extracted to $output_dir"
    return 0
}

# Extract from local filesystem
extract_from_filesystem() {
    local source=$1
    local chip=$2
    local version=$3
    local output_dir=$4
    
    print_info "Extracting firmware from filesystem: $source"
    
    if [ ! -d "$source" ]; then
        print_error "Source directory not found: $source"
        return 1
    fi
    
    mkdir -p "$output_dir"
    
    # Find firmware files
    local fw_files=$(find "$source" -name "fw_bcm*.bin" -o -name "brcmfmac*.bin" 2>/dev/null || true)
    
    if [ -z "$fw_files" ]; then
        print_warning "No firmware files found in $source"
        return 1
    fi
    
    print_success "Found firmware files:"
    echo "$fw_files" | while read -r file; do
        local basename=$(basename "$file")
        echo "  • $basename"
        cp "$file" "$output_dir/"
    done
    
    print_success "Firmware extracted to $output_dir"
    return 0
}

# Create firmware directory structure
create_firmware_structure() {
    local chip=$1
    local version=$2
    local fw_file=$3
    
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local nexmon_root="$(dirname "$script_dir")"
    local fw_dir="$nexmon_root/firmwares/$chip/$version"
    
    print_info "Creating firmware directory structure..."
    
    mkdir -p "$fw_dir"
    
    # Copy firmware file
    if [ -f "$fw_file" ]; then
        cp "$fw_file" "$fw_dir/"
        print_success "Copied firmware to $fw_dir"
    fi
    
    # Create basic definitions.mk if it doesn't exist
    if [ ! -f "$fw_dir/definitions.mk" ]; then
        cat > "$fw_dir/definitions.mk" << 'EOF'
# Firmware definitions for chip version
# TODO: Update these addresses based on firmware analysis

NEXMON_CHIP=CHIP_VER_BCM
NEXMON_CHIP_NUM=0x
NEXMON_FW_VERSION=FW_VER_ALL

# RAM addresses (update based on firmware analysis)
RAMSTART=0x
RAMSIZE=0x

# Function addresses (update based on firmware analysis)
# Use IDA Pro, Ghidra, or radare2 to find these
WLC_UCODE_WRITE_BL_HOOK_ADDR=0x
HNDRTE_RECLAIM_0_END_PTR=0x

# Template RAM
TEMPLATERAMSTART_PTR=0x

# Add more addresses as needed
EOF
        print_success "Created template definitions.mk"
        print_warning "You need to update addresses in $fw_dir/definitions.mk"
    fi
    
    # Create Makefile if it doesn't exist
    if [ ! -f "$fw_dir/Makefile" ]; then
        cat > "$fw_dir/Makefile" << 'EOF'
include definitions.mk
include $(NEXMON_ROOT)/firmwares/common.mk
EOF
        print_success "Created Makefile"
    fi
    
    echo ""
    print_info "Next steps:"
    echo "  1. Analyze firmware with IDA Pro/Ghidra/radare2"
    echo "  2. Update addresses in $fw_dir/definitions.mk"
    echo "  3. Extract flashpatches: cd $fw_dir && make"
    echo "  4. Create patch structure in patches/$chip/$version/"
}

# Main function
main() {
    print_header
    
    local source=""
    local chip=""
    local version=""
    local output_dir=""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -s|--source)
                source="$2"
                shift 2
                ;;
            -c|--chip)
                chip="$2"
                shift 2
                ;;
            -v|--version)
                version="$2"
                shift 2
                ;;
            -o|--output)
                output_dir="$2"
                shift 2
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
    
    # Validate required arguments
    if [ -z "$source" ] || [ -z "$chip" ] || [ -z "$version" ]; then
        print_error "Missing required arguments"
        usage
        exit 1
    fi
    
    # Set default output directory
    if [ -z "$output_dir" ]; then
        local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        local nexmon_root="$(dirname "$script_dir")"
        output_dir="$nexmon_root/firmwares/$chip/$version"
    fi
    
    # Extract based on source type
    case "$source" in
        adb)
            extract_from_adb "$chip" "$version" "$output_dir"
            ;;
        *)
            if [ -d "$source" ]; then
                extract_from_filesystem "$source" "$chip" "$version" "$output_dir"
            else
                print_error "Invalid source: $source"
                exit 1
            fi
            ;;
    esac
    
    # Create firmware structure
    local fw_file=$(find "$output_dir" -name "*.bin" | head -1)
    if [ -n "$fw_file" ]; then
        create_firmware_structure "$chip" "$version" "$fw_file"
    fi
    
    echo ""
    print_success "Firmware extraction complete!"
}

# Run main function
main "$@"
