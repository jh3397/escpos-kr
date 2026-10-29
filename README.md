# escpos-kr

한글이 되는 ESC/POS 영수증 프린터 라이브러리. USB·네트워크로 보내고,
MCP 서버로 다른 에이전트에게 열어줄 수도 있다.

POS-8390 (80mm, 640 dot) 으로 검증했다. 같은 ESC/POS 계열이면 대체로 그대로 쓴다.

## 왜 있나

영수증 프린터 대부분은 **한글 폰트가 없다.** 내장 문자셋이 GB18030 / ASCII /
BIG5 뿐이라 한글을 텍스트로 보내면 깨진다. 이 라이브러리는 줄마다 보고
한글이 섞여 있으면 이미지로 그려 보낸다 — 쓰는 쪽은 신경 쓰지 않아도 된다.

## 설치

```bash
pip install -e "/Volumes/projects/escpos-kr"          # 라이브러리만
pip install -e "/Volumes/projects/escpos-kr[mcp]"     # MCP 서버까지
```

## 쓰기

```python
from escpos_kr import Printer

with Printer() as p:                        # USB 우선, 없으면 ESCPOS_HOST
    p.align("center").size(2, 2).bold().text("가게 이름")
    p.reset().line("=")
    p.row("아메리카노", "4,500원")
    p.row("카페라떼",   "5,000원")
    p.line("-")
    p.bold().row("합계", "9,500원")
    p.qr("https://example.com/receipt/1234")
    p.cut()
```

`with` 를 빠져나갈 때 한 번에 보낸다. 중간에 예외가 나면 보내지 않는다 —
반쪽짜리 영수증이 나오는 것보다 낫다.

| 메서드 | 하는 일 |
|---|---|
| `text(s)` | 한 줄 또는 여러 줄(`\n`). 한글이면 자동 래스터 |
| `row(left, right)` | 왼쪽 끝과 오른쪽 끝에 붙인다 |
| `line(char)` | 구분선. 용지 폭과 글자 크기에 맞춰 길이가 바뀐다. `─` 같은 괘선 문자도 된다 |
| `qr(data)` | 내장 QR. 별도 라이브러리가 필요 없다 |
| `image(path)` | 로고·사진. 경로는 문자열이나 `Path`. 선화는 `dither=False` 가 깨끗하다. 투명 배경은 흰색으로 합성된다 |
| `align` `bold` `underline` `size` `reset` | 꾸밈. 체이닝된다 |
| `feed` `cut` `beep` `drawer` | 급지, 커팅, 부저, 금전함 |
| `bytes()` | 보내지 않고 바이트만 — 시험용 |

전송 경로는 `Printer("usb")`, `Printer("192.168.0.8")` 로 고르거나,
`send(data)` 메서드가 있는 아무 객체나 넘기면 된다 (상속은 필요 없다).

## 설정

코드에 IP 나 폰트 경로를 박지 않는다. 환경변수로 준다.

| 변수 | 기본값 | 뜻 |
|---|---|---|
| `ESCPOS_TARGET` | 자동 | `usb` / `auto` / `usb://...` / IP 주소 |
| `ESCPOS_HOST` | 없음 | 네트워크 주소 (USB 가 없을 때) |
| `ESCPOS_PORT` | 9100 | |
| `ESCPOS_WIDTH` | 576 | **인쇄** 폭(dot). 80mm=576, 58mm=384. 헤드 전체 폭이 아니다 |
| `ESCPOS_COLUMNS` | 폭÷12 | 한 줄 ASCII 글자 수. 80mm=48, 58mm=32 |
| `ESCPOS_FONT` | 자동 탐색 | 한글 폰트 경로 |

폰트는 macOS·Linux·Windows 의 흔한 한글 폰트를 차례로 찾는다.
못 찾으면 어디를 뒤졌는지 알려주고 멈춘다.

한 줄 글자 수는 인쇄 폭을 글자 칸(12 dot)으로 나눈 값이다 — 576/12=48,
384/12=32. `ESCPOS_WIDTH` 에는 **헤드 폭이 아니라 실제로 찍히는 폭**을 넣는다.
POS-8390 은 셀프테스트에 640 dot 이라고 인쇄하지만 종이에 나오는 것은 576 까지다.
**구분선이 다음 줄로 접히거나 오른쪽 글자가 잘리면** 이 값이 큰 것이다.

## MCP

다른 에이전트가 쓰게 하려면 [docs/MCP.md](docs/MCP.md).
도구는 `list_printers`, `print_receipt`, `print_text` 세 개이고,
전부 `dry_run` 을 받는다.

## 확인

```bash
python print_test.py                    # 한 장 뽑아 연결 확인
python tests/test_payload.py            # 프린터 없이 15개 검사
python tests/check_mcp.py               # MCP 서버 접속 확인 (종이 안 나감)
python examples/receipt.py --dry-run    # 찍지 않고 결과만
```

## 문서

- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — 안 찍힐 때 확인할 것
- [docs/MCP.md](docs/MCP.md) — MCP 서버 등록과 도구
- [docs/pos-8390/](docs/pos-8390/) — POS-8390 전용. 무선 설정 절차와
  설정 페이지 도구, 성만교회 설치 당시의 진단 기록
