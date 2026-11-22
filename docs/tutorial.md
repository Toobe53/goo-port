# 使用教程 / User Tutorial

本教程面向第一次使用 **GOO NPR** 的用户，覆盖安装、Blender 内操作、CLI/GUI 工作流、常见问题和从源码验证。完整的命令参考见 [CLI 文档](cli.md)，功能逐项说明见 [功能矩阵](features.md)，与 GOO Engine 的差异见 [兼容性说明](compatibility.md)。

This tutorial is for first-time users of **GOO NPR**. It covers installation, the
Blender UI, CLI/GUI workflows, troubleshooting, and verification from source. See the
[CLI reference](cli.md) for every option, the [feature matrix](features.md) for what is
implemented, and [compatibility](compatibility.md) for the honest differences from GOO Engine.

---

## 中文

### 1. 这是什么

GOO NPR 把 GOO Engine 4.4 中与 NPR 渲染相关的功能，以**纯 Python** 的方式近似移植到
**Blender 5.2**，由两部分组成：

| 部分 | 作用 | 使用方式 |
| --- | --- | --- |
| `goo_npr` | Blender 插件，无编译扩展 | 安装 zip 后，Blender 内出现 22 个 GOO 节点组、灯光组面板和 GOO 工具 |
| `goo` | 外置 CLI + Tk GUI | 无头多 pass 渲染、灯光组拆分、合成、安装/打包/校验 |

它不是 GOO Engine 的 C++ 渲染器分支，也不修改 Blender 二进制。节点组、Light Groups、
合成器和工具都是 Blender 5.2 的公开 Python/几何节点能力重建的；无法从 Python 触达的
渲染器内部行为（例如 shadow ID、holdout alpha、折射缓冲）在兼容性文档中明确标为 N/A。

### 2. 系统要求

- **Blender 5.2.x**（5.2.0 及以上；推荐 5.2.3 LTS）。Blender 4.x 不受支持。
- **Python 3.10+**，仅用于外置 CLI/GUI；插件本身在 Blender 自带 Python 中运行。
- Windows 10/11、macOS 12+（Apple Silicon 或 Intel）或主流 Linux 桌面。
- 渲染需要 EEVEE（Blender 5.2 的 EEVEE Next）；本项目不依赖 Cycles。
- CLI 只使用 Python 标准库，不需要 `pip install` 任何第三方包。

### 3. 安装

#### 3.1 推荐：安装发布 zip

1. 从 GitHub Releases 下载 `goo_npr-0.1.0.zip`；也可以在 **Actions ▸ build** 的
   `goo-port-<platform>` Artifacts 中下载该 zip。
2. 打开 Blender 5.2，选择 **Edit ▸ Preferences ▸ Add-ons**。
3. 点击右上角下拉菜单，选择 **Install from Disk…**。
4. 选中 `goo_npr-0.1.0.zip`，勾选启用 **GOO NPR**。
5. 打开 **Node Editor**，按 `Shift+A`，应能看到 **GOO Engine** 子菜单。
6. 打开 **Properties ▸ Scene**，应能看到 **GOO Light Groups** 面板。

不要解压 zip 后只复制其中一层目录；Blender 的原生安装器需要 zip 本身。

#### 3.2 从源码安装插件

在源码目录（含 `goo_npr/` 和 `goo/` 的目录）运行：

```bash
# Windows
python -m goo install --blender "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"

# macOS
python -m goo install --blender "/Applications/Blender.app/Contents/MacOS/Blender"

# Linux
python -m goo install --blender "/usr/bin/blender"
```

常用选项：

```bash
python -m goo install --dry-run --json       # 只显示会写入哪些文件
python -m goo install --no-enable            # 安装但不自动启用
python -m goo install --target "<scripts>/addons" --no-enable
```

安装是幂等的：重复执行会替换旧副本，不会产生重复插件。安装后重启 Blender，或卸载再启用
一次插件。

#### 3.3 验证安装

```bash
python -m goo doctor
python -m goo nodes
```

