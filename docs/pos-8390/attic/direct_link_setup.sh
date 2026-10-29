#!/bin/bash
# 맥북 <-> POS-8390 랜 직결 설정 및 탐색 (sudo 필요)
# Wi-Fi 가 192.168.0.x 를 쓰고 있어 대역이 겹치므로, 작업 중에만 Wi-Fi 를 끈다.
# 끝나면 자동으로 다시 켠다.
IFACE=en12
WIFI=en0
MAC_IP=192.168.0.50
MAC_PREFIX="11:22:33"      # POS-8390 MAC 앞 3바이트

cleanup() { echo "[*] Wi-Fi 복구"; networksetup -setairportpower $WIFI on; }
trap cleanup EXIT

echo "[1/5] 잘못된 호스트 라우트 제거"
sudo route -n delete -host 192.168.0.200 2>/dev/null || true
sudo arp -d 192.168.0.200 2>/dev/null || true

echo "[2/5] Wi-Fi 끄기 (대역 충돌 방지)"
networksetup -setairportpower $WIFI off
sleep 2

echo "[3/5] $IFACE 에 $MAC_IP 할당"
sudo ifconfig $IFACE inet $MAC_IP netmask 255.255.255.0 alias 2>/dev/null
ifconfig $IFACE | grep "inet "

echo "[4/5] 192.168.0.0/24 스캔"
for i in $(seq 1 254); do ping -c1 -W 300 192.168.0.$i >/dev/null 2>&1 & done
wait
FOUND=$(arp -an | grep -i "$MAC_PREFIX" | sed -E 's/.*\(([0-9.]+)\).*/\1/' | head -1)

if [ -z "$FOUND" ]; then
    echo "[5/5] MAC 미발견 -> 20초간 패킷 수신 대기"
    echo "      >>> 지금 프린터 전원을 껐다 켜주세요 <<<"
    sudo timeout 20 tcpdump -i $IFACE -n -e "arp or udp port 67 or udp port 68" 2>/dev/null \
        | grep -iv "98:fc:84" | head -20
    echo "--- 수신 종료. 위에 보이는 IP/MAC 이 프린터입니다."
    exit 1
fi

echo "[5/5] 프린터 발견: $FOUND"
nc -z -G 2 "$FOUND" 9100 \
    && echo "  >> 9100 열림.  실행:  python3 print_test.py $FOUND" \
    || echo "  >> 9100 닫힘"
