#!/usr/bin/env python3

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ANSI_RE = re.compile(r"\x1b\[([0-9;]*)m")
PALETTE_16 = {
    30: "#000000",
    31: "#AA0000",
    32: "#00AA00",
    33: "#AA5500",
    34: "#0000AA",
    35: "#AA00AA",
    36: "#00AAAA",
    37: "#AAAAAA",
    90: "#555555",
    91: "#FF5555",
    92: "#55FF55",
    93: "#FFFF55",
    94: "#5555FF",
    95: "#FF55FF",
    96: "#55FFFF",
    97: "#FFFFFF",
}

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "assets" / "preview.png"
THEME_DIR = ROOT / "eza"


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def parse_ansi_line(line: str, default_fg: str = "#CAD3F5") -> list[tuple[str, str]]:
    segments: list[tuple[str, str]] = []
    current_fg = default_fg
    pos = 0

    for match in ANSI_RE.finditer(line):
        if match.start() > pos:
            text = line[pos : match.start()]
            if text:
                segments.append((text, current_fg))

        codes = [int(code) for code in match.group(1).split(";") if code]
        if not codes:
            codes = [0]

        i = 0
        while i < len(codes):
            code = codes[i]
            if code == 0:
                current_fg = default_fg
            elif code in PALETTE_16:
                current_fg = PALETTE_16[code]
            elif code == 38 and i + 4 < len(codes) and codes[i + 1] == 2:
                current_fg = "#{:02X}{:02X}{:02X}".format(
                    codes[i + 2], codes[i + 3], codes[i + 4]
                )
                i += 4
            i += 1

        pos = match.end()

    if pos < len(line):
        segments.append((line[pos:], current_fg))

    return segments


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/Users/andrew/Library/Fonts/JetBrainsMonoNerdFontMono-Regular.ttf",
        "/Users/andrew/Library/Fonts/MesloLGS NF Regular.ttf",
        "/Library/Fonts/MesloLGS NF Regular.ttf",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/System/Library/Fonts/Menlo.ttc",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def write_file(path: Path, size: int = 0, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    if executable:
        path.chmod(0o755)


def set_mtime(path: Path, when: datetime) -> None:
    timestamp = when.timestamp()
    os.utime(path, (timestamp, timestamp), follow_symlinks=False)


def build_fixture(root: Path) -> None:
    fixture_time = datetime(2026, 6, 16, 11, 58)
    entries: list[tuple[str, int, bool]] = [
        (".pre-commit.yaml", 0, False),
        ("arch.iso", 4, False),
        ("Cargo.lock", 0, False),
        ("Cargo.toml", 0, False),
        ("cfg.ini", 0, False),
        ("doc.pdf", 0, False),
        ("file", 0, True),
        ("file.cpp", 0, False),
        ("file.mp4", 7, False),
        ("file.pdf", 0, False),
        ("file.pem", 0, False),
        ("file.png", 0, False),
        ("file.rs", 0, False),
        ("file.tar.gz", 8, False),
        ("file.toml", 0, False),
        ("file.yml", 0, False),
        ("init.sh", 0, True),
        ("justfile", 0, False),
        ("Makefile", 7, False),
        ("nginx.conf", 0, False),
        ("README.md", 0, False),
        ("release.tar.gz", 8, False),
        ("resume.docx", 0, False),
        ("rust.rs", 0, False),
        ("song.flac", 6, False),
        ("song.mp3", 0, False),
        ("source.cpp", 0, False),
    ]

    directories = [".config", ".github", "src"]

    for idx, directory in enumerate(directories):
        path = root / directory
        path.mkdir(parents=True, exist_ok=True)
        set_mtime(path, fixture_time + timedelta(minutes=idx + 1))

    for idx, (name, size, executable) in enumerate(entries):
        path = root / name
        write_file(path, size=size, executable=executable)
        set_mtime(path, fixture_time + timedelta(minutes=idx + 2))


def capture_eza_output(fixture_root: Path) -> str:
    eza = shutil.which("eza")
    if not eza:
        raise RuntimeError("eza is required to render the preview")

    env = os.environ.copy()
    env.pop("LS_COLORS", None)
    env.pop("EZA_COLORS", None)
    env["EZA_CONFIG_DIR"] = str(THEME_DIR)

    result = subprocess.run(
        [
            eza,
            "--color=always",
            "--icons=always",
            "--all",
            "--long",
            "--header",
            "--group-directories-first",
            str(fixture_root),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.stdout


def sanitize_segments(
    lines: list[list[tuple[str, str]]], current_user: str
) -> list[list[tuple[str, str]]]:
    sanitized: list[list[tuple[str, str]]] = []
    for line in lines:
        new_line: list[tuple[str, str]] = []
        for text, color in line:
            text = text.replace(current_user, "eza-test")
            new_line.append((text, color))
        sanitized.append(new_line)
    return sanitized


def render_preview(ansi_text: str) -> None:
    font = load_font(24)
    line_height = 34
    left_padding = 36
    top_padding = 18
    # NvChad/base46 chadracula-evondev: base_30.black
    bg = "#141423"

    lines = [parse_ansi_line(line) for line in ansi_text.splitlines()]
    lines = sanitize_segments(lines, os.environ.get("USER", "user"))

    dummy = Image.new("RGB", (10, 10), hex_to_rgb(bg))
    draw = ImageDraw.Draw(dummy)

    max_width = 0
    for line in lines:
        text = "".join(part for part, _ in line)
        bbox = draw.textbbox((0, 0), text, font=font)
        max_width = max(max_width, bbox[2] - bbox[0])

    width = max_width + left_padding * 2
    height = len(lines) * line_height + top_padding * 2
    image = Image.new("RGB", (width, height), hex_to_rgb(bg))
    draw = ImageDraw.Draw(image)

    y = top_padding
    for line in lines:
        x = left_padding
        for segment, fg in line:
            if segment:
                draw.text((x, y), segment, font=font, fill=hex_to_rgb(fg))
                bbox = draw.textbbox((x, y), segment, font=font)
                x = bbox[2]
        y += line_height

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUT_PATH)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="eza-theme-preview-") as tmp:
        fixture_root = Path(tmp)
        build_fixture(fixture_root)
        ansi = capture_eza_output(fixture_root)
        render_preview(ansi)


if __name__ == "__main__":
    main()
