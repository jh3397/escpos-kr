"""프린터 없이 돌아가는 검사. 바이트가 제대로 조립되는지만 본다.

    .venv/bin/python -m pytest tests -q
    .venv/bin/python tests/test_payload.py      # pytest 없이도 실행된다
"""
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

from escpos_kr import CHARS_PER_LINE, Printer
from escpos_kr import commands as cmd
from escpos_kr import config
from escpos_kr import raster as rs
from escpos_kr import transport as tr


@contextmanager
def env(**kw):
    """환경변수를 잠깐 바꾼다."""
    old = {k: os.environ.get(k) for k in kw}
    try:
        for k, v in kw.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _dots(payload):
    """래스터 payload 에서 '찍는 점' 의 비율."""
    body = payload[8:]
    return sum(bin(b).count("1") for b in body) / (len(body) * 8)


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


def test_higher_threshold_prints_fewer_dots():
    """임계값을 올리면 획이 얇아져야 한다.

    이게 뒤집히면 번짐을 줄이려고 올린 값이 오히려 글자를 굵게 만든다.
    """
    def dots(threshold):
        data = rs.render_lines(["성만교회 헌금 영수증"], threshold=threshold)
        return sum(bin(b).count("1") for b in data)

    thin, thick = dots(200), dots(80)
    assert thin < thick, f"임계값 200 이 80 보다 점이 많다 ({thin} >= {thick})"


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


def _row_body(p, left, right, filler=" "):
    """row() 가 더한 바이트만 떼어 낸다 (앞선 상태 명령은 빼고)."""
    before = len(p.bytes())
    p.row(left, right, filler)
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


# ---- 리뷰에서 나온 결함들의 회귀 검사 ----

def test_escpos_target_is_honored():
    """문서에 적힌 ESCPOS_TARGET 이 실제로 전송 경로를 바꿔야 한다."""
    with env(ESCPOS_TARGET="192.0.2.99"):
        t = tr.open_transport()
    assert isinstance(t, tr.Network) and t.host == "192.0.2.99"


def test_explicit_target_beats_env():
    with env(ESCPOS_TARGET="192.0.2.99"):
        t = tr.open_transport("usb://explicit")
    assert isinstance(t, tr.USB) and t.uri == "usb://explicit"


def test_missing_nc_keeps_original_cause():
    """nc 가 없다고 해서 '연결 실패' 라는 진짜 원인이 가려지면 안 된다."""
    real = subprocess.run

    def fake(cmd_, *a, **k):
        if cmd_ and cmd_[0] == "nc":
            raise FileNotFoundError(2, "No such file or directory", "nc")
        return real(cmd_, *a, **k)

    subprocess.run = fake
    try:
        n = tr.Network("192.0.2.1", timeout=0.3)
        try:
            n.send(b"x")
        except tr.TransportError as e:
            assert "nc" in str(e)
        except FileNotFoundError:
            raise AssertionError("FileNotFoundError 가 그대로 올라왔다")
        else:
            raise AssertionError("실패해야 하는데 성공했다")
    finally:
        subprocess.run = real


def test_transparent_image_is_not_all_black():
    """투명 배경 로고가 용지를 새까맣게 채우면 안 된다."""
    transparent = Image.new("RGBA", (64, 16), (0, 0, 0, 0))
    assert _dots(rs.render_image(transparent)) == 0


def test_transparent_image_keeps_its_content():
    img = Image.new("RGBA", (64, 16), (0, 0, 0, 0))
    for x in range(10, 20):
        for y in range(4, 12):
            img.putpixel((x, y), (0, 0, 0, 255))
    assert 0 < _dots(rs.render_image(img, dither=False)) < 0.5


def test_image_accepts_pathlib_path(tmpdir=None):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "logo.png"
        Image.new("RGB", (32, 16), "white").save(f)
        assert rs.render_image(f)            # AttributeError 가 나면 실패


def test_columns_follow_paper_width():
    """58mm(384dot) 에서 48자로 계산하면 구분선이 접힌다."""
    with env(ESCPOS_WIDTH="384", ESCPOS_COLUMNS=None):
        assert config.columns() == 32
        p = Printer("usb://dummy")
        assert p.chars_per_line == 32
        before = len(p.bytes())
        p.line()
        assert len(p.bytes()[before:].rstrip(b"\n")) == 32


def test_columns_can_be_overridden():
    with env(ESCPOS_COLUMNS="42"):
        assert Printer("usb://dummy").chars_per_line == 42


def test_non_ascii_rule_does_not_raise():
    """한국어 문서에서 흔한 괘선 문자도 받아야 한다."""
    p = Printer("usb://dummy")
    p.line("─")
    assert b"\x1dv0" in p.bytes()


