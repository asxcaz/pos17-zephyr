# PixelOS Android 17 for Zephyr (MT6895)

个人 PixelOS 移植实验，目标是 realme GT Neo 3 / OnePlus 10R 共用设备树 `zephyr`。网页端使用 Crave Devspace + VS Code Web；完整同步与编译只能通过 `crave run` 排入构建队列。

> 当前状态：上游浅克隆和文件布局检查已通过，但从未完成 Android 17 的整机编译或启动验证。

## 设备与源码

- ROM: [PixelOS Android 17 manifest](https://github.com/PixelOS-AOSP/android_manifest), branch `seventeen`
- Product: `custom_zephyr-cp2a-userdebug`
- Device tree: `oplus-mt6895/android_device_oplus_zephyr`, default branch currently `lineage-24.0`
- MediaTek vendor sepolicy: `oplus-mt6895/android_device_mediatek_sepolicy_vndr`, default `lineage-24.0`
- MediaTek hardware: `oplus-mt6895/android_hardware_mediatek`, default `lineage-24.0`
- OPlus hardware: `oplus-mt6895/android_hardware_oplus`, default `lineage-23.2`
- Kernel prebuilt: `https://gitlab.com/almightygodthor/android_device_oplus_zephyr-kernel.git`, default branch verified by Actions as `los-24`
- Proprietary vendor: `https://gitlab.com/almightygodthor/proprietary_vendor_oplus_zephyr.git`, default currently `lineage-23.2`

The GitHub local manifest uses an explicit `https://github.com` remote for OPlus repositories. GitLab kernel/vendor clones are checked out from each remote's actual default branch; do not guess or normalize branch names.

## Crave workflow (read before running)

This follows Crave's queued-build workflow, not a normal local Android build.

- Open Crave web dashboard → **Sessions** → create/connect a web Devspace or **Connect VSCode**.
- In the Devspace/VS Code terminal, only manage your Crave clone and submit builds. Do **not** run `repo init`, `repo sync`, `m`, `mka`, or other compilation directly in this terminal.
- Crave project names/IDs are labels for prepared source/workspace profiles; they do not lock the final ROM target. In the current account, use project ID `99` (`LOS 23.2`, setup complete) as the starting Crave clone. The queued script reinitializes that workspace to PixelOS Android 17 (`seventeen`), so the build target remains PixelOS, not LineageOS.
- Create a clone once, then keep reusing the same clone path and project for incremental builds. Example path below; do not create/destroy clones for ordinary retries.

```bash
crave clone list
crave clone create --projectID 99 /crave-devspaces/PixelOS-zephyr17
cd /crave-devspaces/PixelOS-zephyr17
```

For an unsupported device/ROM combination, initialize/sync the target ROM and add device sources **inside the queued `crave run` command**. Crave recommends using `/opt/crave/resync.sh` instead of raw `repo sync` because it handles common checkout conflicts. The script in this repository follows that rule, uses `repo init --depth=1`, and does not fall back to raw `repo sync`.

### One queued build — synchronize, configure and compile

Because Crave builds wait in a shared queue, the default path is one `crave run`, not a separate sync job followed by another compile job. The remote worker performs the following in order:

1. Reinitialize the existing Crave workspace to PixelOS `seventeen` with `--depth=1`.
2. Replace inherited local manifests with this repository's `zephyr.xml`.
3. Run `/opt/crave/resync.sh` to handle sync/checkout conflicts.
4. Clone the GitLab kernel prebuilt and vendor blobs using their actual remote default branches.
5. Prepare and register the `custom_zephyr` product, disable the old Android 16 `vendorsetup.sh`, and run `source build/envsetup.sh` plus `lunch custom_zephyr-cp2a-userdebug`.
6. Compile with `m pixelos` and print the generated ZIP path.

Run from the root of the Crave Clone in the Devspace VS Code terminal:

```bash
crave run --no-patch -- "curl -fsSL https://raw.githubusercontent.com/asxcaz/pos17-zephyr/main/scripts/crave-build.sh -o /tmp/pos17-crave-build.sh && bash /tmp/pos17-crave-build.sh"
```

The quoted command is executed on the queued build worker, not directly in the Devspace terminal. Do not run `repo init`, `repo sync`, `m`, or `mka` yourself in the Devspace terminal. Do not queue multiple Crave jobs at once.

Optional diagnostic-only run (sync + device preparation + product/lunch validation, but no compile):

```bash
crave run --no-patch -- "curl -fsSL https://raw.githubusercontent.com/asxcaz/pos17-zephyr/main/scripts/crave-build.sh -o /tmp/pos17-crave-build.sh && POS17_SKIP_BUILD=1 bash /tmp/pos17-crave-build.sh"
```

Use this only when debugging the product configuration, because it requires another queue entry if you later want to compile. It still runs the device prep and `lunch` checks so an invalid build target is caught before the full compile.

After a successful build, use the exact ZIP path printed in the Crave build log. From the same Devspace clone directory:

```bash
crave pull out/target/product/*/*.zip
```

Crave documentation warns not to use `--clean`, `make clean`, or `rm -rf out` for ordinary retries. These remove incremental build progress and waste shared queue time. Secure the previous build's ZIP before starting another build.

## Device-porting caution

The upstream device tree's `vendorsetup.sh` applies an Android 16 QPR2 IMS dependency and fixed framework/Aperture cherry-picks. The build script disables it locally for now; these changes must be reviewed and ported individually for Android 17 rather than blindly cherry-picked.

The build script only edits the checked-out Crave build workspace. It does not push commits into the upstream OPlus repositories.

## GitHub Actions preflight

Workflow: [Upstream preflight](https://github.com/asxcaz/pos17-zephyr/actions/workflows/preflight.yml)

It validates shell syntax and manifest XML, prints `df -h` and `df -i`, shallow-clones the six upstream repositories, checks default branches and required device files, then removes temporary clones. One successful run measured about 87 GiB available on a 145 GiB GitHub-hosted runner. That is a measurement from that run, not a permanent capacity guarantee.

These checks reduce avoidable source/configuration problems; they do not prove that the Android 17 tree compiles, boots, or has working hardware.

## References

- [Crave docs](https://foss.crave.io/docs/)
- [Crave CLI README](https://github.com/accupara/crave/blob/master/README.md)
- [PixelOS build guide](https://blog.pixelos.net/docs/maintainers/guide/building-pixelos/)
- [Zephyr device organization README](https://github.com/oplus-mt6895/.github/blob/main/profile/README.md)
- [Crave build workflow guide](https://fosson.top/crave/getting-started/building-crave-run)
- [Crave rules](https://fosson.top/crave/rules)
