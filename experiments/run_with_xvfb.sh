#!/bin/sh
set -eu

display_number="${KHALINOS_XVFB_DISPLAY:-99}"
export DISPLAY=":${display_number}"
log_file="/tmp/khalinos-xvfb-${display_number}.log"

echo "Starting bounded Xvfb display ${DISPLAY}." >&2
Xvfb "${DISPLAY}" -screen 0 1280x720x24 -nolisten tcp -ac >"${log_file}" 2>&1 &
xvfb_pid=$!

cleanup() {
    kill "${xvfb_pid}" 2>/dev/null || true
    wait "${xvfb_pid}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

attempt=0
while [ "${attempt}" -lt 50 ]; do
    if ! kill -0 "${xvfb_pid}" 2>/dev/null; then
        echo "Xvfb exited before its display became ready." >&2
        cat "${log_file}" >&2 || true
        exit 70
    fi
    if [ -S "/tmp/.X11-unix/X${display_number}" ]; then
        echo "Xvfb display ${DISPLAY} is ready." >&2
        "$@"
        exit $?
    fi
    attempt=$((attempt + 1))
    sleep 0.1
done

echo "Xvfb display ${DISPLAY} did not become ready within 5 seconds." >&2
cat "${log_file}" >&2 || true
exit 71
