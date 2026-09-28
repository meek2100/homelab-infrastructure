#!/usr/bin/env bash
TARGET="${1:-35.212.229.212}"
SSH_USER="${2:-meek2100}"
SSH_KEY="${3:-${HOME}/.ssh/free-email-server_id_ed25519}"

if [ ! -f "${SSH_KEY}" ]; then
    SSH_KEY="${HOME}/.ssh/id_ed25519"
fi

echo "🔑 Connecting to ${SSH_USER}@${TARGET} with key ${SSH_KEY}..."
ssh -i "${SSH_KEY}" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new "${SSH_USER}@${TARGET}" 'bash -s' < "$(dirname "$0")/audit-external-host.sh"
