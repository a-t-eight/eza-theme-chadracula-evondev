#!/usr/bin/env python3

import html
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ANSI_RE = re.compile(r"\x1b\[([0-9;]*)m")


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


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


def parse_ansi_line(line: str, default_fg: str = "#E9E9F4") -> list[tuple[str, str]]:
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
        "/System/Library/Fonts/SFNSMono.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/Library/Fonts/MesloLGS NF Regular.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def render_block(
    title: str,
    ansi_text: str,
    width: int,
    bg: str = "#141423",
    title_fg: str = "#F8F8F2",
    subtitle_fg: str = "#6060A4",
) -> Image.Image:
    font = load_font(22)
    title_font = load_font(28)
    line_height = 34
    padding = 28

    lines = ansi_text.splitlines()
    height = padding * 2 + 60 + max(1, len(lines)) * line_height
    image = Image.new("RGB", (width, height), hex_to_rgb(bg))
    draw = ImageDraw.Draw(image)

    draw.text((padding, padding), title, font=title_font, fill=hex_to_rgb(title_fg))
    draw.text(
        (padding, padding + 36),
        "Rendered from real eza ANSI output",
        font=font,
        fill=hex_to_rgb(subtitle_fg),
    )

    y = padding + 76
    for line in lines:
        x = padding
        for segment, fg in parse_ansi_line(line):
            if not segment:
                continue
            draw.text((x, y), segment, font=font, fill=hex_to_rgb(fg))
            bbox = draw.textbbox((x, y), segment, font=font)
            x = bbox[2]
        y += line_height

    return image


def main() -> None:
    root = Path("/Users/andrew/Documents/shell-config")
    prior = (root / "artifacts/prior-eza-output.ansi").read_text()
    current = (root / "artifacts/current-eza-output.ansi").read_text()

    left = render_block("Prior Theme", prior, 900)
    right = render_block("Current Theme", current, 900)

    gap = 24
    outer = 24
    canvas = Image.new(
        "RGB",
        (left.width + right.width + gap + outer * 2, max(left.height, right.height) + outer * 2),
        hex_to_rgb("#10101B"),
    )
    canvas.paste(left, (outer, outer))
    canvas.paste(right, (outer + left.width + gap, outer))
    canvas.save(root / "artifacts/eza-theme-compare.png")


if __name__ == "__main__":
    main()