`doctor` 会报告 Blender 版本、插件路径、插件版本和节点库数量；`nodes` 列出 22 个 GOO
节点组。正常输出中应看到 `GOO Active Camera`、`GOO Light Info New`、`GOO Scene Time`、
`GOO Line Composite` 等名称。

### 4. Blender 内使用

#### 4.1 节点组

在 Shader Editor、Geometry Node Editor 或 Compositor 中：

1. 按 `Shift+A` 打开添加菜单。
2. 进入 **GOO Engine**。
3. 选择需要的节点组。

主要节点组：

- **Shader**：Shader Info、Curvature、Light Info、Light Info New、Set Depth、
  Screen Space Info、Twirl、Water Ripples、Hex Grid、SDF Primitive/Op/Vector Op/Noise、
  OKLab Mix、OKLab Color Ramp、Depth Fade、Threshold Mask、Scene Time、Active Camera。
- **Geometry**：Scene Time、Active Camera。
- **Compositor**：Line Composite、Kuwahara NPR、Depth Fog。

其中 **GOO Active Camera** 用 `Switch` 在“场景相机”和“覆盖相机”之间选择；输入
`Ignore Scene Override` 默认开启。它适合在节点树里做相机覆盖，而不是修改场景设置。

节点组的中文标签/描述会随 Blender 语言切换；若显示英文，检查
**Preferences ▸ Interface ▸ Translation** 是否启用了简体中文。

#### 4.2 Light Groups

1. 打开 **Properties ▸ Scene ▸ GOO Light Groups**。
2. 新建组，例如 `key`、`fill`、`ambient`。
3. 在场景中选中灯光，在灯光属性或 GOO 面板中把它分配到对应组。
4. 每个组可以单独控制是否投射阴影；空组会被安全跳过。

Light Groups 使用的是 Blender 5.2 原生的 light linking（`Light.light_linking`），所以
它不需要修改渲染器。CLI 的 `--light-groups` 会为每个非空组渲染一张 pass，再线性合成。

#### 4.3 GOO 工具

- **3D Viewport ▸ Sidebar ▸ GOO**：场景相机、film transparent、collection force-enable、
  拓扑镜像、viewport line width 等。
- **GOO Pose**：隔离骨骼、Copy Rotation Invert All、合并约束、`hide_outliner` 标记。
- **GP（Grease Pencil）**：自动闭合、纹理随机化、笔划平滑（拉普拉斯平滑，可设
  factor/iterations，开放笔划保留端点）。
- **F-Curve**：只显示/隔离当前对象的曲线。

这些工具都是操作当前选择或当前对象；先选中对象再执行。

### 5. 外置 CLI

#### 5.1 基本命令

在源码目录直接运行 `python -m goo ...`；也可以安装 wheel 后直接运行 `goo ...`：

```bash
# 任选其一：源码目录运行，或安装构建好的 wheel
python -m goo version
python -m pip install goo_port-0.1.0-py3-none-any.whl
goo version
```

`--json` 适合脚本消费；机器 JSON 始终是 ASCII 安全的，中文控制台不会因 cp936/GBK
编码而出现乱码。

#### 5.2 多 pass 灯光组工作流

```bash
# 1. 确认场景里已有 GOO 灯光组
python -m goo doctor scene.blend

# 2. 为每个灯光组渲染一张 EXR pass（key/fill/ambient 各自一张）
python -m goo render scene.blend --light-groups -o out/passes --format exr

# 3. 线性合成，输出 PNG 预览和 EXR
python -m goo composite out/passes --png

# 4. 如果只要单张 beauty，不加 --light-groups
python -m goo render scene.blend -o out/still --format png
```

#### 5.3 相机、视图层与烧录

```bash
# 用指定相机渲染
python -m goo render scene.blend --camera "Camera.Key" -o out/key

# 只渲染指定 View Layer
python -m goo render scene.blend --view-layer "ViewLayer" -o out/layer

# GOO 的 burn-in：把文件名和帧号烧进 PNG
python -m goo render scene.blend -o out/frame --format png --burn-in
```

