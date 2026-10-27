# PixelOS Android 17 for Zephyr (MT6895)

这是一个面向 Crave.io 网页 Devspace / VS Code 终端的个人移植工作区。ROM 基础为 PixelOS `seventeen`，设备树目标为 OPlus/MediaTek `zephyr`。

> 当前状态：预检与脚本骨架。不是已验证可启动的 ROM；只有 GitHub Actions 的浅克隆/配置检查通过后，才建议排 Crave 完整编译。

## 设备与源码约定

- PixelOS manifest: `https://github.com/PixelOS-AOSP/android_manifest.git`, branch `seventeen`
- Product target: `custom_zephyr-cp2a-userdebug`
- Device tree: `oplus-mt6895/android_device_oplus_zephyr`，使用其当前默认分支 `lineage-24.0`
- MediaTek vendor sepolicy: `oplus-mt6895/android_device_mediatek_sepolicy_vndr`，默认分支 `lineage-24.0`
- MediaTek hardware: `oplus-mt6895/android_hardware_mediatek`，默认分支 `lineage-24.0`
- OPlus hardware: `oplus-mt6895/android_hardware_oplus`，默认分支 `lineage-23.2`

设备树还需要预编译内核与设备 vendor blobs。Crave 构建脚本会尝试从迁移后的 GitLab URL 克隆它们，并以远端默认分支为准：

- `https://gitlab.com/almightygodthor/android_device_oplus_zephyr-kernel.git`
- `https://gitlab.com/almightygodthor/proprietary_vendor_oplus_zephyr.git`

这些 GitLab URL 会在 GitHub Actions 中做浅克隆及必需文件检查。如果仓库改址、权限或默认分支有变化，先修正检查结果，不要猜测分支名。

## GitHub Actions 预检做什么

`.github/workflows/preflight.yml` 会在 push、PR 和手动触发时：

1. 打印 Runner 的 `df -h` / `df -i`，便于记录实际磁盘空间；
2. 检查 shell 脚本语法、XML 格式和 local manifest 中的设备仓库配置；
3. 用浅克隆验证设备树、三个 GitHub 依赖及两个 GitLab 仓库的可访问性、默认分支和关键文件；
4. 删除每个临时克隆，尽量避免累积占用 Actions 磁盘。

最近一次 Actions Runner 检查到根文件系统约 145 GiB、可用空间约 87 GiB；这只是本次 Runner 的实测值，不应当视为 GitHub 对每次运行的固定保证。Android 全量源码不会在此 workflow 中同步，它只做小规模浅克隆检查。

这些测试只能降低明显的来源/配置错误，不能代替 Android 17 的 Soong 编译、启动测试或实机验证。

## Crave 用法

在 Crave 网页 Devspace 的 VS Code 终端里，先查看账户可用的项目：

```bash
crave clone list
```

创建或进入已存在的 PixelOS 工作区（项目 ID 必须取自你的账户实际列表；不要照抄网上示例 ID）：

```bash
crave clone create --projectID <PIXEL_OS_PROJECT_ID> /crave-devspaces/PixelOS-zephyr17
cd /crave-devspaces/PixelOS-zephyr17
```

将以下命令提交到 Crave 队列。确保当前目录是 Crave Clone 的 PixelOS 源码根目录：

```bash
crave run --no-patch -- "curl -fsSL https://raw.githubusercontent.com/asxcaz/pos17-zephyr/main/scripts/crave-build.sh | bash"
```

构建完成后，先在 Crave 构建日志中确认 ZIP 的实际路径，再使用 `crave pull` 拉取产物。不要为了重试直接加 `--clean`，也不要删除 `out/`，这样更容易保留增量构建成果。

## 当前移植注意事项

设备树自带的 `vendorsetup.sh` 会克隆 Android 16 QPR2 的 IMS，并向 frameworks / Aperture 应用固定 cherry-pick。它不会被自动当作 Android 17 补丁使用；构建脚本会在本地构建工作区中禁用它，避免首次加载 build env 时执行旧操作。

脚本会创建 PixelOS 产品文件 `custom_zephyr.mk`，并注册 `custom_zephyr` 产品。它只修改 Crave 工作区中的同步源码，不向设备树上游仓库推送提交。

## 参考资料

- [Crave 官方文档](https://foss.crave.io/docs/)
- [Crave CLI](https://github.com/accupara/crave)
- [PixelOS Android 17 manifest](https://github.com/PixelOS-AOSP/android_manifest/tree/seventeen)
- [PixelOS 构建指南](https://blog.pixelos.net/docs/maintainers/guide/building-pixelos/)
- [Zephyr 设备组织说明](https://github.com/oplus-mt6895/.github/blob/main/profile/README.md)
