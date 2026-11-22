# SPDX-License-Identifier: GPL-3.0-or-later
"""Argument parsing and human readable output for the ``goo`` command.

The CLI itself is pure stdlib: every actual Blender operation happens inside a
child ``blender --background`` process (see :mod:`goo.blender`).  All subcommands
return a JSON-serialisable payload; ``--json`` prints that payload verbatim, the
default mode renders it as a compact report.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from typing import Any, Callable, Optional, Sequence

from . import REPO_ROOT, __version__
from . import pipeline
from .errors import (
    EXIT_INTERNAL,
    EXIT_NO_BLENDER,
    EXIT_OK,
    GooError,
    JobFailed,
    UsageError,
)
from .util import format_duration, human_bytes, json_dumps, plural, sanitize_text, shorten_path

PROG = "goo"

#: One line ``--help`` texts reuse the same bilingual hint style.
HINT_BLENDER = "Blender 5.2 executable (default: auto-detect) / Blender 5.2 可执行文件（默认自动检测）"
HINT_ADDON = "Directory containing goo_npr (default: this checkout) / 包含 goo_npr 的目录（默认为当前仓库）"


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the CLI and return the process exit code."""
    raw = list(sys.argv[1:] if argv is None else argv)
    json_mode = "--json" in raw
    raw = [arg for arg in raw if arg != "--json"]
    parser = build_parser()
    args = parser.parse_args(raw)
    args.json = json_mode
    try:
        payload = args.run(args)
    except GooError as exc:
        _report_error(exc, json_mode)
        return exc.code
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        _stderr("\ngoo: interrupted / 已中断")
        return 130
    except Exception as exc:  # noqa: BLE001 - last resort, never a bare traceback for users
        if os.environ.get("GOO_DEBUG"):
            traceback.print_exc()
        _stderr(f"goo: internal error: {type(exc).__name__}: {exc}")
        _stderr("hint: re-run with GOO_DEBUG=1 for a traceback / 设置 GOO_DEBUG=1 查看详细堆栈")
        return EXIT_INTERNAL

    if json_mode:
        print(json_dumps(payload, pretty=True, ensure_ascii=True))
    else:
        try:
            _print_payload(args.command, payload)
        except BrokenPipeError:  # pragma: no cover - piped output
            pass
    if args.command == "doctor" and args.blend and (payload.get("inspect") is None):
        return 4
    if args.command == "verify" and not payload.get("ok"):
        return 2
    return EXIT_OK


def _stderr(message: str) -> None:
    try:
        print(sanitize_text(message), file=sys.stderr)
    except (UnicodeEncodeError, OSError):  # pragma: no cover - legacy console
        pass


def _report_error(exc: GooError, json_mode: bool) -> None:
    if json_mode:
        print(json_dumps(exc.as_dict(), pretty=True, ensure_ascii=True))
    else:
        _stderr(f"goo: error: {sanitize_text(exc.message)}")
        if exc.hint:
            _stderr(f"hint: {sanitize_text(exc.hint)}")
    if isinstance(exc, JobFailed) and exc.stderr_tail:
        if json_mode:
            return
        _stderr("")
        _stderr("--- Blender log (tail) ---")
        for line in exc.stderr_tail.splitlines()[-25:]:
            _stderr(f"  {line}")
        _stderr("--------------------------")