def test_non_ascii_filler_falls_back_to_raster():
    p = Printer("usb://dummy")
    p.row("A", "B", filler="·")
    assert b"\x1dv0" in p.bytes()


def test_style_survives_send():
    """INIT 이 프린터를 되돌리므로, 다음 전송에 꾸밈을 다시 적어야 한다."""
    sent = []

    class Fake:
        def send(self, data):
            sent.append(data)

    p = Printer(Fake())
    p.align("center").bold().text("A").send()
    p.text("B").send()
    assert cmd.ALIGN["center"] in sent[1]
    assert cmd.BOLD_ON in sent[1]


def test_width_and_columns_stay_consistent():
    """둘이 어긋나면 우측 정렬한 글자가 종이 밖으로 나간다 (실물에서 겪었다)."""
    assert cmd.WIDTH_DOTS == config.DEFAULT_WIDTH
    assert config.columns_for(config.DEFAULT_WIDTH) == CHARS_PER_LINE
    assert config.DEFAULT_WIDTH % config.CHAR_WIDTH_DOTS == 0


def test_right_aligned_text_stays_inside_paper():
    """우측 정렬 래스터의 마지막 점이 인쇄 폭 안에 있어야 한다."""
    payload = rs.render_row("왼쪽", "오른쪽 끝", width=config.DEFAULT_WIDTH)
    width_bytes = payload[4] + payload[5] * 256
    assert width_bytes * 8 <= config.DEFAULT_WIDTH + 7

    body = payload[8:]
    rows = len(body) // width_bytes
    last_col_used = 0
    for r in range(rows):
        row = body[r * width_bytes:(r + 1) * width_bytes]
        for i in range(width_bytes - 1, -1, -1):
            if row[i]:
                last_col_used = max(last_col_used, i)
                break
    assert last_col_used * 8 < config.DEFAULT_WIDTH


def test_partial_send_is_not_retried():
    """일부가 이미 인쇄됐는데 nc 로 전체를 다시 보내면 영수증이 두 장 나온다."""
    nc_calls = []
    real = subprocess.run

    def fake_run(cmd_, *a, **k):
        if cmd_ and cmd_[0] == "nc":
            nc_calls.append(cmd_)

            class R:
                returncode = 0
            return R()
        return real(cmd_, *a, **k)

    class HalfDeadSocket:
        def __init__(self):
            self.sent = 0

        def send(self, chunk):
            if self.sent:                      # 두 번째 호출에서 끊긴다
                raise OSError("connection reset")
            self.sent = 10
            return 10

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    real_conn = tr.socket.create_connection
    tr.socket.create_connection = lambda *a, **k: HalfDeadSocket()
    subprocess.run = fake_run
    try:
        try:
            tr.Network("192.0.2.1").send(b"x" * 100)
        except tr.TransportError as e:
            assert "도중에 끊" in str(e) and "10/100" in str(e)
        else:
            raise AssertionError("실패해야 하는데 성공했다")
        assert nc_calls == [], "부분 전송 후 nc 로 재전송했다"
    finally:
        tr.socket.create_connection = real_conn
        subprocess.run = real


def test_connect_failure_still_falls_back_to_nc():
    """연결 자체가 막힌 경우(로컬 네트워크 권한)는 재전송이 안전하다."""
    nc_calls = []
    real = subprocess.run

    def fake_run(cmd_, *a, **k):
        if cmd_ and cmd_[0] == "nc":
            nc_calls.append(cmd_)

            class R:
                returncode = 0
            return R()
        return real(cmd_, *a, **k)

    real_conn = tr.socket.create_connection

    def refuse(*a, **k):
        raise OSError(65, "No route to host")

    tr.socket.create_connection = refuse
    subprocess.run = fake_run
    try:
        tr.Network("192.0.2.1").send(b"hello")
        assert len(nc_calls) == 1
    finally:
        tr.socket.create_connection = real_conn
        subprocess.run = real


def test_usb_temp_file_is_cleaned_up_on_failure():
    """백엔드가 실패해도 임시파일이 남으면 안 된다."""
    import glob
    import tempfile as tf

    real = subprocess.run

    def failing(cmd_, *a, **k):
        class R:
            returncode = 1
            stderr = "boom"
        return R()

    subprocess.run = failing
    try:
        before = set(glob.glob(str(Path(tf.gettempdir()) / "*.escpos")))
        u = tr.USB("usb://dummy")
        try:
            u.send(b"data")
        except tr.TransportError:
            pass
        else:
            raise AssertionError("실패해야 한다")
        after = set(glob.glob(str(Path(tf.gettempdir()) / "*.escpos")))
        assert after == before
    finally:
        subprocess.run = real


