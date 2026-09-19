#!/bin/bash
set -e

# === CONFIG ===
OPENWRT_USER="root"
OPENWRT_IP="192.168.1.225"
DEBIAN_USER="$USER"
DEBIAN_IP=$(hostname -I | awk '{print $1}')
DEBIAN_PUB="$HOME/.ssh/id_ed25519.pub"
OPENWRT_KEY_PATH="/root/.ssh/id_ed25519"

# === FUNCTIONS ===
generate_ssh_key_if_missing() {
  local keyfile="$1"
  if [ ! -f "$keyfile" ]; then
    echo "Generating SSH key: $keyfile"
    ssh-keygen -t ed25519 -f "$keyfile" -N "" -q
  fi
}

install_key_to_remote() {
  local pubkey="$1"
  local user="$2"
  local host="$3"
  echo "Installing public key to $user@$host..."
  ssh "$user@$host" "mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
  cat "$pubkey" | ssh "$user@$host" "grep -qF \"$(cat $pubkey)\" ~/.ssh/authorized_keys || cat >> ~/.ssh/authorized_keys"
}

# === PART 1: Debian to OpenWRT ===
echo "-----[ Debian → OpenWRT ]-----"
generate_ssh_key_if_missing "$HOME/.ssh/id_ed25519"
install_key_to_remote "$DEBIAN_PUB" "$OPENWRT_USER" "$OPENWRT_IP"

# === PART 2: OpenWRT to Debian ===
echo "-----[ OpenWRT → Debian ]-----"
# Generate key on OpenWRT
ssh "$OPENWRT_USER@$OPENWRT_IP" <<'EOF'
  mkdir -p ~/.ssh
  chmod 700 ~/.ssh
  if [ ! -f ~/.ssh/id_ed25519 ]; then
    dropbearkey -t ed25519 -f ~/.ssh/id_ed25519 > /tmp/openwrt.key.out
    grep "^ssh-" /tmp/openwrt.key.out > ~/.ssh/id_ed25519.pub
    chmod 600 ~/.ssh/id_ed25519
    rm -f /tmp/openwrt.key.out
  fi
EOF

# Fetch OpenWRT public key and install to Debian
ssh "$OPENWRT_USER@$OPENWRT_IP" "cat ~/.ssh/id_ed25519.pub" >> ~/.ssh/authorized_keys
sort -u -o ~/.ssh/authorized_keys ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

echo "✅ SSH key exchange complete. You should now be able to SSH both directions without a password."