约束：

- `--burn-in` 只支持 PNG；与 `--format exr` 或 `--light-groups` 同用会以退出码 2 报错。
- `--camera` 指定的对象必须存在；错误信息会列出可用相机名。
- `--view-layer` 指定的层必须存在；不存在时退出码 4，并列出可用层。

#### 5.4 GUI

```bash
python -m goo gui
```

GUI 提供与 CLI 相同的核心选项：输入/输出、相机、View layer、灯光组、格式、samples、
分辨率百分比、burn-in、Verify 按钮。没有桌面环境（例如服务器）时请使用 CLI。

#### 5.5 打包、安装与发布校验

```bash
# 构建 Blender 插件 zip（默认 dist/goo_npr-0.1.0.zip）
python -m goo bundle

# 构建可复现的源码/文档/测试包
python -m goo bundle --source

# 校验 dist/SHA256SUMS 与归档必需成员
python -m goo verify
```

`goo verify` 会逐文件重算 SHA-256，并检查 wheel/source 中是否包含运行所需模块；失败时
退出码为 2，适合放在 CI 的发布门禁里。

### 6. 典型工作流：从场景到合成

```bash
# 1. 安装插件并确认节点库
python -m goo install --blender "<Blender 路径>"
python -m goo doctor

# 2. 应用 GOO 节点库到场景（如果场景是空库）
python -m goo apply scene.blend -o scene_goo.blend

# 3. 渲染灯光组 pass
python -m goo render scene_goo.blend --light-groups -o out/passes --samples 64

# 4. 合成
python -m goo composite out/passes --png

# 5. 需要单张成片时
python -m goo render scene_goo.blend -o out/beauty --camera "Camera" --format png
```

### 7. 常见问题

**Blender 里找不到 GOO 菜单。**
确认 Blender 版本是 5.2.x；在 Preferences ▸ Add-ons 中确认 **GOO NPR** 已勾选；查看
Blender 控制台是否有插件注册错误。也可以运行 `python -m goo install --blender ...`
重新安装。

**`goo doctor` 报 Blender not found。**
用 `--blender` 指向可执行文件；Windows 一般在
`C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`，macOS 在
`/Applications/Blender.app/Contents/MacOS/Blender`。也可以设置 `GOO_BLENDER` 环境变量。

**渲染报 EEVEE/引擎错误。**
本项目只支持 EEVEE；请把 Render Engine 设为 EEVEE。无 GPU 的 Linux 服务器需要可用的
OpenGL/EGL 软件渲染环境，或改用有桌面/GPU 的机器。

**灯光组渲染结果和预期不同。**
检查灯光是否已分配到组、组是否为空、是否启用了原生 light linking；先用
`goo doctor scene.blend` 查看组和 pass 数。合成默认是线性相加，不包含 tone mapping。

**Windows 控制台中文乱码。**
CLI 的 `--json` 输出是 ASCII 安全的；普通文本输出可先执行 `chcp 65001`，或把输出重定向
到 UTF-8 文件。

**安装后升级/卸载。**
重新执行 `goo install` 即可覆盖升级；卸载在 Preferences ▸ Add-ons 中点击 Remove。CLI 的
`--target` 安装可以用 `--dry-run` 先确认目标目录。

### 8. 从源码开发与测试

```bash
# 纯 Python 测试（不需要 Blender）
python tests/test_paths.py
python tests/test_cli.py          # 没有 Blender 时，依赖 Blender 的用例会 skip

# 插件测试（需要 Blender 5.2）
blender --background --factory-startup --python tests/test_addon.py
```

测试基线：插件 **82 checks**、CLI **17 tests**、路径 **13 tests**；完整的实测记录见
[验证报告](verification.md)。源码包是自包含的：解压后设置 `PYTHONPATH` 即可运行
`python -m goo`，并能用 `goo bundle` / `goo bundle --source` 复现发布包。

