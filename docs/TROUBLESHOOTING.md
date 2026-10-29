# 안 찍힐 때 확인할 것

증상이 대부분 "네트워크 문제"처럼 보여서 엉뚱한 곳을 파기 쉽다.
실제로 겪은 것들을 원인별로 적는다.

## 급지도 커팅도 되는데 백지만 나온다

**감열지가 뒤집혔다.** 열에 반응하는 면이 헤드(위)를 향해야 한다.
손톱으로 긁어 검은 줄이 나는 쪽이 발색면이다.

소프트웨어 문제와 구분하려면 새까만 래스터 블록을 보내 본다.
그래도 백지면 용지 방향이다.

## 한글이 깨진다

**내장 폰트에 한글이 없다.** 문자셋이 GB18030 / ASCII / BIG5 뿐이다.
Pillow 로 이미지를 그려 `GS v 0` 래스터 명령으로 보내야 한다
(`escpos_kr/raster.py`).

같은 네 줄이 텍스트로는 224바이트, 래스터로는 13.7KB. 60배 무겁다.

## Python 만 `No route to host` 가 난다

라우트도 ARP 도 멀쩡하고 `ping` 과 `nc` 는 되는데 Python 만 막히면
**macOS Sequoia 의 '로컬 네트워크' 권한**이다. 권한 없는 Homebrew Python 은
LAN 접속이 `OSError: [Errno 65]` 로 차단된다.

라우팅 문제로 오진하기 쉽다. `escpos_kr/transport.py` 의 `Network.send()` 에 `nc` 폴백을
넣어 우회해 두었다.

## USB 로 보냈는데 깨져 나온다

**macOS 가 raw 큐를 폐지했다.** `lpadmin -m raw` 는
"원본 대기열이 macOS에서 더 이상 지원되지 않습니다" 로 거부되고,
일반 PPD 를 쓰면 ESC/POS 바이트가 가공되어 깨진다.

CUPS **USB 백엔드를 직접 호출**하면 통과한다 (sudo 불필요):

```bash
/usr/libexec/cups/backend/usb          # 인자 없이 = 장치 URI 탐색 (여기서 나온
                                       # URI 를 그대로 DEVICE_URI 에 넣는다)
DEVICE_URI='usb://Printer/POS-80?serial=XXXXXXXXXXXX' \
  /usr/libexec/cups/backend/usb 1 "$USER" job 1 "" payload.bin
```

## 설정 페이지(192.168.4.1)가 빈 응답만 준다

**웹서버가 HTTP/0.9 로 답한다.** 상태줄도 헤더도 없이 본문만 보낸다.
그래서 `nc` 로 만든 생 요청도, 평범한 `curl` 도 아무것도 못 받는다
(`curl: (1) Received HTTP/0.9 when not allowed`).

`curl --http0.9` 를 써야 한다. 브라우저만 열리고 명령줄은 전부 안 되는 것처럼
보여서 오래 헤맸다.

## 설정 페이지가 아예 죽었다 (포트까지 닫힘)

**이 Wi-Fi 모듈은 동시 접속을 하나만 받는다.** 요청을 연달아 보내면
웹서버가 죽고 포트까지 닫힌다. 전원을 다시 넣어야 살아난다.
한 번에 하나씩, 간격을 두고 보낼 것.

## 맥북이 프린터 AP 에 갇혔다

AP 에 붙었다 돌아올 때 **SSID 이름에 의존해 복구하면 안 된다.**
위치 권한이 없으면 `networksetup -getairportnetwork` 가 SSID 대신
`"You are not associated with an AirPort network."` 라는 **문장**을 돌려준다.
그 문장을 SSID 로 넣어 복구를 시도하니 실패한다.

대신 AP 를 기억 목록에서 지우고 Wi-Fi 전원을 껐다 켜서, 키체인에 저장된
네트워크로 자동 재접속시킨다 (`docs/pos-8390/ap_fetch.sh` 의 `restore()`).

## 쓰면 안 되는 것

`route -host <IP> -interface <en>` 은 **쓰지 말 것.** 대상 IP 를 맥북 자신의
MAC 에 묶는 permanent ARP 항목을 만들어 통신을 조용히 막는다.
대역이 겹칠 때는 Wi-Fi 를 잠시 끄는 쪽이 낫다.
