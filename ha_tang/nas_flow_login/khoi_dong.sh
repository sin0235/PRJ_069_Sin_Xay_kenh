#!/bin/sh
set -eu

DISPLAY=${DISPLAY:-:99}
export DISPLAY

Xvfb "$DISPLAY" -screen 0 1440x900x24 -nolisten tcp -noreset &
xvfb_pid=$!

cleanup() {
    kill "$websockify_pid" "$vnc_pid" "$xvfb_pid" 2>/dev/null || true
    wait "$websockify_pid" "$vnc_pid" "$xvfb_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

i=0
until xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -ge 30 ]; then
        echo "Không khởi tạo được màn hình ảo Xvfb." >&2
        exit 1
    fi
    sleep 1
done

# Có VNC_PASSWORD thì bắt buộc nhập mật khẩu khi mở noVNC (cần khi mở cổng ra mạng LAN để đăng nhập).
if [ -n "${VNC_PASSWORD:-}" ]; then
    x11vnc -display "$DISPLAY" -localhost -rfbport 5900 -forever -shared -passwd "$VNC_PASSWORD" &
else
    x11vnc -display "$DISPLAY" -localhost -rfbport 5900 -forever -shared -nopw &
fi
vnc_pid=$!
websockify --web=/usr/share/novnc --heartbeat=30 6080 127.0.0.1:5900 &
websockify_pid=$!
sleep 1
kill -0 "$vnc_pid"
kill -0 "$websockify_pid"

python /app/dang_nhap_flow.py