GitHub Actions 在 Windows x64、Linux x64、macOS arm64 上构建并运行 Blender 集成测试；
在 **Actions ▸ build** 页面可下载 `goo-port-<platform>` 产物，正式版本见 **Releases**。

### 9. 与 GOO Engine 的差异

本项目是**近似层**，不是 GOO Engine 的完整渲染器分支。49 项可比行为全部有落点
（Ported 9 / Native 1 / Approx 25 / N/A 14 / Not shipped 0），但以下内容仍与原生 GOO
不同：

- 渲染器内部的 shadow ID、holdout alpha、折射缓冲等没有 Python 入口，标为 N/A。
- Active Camera 用节点组/`--camera` 近似，不修改 `scene->gn_camera_override`。
- Outliner 的 `hide_outliner` 只保留数据模型和标记，Blender 5.2 没有 Outliner 行过滤钩子。
- 需要真正渲染器级行为时，见 [原生扩展方案](native-extension.md)。

### 10. 许可

项目以 **GPL-3.0-or-later** 发布；详见仓库根目录的 `LICENSE`。

---

## English

### 1. What this is

GOO NPR is a portable, pure-Python approximation of the NPR-related features that
DillonGoo Studios added to **GOO Engine 4.4**, targeting **Blender 5.2**:

| Part | Role | How to use |
| --- | --- | --- |
| `goo_npr` | Blender add-on, no compiled extension | Install the zip; 22 GOO node groups, light-group panels and GOO tools appear in Blender |
| `goo` | External CLI + Tk GUI | Headless multi-pass render, light-group decomposition, compositing, install/bundle/verify |

It is not a C++ renderer fork and does not patch Blender. The node groups, Light Groups,
compositor nodes and tools are rebuilt on Blender 5.2's public Python/geometry-node APIs.
Renderer-internal behaviour that Python cannot reach (shadow IDs, holdout alpha,
refraction buffers) is explicitly listed as N/A in the compatibility document.

### 2. Requirements

- **Blender 5.2.x** (5.2.0 or newer; 5.2.3 LTS recommended). Blender 4.x is not supported.
- **Python 3.10+** for the external CLI/GUI only. The add-on runs in Blender's bundled Python.
- Windows 10/11, macOS 12+ (Apple Silicon or Intel), or a mainstream Linux desktop.
- Rendering uses EEVEE (EEVEE Next in Blender 5.2); Cycles is not required.
- The CLI uses only the Python standard library, with no third-party runtime dependency.

### 3. Installation

#### 3.1 Recommended: install the release zip

1. Download `goo_npr-0.1.0.zip` from **GitHub Releases**, or from the
   `goo-port-<platform>` artifact of the **Actions ▸ build** workflow.
2. Open Blender 5.2 and go to **Edit ▸ Preferences ▸ Add-ons**.
3. Open the top-right dropdown and choose **Install from Disk…**.
4. Select `goo_npr-0.1.0.zip` and enable **GOO NPR**.
5. In the **Node Editor**, press `Shift+A`; the **GOO Engine** submenu should appear.
6. In **Properties ▸ Scene**, the **GOO Light Groups** panel should appear.

Do not unzip the archive and copy only one nested directory: Blender's native installer
expects the zip itself.

#### 3.2 Install the add-on from source

From the repository root (the directory containing `goo_npr/` and `goo/`):

```bash
# Windows
python -m goo install --blender "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"

# macOS
python -m goo install --blender "/Applications/Blender.app/Contents/MacOS/Blender"

# Linux
python -m goo install --blender "/usr/bin/blender"
```

Useful options:

```bash
python -m goo install --dry-run --json       # list files without writing
python -m goo install --no-enable            # install but do not enable
python -m goo install --target "<scripts>/addons" --no-enable
```

Installation is idempotent: re-running replaces the old copy instead of creating duplicates.
Restart Blender, or disable and re-enable the add-on, after installation.

#### 3.3 Verify

```bash
python -m goo doctor
python -m goo nodes
```

