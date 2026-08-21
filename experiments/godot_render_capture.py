"""Isolated feasibility probe for a real Godot viewport capture with a trusted PNG."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import struct
import zlib
from pathlib import Path
from time import monotonic


PROJECT_GODOT = """[application]
config/name="KHALINOS Godot Render Capture"
run/main_scene="res://main.tscn"

[display]
window/size/viewport_width=1280
window/size/viewport_height=720
window/size/window_width_override=1280
window/size/window_height_override=720

[rendering]
renderer/rendering_method="gl_compatibility"
renderer/rendering_method.mobile="gl_compatibility"
environment/defaults/default_clear_color=Color(0.02, 0.025, 0.035, 1)
"""


SCENE = """[gd_scene load_steps=3 format=3]

[ext_resource type="Texture2D" path="res://assets/visual-foundation.png" id="1_asset"]
[ext_resource type="Script" path="res://capture.gd" id="2_script"]

[node name="VisualPrototype" type="Control"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
script = ExtResource("2_script")

[node name="Background" type="TextureRect" parent="."]
layout_mode = 1
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
texture = ExtResource("1_asset")
expand_mode = 1
stretch_mode = 6

[node name="Scrim" type="ColorRect" parent="."]
layout_mode = 1
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
color = Color(0.015, 0.02, 0.03, 0.42)
mouse_filter = 2

[node name="Panel" type="PanelContainer" parent="."]
layout_mode = 0
offset_left = 72.0
offset_top = 72.0
offset_right = 656.0
offset_bottom = 648.0

[node name="Margin" type="MarginContainer" parent="Panel"]
layout_mode = 2
theme_override_constants/margin_left = 36
theme_override_constants/margin_top = 34
theme_override_constants/margin_right = 36
theme_override_constants/margin_bottom = 34

[node name="Content" type="VBoxContainer" parent="Panel/Margin"]
layout_mode = 2
theme_override_constants/separation = 22

[node name="Eyebrow" type="Label" parent="Panel/Margin/Content"]
layout_mode = 2
text = "KHALINOS · GODOT VISUAL PROTOTYPE"

[node name="Title" type="Label" parent="Panel/Margin/Content"]
layout_mode = 2
theme_override_font_sizes/font_size = 42
text = "THE THREEFOLD PASSAGE"
autowrap_mode = 2

[node name="Description" type="Label" parent="Panel/Margin/Content"]
layout_mode = 2
text = "Read the ancient signals. Choose one route. Preserve the verified state."
autowrap_mode = 2

[node name="Routes" type="VBoxContainer" parent="Panel/Margin/Content"]
layout_mode = 2
theme_override_constants/separation = 12

[node name="RouteA" type="Button" parent="Panel/Margin/Content/Routes"]
layout_mode = 2
text = "SOLAR MARK · STABLE"

[node name="RouteB" type="Button" parent="Panel/Margin/Content/Routes"]
layout_mode = 2
text = "TIDAL MARK · UNCERTAIN"

[node name="RouteC" type="Button" parent="Panel/Margin/Content/Routes"]
layout_mode = 2
text = "ROOT MARK · GUARDED"

[node name="Status" type="Label" parent="Panel/Margin/Content"]
layout_mode = 2
text = "AWAITING ROUTE SELECTION"
"""


CAPTURE_SCRIPT = """extends Control

func _ready() -> void:
    $Panel/Margin/Content/Routes/RouteA.grab_focus()
"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fixture_png(width: int = 640, height: int = 360) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)

    rows = b"".join(
        b"\x00" + b"".join(
            bytes((18 + x * 45 // width, 40 + y * 90 // height, 64 + x * 95 // width, 255))
            for x in range(width)
        )
        for y in range(height)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--asset", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--headless-render", action="store_true")
    args = parser.parse_args()

    started = monotonic()

    def stage(message: str) -> None:
        print(f"[{monotonic() - started:7.2f}s] {message}", flush=True)

    root = args.output_root.resolve()
    project = root / "project"
    capture_prefix = root / "godot-render.png"
    if root.exists():
        raise FileExistsError(f"output root already exists: {root}")
    (project / "assets").mkdir(parents=True)
    source_asset = args.asset.resolve() if args.asset else root / "fixture-input.png"
    if args.asset:
        shutil.copyfile(source_asset, project / "assets" / "visual-foundation.png")
    else:
        payload = fixture_png()
        source_asset.write_bytes(payload)
        (project / "assets" / "visual-foundation.png").write_bytes(payload)
    (project / "project.godot").write_text(PROJECT_GODOT, encoding="utf-8", newline="\n")
    (project / "main.tscn").write_text(SCENE, encoding="utf-8", newline="\n")
    (project / "capture.gd").write_text(CAPTURE_SCRIPT, encoding="utf-8", newline="\n")
    stage(f"fixture project materialized at {project}")

    command = [
        str(args.godot.resolve()),
        "--headless",
        "--path",
        str(project),
        "--editor",
        "--quit",
    ]
    stage("starting headless Godot import probe")
    try:
        imported = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
        )
    except subprocess.TimeoutExpired as error:
        stage("headless Godot import probe timed out")
        print((error.stdout or b"").decode("utf-8", errors="replace") if isinstance(error.stdout, bytes) else (error.stdout or ""), flush=True)
        print((error.stderr or b"").decode("utf-8", errors="replace") if isinstance(error.stderr, bytes) else (error.stderr or ""), flush=True)
        return 124
    stage(f"headless Godot import probe returned {imported.returncode}")
    if imported.returncode != 0:
        print(imported.stdout)
        print(imported.stderr)
        return imported.returncode

    command = [str(args.godot.resolve())]
    if args.headless_render:
        command.append("--headless")
    else:
        command.append("--windowed")
    command.extend([
        "--path", str(project),
        "--write-movie",
        str(capture_prefix),
        "--fixed-fps",
        "30",
        "--quit-after",
        "3",
    ])
    stage("starting display-backed MovieWriter capture")
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
        )
    except subprocess.TimeoutExpired as error:
        stage("display-backed MovieWriter capture timed out")
        print((error.stdout or b"").decode("utf-8", errors="replace") if isinstance(error.stdout, bytes) else (error.stdout or ""), flush=True)
        print((error.stderr or b"").decode("utf-8", errors="replace") if isinstance(error.stderr, bytes) else (error.stderr or ""), flush=True)
        return 124
    stage(f"display-backed MovieWriter capture returned {completed.returncode}")
    frames = sorted(root.glob("godot-render????????.png"))
    capture = frames[-1] if frames else capture_prefix
    report = {
        "godot": str(args.godot.resolve()),
        "godot_sha256": sha256(args.godot.resolve()),
        "asset": str(source_asset),
        "asset_sha256": sha256(source_asset),
        "returncode": completed.returncode,
        "headless_render": args.headless_render,
        "frame_count": len(frames),
        "capture_exists": capture.is_file(),
        "capture_bytes": capture.stat().st_size if capture.is_file() else 0,
        "capture_sha256": sha256(capture) if capture.is_file() else None,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    (root / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if completed.returncode == 0 and report["capture_bytes"] > 10_000 else 1


if __name__ == "__main__":
    raise SystemExit(main())
