"""ESC/POS 명령 바이트.

POS-8390 기준. 80mm 용지의 인쇄 폭 576 dot, 내장 폰트 A 기준 48자/줄.
내장 문자셋은 GB18030 / ASCII / BIG5 뿐이라 한글은 여기 없다 — raster.py 를 쓴다.
"""

WIDTH_DOTS = 576        # 인쇄되는 폭. 헤드는 640 이지만 576 까지만 찍힌다
CHARS_PER_LINE = 48

INIT = b"\x1b@"

# 정렬
ALIGN = {"left": b"\x1ba\x00", "center": b"\x1ba\x01", "right": b"\x1ba\x02"}

# 강조
BOLD_ON = b"\x1bE\x01"
BOLD_OFF = b"\x1bE\x00"
UNDERLINE_OFF = b"\x1b-\x00"
UNDERLINE_ON = b"\x1b-\x01"

# 되돌리기
RESET_SIZE = b"\x1d!\x00"

CUT_FULL = b"\x1dV\x00"
CUT_PARTIAL = b"\x1dV\x01"
BEEP = b"\x1bB\x02\x03"

# 금전함 (POS 서랍) — ESC p m t1 t2
DRAWER = b"\x1bp\x00\x19\xfa"


def size(width: int = 1, height: int = 1) -> bytes:
    """GS ! — 가로·세로 배율. 각각 1~8."""
    if not (1 <= width <= 8 and 1 <= height <= 8):
        raise ValueError("배율은 1~8 사이여야 합니다")
    return b"\x1d!" + bytes([((width - 1) << 4) | (height - 1)])


def feed(lines: int = 1) -> bytes:
    """ESC d — n 줄 급지."""
    if not (0 <= lines <= 255):
        raise ValueError("급지 줄 수는 0~255 사이여야 합니다")
    return b"\x1bd" + bytes([lines])


def raster(bitmap: bytes, width_bytes: int, height: int) -> bytes:
    """GS v 0 — 래스터 비트 이미지.

    bitmap 은 한 줄당 width_bytes 바이트, 비트 1 이 검은 점이다.
    """
    if height > 0xFFFF or width_bytes > 0xFFFF:
        raise ValueError("이미지가 너무 큽니다")
    return (b"\x1dv0\x00"
            + bytes([width_bytes & 0xFF, width_bytes >> 8,
                     height & 0xFF, height >> 8])
            + bitmap)


def qr(data: str, module: int = 6, ec: str = "M") -> bytes:
    """GS ( k — 내장 QR 코드. 별도 라이브러리가 필요 없다.

    module 1~16 은 점 크기, ec 는 L/M/Q/H 오류정정 수준.
    """
    if not (1 <= module <= 16):
        raise ValueError("module 은 1~16 사이여야 합니다")
    levels = {"L": 48, "M": 49, "Q": 50, "H": 51}
    if ec not in levels:
        raise ValueError("ec 는 L, M, Q, H 중 하나여야 합니다")

    payload = data.encode("utf-8")
    n = len(payload) + 3
    if n > 0xFFFF:
        raise ValueError("QR 데이터가 너무 깁니다")

    model = b"\x1d(k\x04\x001A2\x00"
    dot = b"\x1d(k\x03\x001C" + bytes([module])
    level = b"\x1d(k\x03\x001E" + bytes([levels[ec]])
    store = b"\x1d(k" + bytes([n & 0xFF, n >> 8]) + b"1P0" + payload
    emit = b"\x1d(k\x03\x001Q0"
    return model + dot + level + store + emit
