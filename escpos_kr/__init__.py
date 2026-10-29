"""escpos-kr — 한글이 되는 ESC/POS 영수증 프린터 라이브러리.

POS-8390 (80mm, 640 dot) 으로 검증했고, 같은 ESC/POS 계열 영수증 프린터면
대체로 그대로 쓸 수 있다. 용지 폭이 다르면 ESCPOS_WIDTH 로 바꾼다 (58mm=384).

    from escpos_kr import Printer

    with Printer() as p:                 # USB 우선, 없으면 host 로 네트워크
        p.align("center").size(2, 2).bold().text("가게 이름")
        p.reset().line()
        p.row("십일조", "50,000원")
        p.cut()

이 프린터에는 한글 폰트가 없다. text() 가 줄마다 보고 한글이 섞여 있으면
자동으로 이미지로 그려 보낸다 — 호출하는 쪽은 신경 쓰지 않아도 된다.
"""
from .commands import CHARS_PER_LINE, WIDTH_DOTS
from .printer import Printer
from .transport import (Network, Transport, TransportError, USB, auto,
                        find_usb, is_transport, open_transport)

__version__ = "0.1.0"
__all__ = [
    "Printer",
    "Transport", "USB", "Network", "TransportError",
    "auto", "find_usb", "is_transport", "open_transport",
    "WIDTH_DOTS", "CHARS_PER_LINE",
]
