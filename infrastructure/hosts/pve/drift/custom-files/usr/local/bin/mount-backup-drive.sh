#!/bin/bash

# Configuration
LOG_FILE="/var/log/mount-backup-drive.log" # Changed for systemd
DIRECTORY="/mnt/pve/backup2"
DRIVE_ID="41d79ae9-1b08-4340-bd07-fa29fb713f6a"
MOUNT_POINT="/mnt/pve/backup2"
MAX_RETRIES=5      # Maximum mount attempts
RETRY_DELAY=10     # Delay between retries in seconds
BACKOFF_MULTIPLIER=2 # Multiplier for backoff

# Function to log messages (systemd-friendly)
log_message() {
    # Use systemd's journal logging if possible, otherwise fall back to file
    if command -v systemd-cat >/dev/null 2>&1; then
        systemd-cat -t mount-backup-drive "$@"
    else
        timestamp=$(date "+%Y-%m-%d %H:%M:%S")
        printf "%s: %s\n" "$timestamp" "$@" >> "$LOG_FILE"
    fi
}

# Function to check if the drive is mounted
is_mounted() {
    findmnt -n -M "$MOUNT_POINT" >/dev/null 2>&1
}

# Function to mount the drive with retries and backoff
mount_drive() {
    local retries=0
    local delay=$RETRY_DELAY

    while [ $retries -lt $MAX_RETRIES ]; do
        if mount UUID="$DRIVE_ID" "$MOUNT_POINT"; then
            log_message "Successfully mounted $MOUNT_POINT."
            return 0
        else
            local mount_output=$(mount 2>&1)
            log_message "Failed to mount $MOUNT_POINT (attempt $((retries + 1))/$MAX_RETRIES). Error: $mount_output"
            retries=$((retries + 1))
            if [ $retries -lt $MAX_RETRIES ]; then
                log_message "Retrying in $delay seconds..."
                sleep $delay
                delay=$((delay * BACKOFF_MULTIPLIER)) # Exponential backoff
            fi
        fi
    done
    log_message "Failed to mount $MOUNT_POINT after $MAX_RETRIES attempts.  Manual intervention required."
    return 1 # Return non-zero for failure
}

# Function to unmount the drive
unmount_drive() {
    if is_mounted; then
        if umount "$MOUNT_POINT"; then
            log_message "Successfully unmounted $MOUNT_POINT."
            return 0
        else
            log_message "Failed to unmount $MOUNT_POINT."
            return 1
        fi
    else
        log_message "$MOUNT_POINT was not mounted."
        return 0 # Consider it successful if it's already unmounted
    fi
}
# Check and create directory
if [ ! -d "$DIRECTORY" ]; then
    if ! mkdir -p "$DIRECTORY"; then
        log_message "Error creating directory '$DIRECTORY'. Exiting."
        exit 1
    fi
fi

# Main logic based on command
case "$1" in
    start)
        log_message "Starting mount-backup-drive service..."
        if ! is_mounted; then
           if ! mount_drive; then
              exit 1
           fi
        else
          log_message "$MOUNT_POINT is already mounted."
        fi
        ;;
    stop)
        log_message "Stopping mount-backup-drive service..."
        unmount_drive
        ;;
    check) #check added
        if ! is_mounted; then
            log_message "$MOUNT_POINT is unmounted, attempting to mount..."
            if ! mount_drive; then
                log_message "Mount failed after retries.  System may be unstable."
                exit 1
            fi
        else
            log_message "$MOUNT_POINT is mounted."
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|check}"
        exit 1
        ;;
esac

exit 0
