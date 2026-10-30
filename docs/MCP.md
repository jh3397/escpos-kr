# MCP 서버 — 다른 에이전트에게 프린터를 열어주기

`escpos-kr-mcp` 는 stdio MCP 서버다. Claude Code, Claude Desktop 등
MCP 를 지원하는 에이전트에 붙이면 그 에이전트가 영수증을 찍을 수 있다.

## 설치

```bash
pip install -e "/Volumes/projects/escpos-kr[mcp]"
```

## 등록

### Claude Code

명령 한 줄이면 된다. `-s user` 면 모든 프로젝트에서,
`-s project` 면 그 프로젝트의 `.mcp.json` 에만 들어간다.

```bash
claude mcp add-json -s user escpos-kr '{
  "type": "stdio",
  "command": "/Volumes/projects/escpos-kr/.venv/bin/escpos-kr-mcp",
  "env": { "ESCPOS_HOST": "192.168.0.8" }
}'
```

> **`claude mcp add` 는 쓰지 말 것.** `-e` 옵션이 가변 인자라
> `claude mcp add -e KEY=v 서버이름 -- 명령` 으로 쓰면 **서버 이름까지
> 환경변수로 삼켜** `missing required argument 'commandOrUrl'` 이 난다.
> `add-json` 은 이런 모호함이 없다.

확인:

```bash
claude mcp get escpos-kr      # Status: ✓ Connected 이어야 한다
claude mcp list
```

등록해도 **이미 열려 있는 세션에는 붙지 않는다.** 다시 시작해야 도구가 보인다.

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` 에 넣고 앱을 다시 시작한다.

### 그 밖의 MCP 클라이언트

stdio 서버를 받는 곳이면 어디든 같은 모양이다.

```json
{
  "mcpServers": {
    "escpos-kr": {
      "command": "/Volumes/projects/escpos-kr/.venv/bin/escpos-kr-mcp",
      "env": { "ESCPOS_HOST": "192.168.0.8" }
    }
  }
}
```

USB 로 쓸 거면 `ESCPOS_HOST` 대신 `"ESCPOS_TARGET": "usb"` 를 주거나,
아무것도 주지 않아도 된다 — USB 가 꽂혀 있으면 자동으로 찾는다.
용지 폭이 다른 프린터는 `"ESCPOS_WIDTH": "384"` (58mm) 를 함께 준다.
한글이 번져 보이면 `"ESCPOS_THRESHOLD": "160"` 을 더한다 (획이 얇아진다).
자세한 것은 [TROUBLESHOOTING.md](TROUBLESHOOTING.md) 의 "한글만 번진다".
이 값은 헤드 폭이 아니라 **실제로 찍히는 폭**이다.

### 두 가지 전제

- **나스가 마운트돼 있어야 한다.** `/Volumes/projects` 가 풀리면 서버가 뜨지 않는다.
  자주 쓸 기기라면 소스를 로컬에 복사해 두는 편이 낫다.
- 명령을 **절대 경로**로 적었으므로 PATH 설정에 영향받지 않는다.
  `uv` 나 `npx` 로 띄우는 서버들이 PATH 때문에 연결에 실패하는 일이 흔한데,
  이 서버는 그 문제가 없다.

## 에이전트가 서버를 못 찾을 때

**등록은 클라이언트마다 따로다.** Claude Code 에 등록해도 Claude Desktop,
Cursor 등은 보지 못한다. 설정 파일이 서로 다르기 때문이다.

| 클라이언트 | 설정 위치 |
|---|---|
| Claude Code | `~/.claude.json` 의 최상위 `mcpServers` (`claude mcp add-json -s user`) |
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| 그 밖 | 각자의 MCP 설정 파일 |

순서대로 확인한다.

1. **그 클라이언트에 등록되어 있나** — 위 표의 파일에 `escpos-kr` 항목이 있는지 본다.
   없으면 아래 JSON 을 넣는다.
2. **클라이언트를 다시 시작했나** — 등록해도 이미 떠 있는 세션에는 붙지 않는다.
3. **나스가 마운트돼 있나** — `/Volumes/projects` 가 풀리면 실행 파일을 못 찾는다.
   자주 쓸 기기라면 소스를 로컬에 두는 편이 낫다.
4. **서버 자체는 멀쩡한가** — `python tests/check_mcp.py` 로 확인한다.
   여기서 정상이면 문제는 클라이언트 쪽 등록이다.

> `claude mcp list` 가 `✗ Failed to connect` 로 나오는데 서버는 멀쩡한 경우가 있다.
> 점검을 돌린 셸의 PATH 에 그 서버가 쓰는 명령(`uv`, `node` 등)이 없으면 그렇게 보인다.
> 이 서버는 절대 경로로 실행하므로 PATH 영향을 받지 않는다.

## 도구 세 가지

### `list_printers`
연결 상태를 돌려준다. 읽기 전용이라 종이가 나오지 않는다.
출력하기 전에 먼저 부르면 프린터가 없을 때 헛물켜지 않는다.

```json
{ "usb": "usb://Printer/POS-80?serial=...", "network_host": "192.168.0.8",
  "will_use": "USB", "paper_width_dots": 576,
  "korean_font": "/System/Library/Fonts/AppleSDGothicNeo.ttc" }
