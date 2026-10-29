#!/bin/bash
# POS-8390 영수증 프린터를 현재 네트워크에서 찾는다.
# 사용법: ./find_printer.sh
MAC_PREFIX="11:22:33"          # POS-8390 MAC 앞 3바이트
SUBNET="${1:-192.168.0}"

echo "[1/3] $SUBNET.0/24 스캔 중..."
for i in $(seq 1 254); do ping -c1 -W 200 "$SUBNET.$i" >/dev/null 2>&1 & done
wait

echo "[2/3] MAC 주소로 프린터 찾는 중..."
HIT=$(arp -an | grep -i "$MAC_PREFIX" | sed -E 's/.*\(([0-9.]+)\).*/\1/')

if [ -n "$HIT" ]; then
    echo "  >> 프린터 발견: $HIT"
else
    echo "  >> MAC 못 찾음. 9100 포트 열린 기기를 대신 표시합니다:"
    for ip in $(arp -an | grep -v incomplete | sed -E 's/.*\(([0-9.]+)\).*/\1/' | grep "^$SUBNET\."); do
        (nc -z -G 1 "$ip" 9100 2>/dev/null && echo "     9100 열림: $ip") &
    done
    wait
    exit 1
fi

echo "[3/3] 9100 포트 확인..."
if nc -z -G 2 "$HIT" 9100 2>/dev/null; then
    echo "  >> 준비 완료.  실행:  python3 print_test.py $HIT"
else
    echo "  >> $HIT 는 응답하지만 9100 포트가 닫혀 있습니다."
fi
