"""다른 에이전트가 영수증 프린터를 쓸 수 있게 하는 MCP 서버.

실행:
    escpos-kr-mcp                       # stdio
    python -m escpos_kr.mcp_server

설정은 환경변수로 준다 (config.py 참고). 보통은 둘 중 하나면 된다.
    ESCPOS_HOST=192.168.0.8             # 네트워크 프린터 주소
    ESCPOS_TARGET=usb                   # USB 강제

에이전트에게는 '문서'를 받는 하나의 도구를 준다. 명령을 하나씩 호출하게 하면
왕복이 많아지고 중간에 끊기면 반쪽짜리 영수증이 나온다. 한 번에 받아서
한 번에 찍는 쪽이 안전하다.
"""
from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from . import config
from .printer import Printer
from .transport import TransportError, find_usb_devices

try:                                    # 설치본에서 버전을 읽는다
    from . import __version__
except ImportError:                     # 순환 참조 방어
    __version__ = "0"

server = MCPServer(
    name="escpos-kr",
    version=__version__,
    instructions=(
        "ESC/POS 영수증 프린터로 출력합니다. 한글을 그대로 쓰면 됩니다 — "
        "내장 폰트가 없는 프린터라도 자동으로 이미지로 바꿔 찍습니다.\n"
        "실제로 종이가 나오는 동작이니, 확신이 서지 않으면 dry_run=true 로 "
        "먼저 확인하세요. 프린터가 연결돼 있는지는 list_printers 로 봅니다."
    ),
)


class Block(BaseModel):
    """영수증을 이루는 한 토막."""

    type: Literal["text", "row", "line", "qr", "feed", "image"] = Field(
        description="text=한 줄 글, row=왼쪽·오른쪽 끝에 붙는 항목/금액 줄, "
                    "line=구분선, qr=QR코드, feed=빈 줄, image=이미지 파일")
    text: str = Field("", description="type=text 의 내용. 줄바꿈(\\n) 가능")
    left: str = Field("", description="type=row 의 왼쪽 (항목명)")
    right: str = Field("", description="type=row 의 오른쪽 (금액 등)")
    data: str = Field("", description="type=qr 에 넣을 문자열")
    path: str = Field("", description="type=image 의 파일 경로")
    dither: bool = Field(
        True,
        description="type=image 의 농담 표현. 사진은 True(기본), "
                    "로고·선화는 False 가 깨끗하다 — True 면 또렷한 면이 "
                    "얼룩진다")
    char: str = Field("-", description="type=line 에 쓸 문자")
    filler: str = Field(
        " ", min_length=1, max_length=4,
        description="type=row 에서 항목과 금액 사이를 채울 문자. "
                    "'·' 이나 '.' 을 주면 점선 리더가 된다. 기본은 공백")
    lines: int = Field(1, ge=1, le=20, description="type=feed 의 빈 줄 수")
    align: Literal["left", "center", "right"] | None = Field(
        None, description="정렬. 지정하면 이후 블록에도 이어진다")
    size: int = Field(1, ge=1, le=4, description="글자 배율. 1=보통, 2=두 배")
    bold: bool = Field(False, description="굵게")
    module: int = Field(6, ge=1, le=16, description="type=qr 의 점 크기")


def _compose(p: Printer, blocks: list[Block]) -> None:
    for b in blocks:
        if b.align:
            p.align(b.align)
        styled = b.bold or b.size != 1
        if b.bold:
            p.bold(True)
        if b.size != 1:
            p.size(b.size, b.size)

        if b.type == "text":
            p.text(b.text)
        elif b.type == "row":
            p.row(b.left, b.right, filler=b.filler)
        elif b.type == "line":
            p.line(b.char or "-")
        elif b.type == "qr":
            if not b.data:
                raise ValueError("type=qr 에는 data 가 필요합니다")
            p.qr(b.data, module=b.module)
        elif b.type == "feed":
            p.feed(b.lines)
        elif b.type == "image":
            if not b.path:
                raise ValueError("type=image 에는 path 가 필요합니다")
            p.image(b.path, dither=b.dither)

        if styled:
            p.reset()


def _summary(data: bytes) -> dict:
    return {
        "bytes": len(data),
        "raster_blocks": data.count(b"\x1dv0"),
        "has_qr": b"\x1d(k" in data,
    }


@server.tool(
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
    description="연결된 프린터와 현재 설정을 확인한다. 출력하기 전에 먼저 본다.",
)
def list_printers() -> dict:
    devices = find_usb_devices()
    usb = devices[0] if devices else None
    host = config.host()
    try:
        font = config.font()
    except RuntimeError as e:
        font = f"없음 ({e.args[0].splitlines()[0]})"
    out = {
        "usb": usb or "없음",
        "network_host": host or "없음 (ESCPOS_HOST 미설정)",
        "will_use": "USB" if usb else (host or "사용 가능한 프린터 없음"),
        "paper_width_dots": config.width(),
        "korean_font": font,
    }
    if len(devices) > 1:
        # 여러 대가 걸리면 어느 것을 쓰는지 드러내 준다.
        out["usb_candidates"] = devices
        out["note"] = ("영수증 프린터로 보이는 USB 장치가 여러 대입니다. "
                       "첫 번째를 씁니다 — 다르면 target 으로 지정하세요.")
    return out


@server.tool(
    annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=False,
                                openWorldHint=False),
    description=(
        "영수증을 출력한다. blocks 에 토막들을 순서대로 담는다. "
        "한글은 그대로 쓰면 된다. dry_run=true 면 찍지 않고 결과만 알려준다."),
)
def print_receipt(
    blocks: list[Block],
    # 기본값 자리에 Field(...) 를 쓰면 MCP 를 거치지 않고 파이썬에서 직접 부를 때
    # 인자가 FieldInfo 객체가 된다. dry_run 이 항상 참이 되어 조용히 안 찍힌다.
    # Annotated 로 감싸면 스키마 설명은 유지하면서 진짜 기본값을 갖는다.
    cut: Annotated[bool, Field(description="끝에 용지를 자른다")] = True,
    dry_run: Annotated[bool, Field(description="실제로 찍지 않고 확인만")] = False,
    target: Annotated[str | None, Field(
        description="'usb' 또는 IP 주소. 생략하면 USB 우선, 없으면 설정값")] = None,
) -> dict:
    if not blocks:
        raise ValueError("blocks 가 비어 있습니다")

    p = Printer(target or ("usb://dry-run" if dry_run else None))
    _compose(p, blocks)
    if cut:
        p.cut()

    data = p.bytes()
    info = _summary(data)
    if dry_run:
        return {"printed": False, **info,
                "note": "확인만 했습니다. 실제로 찍으려면 dry_run 을 빼세요."}
    try:
        p.send()
    except TransportError as e:
        raise RuntimeError(f"출력 실패: {e}") from e
    return {"printed": True, **info}


@server.tool(
    annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=False,
                                openWorldHint=False),
    description="짧은 글 한 덩이를 바로 출력한다. 영수증 형식이 필요 없을 때.",
)
def print_text(
    text: str,
    align: Literal["left", "center", "right"] = "left",
    size: Annotated[int, Field(ge=1, le=4)] = 1,
    bold: bool = False,
    cut: bool = True,
    dry_run: bool = False,
) -> dict:
    return print_receipt(
        blocks=[Block(type="text", text=text, align=align, size=size,
                      bold=bold)],
        cut=cut, dry_run=dry_run, target=None)


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
