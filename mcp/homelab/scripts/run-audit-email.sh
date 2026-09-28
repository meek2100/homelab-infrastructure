#!/usr/bin/env bash
TARGET="${1:-mail.theurer.dev}"
SSH_USER="${2:-dtheurer}"
SSH_KEY="${3:-${HOME}/.ssh/free-email-server_id_ed25519}"

if [ ! -f "${SSH_KEY}" ]; then
    SSH_KEY="${HOME}/.ssh/id_ed25519"
fi

if [ -f "${SSH_KEY}" ]; then
    echo "🔑 Using SSH Key: ${SSH_KEY} (Target: ${SSH_USER}@${TARGET})"
    ssh -i "${SSH_KEY}" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new "${SSH_USER}@${TARGET}" 'bash -s' < "$(dirname "$0")/audit-external-host.sh"
else
    ssh -o StrictHostKeyChecking=accept-new "${SSH_USER}@${TARGET}" 'bash -s' < "$(dirname "$0")/audit-external-host.sh"
fi
