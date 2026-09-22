#!/bin/sh

# This script enables passwordless SSH from OpenWRT to another host using Dropbear's existing host key.

KEY_SRC="/etc/dropbear/dropbear_ed25519_host_key"
KEY_DST_DIR="/root/.ssh"
KEY_DST="$KEY_DST_DIR/id_ed25519"
PUB_DST="$KEY_DST.pub"
REMOTE_USER="meek2100"
REMOTE_HOST="192.168.1.150"
AUTHORIZED_KEYS_PATH="/home/$REMOTE_USER/.ssh/authorized_keys"

echo "==> Using Dropbear host key as client identity key..."

# Ensure .ssh directory
mkdir -p "$KEY_DST_DIR"
chmod 700 "$KEY_DST_DIR"

# Copy private key
cp "$KEY_SRC" "$KEY_DST"
chmod 600 "$KEY_DST"

# Extract public key
dropbearkey -y -f "$KEY_SRC" | grep "^ssh-ed25519" > "$PUB_DST"
chmod 644 "$PUB_DST"

echo "==> Generated public key:"
cat "$PUB_DST"

# Prompt user to copy the key to Debian
echo
echo "==> Now attempting to copy public key to $REMOTE_USER@$REMOTE_HOST..."
echo "    You'll be prompted for the remote user's password once."

# Copy the public key to the remote authorized_keys
cat "$PUB_DST" | ssh "$REMOTE_USER@$REMOTE_HOST" "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"

echo
echo "==> Test SSH login:"
ssh -i "$KEY_DST" "$REMOTE_USER@$REMOTE_HOST" uptime
