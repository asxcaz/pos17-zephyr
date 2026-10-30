#!/usr/bin/env bash
set -Eeuo pipefail

TMP_DIR="$(mktemp -d)"
cleanup() {
    rm -rf "$TMP_DIR"
    echo
    echo "Disk usage after cleanup:"
    df -h .
    df -i .
}
trap cleanup EXIT

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

default_branch() {
    local url="$1"
    local line
    line="$(git ls-remote --symref "$url" HEAD | awk '$1 == "ref:" && $3 == "HEAD" { print $2; exit }')"
    [[ -n "$line" ]] || fail "Cannot read symbolic HEAD/default branch from $url"
    printf '%s\n' "${line#refs/heads/}"
}

clone_repo() {
    local label="$1"
    local url="$2"
    local expected_branch="$3"
    local dest="$TMP_DIR/$label"
    local branch

    echo "== $label ==" >&2
    branch="$(default_branch "$url")"
    echo "URL: $url" >&2
    echo "Remote default branch: $branch" >&2

    if [[ -n "$expected_branch" && "$branch" != "$expected_branch" ]]; then
        fail "$label default branch changed: expected '$expected_branch', got '$branch'. Review the manifest before updating it."
    fi

    git clone --depth=1 --single-branch --branch "$branch" "$url" "$dest" >&2
    if command -v git-lfs >/dev/null 2>&1; then
        git -C "$dest" lfs pull >&2 || fail "Git LFS download failed for $label"
    fi
    printf '%s\n' "$dest"
}

require_files() {
    local repo="$1"
    shift
    local path
    for path in "$@"; do
        [[ -e "$repo/$path" ]] || fail "Expected file/path missing: $repo/$path"
    done
}

echo "Runner disk before clones:"
df -h .
df -i .

DEVICE_URL="https://github.com/oplus-mt6895/android_device_oplus_zephyr.git"
SEPOLICY_URL="https://github.com/oplus-mt6895/android_device_mediatek_sepolicy_vndr.git"
MTK_HW_URL="https://github.com/oplus-mt6895/android_hardware_mediatek.git"
HIDL_TOOLS_URL="https://android.googlesource.com/platform/system/tools/hidl"
OPLUS_HW_URL="https://github.com/oplus-mt6895/android_hardware_oplus.git"
KERNEL_URL="https://gitlab.com/almightygodthor/android_device_oplus_zephyr-kernel.git"
VENDOR_URL="https://gitlab.com/almightygodthor/proprietary_vendor_oplus_zephyr.git"
IMS_URL="https://github.com/Adarsh0127-Elite/android_vendor_mediatek_ims.git"
IMS_BRANCH="android-16-qpr2"

device="$(clone_repo device "$DEVICE_URL" lineage-24.0)"
require_files "$device" AndroidProducts.mk BoardConfig.mk device.mk lineage_zephyr.mk vendorsetup.sh lineage.dependencies
echo "Device tree structure: OK"
rm -rf "$device"

sepolicy="$(clone_repo sepolicy "$SEPOLICY_URL" lineage-24.0)"
require_files "$sepolicy" SEPolicy.mk
echo "MediaTek vendor sepolicy structure: OK"
rm -rf "$sepolicy"

mtk_hw="$(clone_repo mtk-hardware "$MTK_HW_URL" lineage-24.0)"
require_files "$mtk_hw" Android.bp vintf
echo "MediaTek hardware structure: OK"

hidl_tools="$(clone_repo hidl-tools "$HIDL_TOOLS_URL" "")"
require_files "$hidl_tools" build/hidl_interface.go build/properties.go
echo "AOSP HIDL generator structure: OK"

# Exercise the exact local patcher against disposable shallow clones of the
# actual MediaTek declarations and AOSP HIDL generator source.
test_rom="$TMP_DIR/test-rom"
mkdir -p "$test_rom/hardware" "$test_rom/system/tools"
mv "$mtk_hw" "$test_rom/hardware/mediatek"
mv "$hidl_tools" "$test_rom/system/tools/hidl"
python3 "$(dirname "${BASH_SOURCE[0]}")/fix-mtk-hidl-partitions.py" "$test_rom"

grep -q 'Soc_specific: socSpecific,' "$test_rom/system/tools/hidl/build/hidl_interface.go" \
    || fail "HIDL generator did not mark the selected generated libraries soc_specific"
grep -Fq 'Soc_specific *bool' "$test_rom/system/tools/hidl/build/properties.go" \
    || fail "HIDL generator ccProperties does not expose soc_specific"
grep -q 'vendor.mediatek.hardware.mtkradioex@2.0' "$test_rom/system/tools/hidl/build/hidl_interface.go" \
    || fail "mtkradioex 2.0 vendor-only mapping was not installed"
grep -q 'vendor.mediatek.hardware.mtkradioex@3.0' "$test_rom/system/tools/hidl/build/hidl_interface.go" \
    || fail "mtkradioex 3.0 vendor-only mapping was not installed"
grep -q 'vendor.mediatek.hardware.netdagent@1.0' "$test_rom/system/tools/hidl/build/hidl_interface.go" \
    || fail "netdagent 1.0 vendor-only mapping was not installed"
echo "MediaTek HIDL source and generated-library partition patch: OK"
rm -rf "$test_rom"

oplus_hw="$(clone_repo oplus-hardware "$OPLUS_HW_URL" lineage-23.2)"
require_files "$oplus_hw" Android.bp vintf
echo "OPlus hardware structure: OK"
rm -rf "$oplus_hw"

kernel="$(clone_repo zephyr-kernel "$KERNEL_URL" "")"
require_files "$kernel" Image.gz dtb/mt6895.dtb modules/vendor_dlkm.modules.load modules/vendor_ramdisk.modules.load modules/vendor_ramdisk.modules.load.recovery
kernel_size="$(stat -c '%s' "$kernel/Image.gz")"
(( kernel_size > 1000000 )) || fail "Image.gz is unexpectedly small ($kernel_size bytes); it may be a Git LFS pointer rather than the real kernel image."
echo "Prebuilt kernel structure: OK (Image.gz: $kernel_size bytes)"
rm -rf "$kernel"

vendor="$(clone_repo zephyr-vendor "$VENDOR_URL" "")"
require_files "$vendor" BoardConfigVendor.mk
echo "Proprietary vendor structure: OK"
rm -rf "$vendor"

ims="$(clone_repo mediatek-ims "$IMS_URL" "$IMS_BRANCH")"
require_files "$ims" ims.mk Android.bp
echo "MediaTek IMS dependency structure: OK (branch: $IMS_BRANCH)"
rm -rf "$ims"

echo
echo "All shallow-clone preflight checks passed."
echo "Note: this validates reachability, default branches and expected file layout only; it does not prove the Android 17 build will compile or boot."
