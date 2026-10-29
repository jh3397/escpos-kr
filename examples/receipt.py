"""영수증 예제. 항목·금액·합계·QR 이 있는 전형적인 형태.

    .venv/bin/python examples/receipt.py            # 실제 출력
    .venv/bin/python examples/receipt.py --dry-run  # 바이트만 확인
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from escpos_kr import Printer

HEADER = "가게 이름"        # 쓰는 곳에 맞게 바꾼다
ITEMS = [("아메리카노", 4500), ("카페라떼", 5000), ("치즈케이크", 7000)]


def build(p: Printer) -> Printer:
    p.align("center").size(2, 2).bold().text(HEADER)
    p.reset().text("영수증").feed(1)

    p.align("left").line("=")
    p.text(f"일자: {date.today():%Y-%m-%d}")
    p.line("-")

    for name, amount in ITEMS:
        p.row(name, f"{amount:,}원")

    p.line("-")
    p.bold().row("합계", f"{sum(a for _, a in ITEMS):,}원").reset()
    p.line("=")

    p.feed(1).align("center").text("감사합니다")
    p.qr("https://example.com/receipt/1234", module=5)
    return p.cut()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    p = build(Printer("usb://dry-run" if dry else None))
    if dry:
        data = p.bytes()
        print(f"{len(data):,} 바이트 — 전송하지 않음")
        raster_count = data.count(b"\x1dv0")
        has_qr = b"\x1d(k" in data
        print(f"  래스터 {raster_count}장, QR {'있음' if has_qr else '없음'}")
    else:
        p.send()
        print("출력 완료")
