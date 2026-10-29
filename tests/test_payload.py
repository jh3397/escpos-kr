"""프린터 없이 돌아가는 검사. 바이트가 제대로 조립되는지만 본다.

    .venv/bin/python -m pytest tests -q
    .venv/bin/python tests/test_payload.py      # pytest 없이도 실행된다
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

from escpos_kr import CHARS_PER_LINE, Printer
from escpos_kr import commands as cmd
from escpos_kr import raster as rs


def test_size_encoding():
    assert cmd.size(1, 1) == b"\x1d!\x00"
    assert cmd.size(2, 2) == b"\x1d!\x11"
    assert cmd.size(8, 1) == b"\x1d!\x70"
    for bad in [(0, 1), (1, 9), (-1, 1)]:
        try:
            cmd.size(*bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{bad} 는 거부되어야 한다")


def test_qr_structure():
    q = cmd.qr("hello", module=4, ec="H")
    assert q.startswith(b"\x1d(k\x04\x001A2\x00")   # 모델 지정
    assert b"\x1d(k\x03\x001C\x04" in q             # 점 크기 4
    assert b"\x1d(k\x03\x001E\x33" in q             # 오류정정 H
    assert q.endswith(b"\x1d(k\x03\x001Q0")         # 인쇄 명령
    assert b"hello" in q


def test_raster_bit_polarity():
    """비트 1 이 '찍는 점' 이어야 한다. 뒤집히면 용지가 새까맣게 나온다."""
    blank = rs.image_to_raster(Image.new("1", (16, 2), 0))
    assert blank[8:] == b"\x00" * 4

    filled = rs.image_to_raster(Image.new("1", (16, 2), 1))
    assert filled[8:] == b"\xff" * 4


def test_raster_header_dimensions():
    data = rs.image_to_raster(Image.new("1", (640, 10), 0))
    assert data[:4] == b"\x1dv0\x00"
    assert data[4] == 80 and data[5] == 0      # 가로 80바이트 = 640 dot
    assert data[6] == 10 and data[7] == 0      # 세로 10줄
    assert len(data) == 8 + 80 * 10


def test_ascii_stays_text():
    """영문만 있으면 래스터를 쓰지 않는다 — 60배 무거워지기 때문."""
    p = Printer("usb://dummy")
    p.text("HELLO WORLD")
    out = p.bytes()
    assert b"HELLO WORLD\n" in out
    assert b"\x1dv0" not in out


def test_korean_becomes_raster():
    p = Printer("usb://dummy")
    p.text("성만교회")
    out = p.bytes()
    assert b"\x1dv0" in out


def test_mixed_lines_split_correctly():
    """한 호출에 섞여 있어도 줄 단위로 알맞게 나뉜다."""
    p = Printer("usb://dummy")
    p.text("ASCII\n한글\nASCII2")
    out = p.bytes()
    assert b"ASCII\n" in out and b"ASCII2\n" in out
    assert out.count(b"\x1dv0") == 1


def _row_body(p, left, right):
    """row() 가 더한 바이트만 떼어 낸다 (앞선 상태 명령은 빼고)."""
    before = len(p.bytes())
    p.row(left, right)
    return p.bytes()[before:].rstrip(b"\n")


def test_row_alignment_ascii():
    body = _row_body(Printer("usb://dummy"), "Item", "1,000")
    assert len(body) == CHARS_PER_LINE
    assert body.startswith(b"Item") and body.endswith(b"1,000")


def test_row_respects_double_width():
    """글자가 2배폭이면 한 줄에 들어가는 글자 수도 절반이다."""
    p = Printer("usb://dummy").size(2, 1)
    assert len(_row_body(p, "A", "B")) == CHARS_PER_LINE // 2


def test_row_never_overflows():
    """양쪽을 합쳐 한 줄을 넘겨도 글자가 잘리지 않는다."""
    body = _row_body(Printer("usb://dummy"), "X" * 40, "Y" * 40)
    assert b"X" * 40 in body and b"Y" * 40 in body


def test_row_korean_becomes_raster():
    body = _row_body(Printer("usb://dummy"), "십일조", "50,000원")
    assert body.startswith(b"\x1dv0")


def test_buffer_resets_after_send():
    sent = []

    class Fake:
        def send(self, data):
            sent.append(data)

    p = Printer(Fake())
    p.text("ONE").send()
    p.text("TWO").send()
    assert b"ONE" in sent[0] and b"TWO" not in sent[0]
    assert b"TWO" in sent[1] and b"ONE" not in sent[1]


def test_context_manager_sends_once():
    sent = []

    class Fake:
        def send(self, data):
            sent.append(data)
        def __enter__(self): return self
        def __exit__(self, *a): return False

    with Printer(Fake()) as p:
        p.text("HI").cut()
    assert len(sent) == 1 and b"HI" in sent[0]


def test_context_manager_skips_send_on_error():
    """예외가 났는데 반쪽짜리 영수증이 나오면 안 된다."""
    sent = []

    class Fake:
        def send(self, data):
            sent.append(data)
        def __enter__(self): return self
        def __exit__(self, *a): return False

    try:
        with Printer(Fake()) as p:
            p.text("HI")
            raise RuntimeError("중간에 실패")
    except RuntimeError:
        pass
    assert sent == []


def test_cut_feeds_first():
    """칼날이 인쇄 위치보다 위에 있어 급지 없이 자르면 글자가 잘린다."""
    p = Printer("usb://dummy")
    p.cut()
    assert p.bytes().endswith(b"\x1bd\x04\x1dV\x00")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  OK  {fn.__name__}")
    print(f"\n{len(fns)}개 통과")
