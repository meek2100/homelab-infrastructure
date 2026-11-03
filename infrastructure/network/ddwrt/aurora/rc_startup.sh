(
  # 1. Wait for the USB drive to mount (check mount table directly via pure ash/sh)
  i=0
  while [ "$i" -lt 35 ]; do
    if grep -q "/opt.*rw" /proc/mounts 2>/dev/null; then
      break
    fi
    sleep 1
    i=$((i + 1))
  done
  
  # 2. Add a short buffer for the filesystem to initialize
  sleep 5
  
  # 3. Launch the watchdog and route any fatal startup errors to a log file
  /opt/sbin/pia-watchdog > /tmp/pia-startup-crash.log 2>&1 &
) &
