"""영수증을 조립해서 한 번에 보내는 고수준 API.

명령을 버퍼에 쌓아 두었다가 send() 에서 한 번에 내보낸다. 이 프린터의 Wi-Fi
모듈은 동시 접속을 하나만 받으므로, 조각조각 보내는 것보다 모아 보내는 쪽이
안전하고 빠르다.

한글과 영문을 섞어 써도 된다. text() 가 줄마다 보고 ASCII 면 내장 폰트로,
한글이 섞여 있으면 래스터로 알아서 처리한다.
"""
from __future__ import annotations

from . import commands as cmd
from . import config
from . import raster as rs
from .transport import Transport, is_transport, open_transport


def _is_ascii(s: str) -> bool:
    return all(32 <= ord(c) <= 126 for c in s)


class Printer:
    """사용 예::

        with Printer() as p:                      # USB 우선, 없으면 네트워크
            p.align("center").size(2, 2).text("가게 이름")
            p.reset().line()
            p.row("십일조", "50,000원")
            p.cut()

    with 블록을 빠져나갈 때 자동으로 전송한다.
    """

    def __init__(self, target: str | Transport | None = None,
                 host: str | None = None,
                 font_size: int = rs.DEFAULT_SIZE,
                 font_path: str | None = None,
                 width: int | None = None,
                 columns: int | None = None,
                 threshold: int | None = None):
        self._target = target
        self._host = host
        self._transport: Transport | None = (
            target if is_transport(target) else None)
        self.font_size = font_size
        self.font_path = font_path          # None 이면 쓸 때 설정에서 찾는다
        # 획 두께. None 이면 ESCPOS_THRESHOLD, 없으면 128. 올리면 획이 얇아져
        # 작은 한글이 서로 붙는 번짐이 줄어든다.
        self.threshold = threshold
        self.width = width or config.width()
        # 인자 > ESCPOS_COLUMNS > 폭에서 유도. 환경변수는 기종 보정으로
        # 일부러 설정해 둔 값이라 폭에서 유도한 값보다 세야 한다.
        self.columns = columns or config.columns(self.width)

        self._buf = bytearray(cmd.INIT)
        self._dirty = False                 # 종이에 나갈 내용이 쌓였는가
        self._align = "left"
        self._bold = False
        self._underline = False
        self._w = 1
        self._h = 1

    # --- 상태 ---

    def align(self, how: str) -> "Printer":
        if how not in cmd.ALIGN:
            raise ValueError("정렬은 left, center, right 중 하나여야 합니다")
        self._align = how
        self._buf += cmd.ALIGN[how]
        return self

    def bold(self, on: bool = True) -> "Printer":
        self._bold = on
        self._buf += cmd.BOLD_ON if on else cmd.BOLD_OFF
        return self

    def underline(self, on: bool = True) -> "Printer":
        self._underline = on
        self._buf += cmd.UNDERLINE_ON if on else cmd.UNDERLINE_OFF
        return self

    def size(self, width: int = 1, height: int = 1) -> "Printer":
        self._w, self._h = width, height
        self._buf += cmd.size(width, height)
        return self

    def reset(self) -> "Printer":
        """글자 꾸밈을 모두 되돌린다. 정렬은 그대로 둔다."""
        self._bold = False
        self._underline = False
        self._w = self._h = 1
        self._buf += cmd.BOLD_OFF + cmd.UNDERLINE_OFF + cmd.RESET_SIZE
        return self

    # --- 내용 ---

    @property
    def chars_per_line(self) -> int:
        """지금 글자 크기로 한 줄에 들어가는 ASCII 글자 수.

        용지 폭에서 계산한다. 고정값을 쓰면 58mm(384dot) 프린터에서
        구분선과 금액이 다음 줄로 접힌다.
        """
        return max(1, self.columns // self._w)

    def text(self, s: str = "") -> "Printer":
        """한 줄 또는 여러 줄. 한글이 섞이면 자동으로 래스터로 찍는다."""
        lines = s.split("\n")
        batch: list[str] = []

        def flush_batch():
            if batch:
                self._buf += rs.render_lines(
                    batch, font_size=self.font_size * self._h,
                    bold=self._bold, align=self._align, width=self.width,
                    font_path=self.font_path, threshold=self.threshold)
                batch.clear()

        for line in lines:
            if _is_ascii(line):
                flush_batch()
                self._buf += line.encode("ascii") + b"\n"
            else:
                batch.append(line)
        flush_batch()
        self._dirty = True
        return self

    def line(self, char: str = "-") -> "Printer":
        """구분선. `─` 같은 괘선 문자도 받는다 (내장 폰트에 없어 래스터로 그린다)."""
        if _is_ascii(char):
            self._buf += (char * self.chars_per_line).encode("ascii") + b"\n"
        else:
            self._buf += rs.render_rule(
                char, font_size=self.font_size * self._h,
                width=self.width, font_path=self.font_path,
                threshold=self.threshold)
        self._dirty = True
        return self

    def row(self, left: str, right: str, filler: str = " ") -> "Printer":
        """'항목 ─ 금액' 한 줄. 왼쪽 끝과 오른쪽 끝에 붙인다.

        filler 가 공백이 아니면 사이를 그 문자로 채운다 (점선 리더).
        """
        filler = filler or " "              # 빈 문자열이면 채울 수 없다
        if _is_ascii(left) and _is_ascii(right) and _is_ascii(filler):
            gap = self.chars_per_line - len(left) - len(right)
            if gap < 1:
                gap = 1
            # 여러 글자짜리 filler 는 그대로 곱하면 줄을 넘긴다. 칸 수에 맞춰 자른다.
            middle = (filler * gap)[:gap]
            self._buf += (left + middle + right).encode("ascii") + b"\n"
        else:
            self._buf += rs.render_row(
                left, right, font_size=self.font_size * self._h,
                bold=self._bold, width=self.width, font_path=self.font_path,
                filler=filler, threshold=self.threshold)
        self._dirty = True
        return self

    def qr(self, data: str, module: int = 6, ec: str = "M") -> "Printer":
        """내장 QR 코드. 별도 라이브러리가 필요 없다."""
        self._buf += cmd.qr(data, module, ec)
        self._dirty = True
        return self

    def image(self, source, dither: bool = True,
              width: int | None = None, align: str | None = None) -> "Printer":
        """사진·로고. 경로나 PIL 이미지를 받는다.

        width 는 그림의 폭(dot)이고, 비우면 용지 폭을 다 쓴다. 낙관이나 로고는
        작게 쓰는 것이 보통이라 `width=160` 처럼 준다. align 을 비우면 지금
        설정된 정렬을 따른다.
        """
        self._buf += rs.render_image(
            source, width=width, dither=dither,
            align=align or self._align, paper_width=self.width)
        self._dirty = True
        return self

    def raw(self, data: bytes) -> "Printer":
        """직접 만든 ESC/POS 바이트를 끼워 넣는다."""
        self._buf += data
        self._dirty = True
        return self

    # --- 마무리 ---

    def feed(self, lines: int = 1) -> "Printer":
        self._buf += cmd.feed(lines)
        self._dirty = True
        return self

    def cut(self, feed: int = 4, partial: bool = False) -> "Printer":
        """커팅. 칼날이 인쇄 위치보다 위에 있어 급지 없이 자르면 글자가 잘린다."""
        if feed:
            self._buf += cmd.feed(feed)
        self._buf += cmd.CUT_PARTIAL if partial else cmd.CUT_FULL
        self._dirty = True
        return self

    def beep(self) -> "Printer":
        self._buf += cmd.BEEP
        self._dirty = True
        return self

    def drawer(self) -> "Printer":
        """금전함을 연다 (서랍이 연결된 경우)."""
        self._buf += cmd.DRAWER
        self._dirty = True
        return self

    # --- 전송 ---

    @property
    def transport(self) -> Transport:
        if self._transport is None:
            self._transport = open_transport(self._target, self._host)
        return self._transport

    def bytes(self) -> bytes:
        """보낼 내용을 바이트로 돌려준다. 전송은 하지 않는다 (시험용)."""
        return bytes(self._buf)

    def _fresh_buffer(self) -> bytearray:
        """INIT 뒤에 현재 꾸밈 상태를 다시 적어 둔 새 버퍼.

        INIT 은 프린터의 정렬·굵기·배율을 모두 되돌린다. 객체의 상태만 남겨
        두면 다음 전송에서 ASCII 는 초기 상태로, 한글 래스터는 객체 상태로
        그려져 둘이 어긋난다.
        """
        buf = bytearray(cmd.INIT)
        if self._align != "left":
            buf += cmd.ALIGN[self._align]
        if self._bold:
            buf += cmd.BOLD_ON
        if self._underline:
            buf += cmd.UNDERLINE_ON
        if (self._w, self._h) != (1, 1):
            buf += cmd.size(self._w, self._h)
        return buf

    def send(self) -> "Printer":
        """쌓인 내용을 보내고 버퍼를 비운다. 꾸밈 상태는 이어진다."""
        # 꾸밈 상태를 미리 적어 두므로 버퍼 길이로는 '보낼 것이 있는지' 를
        # 알 수 없다. 종이에 나갈 내용이 쌓였을 때만 보낸다 — 아니면 빈
        # 전송이 생기고, 동시 접속을 하나만 받는 프린터에 연결만 낭비된다.
        if self._dirty:
            self.transport.send(bytes(self._buf))
        self._buf = self._fresh_buffer()
        self._dirty = False
        return self

    def __enter__(self) -> "Printer":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            self.send()
        return False

    def __len__(self) -> int:
        return len(self._buf)
