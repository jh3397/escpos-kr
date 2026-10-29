#!/bin/bash
# 프린터 자체 AP(OLDAP-000000)에 붙어서 테스트 출력하고, 원래 Wi-Fi 로 복귀.
# 접속 중에는 인터넷이 끊기므로 모든 과정을 한 번에 처리한다.
# 사용법: ./wifi_print.sh     (결과는 wifi_print.log 에도 저장)
exec > >(tee "$(dirname "$0")/wifi_print.log") 2>&1

WIFI=en0
AP="OLDAP-000000"
CANDIDATES="192.168.10.110 192.168.10.1 10.10.100.254"

ORIG=$(networksetup -getairportnetwork $WIFI | sed 's/^Current Wi-Fi Network: //')
echo "[0] 원래 네트워크: $ORIG"

restore() {
    echo "[*] 원래 Wi-Fi 복구 시도: $ORIG"
    [ -n "$ORIG" ] && [ "$ORIG" != "$AP" ] && networksetup -setairportnetwork $WIFI "$ORIG" 2>&1
    sleep 5
    networksetup -getairportnetwork $WIFI
}
trap restore EXIT

echo "[1] '$AP' 접속 시도 (암호 없음)"
if ! networksetup -setairportnetwork $WIFI "$AP" 2>&1; then
    echo "    >> 접속 실패. AP 가 안 보이거나 범위 밖입니다."
    exit 1
fi
sleep 8

IP=$(ipconfig getifaddr $WIFI)
echo "[2] 맥북이 받은 IP: ${IP:-없음}"
[ -z "$IP" ] && { echo "    >> IP 할당 실패"; exit 1; }

echo "[2-1] 게이트웨이 / 웹 설정 페이지 탐색"
GW=$(route -n get default 2>/dev/null | awk '/gateway/{print $2}')
echo "    게이트웨이: ${GW:-없음}"
for w in $GW 192.168.10.1 10.10.100.254; do
    [ -z "$w" ] && continue
    nc -z -G 1 "$w" 80 2>/dev/null && echo "    >> 웹 설정 페이지: http://$w  (admin / admin)"
done

echo "[3] 프린터 탐색"
TARGET=""
for c in $CANDIDATES; do
    if nc -z -G 2 "$c" 9100 2>/dev/null; then echo "    9100 열림: $c"; TARGET=$c; break; fi
done

if [ -z "$TARGET" ]; then
    echo "    후보 실패 -> 대역 전체 스캔"
    BASE=$(echo "$IP" | cut -d. -f1-3)
    for i in $(seq 1 254); do ping -c1 -W 300 "$BASE.$i" >/dev/null 2>&1 & done
    wait
    for ip in $(arp -an | sed -E 's/.*\(([0-9.]+)\).*/\1/' | grep "^$BASE\." | sort -u); do
        nc -z -G 1 "$ip" 9100 2>/dev/null && { echo "    9100 열림: $ip"; TARGET=$ip; break; }
    done
fi

[ -z "$TARGET" ] && { echo "    >> 프린터를 못 찾았습니다."; exit 1; }

echo "[4] 테스트 출력 -> $TARGET"
python3 "$(dirname "$0")/print_test.py" "$TARGET"
echo "[5] 완료. 프린터 IP = $TARGET"
