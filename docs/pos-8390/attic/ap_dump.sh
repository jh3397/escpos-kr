#!/bin/bash
# 프린터 설정 AP(MYPrint)에 붙어 설정 페이지를 통째로 저장하고 복귀한다.
#
# 복구는 SSID 이름에 의존하지 않는다. macOS 의
#   networksetup -getairportnetwork
# 는 위치 권한이 없으면 SSID 대신 "You are not associated..." 라는 문장을
# 돌려주므로, 그 값을 복구에 쓰면 맥북이 MYPrint 에 갇힌다.
# 대신 MYPrint 를 기억 목록에서 지우고 Wi-Fi 전원을 껐다 켜서
# 키체인에 저장된 원래 네트워크로 자동 재접속시킨다.
#
# 저장 위치: ap_pages/   인터넷 끊김: 1분 내외
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
WIFI=en0; AP="MYPrint"; HOST=""
DIR="$(cd "$(dirname "$0")" && pwd)/ap_pages"; mkdir -p "$DIR"
LOG="$DIR/dump.log"; : > "$LOG"
say() { echo "$@" | tee -a "$LOG"; }

restored=0
restore() {
    [ "$restored" = 1 ] && return; restored=1
    say "[*] Wi-Fi 복구 중 (기억 목록에서 $AP 제거 후 전원 재투입)"
    networksetup -removepreferredwirelessnetwork $WIFI "$AP" >/dev/null 2>&1
    networksetup -setairportpower $WIFI off >/dev/null 2>&1
    sleep 3
    networksetup -setairportpower $WIFI on  >/dev/null 2>&1
    for i in $(seq 1 24); do
        sleep 2
        ip=$(ipconfig getifaddr $WIFI 2>/dev/null)
        case "$ip" in ""|169.254.*) continue;; esac
        gw=$(route -n get default 2>/dev/null | awk '/gateway/{print $2}')
        say "    복구됨: IP $ip / GW ${gw:-?} (${i}회 시도)"
        ping -c1 -W 2000 "${gw:-192.168.0.1}" >/dev/null 2>&1 \
            && say "    게이트웨이 응답 정상" || say "    !! 게이트웨이 무응답"
        return
    done
    say "    !! 자동 복구 실패 — 메뉴바에서 Wi-Fi 를 직접 선택해 주세요"
}
trap restore EXIT INT TERM

say "[1] '$AP' 접속 시도"
OFFICE_PREFIX="192.168.0."          # 사무실 대역 — 여기 머물러 있으면 접속 실패다
JOIN=$(networksetup -setairportnetwork $WIFI "$AP" 2>&1)
[ -n "$JOIN" ] && say "    $JOIN"
sleep 8
IP=$(ipconfig getifaddr $WIFI 2>/dev/null)
GW=$(route -n get default 2>/dev/null | awk '/gateway/{print $2}')
say "    맥북 IP: ${IP:-없음} / 게이트웨이: ${GW:-없음}"

# 접속 성공 판정은 '명령이 오류를 안 냈다'가 아니라 '대역이 바뀌었다' 로 한다.
# networksetup 은 AP 가 없어도 조용히 성공한 척하는 경우가 있다.
case "${IP:-없음}" in
    "$OFFICE_PREFIX"*|없음|169.254.*)
        say "  >> $AP 에 붙지 못했습니다 (여전히 사무실 대역이거나 IP 없음)."
        say "     프린터가 설정 모드가 아닐 가능성이 큽니다 —"
        say "     FEED 버튼을 누른 채 전원을 연결하면 설정 모드로 들어갑니다."
        exit 1;;
esac
say "    >> 대역 변경 확인 — $AP 에 접속됨"

say "[2] 설정 페이지 주소 확인"
for h in 192.168.4.1 10.10.100.254 $GW; do
    [ -z "$h" ] && continue
    case "$h" in "$OFFICE_PREFIX"*) say "    -- 건너뜀(사무실 공유기): $h"; continue;; esac
    if nc -z -G 2 "$h" 80 2>/dev/null; then say "    >> 응답함: $h"; HOST=$h; break
    else say "    -- 무응답: $h"; fi
done
[ -z "$HOST" ] && { say "  >> 설정 페이지를 못 찾았습니다."; exit 1; }
say "$HOST" > "$DIR/.host"

grab() {  # grab <경로> <저장이름>
    local out="$DIR/$2"
    printf 'GET %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: Mozilla/5.0\r\nConnection: close\r\n\r\n' \
        "$1" "$HOST" | nc -w 6 "$HOST" 80 > "$out" 2>/dev/null
    local n=$(wc -c < "$out" | tr -d ' ')
    if [ "$n" -lt 20 ]; then rm -f "$out"; say "    $1 -> (빈 응답)"
    else say "    $1 -> $2 (${n}B)"; fi
}

name_of() { echo "$1" | sed 's#^/##; s#[/?&=]#_#g; s#^$#root#' ; }

say "[3] 1차 수집 (알려진 경로)"
grab "/" root.html
for p in /index.html /index.htm /wifi /wifi.htm /wifi.html /wlan /wlan.htm \
         /sta /sta.htm /ap /ap.htm /net /net.htm /network /network.htm \
         /config /config.htm /setting /settings /system /system.htm \
         /ip_config.htm /scan /set /setwifi /wifisave /wifi_save /apply /save \
         /status /info /menu.htm /main.htm /home.htm /style.css /index.js; do
    grab "$p" "$(name_of "$p").html"
done

say "[4] 2차 수집 (1차 결과에서 참조된 파일)"
refs=$(cat "$DIR"/*.html 2>/dev/null \
  | grep -o -i -E '(src|href|action)[[:space:]]*=[[:space:]]*"[^"]{1,80}"' \
  | sed -E 's/.*"(.*)"/\1/' \
  | grep -v -i -E '^(https?:|mailto:|#|javascript:)' \
  | sed 's#^\./##' | sort -u)
if [ -z "$refs" ]; then say "    (참조 없음)"; fi
for r in $refs; do
    case "$r" in /*) path="$r";; *) path="/$r";; esac
    f="$DIR/$(name_of "$path").html"
    [ -f "$f" ] && { say "    $path (이미 수집)"; continue; }
    grab "$path" "$(name_of "$path").html"
done

say "[5] 완료 -> $DIR"
ls -1S "$DIR" | sed 's/^/    /' | tee -a "$LOG"
