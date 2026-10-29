#!/usr/bin/env python3
"""Align Zephyr's six MediaTek HIDL interface prebuilts with system_ext."""

import pathlib
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit(f"Usage: {sys.argv[0]} VENDOR_TREE")

root = pathlib.Path(sys.argv[1])
if not root.is_dir():
    raise SystemExit(f"ERROR: vendor tree does not exist: {root}")

targets = {
    "vendor.mediatek.hardware.bluetooth.audio@2.1",
    "vendor.mediatek.hardware.bluetooth.audio@2.2",
    "vendor.mediatek.hardware.lbs@1.0",
    "vendor.mediatek.hardware.mtkradioex@2.0",
    "vendor.mediatek.hardware.mtkradioex@3.0",
    "vendor.mediatek.hardware.netdagent@1.0",
}
found = {name: 0 for name in targets}
changed = []

# Android.bp module declarations close at column zero. Restrict matching to
# complete top-level module blocks and inspect only name/source_module_name.
module_re = re.compile(r"(?ms)^[A-Za-z_][A-Za-z0-9_]*[ \t]*\{.*?^\}")
system_ext_re = re.compile(
    r"(?m)^[ \t]*system_ext_specific[ \t]*:[ \t]*true[ \t]*,?[ \t]*$"
)
vendor_re = re.compile(r"(?m)^([ \t]*)vendor[ \t]*:[ \t]*true([ \t]*,?)[ \t]*$")

for path in root.rglob("Android.bp"):
    try:
        original = path.read_text()
    except (OSError, UnicodeError):
        continue
    updated = original
    matches = list(module_re.finditer(original))
    for match in reversed(matches):
        block = match.group(0)
        identity = re.findall(
            r'\b(?:name|source_module_name)[ \t]*:[ \t]*"([^"]+)"', block
        )
        hit = next((name for name in targets if (
            name in identity or ("prebuilt_" + name) in identity
        )), None)
        if hit is None:
            continue
        found[hit] += 1
        if system_ext_re.search(block):
            continue
        if not vendor_re.search(block):
            raise SystemExit(
                f"ERROR: {path}: module for {hit} has neither "
                "system_ext_specific: true nor a simple vendor: true property; "
                "refusing an ambiguous partition rewrite."
            )
        patched = vendor_re.sub(
            lambda m: m.group(1) + "system_ext_specific: true" + m.group(2),
            block,
            count=1,
        )
        updated = updated[:match.start()] + patched + updated[match.end():]
        changed.append((path, hit))
    if updated != original:
        path.write_text(updated)

missing = sorted(name for name, count in found.items() if count == 0)
if missing:
    raise SystemExit(
        "ERROR: Could not find matching MediaTek vendor prebuilt module(s): "
        + ", ".join(missing)
        + ". No Crave build will be started with a partial partition fix."
    )
for name in sorted(targets):
    print(f"Verified prebuilt module: {name} (definitions: {found[name]})")
for path, name in changed:
    print(f"Patched local vendor partition: {name} in {path}")
print(f"Partition check complete: {len(targets)} MediaTek HIDL modules.")
