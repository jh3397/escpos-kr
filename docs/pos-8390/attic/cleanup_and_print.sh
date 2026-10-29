#!/bin/bash
# 직결 테스트 때 남은 라우트/ARP/별칭IP 를 정리하고, 공유기의 프린터로 테스트 출력.
# sudo 필요 (비밀번호 1회)
PRINTER=${1:-192.168.0.200}
IFACE=en12

echo "[1/4] 잘못된 호스트 라우트 / ARP / 별칭 IP 제거"
sudo route -n delete -host "$PRINTER" 2>/dev/null && echo "    라우트 삭제됨" || echo "    라우트 없음"
sudo arp -d "$PRINTER"                2>/dev/null && echo "    ARP 삭제됨"   || echo "    ARP 없음"
sudo ifconfig $IFACE -alias 192.168.0.50 2>/dev/null && echo "    별칭 IP 제거됨" || echo "    별칭 IP 없음"

echo "[2/4] 정리 결과 확인"
netstat -rn -f inet | grep "$PRINTER" && echo "    !! 아직 라우트가 남아있음" || echo "    라우트 깨끗함"

echo "[3/4] $PRINTER 연결 확인"
ping -c3 -W 1000 "$PRINTER" | tail -3
if ! nc -z -G 3 "$PRINTER" 9100 2>/dev/null; then
    echo "    >> 9100 포트가 닫혀 있습니다."
    echo "       ARP 확인:"; arp -an | grep "$PRINTER"
    exit 1
fi
echo "    >> 9100 열림"

echo "[4/4] 테스트 출력"
python3 "$(dirname "$0")/print_test.py" "$PRINTER"
