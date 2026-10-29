"""프로젝트마다 다른 값은 여기서 모은다.

코드에 IP 나 폰트 경로를 박아 두면 프로젝트를 옮길 때마다 고쳐야 한다.
환경변수로 덮어쓸 수 있게 하고, 없으면 쓸 만한 기본값을 찾는다.

    ESCPOS_TARGET   "usb" | "auto" | "usb://..." | IP 주소
    ESCPOS_HOST     네트워크 주소 (USB 가 없을 때 쓰인다)
    ESCPOS_PORT     기본 9100
    ESCPOS_FONT     한글 폰트 파일 경로
    ESCPOS_WIDTH    용지 폭 (dot). 80mm=640, 58mm=384
    ESCPOS_COLUMNS  한 줄 ASCII 글자 수. 비우면 용지 폭에서 계산한다
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_PORT = 9100
DEFAULT_WIDTH = 640          # 80mm. 58mm 프린터는 384

# 한 줄 글자 수는 용지 폭을 글자 칸으로 나눠 추정하면 기종마다 어긋난다.
# POS-8390 은 셀프테스트에 640 dot / 48자 라고 인쇄하는데, 640/48 은 13.3 이라
# 표준 폰트 A(12dot)와 맞지 않는다. 그래서 표준 용지 두 가지를 그대로 적는다.
# 그 밖의 기종은 ESCPOS_COLUMNS 로 지정한다.
COLUMNS_80MM = 48            # 576 / 640 dot
COLUMNS_58MM = 32            # 384 dot

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


def columns_for(paper_width: int) -> int:
    """그 용지 폭에서 한 줄에 들어가는 ASCII 글자 수."""
    return COLUMNS_80MM if paper_width >= 512 else COLUMNS_58MM


def columns() -> int:
    """한 줄에 들어가는 ASCII 글자 수.

    폰트 B 를 쓰거나 인쇄폭이 다른 기종은 ESCPOS_COLUMNS 로 지정한다 —
    구분선이 다음 줄로 접히면 이 값이 큰 것이다.
    """
    raw = os.environ.get("ESCPOS_COLUMNS")
    if raw:
        return int(raw)
    return columns_for(width())


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
