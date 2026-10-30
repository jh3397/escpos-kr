# escpos-kr MCP 붙이기

영수증 프린터(POS-8390)를 MCP 로 쓰는 설정입니다.
**클라이언트마다 따로 등록해야 합니다** — 한 곳에 넣는다고 다른 앱이 보지 않습니다.

## 설정 JSON

```json
{
  "mcpServers": {
    "escpos-kr": {
      "command": "/Volumes/projects/escpos-kr/.venv/bin/escpos-kr-mcp",
      "env": {
        "ESCPOS_HOST": "192.168.0.8"
      }
    }
  }
}
```

## 넣는 곳

| 클라이언트 | 방법 |
|---|---|
| Claude Code | `claude mcp add-json -s user escpos-kr '<위 JSON 의 escpos-kr 값>'` |
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` 에 `mcpServers` 항목으로 추가 |
| Cursor · 그 밖 | 각 앱의 MCP 설정 파일에 같은 모양으로 추가 |

넣은 뒤 **앱을 다시 시작**해야 붙습니다.

## 쓸 수 있는 도구

- `list_printers` — 연결 상태 확인 (읽기 전용, 종이 안 나감)
- `print_receipt` — 영수증 출력. `blocks` 에 토막을 순서대로 담음
- `print_text` — 글 한 덩이 출력

둘 다 `dry_run: true` 를 주면 찍지 않고 결과만 알려줍니다.

### print_receipt 예시

```json
{
  "blocks": [
    {"type": "text", "text": "가게 이름", "align": "center", "size": 2, "bold": true},
    {"type": "line", "char": "="},
    {"type": "row", "left": "아메리카노", "right": "4,500원", "filler": "."},
    {"type": "row", "left": "카페라떼",   "right": "5,000원", "filler": "."},
    {"type": "line", "char": "-"},
    {"type": "row", "left": "합계", "right": "9,500원", "bold": true},
    {"type": "qr", "data": "https://example.com/receipt/1234"}
  ]
}
```

한글은 그냥 한글로 쓰면 됩니다. 프린터에 한글 폰트가 없지만 서버가 이미지로
바꿔 보냅니다.

## 안 될 때

1. 그 클라이언트의 설정 파일에 `escpos-kr` 가 있는지 확인
2. 앱을 다시 시작했는지 확인
3. `/Volumes/projects` 나스가 마운트돼 있는지 확인
4. 서버 자체 점검: `/Volumes/projects/escpos-kr/.venv/bin/python /Volumes/projects/escpos-kr/tests/check_mcp.py`

4번이 "정상" 이면 서버는 멀쩡한 것이고, 문제는 클라이언트 등록입니다.

## 프린터 정보

- 무선: `192.168.0.8:9100` (현재 이 경로로 설정됨)
- 응답 50ms 내외, 30KB 전송 0.4초
- 절전에서 깨는 첫 요청은 1~2초 걸릴 수 있음 — 정상입니다
