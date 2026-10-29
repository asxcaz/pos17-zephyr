#!/usr/bin/env python3
"""Align six Zephyr MediaTek HIDL source modules with their vendor prebuilts."""

import pathlib
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit(f"Usage: {sys.argv[0]} ROM_ROOT")

rom_root = pathlib.Path(sys.argv[1]).resolve()
if not rom_root.is_dir():
    raise SystemExit(f"ERROR: ROM root does not exist: {rom_root}")

# These exact source modules failed Soong partition consistency checks.
# Their matching proprietary shared libraries are shipped from vendor, so the
# source hidl_interface declarations must also be vendor modules.
targets = {
    "interfaces/hardware/bluetooth/audio/2.1/Android.bp": "vendor.mediatek.hardware.bluetooth.audio@2.1",
    "interfaces/hardware/bluetooth/audio/2.2/Android.bp": "vendor.mediatek.hardware.bluetooth.audio@2.2",
    "interfaces/hardware/lbs/1.0/Android.bp": "vendor.mediatek.hardware.lbs@1.0",
    "interfaces/hardware/mtkradioex/2.0/Android.bp": "vendor.mediatek.hardware.mtkradioex@2.0",
    "interfaces/hardware/mtkradioex/3.0/Android.bp": "vendor.mediatek.hardware.mtkradioex@3.0",
    "interfaces/hardware/netdagent/1.0/Android.bp": "vendor.mediatek.hardware.netdagent@1.0",
}

source_root = rom_root / "hardware/mediatek"
module_re = re.compile(r"(?ms)^hidl_interface[ \t]*\\{.*?^\\}")
name_re = re.compile(r'(?m)^\\s*name[ \t]*:[ \t]*"([^"]+)"[ \t]*,?[ \t]*$')
system_ext_re = re.compile(r"(?m)^([ \t]*)system_ext_specific[ \t]*:[ \t]*true([ \t]*,?)[ \t]*$")
vendor_re = re.compile(r"(?m)^[ \t]*vendor[ \t]*:[ \t]*true[ \t]*,?[ \t]*$")

changed = []
for relative_path, expected_name in targets.items():
    path = source_root / relative_path
    if not path.is_file():
        raise SystemExit(f"ERROR: required HIDL source file is missing: {path}")
    original = path.read_text()
    matches = list(module_re.finditer(original))
    matching = []
    for match in matches:
        block = match.group(0)
        names = name_re.findall(block)
        if expected_name in names:
            matching.append(match)

    if len(matching) != 1:
        raise SystemExit(
            f"ERROR: expected exactly one hidl_interface named {expected_name} "
            f"in {path}, found {len(matching)}"
        )

    match = matching[0]
    block = match.group(0)
    if vendor_re.search(block):
        print(f"Already vendor-aligned: {expected_name}")
        continue
    if not system_ext_re.search(block):
        raise SystemExit(
            f"ERROR: {expected_name} has neither vendor: true nor "
            f"system_ext_specific: true in {path}; refusing an ambiguous edit."
        )

    patched = system_ext_re.sub(
        lambda m: m.group(1) + "vendor: true" + m.group(2), block, count=1
    )
    updated = original[:match.start()] + patched + original[match.end():]
    path.write_text(updated)
    changed.append((path, expected_name))
    print(f"Patched source partition: {expected_name} -> vendor in {path}")

print(
    f"Partition alignment complete: {len(targets)} HIDL source modules checked; "
    f"{len(changed)} changed."
)
