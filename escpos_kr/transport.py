"""프린터로 바이트를 보내는 경로.

USB 와 네트워크(9100) 두 가지가 있고, 둘 다 macOS 에서 평범한 방법이 막혀 있다.
자세한 사정은 각 클래스의 주석에 적어 두었다.
"""
from __future__ import annotations   # 구버전 파이썬에서도 str | None 표기를 쓰기 위해

import os
import re
import socket
import subprocess
import tempfile

from . import config

USB_BACKEND = "/usr/libexec/cups/backend/usb"

# 어떤 USB 장치가 영수증 프린터인지 가려내는 표시.
# 단어 경계를 두지 않으면 'composite', 'exposure' 처럼 pos 를 품은 흔한 단어에
# 걸려 엉뚱한 프린터를 고른다 — 잉크젯에 ESC/POS 바이트가 그대로 들어간다.
_RECEIPT_HINT = re.compile(
    r"\bPOS\b|\bPOS-\d|\bTM-\w*\d|\bSRP-\d|\bRP-?\d|thermal|receipt",
    re.I)
_USB_URI = re.compile(r"(usb://\S+)")


class TransportError(RuntimeError):
    pass


class Transport:
    """전송 경로의 공통 인터페이스."""

    def send(self, data: bytes) -> None:
        raise NotImplementedError

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def find_usb_devices() -> list[str]:
    """USB 로 붙은 영수증 프린터로 보이는 장치 URI 들."""
    try:
        out = subprocess.run([USB_BACKEND], capture_output=True, text=True,
                             timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    found = []
    for line in out.splitlines():
        m = _USB_URI.search(line)
        if m and _RECEIPT_HINT.search(line):
            found.append(m.group(1).strip('"'))
    return found


def find_usb() -> str | None:
    """USB 로 붙은 영수증 프린터의 CUPS 장치 URI. 없으면 None.

    여러 대가 걸리면 첫 번째를 쓴다. 어느 것이 걸렸는지는
    find_usb_devices() 로 확인한다 (MCP 의 list_printers 가 함께 보여준다).
    """
    devices = find_usb_devices()
    return devices[0] if devices else None


class USB(Transport):
    """CUPS 의 USB 백엔드를 직접 호출한다.

    macOS 는 raw 큐를 폐지해서 `lpadmin -m raw` 가 거부되고, 일반 PPD 를 끼우면
    ESC/POS 바이트가 가공되어 깨진다. 백엔드 바이너리를 직접 부르면 바이트가
    그대로 통과하며, sudo 도 필요 없다.
    """

    def __init__(self, uri: str | None = None):
        self.uri = uri or find_usb()
        if not self.uri:
            raise TransportError("USB 프린터를 찾지 못했습니다 (케이블·전원 확인)")

    def send(self, data: bytes) -> None:
        fd, path = tempfile.mkstemp(suffix=".escpos")
        try:
            # os.write 를 직접 쓰면 예외가 날 때 기술자가 남고, 반환값을
            # 확인하지 않아 부분 쓰기가 조용히 영수증을 자른다.
            # fdopen 은 예외가 나도 기술자를 닫고, write 는 전량을 보장한다.
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            env = dict(os.environ, DEVICE_URI=self.uri)
            r = subprocess.run(
                [USB_BACKEND, "1", os.environ.get("USER", "escpos"),
                 "escpos-kr", "1", "", path],
                env=env, capture_output=True, text=True, timeout=180)
            if r.returncode != 0:
                raise TransportError(
                    f"USB 전송 실패 (exit={r.returncode})\n{r.stderr.strip()}")
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def __repr__(self):
        return f"USB({self.uri!r})"


class Network(Transport):
    """9100 포트로 보낸다 (JetDirect 방식).

    macOS Sequoia 의 '로컬 네트워크' 권한이 없는 파이썬은 LAN 접속이
    OSError: [Errno 65] No route to host 로 막힌다. 라우트·ARP 가 멀쩡하고
    ping 과 nc 는 되는데 파이썬만 안 되면 이것이다 — 라우팅 문제로 오진하기 쉽다.
    이미 권한이 있는 nc 로 넘겨 우회한다.
    """

    def __init__(self, host: str, port: int | None = None,
                 timeout: float = 5.0):
        self.host = host
        self.port = port or config.port()
        self.timeout = timeout

    def send(self, data: bytes) -> None:
        try:
            sock = socket.create_connection((self.host, self.port),
                                            timeout=self.timeout)
        except OSError as e:
            # 연결 자체가 막힌 경우다. 로컬 네트워크 권한 문제가 여기 걸린다.
            # 아직 한 바이트도 안 나갔으니 nc 로 다시 보내도 안전하다.
            return self._send_via_nc(data, e)

        with sock:
            sent = 0
            try:
                while sent < len(data):
                    n = sock.send(data[sent:])
                    if n == 0:
                        raise OSError("소켓이 더 이상 받지 않습니다")
                    sent += n
            except OSError as e:
                if sent:
                    # 일부가 이미 인쇄되었다. nc 로 전체를 다시 보내면
                    # 잘린 영수증 뒤에 온전한 영수증이 또 나온다.
                    raise TransportError(
                        f"전송이 도중에 끊겼습니다 ({self.host}:{self.port}) — "
                        f"{sent}/{len(data)} 바이트 전송됨. 일부가 이미 인쇄되어 "
                        f"자동 재전송하지 않습니다: {e}") from e
                return self._send_via_nc(data, e)

    def _send_via_nc(self, data: bytes, first: OSError) -> None:
        """권한 있는 nc 로 넘긴다. 아직 아무것도 보내지 않았을 때만 부른다."""
        try:
            r = subprocess.run(["nc", "-w", "15", self.host, str(self.port)],
                               input=data, capture_output=True)
        except OSError as e:
            # nc 가 없는 환경이 흔하다. 여기서 FileNotFoundError 를 그대로
            # 올리면 '프린터 연결 실패' 라는 진짜 원인이 가려진다.
            raise TransportError(
                f"네트워크 전송 실패 ({self.host}:{self.port}) — "
                f"소켓: {first}, nc 실행 불가: {e}") from first
        if r.returncode != 0:
            raise TransportError(
                f"네트워크 전송 실패 ({self.host}:{self.port}) — "
                f"소켓: {first}, nc: exit={r.returncode}") from first

    def __repr__(self):
        return f"Network({self.host!r}, {self.port})"


def auto(host: str | None = None) -> Transport:
    """USB 가 꽂혀 있으면 USB, 아니면 네트워크.

    USB 가 더 안정적이라 먼저 본다. host 를 주지 않으면 네트워크는 쓸 수 없다.
    """
    uri = find_usb()
    if uri:
        return USB(uri)
    host = host or config.host()
    if host:
        return Network(host)
    raise TransportError(
        "USB 프린터가 없고 네트워크 주소도 없습니다. "
        "ESCPOS_HOST 환경변수를 설정하거나 host= 로 넘겨 주세요")


def is_transport(obj) -> bool:
    """send() 만 있으면 전송 경로로 본다.

    Transport 를 상속하도록 강제하지 않는다. 직접 만든 경로나 시험용 가짜를
    끼우는 쪽이 흔하고, 그때마다 상속을 요구할 이유가 없다.
    """
    return not isinstance(obj, str) and callable(getattr(obj, "send", None))


def open_transport(target: str | Transport | None = None,
                   host: str | None = None) -> Transport:
    """문자열 하나로 경로를 고른다.

    None 또는 "auto" → USB 우선, "usb" → USB 강제,
    "usb://..." → 그 장치, 그 밖의 문자열 → 네트워크 주소로 본다.
    """
    if is_transport(target):
        return target
    if target is None:                      # 인자가 없을 때만 환경변수를 본다
        target = config.target()
    if target is None or target == "auto":
        return auto(host)
    if target == "usb":
        return USB()
    if target.startswith("usb://"):
        return USB(target)
    return Network(target)
