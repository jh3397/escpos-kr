"""프로젝트마다 다른 값은 여기서 모은다.

코드에 IP 나 폰트 경로를 박아 두면 프로젝트를 옮길 때마다 고쳐야 한다.
환경변수로 덮어쓸 수 있게 하고, 없으면 쓸 만한 기본값을 찾는다.

    ESCPOS_TARGET   "usb" | "auto" | "usb://..." | IP 주소
    ESCPOS_HOST     네트워크 주소 (USB 가 없을 때 쓰인다)
    ESCPOS_PORT     기본 9100
    ESCPOS_FONT     한글 폰트 파일 경로
    ESCPOS_WIDTH    인쇄 폭 (dot). 80mm=576, 58mm=384. 헤드 전체 폭이 아니다
    ESCPOS_COLUMNS  한 줄 ASCII 글자 수. 비우면 용지 폭에서 계산한다
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_PORT = 9100

# 실제로 찍히는 폭(dot)이다. 헤드의 전체 점 수가 아니다.
# POS-8390 셀프테스트는 640 dot 이라고 인쇄하지만 그건 헤드 전체이고,
# 종이에 나오는 것은 576 dot 까지다 — 640 으로 그리면 오른쪽 64 dot 이
# 잘려 우측 정렬한 글자와 이미지 끝이 날아간다 (실물로 확인).
DEFAULT_WIDTH = 576          # 80mm. 58mm 프린터는 384

# ESC/POS 내장 폰트 A 의 글자 칸 너비(dot). 글자 12 x 24 에 자간이 포함된 값이다.
# 인쇄 폭을 이 값으로 나누면 한 줄 글자 수가 나온다 — 576/12 = 48,
# 384/12 = 32 로 두 표준 용지 모두 떨어진다. 줄자를 찍어 48자를 확인했다.
CHAR_WIDTH_DOTS = 12

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
    """그 인쇄 폭에서 한 줄에 들어가는 ASCII 글자 수."""
    return max(1, paper_width // CHAR_WIDTH_DOTS)


def columns(paper_width: int | None = None) -> int:
    """한 줄에 들어가는 ASCII 글자 수.

    paper_width 를 주면 그 폭에서 유도한다. 다만 ESCPOS_COLUMNS 가 있으면
    그쪽이 이긴다 — 기종 보정으로 일부러 설정해 둔 값이기 때문이다.
    폰트 B 를 쓰거나 인쇄폭이 다른 기종에서, 구분선이 다음 줄로 접히면
    이 값이 큰 것이다.
    """
    raw = os.environ.get("ESCPOS_COLUMNS")
    if raw:
        return int(raw)
    return columns_for(width() if paper_width is None else paper_width)


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