`doctor` reports the Blender version, add-on path/version and node-library count; `nodes`
lists the 22 GOO groups. You should see `GOO Active Camera`, `GOO Light Info New`,
`GOO Scene Time`, `GOO Line Composite`, and the rest.

### 4. Using it in Blender

#### 4.1 Node groups

In the Shader Editor, Geometry Node Editor or Compositor:

1. Press `Shift+A`.
2. Open **GOO Engine**.
3. Pick a group.

Highlights:

- **Shader**: Shader Info, Curvature, Light Info, Light Info New, Set Depth, Screen Space
  Info, Twirl, Water Ripples, Hex Grid, SDF Primitive/Op/Vector Op/Noise, OKLab Mix,
  OKLab Color Ramp, Depth Fade, Threshold Mask, Scene Time, Active Camera.
- **Geometry**: Scene Time, Active Camera.
- **Compositor**: Line Composite, Kuwahara NPR, Depth Fog.

**GOO Active Camera** switches between the scene camera and an override camera with a
`Switch` node. Its `Ignore Scene Override` input defaults to on. Use it inside a node tree
when you need camera override without changing scene settings.

Chinese labels/descriptions follow Blender's UI language. If they stay English, check
**Preferences ▸ Interface ▸ Translation** and enable Simplified Chinese.

#### 4.2 Light Groups

1. Open **Properties ▸ Scene ▸ GOO Light Groups**.
2. Create groups such as `key`, `fill`, `ambient`.
3. Select a light and assign it to a group in the light properties or the GOO panel.
4. Each group can control shadow casting; empty groups are skipped safely.

Light Groups use Blender 5.2's native light linking (`Light.light_linking`), so no renderer
patch is needed. `goo render --light-groups` renders one pass per non-empty group and
composites them linearly.

#### 4.3 GOO tools

- **3D Viewport ▸ Sidebar ▸ GOO**: scene camera, film-transparent toggle, collection
  force-enable, topology mirror, viewport line width.
- **GOO Pose**: isolate bones, Copy Rotation Invert All, merge constraints, `hide_outliner`
  flag helpers.
- **Grease Pencil**: auto-close, texture randomize, stroke smoothing (Laplacian, factor and
  iterations; open strokes keep their endpoints).
- **F-Curve**: show/isolate the active object's curves.

These tools operate on the current selection or active object; select something first.

### 5. External CLI

#### 5.1 Basics

Run `python -m goo ...` from the repository root, or install the wheel and run `goo ...`:

```bash
# Either run from the source tree, or install the built wheel:
python -m goo version
python -m pip install goo_port-0.1.0-py3-none-any.whl
goo version
```

`--json` is intended for scripts; machine JSON is ASCII-safe, so Chinese console code pages
(CP936/GBK) cannot corrupt it.

#### 5.2 Multi-pass light-group workflow

```bash
# 1. Confirm the scene has GOO light groups
python -m goo doctor scene.blend

# 2. Render one EXR pass per group (key/fill/ambient)
python -m goo render scene.blend --light-groups -o out/passes --format exr

# 3. Composite linearly, with PNG preview and EXR
python -m goo composite out/passes --png

# 4. Single beauty render (no --light-groups)
python -m goo render scene.blend -o out/still --format png
```

#### 5.3 Camera, view layer and burn-in

```bash
# Render with a named camera
python -m goo render scene.blend --camera "Camera.Key" -o out/key

# Render only a named view layer
python -m goo render scene.blend --view-layer "ViewLayer" -o out/layer

# GOO burn-in: file name and frame number in the PNG
python -m goo render scene.blend -o out/frame --format png --burn-in
```

Rules:

- `--burn-in` is PNG-only; using it with `--format exr` or `--light-groups` exits 2.
- `--camera` must name an existing object; the error lists available camera names.
- `--view-layer` must name an existing layer; otherwise it exits 4 and lists available layers.

#### 5.4 GUI

```bash
python -m goo gui
```

The GUI exposes the same core options as the CLI: input/output, camera, view layer, light
groups, format, samples, resolution percentage, burn-in and a Verify button. On a headless
server, use the CLI instead.

