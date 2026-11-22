# GOO NPR — GOO Engine 4.4 features for Blender 5.2

[![build](https://github.com/Toobe53/goo-port/actions/workflows/build.yml/badge.svg)](https://github.com/Toobe53/goo-port/actions/workflows/build.yml)

**New here?** Start with the bilingual [user tutorial](docs/tutorial.md), then use the
[CLI reference](docs/cli.md) for exact options.

Portable, pure-Python re-implementation of the features DillonGoo Studios added to
**GOO Engine 4.4** (a Blender fork that renders with EEVEE Legacy and omits Cycles).
The port targets **Blender 5.2** only and is split into two parts:

| Part | What it is | How it is used |
| --- | --- | --- |
| `goo_npr` | Blender add-on (no compiled extensions) | Install the folder as an add-on; 22 GOO node groups (17 shader + 2 geometry + 3 compositor), light-group UI and tools appear in Blender |
| `goo` | External CLI + Tk GUI (standard library only) | Multi-pass rendering, light-group decomposition, compositing, installing/bundling |

Everything lives in this repository, so the project is portable: copy the folder,
run `python -m goo install --blender "…/blender.exe"` on any machine with Blender 5.2.

```
goo-port/
├─ goo_npr/          Blender add-on package
├─ goo/              external CLI package (`goo` command)
├─ docs/             bilingual documentation
└─ tests/            headless verification scripts
```

## Quick start

```bash
# 1. install the add-on into any Blender 5.2 installation (headless, idempotent)
python -m goo install --blender "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"

# 2. check the environment, the add-on and the node library
python -m goo doctor
python -m goo nodes

# 3. render every light group to its own EXR and composite them
python -m goo render scene.blend --light-groups -o out/passes
python -m goo composite out/passes --png

# 3b. GOO's Render burn-in: file name + frame burned into a PNG beauty
python -m goo render scene.blend -o out/still --format png --burn-in

# 4. optional Tk GUI and add-on zip
python -m goo gui
python -m goo bundle
python -m goo bundle --source   # reproducible source/docs/tests zip
python -m goo verify            # check dist/SHA256SUMS and archive members

# 5. verification: 82 add-on checks in Blender, 17 CLI smoke/e2e tests,
#    13 portable path/discovery tests on the host Python
blender --factory-startup --background --python tests/test_addon.py
python tests/test_cli.py
python tests/test_paths.py
```

Inside Blender: `Node Editor ▸ Add ▸ GOO Engine`, `Properties ▸ Scene ▸ GOO Light Groups`,
`Properties ▸ View Layer ▸ GOO View Layer Overrides`, `3D Viewport ▸ Sidebar ▸ GOO`.

## What is ported, and how

The full feature-by-feature analysis is in [docs/features.md](docs/features.md); the
source-verified GOO 4.4 diff is in [docs/goo44-source-diff.md](docs/goo44-source-diff.md);
the subsystem analysis and evidence basis are in [docs/analysis.md](docs/analysis.md); the
honest differences to GOO Engine are listed in [docs/compatibility.md](docs/compatibility.md);
the measured evidence is in [docs/verification.md](docs/verification.md). The optional
renderer-level patch plan is in [docs/native-extension.md](docs/native-extension.md).

Short version:

* **Node groups (17 shader + 2 geometry + 3 compositor)** — Shader Info, Curvature, Light
  Info and Light Info New, Set Depth, Screen Space Info, Twirl, Water Ripples, Hex Grid, four
  SDF groups (Primitive, Op, Vector Op, Noise), OKLab Mix and OKLab Color Ramp, Scene Time
  (with Start/End Frame kept in sync by a frame handler), Active Camera (camera-override
  switch), Depth Fade and Threshold Mask, plus Line Composite, Kuwahara NPR and Depth Fog for
  the compositor. Where Blender 5.2 cannot expose EEVEE-internal data (cast vs. self shadows,
  shader depth writes), the group uses the closest public inputs (AO, Camera Data View Z) and
  the deviation is documented in the node description and in `docs/compatibility.md`.
* **Light Groups** — GOO's name-based groups are rebuilt on Blender 5.2's native light
  linking (`Light.light_linking.receiver_collection`), including per-group shadow
  toggles and empty-group handling. The CLI renders every group as its own pass and
  composites linearly: the result matches a single native render to **1e-6 mean** and a
  real `key+fill−ambient` reconstruction to **0.12 %** of the reference frame.
* **CLI** — headless multi-pass rendering (beauty per light group, depth/shadow passes),
  `--camera` render override, linear compositing, per-view-layer overrides,
  install/bundle (plugin and source zips), config, and a Tk GUI. Pure standard library, no `bpy` import.
* **Tools** — GP auto-close, texture randomize and stroke smoothing, F-Curve isolation,
  viewport line width, collection force-enable, topology mirror, scene camera,
  film-transparent toggle, and a **GOO Pose** sidebar with isolate-bones, Copy Rotation
  Invert All, merge-constraints and the `hide_outliner` flag helpers.
* **Coverage** — all 49 comparable GOO behaviours are now implemented (9 ported, 1 native,
  25 approximated, 14 N/A as C++ internals, **0 not shipped**). Renderer-internal features
  (shadow IDs, holdout alpha, refraction buffers) remain N/A. Render burn-in ships through
  `goo render --burn-in`; camera override through the `GOO Active Camera` group and
  `goo render --camera`; GP sculpt smoothing through `goo.gp_smooth_strokes`; the Outliner
  flag through `goo.pose_outliner_flag` (row filtering has no Python hook in 5.2).

## Documentation

| Document | Contents |
| --- | --- |
| [docs/tutorial.md](docs/tutorial.md) | step-by-step user tutorial: install, Blender UI, CLI/GUI workflows, troubleshooting (EN + ZH) |
| [docs/analysis.md](docs/analysis.md) | GOO 4.4 vs. Blender: what changed per subsystem, evidence, portability verdict |
| [docs/goo44-source-diff.md](docs/goo44-source-diff.md) | source-verified GOO 4.4 diff: files, nodes, sockets, Light Group bit packing, per-light formulas |
| [docs/goo44-source-manifest.txt](docs/goo44-source-manifest.txt) | 178 source-only + 159 source-changed paths behind that analysis |
| [docs/features.md](docs/features.md) | 49-item matrix: ported / approx / CLI / N/A |
| [docs/feature-matrix.json](docs/feature-matrix.json) | machine-readable export of the same 49 rows and status counts |
| [docs/compatibility.md](docs/compatibility.md) | exact formulas, limitations, and what each approximation means |
| [docs/architecture.md](docs/architecture.md) | add-on + CLI internals, entry points, how to extend |
| [docs/cli.md](docs/cli.md) | CLI reference, pipelines, workflows (EN + ZH) |
| [docs/install.md](docs/install.md) | add-on zip/CLI installation, upgrade, troubleshooting (EN + ZH) |
| [docs/verification.md](docs/verification.md) | all measured evidence and reproduction commands |
| [docs/native-extension.md](docs/native-extension.md) | optional C++ patch plan for renderer-level semantics |


## Requirements

* Blender **5.2** (5.2.3 LTS tested), which ships Python 3.13.
* Python **3.10+** for the external CLI (standard library only, `numpy` optional for
  compositing; Blender's bundled Python already includes it).

## License

GPL-3.0-or-later, matching Blender and GOO Engine.

---

# GOO NPR — 在 Blender 5.2 中重写 GOO Engine 4.4 的全部增强功能

本项目用**纯 Python Blender 插件 + 外置命令行程序**重写 DillonGoo Studios 在
**GOO Engine 4.4**（基于 EEVEE Legacy 的 Blender 分支，不含 Cycles）中新增/改动的功能，
只支持 **Blender 5.2**，不包含任何编译扩展，因此可整目录拷贝、跨机器安装。

* `goo_npr`：Blender 插件，提供 GOO 风格节点组、Light Groups 面板与工具。
* `goo`：外置 CLI/Tk GUI，负责逐灯光组多 pass 渲染、合成、安装与打包。

功能逐条对照见 [docs/features.md](docs/features.md)，子系统级差异分析见
[docs/analysis.md](docs/analysis.md)，与 GOO Engine 的真实差异（无法 1:1 的原因与替代
方案）见 [docs/compatibility.md](docs/compatibility.md)，可选 C++ 原生补丁方案见
[docs/native-extension.md](docs/native-extension.md)。

快速开始：

```bash
python -m goo install --blender "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
python -m goo doctor
python -m goo render scene.blend --light-groups -o out/passes
python -m goo composite out/passes --png
python -m goo render scene.blend -o out/still --format png --burn-in
python -m goo render scene.blend -o out/alt --camera DemoCam
python -m goo gui
python -m goo bundle
```

Blender 内：`节点编辑器 ▸ 添加 ▸ GOO Engine`、`属性 ▸ 场景 ▸ GOO Light Groups`、
`属性 ▸ 视图层 ▸ GOO View Layer Overrides`、`3D 视图 ▸ 侧栏 ▸ GOO`。

覆盖范围（逐条见 [docs/features.md](docs/features.md)）：49 个对照条目中 9 项完整移植、
1 项 5.2 原生、25 项近似、14 项属于 C++ 内部无法触达、0 项未实现。Outliner 隐藏骨骼标记
通过 `goo.pose_outliner_flag` 与 ID 属性复刻（5.2 无 Outliner 行过滤钩子，原版 4.4 公开分支
也只存标记、无消费者）。
近似项的具体公式与偏差都写在节点描述和 [docs/compatibility.md](docs/compatibility.md)；
实测数据（含 1e-6 级别的灯光组可加性、Render burn-in 落图）见 [docs/verification.md](docs/verification.md)。

许可：GPL-3.0-or-later（与 Blender、GOO Engine 一致）。
