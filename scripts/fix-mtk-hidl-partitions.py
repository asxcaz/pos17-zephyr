#!/usr/bin/env python3
"""Align Zephyr MediaTek HIDL libraries with their vendor prebuilts."""

import pathlib
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit(f"Usage: {sys.argv[0]} ROM_ROOT")

rom_root = pathlib.Path(sys.argv[1]).resolve()
if not rom_root.is_dir():
    raise SystemExit(f"ERROR: ROM root does not exist: {rom_root}")

# These six source declarations were reported as partition-inconsistent.
# Removing system_ext_specific lets the ordinary interfaces use the platform
# defaults. Three of them also have vendor-only prebuilts; their generated
# C++ libraries must be vendor-specific, not merely vendor_available.
targets = {
    "interfaces/hardware/bluetooth/audio/2.1/Android.bp": "vendor.mediatek.hardware.bluetooth.audio@2.1",
    "interfaces/hardware/bluetooth/audio/2.2/Android.bp": "vendor.mediatek.hardware.bluetooth.audio@2.2",
    "interfaces/hardware/lbs/1.0/Android.bp": "vendor.mediatek.hardware.lbs@1.0",
    "interfaces/hardware/mtkradioex/2.0/Android.bp": "vendor.mediatek.hardware.mtkradioex@2.0",
    "interfaces/hardware/mtkradioex/3.0/Android.bp": "vendor.mediatek.hardware.mtkradioex@3.0",
    "interfaces/hardware/netdagent/1.0/Android.bp": "vendor.mediatek.hardware.netdagent@1.0",
}
vendor_only_interfaces = {
    "vendor.mediatek.hardware.mtkradioex@2.0",
    "vendor.mediatek.hardware.mtkradioex@3.0",
    "vendor.mediatek.hardware.netdagent@1.0",
}

source_root = rom_root / "hardware/mediatek"
module_re = re.compile(r"(?ms)^hidl_interface[ \t]*\{.*?^\}")
name_re = re.compile(r'(?m)^[ \t]*name[ \t]*:[ \t]*"([^"]+)"[ \t]*,?[ \t]*$')
partition_re = re.compile(
    r"(?m)^[ \t]*system_ext_specific[ \t]*:[ \t]*true[ \t]*,?[ \t]*\n"
)

changed = []
for relative_path, expected_name in targets.items():
    path = source_root / relative_path
    if not path.is_file():
        raise SystemExit(f"ERROR: required HIDL source file is missing: {path}")
    original = path.read_text()
    matches = [
        match for match in module_re.finditer(original)
        if expected_name in name_re.findall(match.group(0))
    ]
    if len(matches) != 1:
        raise SystemExit(
            f"ERROR: expected exactly one hidl_interface named {expected_name} "
            f"in {path}, found {len(matches)}"
        )

    match = matches[0]
    block = match.group(0)
    overrides = list(partition_re.finditer(block))
    if len(overrides) > 1:
        raise SystemExit(
            f"ERROR: multiple system_ext partition overrides in {expected_name}; "
            "refusing ambiguous edit."
        )
    if not overrides:
        print(f"Already using default HIDL partition: {expected_name}")
        continue

    patched = partition_re.sub("", block, count=1)
    path.write_text(original[:match.start()] + patched + original[match.end():])
    changed.append(expected_name)
    print(f"Removed system_ext partition override: {expected_name}")

# hidl_interface generates a cc_library internally. The generated library does
# not inherit the hidl_interface module's common partition properties, so the
# Android.bp setting alone cannot move that C++ library into /vendor. Apply a
# narrow local change to the generator for the three vendor-only prebuilts.
hidl_build = rom_root / "system/tools/hidl/build"
properties_path = hidl_build / "properties.go"
interface_path = hidl_build / "hidl_interface.go"
for path in (properties_path, interface_path):
    if not path.is_file():
        raise SystemExit(f"ERROR: required Soong HIDL generator source is missing: {path}")

properties = properties_path.read_text()
struct_match = re.search(r"(?ms)^type ccProperties struct \{.*?^\}", properties)
if not struct_match:
    raise SystemExit(f"ERROR: cannot find ccProperties in {properties_path}")
struct_block = struct_match.group(0)
if not re.search(r"(?m)^\s*Soc_specific\s+\*bool\s*$", struct_block):
    vendor_field = re.search(r"(?m)^(\s*)Vendor_available\s+\*bool\s*$", struct_block)
    if not vendor_field:
        raise SystemExit(
            f"ERROR: cannot find Vendor_available field in ccProperties ({properties_path})"
        )
    indent = vendor_field.group(1)
    insertion = vendor_field.group(0) + "\n" + indent + "Soc_specific *bool"
    properties = (
        properties[:struct_match.start()]
        + struct_block.replace(vendor_field.group(0), insertion, 1)
        + properties[struct_match.end():]
    )
    properties_path.write_text(properties)
    print("Added soc_specific support to the HIDL generated-library properties.")
