# Contributing to Nexmon

Thank you for contributing to Nexmon! This project encompasses kernel drivers, firmware patches, C utilities, and a Python SDK across multiple Broadcom/Cypress Wi-Fi chipsets.

To maintain code quality, security, and stability across all targets, please follow these guidelines when submitting contributions.

---

## 1. Development Environment

Before building or testing patches, source the environment script from the repository root:

```bash
source setup_env.sh
```

Ensure the required build tools and dependencies are installed:
- On **Debian / Ubuntu (x86_64)**:
  ```bash
  sudo dpkg --add-architecture i386
  sudo apt-get update
  sudo apt-get install -y gcc g++-multilib libc6-i386 libgmp-dev libgmp-dev:i386 make gawk xxd qpdf bison flex libpcap-dev libnl-3-dev libnl-genl-3-dev libcap-dev
  ```
- Install Python development and test packages:
  ```bash
  pip install -e .[dev,analysis]
  ```

---

## 2. Code Quality & Pre-Commit Checks

All PRs must pass the CI checks before merging. You can run all checks locally:

### Python Linting & Formatting
We use `ruff` for Python linting:
```bash
ruff check .
```

### Shell Script Checks
We use `shellcheck` with error severity on all build scripts:
```bash
shellcheck -S error setup_env.sh monitor-mode.sh buildtools/*.sh buildtools/scripts/*.sh
```

### Consistency & Integrity Checks
Run the automated validation tools:
```bash
# 1. IOCTL and Capability constants sync check
python buildtools/scripts/sync_constants.py --check

# 2. Wrapper macro consistency and address collision check
python buildtools/scripts/validate_firmware.py --check-wrapper

# 3. Kernel driver syntax and comment guard check (750+ driver files)
python buildtools/scripts/check_drivers.py --check
```

---

## 3. Unit Tests & Driver Compilation

Run the full test suite (over 240 tests covering parser logic, C utilities, Wireshark helpers, and firmware rules):
```bash
python3 -m unittest discover -s tests -v
```

If kernel headers are present on your build host, compile-test the out-of-tree kernel drivers:
```bash
python3 buildtools/scripts/check_drivers.py --compile
```

---

## 4. Firmware Patch Guidelines

When adding or modifying firmware patches under `patches/<chip>/<version>/`:
1. **Zero-Size `.bss` Requirement**: Patches must not introduce uninitialized global variables into `.bss`. Always explicitly initialize global state or allocate from heap memory.
2. **Flashpatch Declarations**: For targets supporting flashpatches, ensure `BPatch` / `GenericPatch` entries in `flashpatches.c` stay within the hardware flashpatch slot limits of the target chip.
3. **Firmware Validation**: Run the validator against your patch directory:
   ```bash
   python3 buildtools/scripts/validate_firmware.py patches/<chip>/<version>/nexmon --require
   ```
4. **Buffer Management**: In firmware RX/TX paths, avoid leaking packet buffers (`pkt_buf_free_skb()`) and adhere to IEEE 802.11 Radiotap header specifications (`it_pad = 0`).

---

## 5. Submitting Pull Requests

1. **Focused Commits**: Structure commits logically by subsystem (e.g. `driver:`, `firmware:`, `utilities:`, `tooling:`).
2. **Documentation**: If adding a new chip target or feature, update `README.md` and `DEVICES.md`.
3. **No Generated Binaries**: Do not commit build artifacts (`.o`, `.elf`, `.ko`, `.so`, or temporary files).
