(
  # 1. Wait for the USB drive to mount
  /usr/bin/is-mounted.sh /opt
  
  # 2. Add a short buffer for the filesystem to initialize
  sleep 5
  
  # 3. Launch the watchdog and route any fatal startup errors to a log file
  /opt/sbin/pia-watchdog > /tmp/pia-startup-crash.log 2>&1 &
) &