else:
    print("HIDL generated-library properties already expose soc_specific.")

interface_source = interface_path.read_text()
helper = """func isZephyrVendorOnlyHidlInterface(name string) bool {
	switch name {
	case
		"vendor.mediatek.hardware.mtkradioex@2.0",
		"vendor.mediatek.hardware.mtkradioex@3.0",
		"vendor.mediatek.hardware.netdagent@1.0":
		return true
	}
	return false
}

"""
mutator_marker = "func hidlInterfaceMutator(mctx android.LoadHookContext, i *hidlInterface) {"
if "func isZephyrVendorOnlyHidlInterface(name string) bool {" not in interface_source:
    if interface_source.count(mutator_marker) != 1:
        raise SystemExit(
            f"ERROR: expected one hidlInterfaceMutator in {interface_path}; "
            "refusing to patch an unknown generator version."
        )
    interface_source = interface_source.replace(
        mutator_marker, helper + mutator_marker, 1
    )

availability_block = re.compile(
    r"(?m)^\s*var vendorAvailable \*bool\n"
    r"\s*if !proptools\.Bool\(i\.properties\.Odm_available\) \{\n"
    r"\s*vendorAvailable = proptools\.BoolPtr\(true\)\n"
    r"\s*\}"
)
if "var socSpecific *bool" not in interface_source:
    matches = list(availability_block.finditer(interface_source))
    if len(matches) != 1:
        raise SystemExit(
            f"ERROR: expected one vendorAvailable block in {interface_path}, "
            f"found {len(matches)}"
        )
    match = matches[0]
    addition = match.group(0) + """

	var socSpecific *bool
	if isZephyrVendorOnlyHidlInterface(name.string()) {
		// These three interfaces have vendor-only prebuilts. Generate the
		// source library as a vendor module instead of creating a core
		// library with a vendor_available variant.
		vendorAvailable = nil
		productAvailable = nil
		socSpecific = proptools.BoolPtr(true)
	}"""
    interface_source = (
        interface_source[:match.start()]
        + addition
        + interface_source[match.end():]
    )

# Keep the upstream HIDL host-build setting unchanged.
if "Soc_specific: socSpecific," not in interface_source:
    # Restrict the edit to the generated C++ library properties block; do not
    # count unrelated declarations or comments elsewhere in this Go file.
    library_start_match = re.search(
        r"mctx\.CreateModule\((?:android\.ModuleFactoryAdaptor\()?cc\.LibraryFactory,\s*&ccProperties\{",
        interface_source,
    )
    if not library_start_match:
        raise SystemExit(
            f"ERROR: cannot locate generated cc.LibraryFactory block in {interface_path}"
        )
    library_end = interface_source.find("\n\t})", library_start_match.end())
    if library_end < 0:
        raise SystemExit(
            f"ERROR: cannot locate end of generated cc.LibraryFactory block in {interface_path}"
        )
    library_block = interface_source[library_start_match.start():library_end]
    vendor_property = re.compile(
        r"(?m)^([ \t]*)Vendor_available[ \t]*:[ \t]*vendorAvailable,[ \t]*$"
    )
    vendor_matches = list(vendor_property.finditer(library_block))
    if len(vendor_matches) != 1:
        raise SystemExit(
            f"ERROR: expected one Vendor_available property in generated C++ library "
            f"block in {interface_path}, found {len(vendor_matches)}"
        )
    vendor_match = vendor_matches[0]
    indent = vendor_match.group(1)
    replacement_line = (
        vendor_match.group(0)
        + "\n"
        + indent
        + "Soc_specific: socSpecific,"
    )
    patched_block = (
        library_block[:vendor_match.start()]
        + replacement_line
        + library_block[vendor_match.end():]
    )
    interface_source = (
        interface_source[:library_start_match.start()]
        + patched_block
        + interface_source[library_end:]
    )
interface_path.write_text(interface_source)

# Fail closed if the final source does not contain all required vendor mappings.
final_interface_source = interface_path.read_text()
for name in vendor_only_interfaces:
    if name not in final_interface_source:
        raise SystemExit(f"ERROR: vendor-only HIDL mapping is missing: {name}")
if "Soc_specific: socSpecific," not in final_interface_source:
    raise SystemExit("ERROR: generated HIDL library is not wired to socSpecific.")

print(
    f"MediaTek HIDL alignment complete: {len(targets)} source modules checked; "
    f"{len(changed)} system_ext overrides removed; "
    f"{len(vendor_only_interfaces)} generated C++ libraries set to vendor-only."
)
