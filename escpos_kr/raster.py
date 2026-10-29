"""한글을 이미지로 그려 보내기 위한 래스터 변환.

이 프린터의 내장 문자셋은 GB18030 / ASCII / BIG5 뿐이라 **한글 폰트가 없다.**
한글을 텍스트로 보내면 깨지므로, Pillow 로 그림을 그려 GS v 0 명령으로 보낸다.
같은 네 줄이 텍스트로는 224바이트, 래스터로는 13.7KB — 60배 무겁다.
"""
from __future__ import annotations

import os

from . import config
from .commands import raster

DEFAULT_SIZE = 28


def _pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as e:
        raise RuntimeError(
            "한글 출력에는 Pillow 가 필요합니다: pip install pillow") from e
    return Image, ImageDraw, ImageFont


def load_font(size: int = DEFAULT_SIZE, path: str | None = None):
    _, _, ImageFont = _pillow()
    path = path or config.font()
    try:
        return ImageFont.truetype(path, size)
    except OSError as e:
        raise RuntimeError(f"폰트를 열 수 없습니다: {path}") from e


def image_to_raster(img) -> bytes:
    """1비트 이미지를 GS v 0 명령으로 바꾼다.

    검은 바탕에 흰 글씨로 그려 두면 tobytes() 의 비트 1 이 그대로
    '찍을 점' 이 된다. 픽셀을 하나씩 도는 것보다 훨씬 빠르다.
    """
    if img.mode != "1":
        img = img.convert("1")
    width_bytes = (img.width + 7) // 8
    return raster(img.tobytes(), width_bytes, img.height)


def _new_canvas(width: int, height: int):
    """검은 바탕 1비트 캔버스. 흰색(1)으로 그린 것이 인쇄된다."""
    Image, ImageDraw, _ = _pillow()
    img = Image.new("1", (width, height), 0)
    return img, ImageDraw.Draw(img)


def _x_for(align: str, text_w: int, width: int, pad: int) -> int:
    if align == "center":
        return max(pad, (width - text_w) // 2)
    if align == "right":
        return max(pad, width - text_w - pad)
    return pad


def render_lines(lines, font_size: int = DEFAULT_SIZE, bold: bool = False,
                 align: str = "left", width: int | None = None,
                 font_path: str | None = None, line_gap: int = 10,
                 pad: int = 8) -> bytes:
    """여러 줄을 한 장의 래스터로 그린다."""
    width = width or config.width()
    if isinstance(lines, str):
        lines = [lines]
    lines = list(lines)
    if not lines:
        return b""

    font = load_font(font_size, font_path)
    stroke = 1 if bold else 0
    line_h = font_size + line_gap
    height = line_h * len(lines) + pad * 2
    img, draw = _new_canvas(width, height)

    for i, line in enumerate(lines):
        box = draw.textbbox((0, 0), line, font=font, stroke_width=stroke)
        x = _x_for(align, box[2] - box[0], width, pad)
        draw.text((x, pad + i * line_h), line, font=font, fill=1,
                  stroke_width=stroke, stroke_fill=1)

    return image_to_raster(img)


def render_row(left: str, right: str, font_size: int = DEFAULT_SIZE,
               bold: bool = False, width: int | None = None,
               font_path: str | None = None, pad: int = 8) -> bytes:
    """영수증의 '항목 ─ 금액' 한 줄. 왼쪽은 왼쪽 끝, 오른쪽은 오른쪽 끝."""
    width = width or config.width()
    font = load_font(font_size, font_path)
    stroke = 1 if bold else 0
    img, draw = _new_canvas(width, font_size + 14)

    draw.text((pad, 4), left, font=font, fill=1,
              stroke_width=stroke, stroke_fill=1)
    box = draw.textbbox((0, 0), right, font=font, stroke_width=stroke)
    draw.text((width - (box[2] - box[0]) - pad, 4), right, font=font, fill=1,
              stroke_width=stroke, stroke_fill=1)
    return image_to_raster(img)


def _flatten_alpha(img):
    """투명 영역을 흰 바탕에 올린다.

    이 과정을 빼고 바로 흑백으로 떨어뜨리면 투명한 곳이 검정(0)으로 읽혀,
    반전 후 '찍을 점' 이 된다. 배경이 투명한 로고 하나가 용지를 새까맣게
    채워 버린다.
    """
    Image, _, _ = _pillow()
    if img.mode not in ("RGBA", "LA", "PA") and not (
            img.mode == "P" and "transparency" in img.info):
        return img
    img = img.convert("RGBA")
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    return Image.alpha_composite(bg, img)


def render_image(source, width: int | None = None, dither: bool = True) -> bytes:
    """사진이나 로고를 인쇄한다. 경로(str/bytes/Path)나 PIL 이미지를 받는다."""
    Image, _, _ = _pillow()
    width = width or config.width()

    if isinstance(source, (str, bytes, os.PathLike)):
        with Image.open(source) as opened:
            img = _flatten_alpha(opened.copy())
    else:
        img = _flatten_alpha(source)

    if img.width != width:
        height = max(1, round(img.height * width / img.width))
        img = img.resize((width, height), Image.LANCZOS)

    # 감열 프린터는 흑백만 찍는다. 그대로 1비트로 떨어뜨리면 사진이 뭉개지므로
    # 기본은 디더링을 쓴다. 로고·선화는 dither=False 가 더 깨끗하다.
    img = img.convert("L")
    img = img.point(lambda v: 255 - v)        # 검은 바탕 기준으로 뒤집는다
    img = img.convert("1", dither=Image.FLOYDSTEINBERG if dither else Image.NONE)
    return image_to_raster(img)


def render_rule(char: str, font_size: int = DEFAULT_SIZE,
                width: int | None = None, font_path: str | None = None,
                pad: int = 8) -> bytes:
    """ASCII 가 아닌 문자로 구분선을 그린다 (─ 같은 괘선).

    내장 폰트로는 보낼 수 없으므로, 폭에 맞는 개수를 재서 이미지로 그린다.
    """
    width = width or config.width()
    font = load_font(font_size, font_path)
    img, draw = _new_canvas(width, font_size + 10)

    box = draw.textbbox((0, 0), char, font=font)
    char_w = max(1, box[2] - box[0])
    count = max(1, (width - pad * 2) // char_w)
    draw.text((pad, 2), char * count, font=font, fill=1)
    return image_to_raster(img)