#### 5.5 Bundling, installation and release verification

```bash
# Build the Blender add-on zip (default: dist/goo_npr-0.1.0.zip)
python -m goo bundle

# Build the reproducible source/docs/tests archive
python -m goo bundle --source

# Check dist/SHA256SUMS and required archive members
python -m goo verify
```

`goo verify` re-hashes every file and checks that the wheel/source contain the modules needed
at runtime. It exits 2 on failure, so it can be used as a CI release gate.

### 6. Typical end-to-end workflow

```bash
# 1. Install the add-on and confirm the node library
python -m goo install --blender "<Blender path>"
python -m goo doctor

# 2. Apply the GOO node library to an existing scene, if needed
python -m goo apply scene.blend -o scene_goo.blend

# 3. Render light-group passes
python -m goo render scene_goo.blend --light-groups -o out/passes --samples 64

# 4. Composite
python -m goo composite out/passes --png

# 5. Optional single beauty frame
python -m goo render scene_goo.blend -o out/beauty --camera "Camera" --format png
```

### 7. Troubleshooting

**No GOO menu in Blender.**
Check that Blender is 5.2.x, that **GOO NPR** is enabled in Preferences ▸ Add-ons, and that
the Blender console has no add-on registration error. Re-run
`python -m goo install --blender ...` if needed.

**`goo doctor` says Blender not found.**
Pass `--blender` explicitly. On Windows this is usually
`C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`; on macOS,
`/Applications/Blender.app/Contents/MacOS/Blender`. You can also set `GOO_BLENDER`.

**Render fails with an EEVEE/engine error.**
This project targets EEVEE only. Set the render engine to EEVEE. Headless Linux needs a
working OpenGL/EGL software or hardware stack; otherwise use a machine with a desktop/GPU.

**Light-group output looks wrong.**
Check that lights are assigned to groups, that the groups are not empty, and that native
light linking is enabled. Run `goo doctor scene.blend` to inspect groups and pass counts.
Compositing is linear addition by default, without tone mapping.

**Chinese text is garbled on Windows.**
`--json` output is ASCII-safe. For human-readable output, run `chcp 65001` or redirect to a
UTF-8 file.

**Upgrade/uninstall.**
Re-run `goo install` to replace the add-on; uninstall via Preferences ▸ Add-ons ▸ Remove.
For `--target` installs, use `--dry-run` to confirm the destination first.

### 8. Development and tests

```bash
# Pure-Python tests (no Blender required)
python tests/test_paths.py
python tests/test_cli.py          # Blender-dependent cases skip if Blender is absent

# Add-on tests (requires Blender 5.2)
blender --background --factory-startup --python tests/test_addon.py
```

Baseline: **82 add-on checks**, **17 CLI tests**, **13 path tests**. See the
[verification report](verification.md) for measured evidence. The source archive is
self-contained: unzip it, set `PYTHONPATH`, and `python -m goo` plus both
`goo bundle` variants work without the original checkout.

GitHub Actions builds and runs the Blender integration tests on Windows x64, Linux x64 and
macOS arm64. Download the `goo-port-<platform>` artifact from **Actions ▸ build**, or use the
tagged files under **Releases**.

### 9. Differences from GOO Engine

This is an approximation layer, not a full GOO Engine renderer fork. All 49 comparable
behaviours have a landing point (Ported 9 / Native 1 / Approx 25 / N/A 14 / Not shipped 0),
with these honest differences:

- Renderer-internal shadow IDs, holdout alpha, and refraction buffers have no Python entry
  point and remain N/A.
- Active Camera is approximated with a node group / `--camera`; it does not set
  `scene->gn_camera_override`.
- The Outliner `hide_outliner` data model and flag are preserved, but Blender 5.2 exposes no
  Outliner row-filter hook.
- For true renderer-level behaviour, see the [native extension plan](native-extension.md).

### 10. License

Released under **GPL-3.0-or-later**; see `LICENSE` at the repository root.
