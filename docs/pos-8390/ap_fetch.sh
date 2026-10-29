#!/bin/bash
# 설정 페이지를 '조심스럽게' 가져온다.
#
# 앞선 시도에서 배운 것:
#  - nc 로 보낸 생 HTTP 요청은 전부 빈 응답이었다 (브라우저로는 열린다).
#    그래서 첫 요청부터 curl 을 쓴다. 브라우저에 가장 가까운 클라이언트다.
#  - 요청 37개를 연달아 때린 뒤 웹서버가 죽었다. 이 Wi-Fi 모듈은 동시 접속을
#    하나만 받으므로, 요청을 한 번에 하나씩, 간격을 두고 보낸다.
#  - 설정 모드는 오래 유지되지 않는 듯하다. 그래서 AP 가 보이면 바로 받는다.
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
WIFI=en0; AP="MYPrint"; H=192.168.4.1
DIR="$(cd "$(dirname "$0")" && pwd)/ap_pages"; mkdir -p "$DIR"
LOG="$DIR/fetch.log"; : > "$LOG"
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

# --- AP 가 뜨기를 기다린다 (사용자가 FEED+전원 하는 동안) ---
say "[1] '$AP' 를 기다립니다 (최대 3분). 지금 FEED 누른 채 전원을 넣어주세요."
JOINED=0
for t in $(seq 1 15); do
    networksetup -setairportnetwork $WIFI "$AP" >/dev/null 2>&1
    sleep 4
    IP=$(ipconfig getifaddr $WIFI 2>/dev/null)
    case "${IP:-x}" in
        192.168.4.*) say "    붙었습니다: $IP (${t}회 시도)"; JOINED=1; break;;
    esac
    say "    ...대기 중 (${t}/15, 현재 IP ${IP:-없음})"
done
[ "$JOINED" = 0 ] && { say "  >> $AP 를 찾지 못했습니다."; exit 1; }

# --- 첫 요청: curl 로 단 한 번 ---
fetch() {  # fetch <포트> <경로> <저장이름>
    local port="$1" path="$2" name="$3"
    local body="$DIR/$name" hdr="$DIR/$name.hdr"
    curl -s -S -m 12 --http1.0 -A 'Mozilla/5.0' \
         -D "$hdr" -o "$body" "http://$H:$port$path" 2>>"$LOG"
    local n=$(wc -c < "$body" 2>/dev/null | tr -d ' '); n=${n:-0}
    say "    :$port$path -> ${n}B"
    [ "$n" = 0 ] && rm -f "$body" "$hdr"
    [ "$n" != 0 ]
}

say "[2] 첫 요청 (curl, 포트 80)"
if fetch 80 / root.html; then
    say "    >> 성공"
else
    say "[2-1] 다른 포트 시도 (하나씩, 2초 간격)"
    GOT=0
    for p in 8080 81 8000 8888; do
        sleep 2
        if fetch $p / root.html; then say "    >> 성공 (포트 $p)"; H_PORT=$p; GOT=1; break; fi
    done
    [ "$GOT" = 0 ] && { say "  >> 어느 포트에서도 응답이 없습니다."; exit 1; }
fi
PORT=${H_PORT:-80}

say "[3] root.html 요약"
sed 's/^/        /' "$DIR/root.html.hdr" 2>/dev/null | head -12 | tee -a "$LOG"
say "    --- 본문 앞부분 ---"
head -c 600 "$DIR/root.html" | sed 's/^/        /' | tee -a "$LOG"; echo | tee -a "$LOG"

say "[4] 참조된 파일 수집 (최대 6개, 1.5초 간격)"
refs=$(grep -o -i -E '(src|href|action)[[:space:]]*=[[:space:]]*"?[^"'"'"' >]{1,60}' "$DIR/root.html" \
  | sed -E 's/.*=[[:space:]]*"?//' \
  | grep -v -i -E '^(https?:|mailto:|#|javascript:)' | sed 's#^\./##' | sort -u | head -6)
if [ -z "$refs" ]; then say "    (참조 없음)"; fi
for r in $refs; do
    sleep 1.5
    case "$r" in /*) path="$r";; *) path="/$r";; esac
    fetch $PORT "$path" "ref_$(echo "$path" | sed 's#^/##; s#[/?&=]#_#g').txt"
done

say "[5] 완료 -> $DIR"
ls -1S "$DIR" | sed 's/^/    /' | tee -a "$LOG"
