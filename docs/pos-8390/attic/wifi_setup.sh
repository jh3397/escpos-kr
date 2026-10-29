#!/bin/bash
# POS-8390 무선 전환 도우미.
# 프린터 Wi-Fi 모듈(OLDAP)의 자체 AP 에 붙어 설정 페이지를 열고,
# 끝나면 원래 Wi-Fi 로 복귀한다. 접속 중에는 인터넷이 끊긴다.
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
WIFI=en0
AP="MYPrint"

ORIG=$(networksetup -getairportnetwork $WIFI | sed 's/^Current Wi-Fi Network: //')
echo "[0] 현재 네트워크: $ORIG"

restore() {
    echo
    echo "[*] 원래 Wi-Fi 복구: $ORIG"
    [ -n "$ORIG" ] && [ "$ORIG" != "$AP" ] && networksetup -setairportnetwork $WIFI "$ORIG"
    sleep 5
    networksetup -getairportnetwork $WIFI
    echo "[*] 프린터 새 IP 찾기:  ./find_printer.sh"
}
trap restore EXIT

echo "[1] '$AP' 접속 (암호 없음)"
networksetup -setairportnetwork $WIFI "$AP" || { echo "  >> 접속 실패. AP 가 안 보입니다."; exit 1; }
sleep 8

IP=$(ipconfig getifaddr $WIFI)
GW=$(route -n get default 2>/dev/null | awk '/gateway/{print $2}')
echo "[2] 맥북 IP: ${IP:-없음} / 게이트웨이: ${GW:-없음}"

echo "[3] 설정 페이지 탐색"
FOUND=""
for w in 192.168.4.1 $GW; do
    [ -z "$w" ] && continue
    if nc -z -G 2 "$w" 80 2>/dev/null; then echo "    >> http://$w"; FOUND=$w; break; fi
done
[ -z "$FOUND" ] && { echo "  >> 설정 페이지를 못 찾았습니다."; exit 1; }

open "http://$FOUND"
cat <<MSG

────────────────────────────────────────────────
 브라우저에서 아래 순서로 진행하세요

  1. 페이지 안내에 따라 사무실 공유기 SSID 선택
     ※ 반드시 2.4GHz 대역이어야 합니다
  2. Wi-Fi 비밀번호 입력 → 저장
  3. 프린터가 자동으로 재시작됩니다

 끝나면 이 창으로 돌아와 Enter 를 누르세요.
────────────────────────────────────────────────
MSG
read -r _