# ---------------------------------------------------------------------------
# argument definitions
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "GOO Port external CLI: NPR node library and light-group pass rendering for Blender 5.2.\n"
            "GOO Port 命令行工具：为 Blender 5.2 应用 NPR 节点库并渲染灯光组通道。"
        ),
        epilog=(
            "examples / 示例:\n"
            "  goo doctor\n"
            "  goo apply scene.blend -o scene_goo.blend\n"
            "  goo render scene.blend -o renders --light-groups --passes beauty depth\n"
            "  goo composite renders --png\n"
            "  goo install --dry-run\n"
            "\n--json may appear before or after the subcommand; -V/--version must come first.\n"
            "Exit codes: 0 ok, 2 usage/config, 3 Blender missing, 4 Blender job failed\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
    )
    parser.add_argument("--json", action="store_true", help="machine readable JSON on stdout / 输出 JSON")
    parser.add_argument("-V", "--version", action="version", version=f"goo {__version__}")
    parser.add_argument("-q", "--quiet", action="store_true", help=argparse.SUPPRESS)

    sub = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    # doctor ---------------------------------------------------------------
    p = sub.add_parser(
        "doctor",
        help="check Blender, the add-on and a .blend / 检查环境",
        description="Report the Blender install, the goo_npr add-on and (optionally) a scene summary.",
        allow_abbrev=False,
    )
    p.add_argument("blend", nargs="?", metavar="FILE.blend", help="optional scene to inspect / 可选：要检查的 .blend")
    p.add_argument("--blender", metavar="PATH", help=HINT_BLENDER)
    p.add_argument("--addon", metavar="DIR", help=HINT_ADDON)
    p.add_argument("--timeout", type=float, metavar="SEC", help="Blender timeout in seconds / 超时秒数")
    p.set_defaults(run=cmd_doctor)

    # nodes ----------------------------------------------------------------
    p = sub.add_parser(
        "nodes",
        help="list the node library (and GOO groups in a .blend) / 列出节点库",
        description="List registered GOO node groups. With a .blend, also list the GOO groups stored in it.",
        allow_abbrev=False,
    )
    p.add_argument("blend", nargs="?", metavar="FILE.blend", help="optional scene to inspect / 可选：要检查的 .blend")
    p.add_argument("--blender", metavar="PATH", help=HINT_BLENDER)
    p.add_argument("--addon", metavar="DIR", help=HINT_ADDON)
    p.add_argument("--timeout", type=float, metavar="SEC", help="Blender timeout in seconds / 超时秒数")
    p.set_defaults(run=cmd_nodes)

    # apply ----------------------------------------------------------------
    p = sub.add_parser(
        "apply",
        help="build GOO node groups and sync light groups / 应用节点库并同步灯光组",
        description="Register goo_npr in a headless session, build/refresh every GOO node group and save the file.",
        allow_abbrev=False,
    )
    p.add_argument("blend", metavar="FILE.blend", help="scene to process / 要处理的 .blend")
    p.add_argument("-o", "--out", metavar="OUT.blend", help="write here instead of the input / 输出文件")
    p.add_argument("--in-place", action="store_true", help="overwrite FILE.blend (keeps a .bak) / 原地保存并备份")
    p.add_argument("--no-build", action="store_true", help="only sync light groups / 仅同步灯光组")
    p.add_argument("--blender", metavar="PATH", help=HINT_BLENDER)
    p.add_argument("--addon", metavar="DIR", help=HINT_ADDON)
    p.add_argument("--timeout", type=float, metavar="SEC", help="Blender timeout in seconds / 超时秒数")
    p.set_defaults(run=cmd_apply)

    # render ---------------------------------------------------------------
    p = sub.add_parser(
        "render",
        help="render beauty passes per light group / 渲染灯光组通道",
        description=(
            "Render one beauty image per light group (plus ambient/utility passes). "
            "Writes manifest.json describing everything."
        ),
        allow_abbrev=False,
    )
    p.add_argument("blend", metavar="FILE.blend", help="scene to render / 要渲染的 .blend")
    p.add_argument("-o", "--out", metavar="DIR", help="output directory / 输出目录")
    p.add_argument(
        "--passes",
        nargs="+",
        metavar="PASS",
        default=["beauty"],
        help=f"passes to render: {', '.join(pipeline.RENDER_PASSES)} (default: beauty)",
    )
    p.add_argument("--light-groups", dest="light_groups", action="store_true", help="one beauty pass per light group / 按灯光组渲染")
    p.add_argument("--no-light-groups", dest="light_groups", action="store_false", help="single combined beauty / 不分灯光组")
    p.add_argument("--samples", type=_positive_int, metavar="N", help="EEVEE render samples / 采样数")
    p.add_argument("--resolution-percentage", type=_percentage, metavar="N", help="resolution scale 1-1000 / 分辨率百分比")
    p.add_argument("--format", choices=("exr", "png"), help="beauty file format (data passes stay EXR) / 图像格式")
    p.add_argument(
        "--camera",
        metavar="NAME",
        help="render through another camera object without editing the .blend / 用指定相机渲染（不改动 .blend）",
    )
    p.add_argument(
        "--view-layer",
        metavar="NAME",
        help="render a named view layer (default: the first layer) / 渲染指定视图层（默认第一层）",
    )
    p.add_argument("--film-transparent", dest="film_transparent", action="store_true", default=None, help="transparent film / 透明背景")
    p.add_argument("--no-film-transparent", dest="film_transparent", action="store_false", help=argparse.SUPPRESS)
    p.add_argument("--no-ambient", dest="ambient", action="store_false", help="skip the ambient pass / 不渲染环境光通道")
    p.add_argument(
        "--burn-in",
        dest="burn_in",
        action="store_true",
        help="burn the blend file name and frame into the rendered beauty (native render stamp; PNG only) / 将文件名与帧号烙入图像（原生 render stamp，仅 PNG）",
    )
    p.add_argument("--blender", metavar="PATH", help=HINT_BLENDER)
    p.add_argument("--addon", metavar="DIR", help=HINT_ADDON)
    p.add_argument("--keep-temp", action="store_true", help="keep the job JSON in a temp dir / 保留临时任务文件")
    p.add_argument("--timeout", type=float, metavar="SEC", help="Blender timeout in seconds / 超时秒数")
    p.set_defaults(run=cmd_render, light_groups=False, ambient=True, burn_in=False)

    # composite ------------------------------------------------------------
    p = sub.add_parser(
        "composite",
        help="additively combine the rendered passes / 合成通道",
        description="Add the per-group beauty EXRs in linear space, optionally subtract ambient and apply the shadow matte.",
        allow_abbrev=False,
    )
    p.add_argument("out", metavar="DIR", help="directory written by `goo render` / render 输出目录")
    p.add_argument("--png", action="store_true", help="also write composite.png / 同时输出 PNG")
    p.add_argument("--no-exr", dest="exr", action="store_false", help="skip composite.exr / 不输出 EXR")
    p.add_argument("--exposure", type=float, default=0.0, metavar="E", help="exposure in stops / 曝光（档）")
    p.add_argument("--contrast", type=float, default=1.0, metavar="C", help="contrast around 0.18 (default 1.0) / 对比度")
    p.add_argument("--shadow", action="store_true", help="multiply the shadow matte / 乘以阴影通道")
    p.add_argument("--no-ambient", dest="subtract_ambient", action="store_false", help="do not subtract duplicate ambient / 不扣除重复环境光")
    p.add_argument("--basename", metavar="NAME", default="composite", help="output file stem (default composite) / 输出文件名")
    p.add_argument("--blender", metavar="PATH", help=HINT_BLENDER)
    p.add_argument("--keep-temp", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--timeout", type=float, metavar="SEC", help="Blender timeout in seconds / 超时秒数")
    p.set_defaults(run=cmd_composite, exr=True, subtract_ambient=True)

    # install --------------------------------------------------------------
    p = sub.add_parser(
        "install",
        help="install goo_npr into Blender's user add-ons / 安装插件到 Blender",
        description=(
            "Copy goo_npr into the Blender user add-on directory and enable it in the user preferences, "
            "without opening the GUI."
        ),
        allow_abbrev=False,
    )
    p.add_argument("--blender", metavar="PATH", help=HINT_BLENDER)
    p.add_argument("--dry-run", action="store_true", help="only report what would happen / 只报告不执行")
    p.add_argument("--target", metavar="DIR", help="custom add-on directory / 自定义插件目录")
    p.add_argument("--no-enable", dest="enable", action="store_false", help="copy only, do not enable / 只复制不启用")
    p.add_argument("--addon", metavar="DIR", help=HINT_ADDON)
    p.add_argument("--timeout", type=float, metavar="SEC", help="Blender timeout in seconds / 超时秒数")
    p.set_defaults(run=cmd_install, enable=True)

    # bundle ---------------------------------------------------------------
    p = sub.add_parser(
        "bundle",
        help="zip goo_npr or the source tree / 打包插件或源码 zip",
        description=(
            "Create dist/goo_npr-<version>.zip, installable through Blender's Preferences > Add-ons. "
            "With --source, create dist/goo-port-<version>-src.zip instead."
        ),
        allow_abbrev=False,
    )
    p.add_argument("-o", "--out", metavar="ZIP", help="output zip path / 输出 zip 路径")
    p.add_argument("--addon", metavar="DIR", help=HINT_ADDON)
    p.add_argument(
        "--source",
        action="store_true",
        help="bundle README, goo, goo_npr, docs and tests / 打包源码、文档与测试",
    )
    p.set_defaults(run=cmd_bundle)

    # config ---------------------------------------------------------------
    p = sub.add_parser(
        "config",
        help="show or change saved defaults / 查看或修改默认配置",
        description="Show the effective configuration, or store defaults used by the other subcommands.",
        allow_abbrev=False,
    )
    p.add_argument("--blender", metavar="PATH", help="default Blender executable / 默认 Blender 路径")
    p.add_argument("--output-dir", metavar="DIR", help="default output directory / 默认输出目录")
    p.add_argument("--samples", type=_positive_int, metavar="N", help="default EEVEE samples / 默认采样数")
    p.add_argument("--format", choices=("exr", "png"), help="default beauty format / 默认格式")
    p.add_argument("--resolution-percentage", type=_percentage, metavar="N", help="default resolution scale / 默认分辨率百分比")
    p.add_argument("--addon", metavar="DIR", dest="addon_path", help="default add-on directory / 默认插件目录")
    p.add_argument("--scope", choices=("user", "local"), default="user", help="write the user or ./.goo config / 写入用户或本地配置")
    p.set_defaults(run=cmd_config)

    # gui ------------------------------------------------------------------
    p = sub.add_parser(
        "gui",
        help="open the Tkinter GUI / 打开图形界面",
        description="Launch the dependency free Tkinter GUI (needs a Python with tkinter).",
        allow_abbrev=False,
    )
    p.add_argument("--blender", metavar="PATH", help=HINT_BLENDER)
    p.set_defaults(run=cmd_gui)

    # verify ---------------------------------------------------------------
    p = sub.add_parser(
        "verify",
        help="verify release artifacts / 校验发布文件",
        description="Hash the files listed in dist/SHA256SUMS and check that the archives contain the required members.",
        allow_abbrev=False,
    )
    p.add_argument("--dist", metavar="DIR", help="release directory (default: dist/) / 发布目录")
    p.set_defaults(run=cmd_verify)

    # version --------------------------------------------------------------
    p = sub.add_parser(
        "version",
        help="print CLI, add-on and Blender versions / 版本信息",
        allow_abbrev=False,
    )
    p.set_defaults(run=cmd_version)

    return parser


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected an integer, got {text!r}") from exc
    if value < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return value


def _percentage(text: str) -> int:
    value = _positive_int(text)
    if value > 1000:
        raise argparse.ArgumentTypeError("must be <= 1000")
    return value


# ---------------------------------------------------------------------------
# subcommand implementations
# ---------------------------------------------------------------------------
def cmd_doctor(args: argparse.Namespace) -> dict:
    return pipeline.doctor(args.blender, args.blend, addon_path=args.addon, timeout=args.timeout)


def cmd_nodes(args: argparse.Namespace) -> dict:
    return pipeline.nodes(args.blender, args.blend, addon_path=args.addon, timeout=args.timeout)


def cmd_apply(args: argparse.Namespace) -> dict:
    if not args.out and not args.in_place:
        raise UsageError(
            "no output path given",
            hint="Pass -o OUT.blend to write a copy, or --in-place to overwrite the input / 请用 -o 指定输出文件，或使用 --in-place",
        )
    if args.out and args.in_place:
        raise UsageError("use either -o or --in-place, not both / -o 与 --in-place 只能选一个")
    return pipeline.apply(
        args.blend,
        args.out,
        in_place=args.in_place,
        build_library=not args.no_build,
        blender=args.blender,
        addon_path=args.addon,
        timeout=args.timeout,
    )


def cmd_render(args: argparse.Namespace) -> dict:
    return pipeline.render(
        args.blend,
        args.out,
        passes=args.passes,
        light_groups=args.light_groups,
        samples=args.samples,
        resolution_percentage=args.resolution_percentage,
        fmt=args.format,
        film_transparent=args.film_transparent,
        ambient=args.ambient,
        burn_in=args.burn_in,
        camera=args.camera,
        view_layer=args.view_layer,
        blender=args.blender,
        addon_path=args.addon,
        timeout=args.timeout,
        keep_temp=args.keep_temp,
    )


def cmd_composite(args: argparse.Namespace) -> dict:
    return pipeline.composite(
        args.out,
        png=args.png,
        exr=args.exr,
        exposure=args.exposure,
        contrast=args.contrast,
        shadow=args.shadow,
        subtract_ambient=args.subtract_ambient,
        basename=args.basename,
        blender=args.blender,
        timeout=args.timeout,
        keep_temp=args.keep_temp,
    )


def cmd_install(args: argparse.Namespace) -> dict:
    return pipeline.install(
        args.blender,
        dry_run=args.dry_run,
        target=args.target,
        enable=args.enable,
        addon_path=args.addon,
        timeout=args.timeout,
    )


def cmd_bundle(args: argparse.Namespace) -> dict:
    if args.source:
        if args.addon:
            raise UsageError("--source cannot be combined with --addon / --source 不能与 --addon 同用")
        return pipeline.source_bundle(args.out)
    return pipeline.bundle(args.out, addon_path=args.addon)


def cmd_config(args: argparse.Namespace) -> dict:
    updates = {
        "blender": args.blender,
        "output_dir": args.output_dir,
        "samples": args.samples,
        "format": args.format,
        "resolution_percentage": args.resolution_percentage,
        "addon_path": args.addon_path,
    }
    if any(value is not None for value in updates.values()):
        return pipeline.config_set(updates, scope=args.scope)
    return pipeline.config_show()


def cmd_gui(args: argparse.Namespace) -> dict:
    from . import gui

    return gui.run(blender=args.blender)


def cmd_version(args: argparse.Namespace) -> dict:
    return pipeline.version_info()


def cmd_verify(args: argparse.Namespace) -> dict:
    from .verify import verify_dist

    return verify_dist(args.dist or os.path.join(REPO_ROOT, "dist"))


# ---------------------------------------------------------------------------
# human readable formatting
# ---------------------------------------------------------------------------
def _print_payload(command: str, payload: dict) -> None:
    printer = {
        "doctor": _print_doctor,
        "nodes": _print_nodes,
        "apply": _print_apply,
        "render": _print_render,
        "composite": _print_composite,
        "install": _print_install,
        "bundle": _print_bundle,
        "config": _print_config,
        "version": _print_version,
        "verify": _print_verify,
        "gui": lambda _payload: None,
    }.get(command)
    if printer is None:
        print(json_dumps(payload, pretty=True, ensure_ascii=True))
        return
    printer(payload)


def _line(label: str, value: Any, width: int = 12) -> None:
    print(f"{label.ljust(width)} {value}")


def _section(title: str) -> None:
    print()
    print(title)


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
    headers = [str(item) for item in headers]
    rows = [[("" if cell is None else str(cell)) for cell in row] for row in rows]
    widths = [len(item) for item in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    print("  ".join(item.ljust(widths[index]) for index, item in enumerate(headers)).rstrip())
    print("  ".join("-" * widths[index] for index in range(len(headers))))
    for row in rows:
        print("  ".join(item.ljust(widths[index]) for index, item in enumerate(row)).rstrip())


def _dash(value: Any) -> str:
    return "-" if value is None or value == "" else str(value)


def _mean_luminance(stats: Optional[dict]) -> str:
    if not stats:
        return "-"
    value = stats.get("mean_luminance")
    return f"{float(value):.4f}" if isinstance(value, (int, float)) else "-"


def _dimensions(stats: Optional[dict]) -> str:
    if not stats:
        return "-"
    width, height = stats.get("width"), stats.get("height")
    if isinstance(width, int) and isinstance(height, int):
        return f"{width}x{height}"
    return "-"


def _warnings(payload: dict) -> None:
    warnings = payload.get("warnings") or []
    if not warnings:
        return
    _section(f"Warnings ({len(warnings)}):")
    for warning in warnings:
        print(f"  ! {warning}")


def _print_doctor(payload: dict) -> None:
    cli = payload.get("cli") or {}
    addon = payload.get("addon") or {}
    blender = payload.get("blender") or {}
    print(f"goo {cli.get('version')}  ·  Python {cli.get('python')}  ·  {cli.get('platform')}")
    print(f"repo        {cli.get('repo_root')}")
    print(f"scripts     {cli.get('scripts_dir')}")
    if blender:
        print(f"Blender     Blender {blender.get('version_string')}  [{blender.get('source')}]")
        print(f"            {blender.get('path')}")
    else:
        print("Blender     not found — install Blender 5.2 LTS or set GOO_BLENDER / 未找到 Blender")
    state = "present" if addon.get("exists") else "MISSING"
    print(f"add-on      {addon.get('path')}  ({state}, version {addon.get('version') or '?'})")
    print(f"            light_groups.py: {'yes' if addon.get('light_groups_module') else 'NO'}")

    inspect = payload.get("inspect")
    if inspect:
        reported = inspect.get("addon") or {}
        print(
            f"            installed in Blender: {'yes' if reported.get('installed') else 'no'}"
            f", enabled: {'yes' if reported.get('enabled') else 'no'}"
        )
        if reported.get("user_addon_path"):
            print(f"            addons dir: {reported.get('user_addon_path')}")
        if reported.get("installed_dir"):
            print(f"            installed copy: {reported.get('installed_dir')}")
        if reported.get("installed") and not reported.get("enabled"):
            print(
                "            note: CLI sessions use --factory-startup, which ignores saved add-on states / "
                "CLI 使用 --factory-startup，无法反映已保存的启用状态"
            )
        if reported.get("bl_info_error"):
            print(f"            ! {reported.get('bl_info_error')}")
        if reported.get("error"):
            print(f"            ! add-on check error: {reported.get('error')}")
        if inspect.get("blend"):
            _section("Scene")
            print(f"{'blend'.ljust(12)} {inspect.get('blend')}")
            resolution = inspect.get("resolution") or {}
            print(f"{'engine'.ljust(12)} {inspect.get('engine')}")
            print(
                f"{'resolution'.ljust(12)} {resolution.get('x')}x{resolution.get('y')} "
                f"({resolution.get('percentage')}%)  film_transparent={inspect.get('film_transparent')}"
            )
            objects = inspect.get("objects") or {}
            print(f"{'objects'.ljust(12)} {objects.get('total')} ({objects.get('meshes')} meshes, {objects.get('lights')} lights)")
            materials = inspect.get("materials") or {}
            print(
                f"{'materials'.ljust(12)} {materials.get('total')} "
                f"({len(materials.get('with_goo_groups') or [])} with GOO nodes)"
            )
            groups = inspect.get("node_groups") or {}
            print(f"{'node groups'.ljust(12)} {len(groups.get('goo') or [])} GOO / {groups.get('total')}")
            _print_inspect_groups(inspect)
        if inspect.get("specs") is not None:
            _print_specs(inspect)
    elif payload.get("error"):
        _section("Scene inspection FAILED")
        for line in str(payload["error"]).splitlines():
            print(f"  {line}")
        print("hint: check the .blend path and that Blender can open it / 请检查 .blend 路径与 Blender 日志")
    _warnings(payload)


def _print_inspect_groups(inspect: dict) -> None:
    light_groups = inspect.get("light_groups") or {}
    if not light_groups.get("available"):
        print(f"{'light groups'.ljust(12)} add-on module unavailable")
        if light_groups.get("error"):
            print(f"{' '.ljust(12)} {light_groups.get('error')}")
        return
    groups = light_groups.get("groups") or []
    passes = light_groups.get("passes") or []
    names = ", ".join(f"{item.get('name')}({item.get('lights')})" for item in groups) or "none"
    print(f"{'light groups'.ljust(12)} {len(groups)}: {names}")
    if passes:
        print(f"{'passes'.ljust(12)} {', '.join(item.get('label') or 'default' for item in passes)}")
    unassigned = light_groups.get("unassigned_lights")
    if unassigned:
        print(f"{'unassigned'.ljust(12)} {unassigned} light(s) without a group")


def _print_nodes(payload: dict) -> None:
    print(f"add-on {payload.get('addon_version') or '?'}  ·  {payload.get('blend') or 'no .blend'}")
    if payload.get("specs") is not None:
        _print_specs(payload)
    groups = (payload.get("node_groups") or {}).get("goo") or []
    if not payload.get("blend"):
        _line("GOO groups", f"{len(groups)} in the startup scene")
    elif groups:
        _section(f"GOO node groups in {payload.get('blend')} ({len(groups)})")
        _table(
            ["NAME", "TYPE", "NODES", "VERSION"],
            [
                [
                    item.get("name"),
                    item.get("type"),
                    item.get("nodes"),
                    (item.get("properties") or {}).get("goo_port_version")
                    or (item.get("properties") or {}).get("goo_builder_version")
                    or (item.get("properties") or {}).get("goo_version")
                    or "-",
                ]
                for item in groups
            ],
        )
    else:
        print("GOO node groups in scene: none (run `goo apply`) / 场景中没有 GOO 节点组")
    _warnings(payload)


def _print_specs(payload: dict) -> None:
    specs = payload.get("specs") or []
    _section(f"Node library ({len(specs)} group{'s' if len(specs) != 1 else ''})")
    if not specs:
        print("  the registry is empty — is goo_npr complete? / 节点注册表为空")
        return
    _table(
        ["NAME", "CATEGORY", "TREE", "VERSION", "DESCRIPTION"],
        [[item.get("name"), item.get("category"), item.get("tree_type"), item.get("version"), item.get("description")] for item in specs],
    )


def _print_apply(payload: dict) -> None:
    print(f"applied to  {payload.get('blend_out') or payload.get('target')}")
    before = (payload.get("node_groups") or {}).get("before", payload.get("groups_before"))
    after = (payload.get("node_groups") or {}).get("after", payload.get("groups_after"))
    if after is not None:
        _line("node groups", f"{before} -> {after}")
    if payload.get("built") is not None:
        _line("built", payload.get("built"))
    light = payload.get("light_groups") or {}
    if light.get("enabled", True):
        groups = light.get("groups")
        pass_map = light.get("pass_counts") or {}
        passes = sum(pass_map.values()) if pass_map else light.get("passes")
        _line("light groups", f"{groups} groups, {passes if passes is not None else '?'} passes")
        if light.get("error"):
            _line("", f"sync warning: {light.get('error')}")
    if payload.get("backup"):
        _line("backup", payload.get("backup"))
    if payload.get("register_error"):
        _section("Add-on registration warning")
        print(f"  {payload.get('register_error')}")
        if payload.get("register_traceback"):
            for line in str(payload["register_traceback"]).strip().splitlines()[-8:]:
                print(f"  {line}")
    _warnings(payload)


def _print_render(payload: dict) -> None:
    settings = payload.get("settings") or {}
    blender = payload.get("blender") or {}
    light = payload.get("light_groups") or {}
    resolution = settings.get("resolution")
    res_text = "-"
    if isinstance(resolution, (list, tuple)) and len(resolution) == 2:
        res_text = f"{resolution[0]}x{resolution[1]}"
    elif settings.get("resolution_x"):
        res_text = f"{settings.get('resolution_x')}x{settings.get('resolution_y')}"
    percent = settings.get("resolution_percentage")
    print(f"rendered    {payload.get('blend') or payload.get('source')}")
    print(f"output      {payload.get('output_dir')}")
    print(
        f"Blender     {blender.get('version') or payload.get('blender_version') or '?'}"
        f"   format {settings.get('format', '?')}   samples {settings.get('samples', '?')}"
        f"   resolution {res_text}" + (f" ({percent}%)" if percent else "")
    )
    if light.get("enabled"):
        groups = light.get("groups") or []
        desc = ", ".join(f"{item.get('name')} [{', '.join(item.get('lights') or []) or 'no lights'}]" for item in groups)
        print(f"light groups {light.get('pass_count', len(groups))}: {desc or 'none'}")
    passes = payload.get("passes") or []
    _section(f"Passes ({len(passes)})")
    rows = []
    for item in passes:
        rows.append(
            [
                _dash(item.get("kind")),
                _dash(item.get("group")),
                _dash(item.get("lighting_type")),
                _dash(item.get("file")),
                _dimensions(item.get("stats")),
                _mean_luminance(item.get("stats")),
                f"{float(item.get('seconds') or 0):.2f}s",
            ]
        )
    _table(["KIND", "GROUP", "LIGHT", "FILE", "SIZE", "MEAN LUM", "TIME"], rows)
    _warnings(payload)
    _line("manifest", payload.get("manifest") or "-")
    _line("total", format_duration(float(payload.get("seconds") or payload.get("duration") or 0)))


def _print_composite(payload: dict) -> None:
    outputs = payload.get("outputs") or {}
    stats = payload.get("stats") or {}
    print(f"output      {payload.get('out_dir')}")
    for kind, path in sorted(outputs.items()):
        try:
            size = human_bytes(os.path.getsize(path))
        except OSError:
            size = "?"
        print(f"{kind.upper().ljust(12)} {path}  ({size})")
    print(f"image       {_dimensions(stats)}   mean luminance {_mean_luminance(stats)}")
    combination = payload.get("combination") or {}
    if combination:
        text = f"{len(combination.get('additive_layers') or [])} layer(s), {combination.get('group_count')} light group(s)"
        if combination.get("ambient_subtracted"):
            text += f", ambient x{combination.get('ambient_factor')}"
        if combination.get("shadow_applied"):
            text += f", shadow matte ({len(combination.get('shadow_files') or [])})"
        print(f"combination {text}")
    inputs = payload.get("inputs") or []
    if inputs:
        _section(f"Inputs ({len(inputs)})")
        _table(
            ["KIND", "GROUP", "FILE", "FORMAT", "MEAN LUM"],
            [
                [
                    _dash(item.get("kind")),
                    _dash(item.get("group")),
                    _dash(item.get("file")),
                    _dash(item.get("format")),
                    f"{float(item.get('mean_luminance') or 0):.4f}",
                ]
                for item in inputs
            ],
        )
    _warnings(payload)
    _line("total", format_duration(float(payload.get("seconds") or 0)))


def _print_install(payload: dict) -> None:
    print(f"source      {payload.get('source')}  (version {payload.get('addon_version') or '?'})")
    print(f"target      {payload.get('target')}")
    if payload.get("dry_run"):
        print(f"dry run     {payload.get('files')} files, {human_bytes(payload.get('bytes') or 0)} — nothing copied")
    else:
        print(f"copied      {payload.get('files')} files, {human_bytes(payload.get('bytes') or 0)}")
        print(f"installed   {payload.get('installed_after')}   enabled {payload.get('enabled_after')}")
        if payload.get("enable_error"):
            _stderr(f"warning: add-on copied but not enabled: {payload.get('enable_error')}")
    _warnings(payload)


def _print_bundle(payload: dict) -> None:
    source = payload.get("tool") == "source-bundle"
    print(f"{'source' if source else 'bundle'}      {payload.get('path')}")
    _line("files", payload.get("files"))
    _line("size", human_bytes(payload.get("bytes") or 0))
    _line("sha256", payload.get("sha256"))
    if not source:
        print("install     Blender > Preferences > Add-ons > Install from Disk / 在 Blender 偏好设置中安装 zip")


def _print_config(payload: dict) -> None:
    if payload.get("updates"):
        print(f"saved {payload.get('scope')} config: {payload.get('path')}")
    print("effective configuration / 当前生效配置:")
    print(json_dumps(payload.get("effective") or {}, pretty=True, ensure_ascii=True))
    files = payload.get("files") or []
    _section("Files (later wins / 后者覆盖前者):")
    for path in files:
        exists = "exists" if os.path.exists(path) else "missing"
        print(f"  {path}  ({exists})")


def _print_version(payload: dict) -> None:
    cli = payload.get("cli") or {}
    addon = payload.get("addon") or {}
    print(f"goo {cli.get('version')}  ·  Python {cli.get('python')}  ·  {cli.get('platform')}")
    print(f"add-on {addon.get('version') or '?'}  {addon.get('path')}")
    blender = payload.get("blender") or {}
    if blender:
        print(f"Blender {blender.get('version_string')}  {blender.get('path')}")
    else:
        print(f"Blender not found: {payload.get('blender_error')}")


def _print_verify(payload: dict) -> None:
    print(f"dist        {payload.get('dist')}")
    _line("files", payload.get("files", 0))
    checks = payload.get("checks") or []
    if checks:
        _section(f"Checks ({len(checks)})")
        for check in checks:
            status = "OK  " if check.get("ok") else "FAIL"
            extra = ""
            if check.get("entries") is not None:
                extra = f"  {check.get('entries')} entries"
            elif check.get("bytes") is not None:
                extra = f"  {human_bytes(check.get('bytes'))}"
            print(f"  {status} {check.get('name')}{extra}")
    errors = payload.get("errors") or []
    if errors:
        _section(f"Problems ({len(errors)})")
        for error in errors:
            print(f"  ! {error}")
    _line("result", "OK" if payload.get("ok") else "FAILED")


# ``python -m goo`` dispatches here; kept at the end so subcommand functions exist.
if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
