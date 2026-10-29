#!/bin/bash
# 설정 AP 의 웹서버가 어떤 요청 형식을 받아들이는지 진단한다.
# 1차 수집이 전부 빈 응답이었으므로, 요청 방식 자체를 바꿔가며 시험한다.
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
WIFI=en0; AP="MYPrint"; H=192.168.4.1
DIR="$(cd "$(dirname "$0")" && pwd)/ap_pages"; mkdir -p "$DIR"
LOG="$DIR/probe.log"; : > "$LOG"
say() { echo "$@" | tee -a "$LOG"; }

restored=0
restore() {
    [ "$restored" = 1 ] && return; restored=1
    say "[*] Wi-Fi 복구 중"
    networksetup -removepreferredwirelessnetwork $WIFI "$AP" >/dev/null 2>&1
    networksetup -setairportpower $WIFI off >/dev/null 2>&1; sleep 3
    networksetup -setairportpower $WIFI on  >/dev/null 2>&1
    for i in $(seq 1 24); do
        sleep 2; ip=$(ipconfig getifaddr $WIFI 2>/dev/null)
        case "$ip" in ""|169.254.*) continue;; esac
        say "    복구됨: IP $ip (${i}회)"; return
    done
    say "    !! 자동 복구 실패 — 메뉴바에서 Wi-Fi 를 직접 선택해 주세요"
}
trap restore EXIT INT TERM

say "[1] '$AP' 접속"
networksetup -setairportnetwork $WIFI "$AP" 2>&1 | tee -a "$LOG"
sleep 8
IP=$(ipconfig getifaddr $WIFI 2>/dev/null)
say "    맥북 IP: ${IP:-없음}"
case "${IP:-x}" in 192.168.4.*) ;; *) say "  >> $AP 접속 실패"; exit 1;; esac

say "[2] 열린 포트 탐색"
OPEN=""
for p in 80 81 8080 8000 8888 9100 23 22; do
    nc -z -G 2 $H $p 2>/dev/null && { say "    열림: $p"; OPEN="$OPEN $p"; }
done
say "    열린 포트:${OPEN:- 없음}"

say "[3] 요청 형식별 시험 (포트 80, 경로 /)"
try() {
    local name="$1"; shift
    local out="$DIR/try_$name.raw"
    printf "$@" | nc -w 8 $H 80 > "$out" 2>/dev/null
    local n=$(wc -c < "$out" | tr -d ' ')
    say "    [$name] ${n}B"
    if [ "$n" -gt 0 ]; then head -c 200 "$out" | tr -d '\000' | sed 's/^/        /' | tee -a "$LOG"; echo | tee -a "$LOG"; fi
}
try "http10_nohost"  'GET / HTTP/1.0\r\n\r\n'
try "http10_host"    'GET / HTTP/1.0\r\nHost: 192.168.4.1\r\n\r\n'
try "http11_host"    'GET / HTTP/1.1\r\nHost: 192.168.4.1\r\n\r\n'
try "simple"         'GET /\r\n\r\n'
try "simple_lf"      'GET /\n\n'
try "http10_ua"      'GET / HTTP/1.0\r\nUser-Agent: Mozilla/5.0\r\nAccept: */*\r\n\r\n'

say "[4] curl 시험"
for v in "--http1.0" "--http1.1"; do
    say "    curl $v"
    curl -s -S -m 10 -D "$DIR/curl_hdr.txt" $v "http://$H/" -o "$DIR/curl_body.html" 2>&1 \
        | sed 's/^/        /' | tee -a "$LOG"
    n=$(wc -c < "$DIR/curl_body.html" 2>/dev/null | tr -d ' ')
    say "        본문 ${n:-0}B / 헤더 $(wc -c < "$DIR/curl_hdr.txt" 2>/dev/null | tr -d ' ')B"
    if [ "${n:-0}" -gt 0 ]; then
        cp "$DIR/curl_body.html" "$DIR/root.html"
        sed 's/^/        /' "$DIR/curl_hdr.txt" | tee -a "$LOG"
        say "        >> 성공 — root.html 로 저장"
        break
    fi
done

say "[5] 완료"
ls -1S "$DIR" | sed 's/^/    /' | tee -a "$LOG"
