#!/usr/bin/env python3
"""연결 확인용 출력. 프린터가 제대로 붙었는지 한 장으로 본다.

    python print_test.py                 # USB 우선, 없으면 ESCPOS_HOST
    python print_test.py usb             # USB 강제
    python print_test.py 192.168.0.8     # 네트워크 강제
"""
import sys

from escpos_kr import Printer, config, find_usb


def main(target=None):
    where = target or ("USB" if find_usb() else (config.host() or "대상 없음"))
    print(f"-> {where} 로 전송")

    with Printer(target) as p:
        p.align("center").size(2, 2).bold().text("ESCPOS-KR")
        p.reset().line("-")
        p.align("left")
        p.row("Transport", "USB" if find_usb() else "Network")
        p.row("Width", f"{config.width()} dot")
        p.line("-")
        p.text("한글 출력 테스트")
        p.row("항목", "50,000원")
        p.align("center").text("정상 출력").cut()

    print("완료")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