def test_receipt_hint_ignores_words_containing_pos():
    """'composite' 같은 단어에 걸려 엉뚱한 프린터를 고르면 안 된다."""
    assert tr._RECEIPT_HINT.search('usb://Printer/POS-80 "Printer POS-80"')
    assert tr._RECEIPT_HINT.search('usb://Epson/TM-T88V "EPSON TM-T88V"')
    assert tr._RECEIPT_HINT.search('usb://X/Y "Generic Thermal Receipt"')
    assert not tr._RECEIPT_HINT.search('usb://HP/DeskJet "HP Composite Device"')
    assert not tr._RECEIPT_HINT.search('usb://C/E2000 "Canon Exposure 2000"')


# ---- 2차 리뷰: 1차 수정이 만든 결함들 ----

def test_serial_number_is_not_mistaken_for_a_receipt_printer():
    """모델명 패턴이 시리얼에 우연히 걸리면 엉뚱한 프린터를 고른다."""
    bad = [
        'direct usb://Brother/HL-L2340D?serial=RP12345 "Brother HL-L2340D"',
        'direct usb://HP/OfficeJet?serial=RP7 "HP OfficeJet 8012"',
        'direct usb://Canon/MG3600?serial=TM-9 "Canon MG3600 series"',
    ]
    for line in bad:
        assert not tr._RECEIPT_HINT.search(tr._SERIAL.sub("", line)), line

    good = [
        'direct usb://Printer/POS-80?serial=XXXXXXXXXXXX "Printer POS-80"',
        'direct usb://Epson/TM-T88V?serial=X "EPSON TM-T88V"',
    ]
    for line in good:
        assert tr._RECEIPT_HINT.search(tr._SERIAL.sub("", line)), line


def test_nothing_is_sent_when_there_is_no_content():
    """꾸밈 상태를 미리 적어 두므로 버퍼 길이로는 판별할 수 없다."""
    sent = []

    class Fake:
        def send(self, data):
            sent.append(data)

    p = Printer(Fake())
    p.align("center").bold()          # 꾸밈만 — 종이에 나갈 것이 없다
    p.send()
    assert sent == []

    p.text("A").send()
    assert len(sent) == 1
    p.send()                          # 다시 불러도 보낼 것이 없다
    assert len(sent) == 1


def test_context_manager_does_not_resend_after_explicit_send():
    sent = []

    class Fake:
        def send(self, data):
            sent.append(data)
        def __enter__(self): return self
        def __exit__(self, *a): return False

    with Printer(Fake()) as p:
        p.align("center").text("A").send()
    assert len(sent) == 1


def test_socket_is_closed_before_nc_fallback():
    """이 프린터는 동시 접속을 하나만 받는다 — 소켓을 쥔 채 nc 를 띄우면 거부된다."""
    state = {"closed": False, "open_at_nc": None}
    real = subprocess.run

    class Sock:
        def send(self, b):
            raise OSError("broken pipe")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            state["closed"] = True
            return False

    def fake_run(cmd_, *a, **k):
        if cmd_ and cmd_[0] == "nc":
            state["open_at_nc"] = not state["closed"]

            class R:
                returncode = 0
            return R()
        return real(cmd_, *a, **k)

    real_conn = tr.socket.create_connection
    tr.socket.create_connection = lambda *a, **k: Sock()
    subprocess.run = fake_run
    try:
        tr.Network("192.0.2.1").send(b"x" * 10)
        assert state["open_at_nc"] is False
    finally:
        tr.socket.create_connection = real_conn
        subprocess.run = real


def test_non_ascii_filler_is_actually_drawn():
    """래스터 경로에서 filler 가 조용히 사라지면 안 된다."""
    def dots(payload):
        body = payload[8:]
        return sum(bin(b).count("1") for b in body)

    plain = rs.render_row("ITEM", "1,000", filler=" ")
    leader = rs.render_row("ITEM", "1,000", filler="·")
    assert dots(leader) > dots(plain)


def test_env_columns_wins_over_width_derivation():
    """기종 보정으로 설정해 둔 값이 폭에서 유도한 값에 지면 안 된다."""
    with env(ESCPOS_COLUMNS="40"):
        assert Printer("usb://dummy").chars_per_line == 40
        assert Printer("usb://dummy", width=576).chars_per_line == 40
        # 명시적 인자는 환경변수보다 세다
        assert Printer("usb://dummy", columns=30).chars_per_line == 30


