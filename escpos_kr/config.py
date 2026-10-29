"""프로젝트마다 다른 값은 여기서 모은다.

코드에 IP 나 폰트 경로를 박아 두면 프로젝트를 옮길 때마다 고쳐야 한다.
환경변수로 덮어쓸 수 있게 하고, 없으면 쓸 만한 기본값을 찾는다.

    ESCPOS_TARGET   "usb" | "auto" | "usb://..." | IP 주소
    ESCPOS_HOST     네트워크 주소 (USB 가 없을 때 쓰인다)
    ESCPOS_PORT     기본 9100
    ESCPOS_FONT     한글 폰트 파일 경로
    ESCPOS_WIDTH    용지 폭 (dot). 80mm=640, 58mm=384
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_PORT = 9100
DEFAULT_WIDTH = 640          # 80mm. 58mm 프린터는 384

# 한글이 들어 있는 폰트를 운영체제별로 훑는다. 먼저 찾은 것을 쓴다.
FONT_CANDIDATES = (
    # macOS
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    # Linux
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    # Windows
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/gulim.ttc",
)


def target() -> str | None:
    return os.environ.get("ESCPOS_TARGET") or None


def host() -> str | None:
    return os.environ.get("ESCPOS_HOST") or None


def port() -> int:
    raw = os.environ.get("ESCPOS_PORT")
    return int(raw) if raw else DEFAULT_PORT


def width() -> int:
    raw = os.environ.get("ESCPOS_WIDTH")
    return int(raw) if raw else DEFAULT_WIDTH


def font() -> str:
    """쓸 수 있는 한글 폰트 경로. 없으면 무엇을 찾았는지 알려주고 실패한다."""
    chosen = os.environ.get("ESCPOS_FONT")
    if chosen:
        if not Path(chosen).exists():
            raise RuntimeError(f"ESCPOS_FONT 가 가리키는 파일이 없습니다: {chosen}")
        return chosen

    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return path

    raise RuntimeError(
        "한글 폰트를 찾지 못했습니다. ESCPOS_FONT 로 지정해 주세요.\n"
        "찾아본 곳:\n  " + "\n  ".join(FONT_CANDIDATES))