```

### `print_receipt`
영수증 한 장을 찍는다. `blocks` 에 토막을 순서대로 담는다.

```json
{
  "blocks": [
    {"type": "text", "text": "가게 이름", "align": "center", "size": 2, "bold": true},
    {"type": "line", "char": "="},
    {"type": "row", "left": "아메리카노", "right": "4,500원", "filler": "."},
    {"type": "row", "left": "카페라떼",   "right": "5,000원", "filler": "."},
    {"type": "line"},
    {"type": "row", "left": "합계", "right": "9,500원"},
    {"type": "qr", "data": "https://example.com/receipt/1234"}
  ]
}
```

| `type` | 쓰는 필드 | 하는 일 |
|---|---|---|
| `text` | `text` | 한 줄 글 (`\n` 으로 여러 줄) |
| `row` | `left`, `right`, `filler` | 왼쪽 끝과 오른쪽 끝에 붙인다. `filler: "."` 면 사이를 점선으로 채운다 |
| `line` | `char` | 구분선 |
| `qr` | `data`, `module` | QR 코드 |
| `feed` | `lines` | 빈 줄 |
| `image` | `path` | 이미지 파일 |

모든 토막에 `align`, `size`(1~4), `bold` 를 줄 수 있다.
`align` 은 지정하면 이후 토막에도 이어지고, `size` 와 `bold` 는 그 토막에만 걸린다.

### `print_text`
형식 없이 글 한 덩이만 찍는다.

## 종이가 나오는 동작이라는 점

`print_receipt` 와 `print_text` 는 **실제로 종이를 뽑는다.** 되돌릴 수 없다.
그래서 둘 다 `dry_run` 을 받는다. `true` 면 찍지 않고 몇 바이트인지,
래스터가 몇 장인지, QR 이 들어갔는지만 알려준다.

에이전트에게는 서버 설명에 "확신이 서지 않으면 dry_run 으로 먼저 확인하라" 고
적어 두었다. MCP 호스트 자체의 승인 절차와는 별개다.

## 한글

에이전트는 한글을 그냥 쓰면 된다. 이 프린터에는 한글 폰트가 없지만,
라이브러리가 줄마다 보고 한글이 섞여 있으면 이미지로 그려 보낸다.
영문만 있는 줄은 내장 폰트로 보내 가볍게 유지한다.

## 확인

```bash
python tests/check_mcp.py
```

stdio 로 실제 접속해 초기화·도구 목록·`list_printers` 를 거치고,
`dry_run` 이 정말 종이를 내보내지 않는지까지 본다. 종이는 나오지 않는다.

연결이 안 되면 순서대로 본다.

1. `/Volumes/projects` 가 마운트돼 있는가
2. `.venv/bin/escpos-kr-mcp` 파일이 있는가 (`pip install -e '.[mcp]'`)
3. `claude mcp get escpos-kr` 가 `✓ Connected` 인가
4. 프린터 자체는 `python print_test.py` 로 따로 확인한다
