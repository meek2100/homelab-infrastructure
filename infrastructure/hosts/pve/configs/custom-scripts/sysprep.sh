#!/bin/bash

# ==============================================================================
# Debian/Ubuntu Clone Sysprep Script
#
# Description:
# This script prepares a cloned Debian-based VM for use. It performs the
# following actions:
#   - Installs sudo, tmux, and nano.
#   - Grants passwordless sudo access to the user 'meek2100'.
#   - Changes the system hostname.
#   - Regenerates unique SSH host keys.
#   - Creates a new unique machine-id.
#
# Usage:
# 1. Save this script as 'sysprep.sh' on the cloned VM.
# 2. Make it executable: chmod +x sysprep.sh
# 3. Run it with root privileges, passing the new hostname as an argument:
#    sudo ./sysprep.sh new-server-name
#
# ==============================================================================

# --- Safety Checks ---
# Exit immediately if a command exits with a non-zero status.
set -e

# Check if the script is run as root
if [ "$(id -u)" -ne 0 ]; then
  echo "❌ This script must be run as root. Please use sudo." >&2
  exit 1
fi

# Check if a hostname was provided as an argument
if [ -z "$1" ]; then
  echo "❌ Usage: $0 <new-hostname>" >&2
  echo "Please provide the desired new hostname for this machine." >&2
  exit 1
fi

# --- Configuration ---
NEW_HOSTNAME="$1"
OLD_HOSTNAME=$(hostname)
SUDO_USER="meek2100"

# --- System Setup & Package Installation ---
echo "🚀 Preparing system and installing required packages..."
echo "--------------------------------------------------"

# Update package list silently
echo "🔄 Step 1: Updating package list (apt-get update)..."
apt-get update > /dev/null 2>&1
echo "✅ Package list updated."
echo ""

# Install required packages
echo "🔄 Step 2: Installing essential packages (sudo, tmux, nano)..."
# The -y flag automatically answers yes to prompts. Output is hidden for cleaner display.
apt-get install -y sudo tmux nano > /dev/null 2>&1
echo "✅ Essential packages installed or already present."
echo ""

# Configure passwordless sudo for the specified user
echo "🔄 Step 3: Configuring passwordless sudo for user '$SUDO_USER'..."
SUDOER_FILE="/etc/sudoers.d/$SUDO_USER"
echo "$SUDO_USER ALL=(ALL) NOPASSWD:ALL" > "$SUDOER_FILE"
# Set correct permissions for the sudoers file to be read by the system.
chmod 440 "$SUDOER_FILE"
echo "✅ User '$SUDO_USER' granted passwordless sudo access."
echo ""

# --- Main Identity Change Execution ---
echo "🚀 Starting unique identity generation for '$NEW_HOSTNAME'..."
echo "--------------------------------------------------"

# 1. Change the Hostname
echo "🔄 Step 4: Changing hostname from '$OLD_HOSTNAME' to '$NEW_HOSTNAME'..."
hostnamectl set-hostname "$NEW_HOSTNAME"
echo "✅ Hostname updated."
echo ""

# 2. Update /etc/hosts file
echo "🔄 Step 5: Updating /etc/hosts file..."
# This command finds the line with the old hostname associated with 127.0.1.1
# and replaces it with the new hostname.
sed -i "s/127.0.1.1\s*$OLD_HOSTNAME/127.0.1.1\t$NEW_HOSTNAME/g" /etc/hosts
echo "✅ /etc/hosts file updated."
echo ""

# 3. Regenerate SSH Host Keys
echo "🔄 Step 6: Regenerating SSH host keys..."
echo "    -> Deleting old keys..."
rm -f /etc/ssh/ssh_host_*
echo "    -> Creating new keys..."
dpkg-reconfigure openssh-server > /dev/null 2>&1
echo "✅ New SSH keys generated."
echo ""

# 4. Regenerate Machine ID
echo "🔄 Step 7: Regenerating machine-id..."
# The machine-id should be unique for each system.
echo "    -> Deleting old machine-id..."
rm -f /etc/machine-id /var/lib/dbus/machine-id
echo "    -> Creating new machine-id..."
systemd-machine-id-setup > /dev/null 2>&1
dbus-uuidgen --ensure=/var/lib/dbus/machine-id > /dev/null 2>&1
echo "✅ New machine-id generated."
echo ""


# --- Final Instructions ---
echo "--------------------------------------------------"
echo "✅ System preparation complete!"
echo ""
echo "🔴 IMPORTANT FINAL STEPS:"
echo "1. A REBOOT is required for all changes to take full effect."
echo "   Please run: sudo reboot"
echo ""
echo "2. On YOUR OWN computer (not this VM), remove the old SSH key for this IP:"
echo "   ssh-keygen -R <vm_ip_address>"
echo "--------------------------------------------------"

