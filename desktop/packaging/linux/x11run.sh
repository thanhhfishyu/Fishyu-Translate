#!/bin/bash
Xvfb ${XDISPLAY:-:97} -screen 0 1280x800x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
XPID=$!
sleep 1.5
export DISPLAY=${XDISPLAY:-:97}
unset WAYLAND_DISPLAY QT_QPA_PLATFORM
openbox >/tmp/openbox.log 2>&1 &
OPID=$!
sleep 1
dbus-run-session -- "$@"
RC=$?
kill $OPID $XPID 2>/dev/null
exit $RC
