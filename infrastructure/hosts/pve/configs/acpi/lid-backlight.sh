#!/bin/bash
BACKLIGHT_PATH="/sys/class/backlight/intel_backlight"
if [ -f /proc/acpi/button/lid/LID0/state ] && grep -q closed /proc/acpi/button/lid/LID0/state; then
    [ -d "$BACKLIGHT_PATH" ] && echo 0 > "${BACKLIGHT_PATH}/brightness" || true
    setterm --blank force --powersave powerdown < /dev/tty1 > /dev/tty1 2>/dev/null || true
else
    [ -d "$BACKLIGHT_PATH" ] && echo 400 > "${BACKLIGHT_PATH}/brightness" || true
    setterm --blank poke < /dev/tty1 > /dev/tty1 2>/dev/null || true
fi