def test_row_filler_never_breaks_line_width():
    """빈 filler 는 정렬을 없애고, 여러 글자짜리는 줄을 넘겼다."""
    for filler in ("", " ", ".", "..", "----"):
        body = _row_body(Printer("usb://dummy"), "ITEM", "1,000", filler)
        assert len(body) == CHARS_PER_LINE, (filler, len(body))
        assert body.startswith(b"ITEM") and body.endswith(b"1,000")


def test_non_ascii_filler_uses_raster_not_text():
    """'···' 같은 문자는 내장 폰트에 없으므로 래스터로 가야 한다."""
    body = _row_body(Printer("usb://dummy"), "ITEM", "1,000", "···")
    assert body.startswith(b"\x1dv0")


def _raster_rows(data):
    """GS v 0 래스터를 (폭바이트, 줄 목록) 으로 푼다."""
    i = data.index(b"\x1dv0")
    wb = data[i+4] + data[i+5]*256
    h = data[i+6] + data[i+7]*256
    body = data[i+8:i+8+wb*h]
    return wb, [body[r*wb:(r+1)*wb] for r in range(h)]


def _ink_columns(rows, wb):
    cols = set()
    for r in rows:
        for byte_i in range(wb):
            if r[byte_i]:
                for bit in range(8):
                    if r[byte_i] & (0x80 >> bit):
                        cols.add(byte_i*8 + bit)
    return cols


def test_small_image_stays_inside_the_paper():
    """작은 그림을 보내도 래스터 폭은 용지 폭이어야 한다.

    폭이 줄어들면 프린터가 줄 길이를 잘못 읽어 그림이 비스듬히 밀린다.
    """
    from PIL import Image
    src = Image.new("L", (100, 100), 0)
    data = rs.render_image(src, width=160, dither=False, paper_width=576)
    wb, rows = _raster_rows(data)
    assert wb == 72, f"폭 바이트가 72 가 아니라 {wb}"


def test_image_align_moves_the_ink():
    """align 이 그림을 실제로 옮겨야 한다. 여백은 희게 남아야 한다."""
    from PIL import Image
    src = Image.new("L", (100, 100), 0)          # 새까만 사각형
    out = {}
    for how in ("left", "center", "right"):
        wb, rows = _raster_rows(
            rs.render_image(src, width=160, dither=False,
                            align=how, paper_width=576))
        out[how] = _ink_columns(rows, wb)

    assert min(out["left"]) == 0, "왼쪽 정렬인데 왼쪽 끝이 비었다"
    assert max(out["right"]) >= 575 - 8, "오른쪽 정렬인데 오른쪽 끝이 비었다"
    assert min(out["center"]) > min(out["left"]), "가운데가 왼쪽과 같다"
    assert max(out["center"]) < max(out["right"]), "가운데가 오른쪽과 같다"
    for how in out:
        assert len(out[how]) <= 160, f"{how}: 잉크가 그림 폭보다 넓다"


def test_image_width_is_clamped_to_the_paper():
    """용지보다 넓게 달라고 해도 넘치면 안 된다."""
    from PIL import Image
    src = Image.new("L", (100, 100), 0)
    wb, _ = _raster_rows(
        rs.render_image(src, width=5000, dither=False, paper_width=576))
    assert wb == 72, f"폭 바이트가 72 가 아니라 {wb}"


def test_mcp_block_exposes_image_width():
    from escpos_kr.mcp_server import Block
    assert Block(type="image", path="x.png").width == 0      # 0 = 용지 폭
    assert Block(type="image", path="x.png", width=160).width == 160


def test_mcp_block_exposes_dither():
    """로고를 깨끗하게 찍으려면 에이전트가 디더링을 끌 수 있어야 한다."""
    from escpos_kr.mcp_server import Block
    assert Block(type="image", path="x.png").dither is True
    assert Block(type="image", path="x.png", dither=False).dither is False


def test_mcp_block_exposes_filler():
    """라이브러리에만 넣고 MCP 에 안 넣으면 에이전트는 쓸 수 없다."""
    from escpos_kr.mcp_server import Block, _compose
    assert "filler" in Block.model_fields

    p = Printer("usb://dummy")
    _compose(p, [Block(type="row", left="ITEM", right="1,000", filler=".")])
    assert b"." * 10 in p.bytes()


def test_mcp_tool_defaults_are_real_values():
    """Field(...) 를 기본값으로 두면 직접 호출 시 항상 dry_run 이 된다."""
    import inspect
    from escpos_kr.mcp_server import print_receipt
    params = inspect.signature(print_receipt).parameters
    assert params["cut"].default is True
    assert params["dry_run"].default is False
    assert params["target"].default is None


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  OK  {fn.__name__}")
    print(f"\n{len(fns)}개 통과")
