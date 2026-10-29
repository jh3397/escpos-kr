"""MCP 서버가 실제로 말이 통하는지 stdio 로 접속해 확인한다.

종이는 나오지 않는다 (dry_run 만 쓴다).

    python tests/check_mcp.py
    python tests/check_mcp.py /경로/escpos-kr-mcp     # 실행 파일 지정
"""
import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

DEFAULT_CMD = str(Path(sys.executable).parent / "escpos-kr-mcp")


async def check(command: str) -> int:
    params = StdioServerParameters(command=command, env=dict(os.environ))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            info = await s.initialize()
            print(f"  서버 : {info.server_info.name} {info.server_info.version}")

            tools = await s.list_tools()
            names = [t.name for t in tools.tools]
            print(f"  도구 : {', '.join(names)}")
            for expected in ("list_printers", "print_receipt", "print_text"):
                if expected not in names:
                    print(f"  !! {expected} 가 없습니다")
                    return 1

            res = await s.call_tool("list_printers", {})
            print("  연결 상태:")
            print("   ", res.content[0].text.replace("\n", "\n    "))

            res = await s.call_tool(
                "print_text", {"text": "확인 (출력 안 함)", "dry_run": True})
            if '"printed": false' not in res.content[0].text:
                print("  !! dry_run 인데 찍었다고 한다")
                return 1
            print("  dry_run : 종이 나가지 않음 확인")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CMD
    if not Path(cmd).exists():
        sys.exit(f"실행 파일이 없습니다: {cmd}\n"
                 f"  pip install -e '<프로젝트경로>[mcp]' 를 먼저 하세요")
    code = asyncio.run(check(cmd))
    print("  >> 정상" if code == 0 else "  >> 문제 있음")
    sys.exit(code)
