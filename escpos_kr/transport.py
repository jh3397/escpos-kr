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

# 어떤 USB 장치가 영수증 프린터인지 가려내는 표시
_RECEIPT_HINT = re.compile(r"POS|TM-|thermal|receipt", re.I)
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


def find_usb() -> str | None:
    """USB 로 붙은 영수증 프린터의 CUPS 장치 URI. 없으면 None."""
    try:
        out = subprocess.run([USB_BACKEND], capture_output=True, text=True,
                             timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        m = _USB_URI.search(line)
        if m and _RECEIPT_HINT.search(line):
            return m.group(1).strip('"')
    return None


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
            os.write(fd, data)
            os.close(fd)
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
            with socket.create_connection((self.host, self.port),
                                          timeout=self.timeout) as s:
                s.sendall(data)
            return
        except OSError as e:
            first = e

        r = subprocess.run(["nc", "-w", "15", self.host, str(self.port)],
                           input=data, capture_output=True)
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
    if target is None or target == "auto":
        return auto(host)
    if target == "usb":
        return USB()
    if target.startswith("usb://"):
        return USB(target)
    return Network(target)
