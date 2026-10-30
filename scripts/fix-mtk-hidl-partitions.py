#!/usr/bin/env python3
"""Align Zephyr MediaTek HIDL interfaces with vendor prebuilts safely."""

import pathlib
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit(f"Usage: {sys.argv[0]} ROM_ROOT")

rom_root = pathlib.Path(sys.argv[1]).resolve()
if not rom_root.is_dir():
    raise SystemExit(f"ERROR: ROM root does not exist: {rom_root}")

# These exact HIDL interfaces were reported as partition-inconsistent with
# proprietary vendor prebuilts. hidl_interface already provides the appropriate
# vendor/product variants; forcing vendor: true is invalid. Remove the
# system_ext_specific/vendor partition override and retain the interface's
# normal availability variants.
targets = {
    "interfaces/hardware/bluetooth/audio/2.1/Android.bp": "vendor.mediatek.hardware.bluetooth.audio@2.1",
    "interfaces/hardware/bluetooth/audio/2.2/Android.bp": "vendor.mediatek.hardware.bluetooth.audio@2.2",
    "interfaces/hardware/lbs/1.0/Android.bp": "vendor.mediatek.hardware.lbs@1.0",
    "interfaces/hardware/mtkradioex/2.0/Android.bp": "vendor.mediatek.hardware.mtkradioex@2.0",
    "interfaces/hardware/mtkradioex/3.0/Android.bp": "vendor.mediatek.hardware.mtkradioex@3.0",
    "interfaces/hardware/netdagent/1.0/Android.bp": "vendor.mediatek.hardware.netdagent@1.0",
}

source_root = rom_root / "hardware/mediatek"
module_re = re.compile(r"(?ms)^hidl_interface[ \t]*\{.*?^\}")
name_re = re.compile(r'(?m)^[ \t]*name[ \t]*:[ \t]*"([^"]+)"[ \t]*,?[ \t]*$')
partition_re = re.compile(
    r"(?m)^[ \t]*(?:system_ext_specific|vendor)[ \t]*:[ \t]*true[ \t]*,?[ \t]*\n"
)

changed = []
for relative_path, expected_name in targets.items():
    path = source_root / relative_path
    if not path.is_file():
        raise SystemExit(f"ERROR: required HIDL source file is missing: {path}")
    original = path.read_text()
    matches = []
    for match in module_re.finditer(original):
        if expected_name in name_re.findall(match.group(0)):
            matches.append(match)

    if len(matches) != 1:
        raise SystemExit(
            f"ERROR: expected exactly one hidl_interface named {expected_name} "
            f"in {path}, found {len(matches)}"
        )

    match = matches[0]
    block = match.group(0)
    overrides = list(partition_re.finditer(block))
    if len(overrides) > 1:
        raise SystemExit(f"ERROR: multiple partition overrides in {expected_name}; refusing ambiguous edit.")

    if not overrides:
        print(f"Already using default HIDL partition variants: {expected_name}")
        continue

    patched = partition_re.sub("", block, count=1)
    updated = original[:match.start()] + patched + original[match.end():]
    path.write_text(updated)
    changed.append(expected_name)
    print(f"Removed invalid partition override: {expected_name}")

print(
    f"Partition alignment complete: {len(targets)} HIDL source modules checked; "
    f"{len(changed)} corrected."
)
