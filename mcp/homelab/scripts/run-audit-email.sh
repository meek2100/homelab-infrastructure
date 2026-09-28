#!/usr/bin/env bash
TARGET="${1:-mail.theurer.dev}"
SSH_USER="${2:-meek2100}"
SSH_KEY="${3:-${HOME}/.ssh/id_ed25519}"

if [ -f "${SSH_KEY}" ]; then
    ssh -i "${SSH_KEY}" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new "${SSH_USER}@${TARGET}" 'bash -s' < "$(dirname "$0")/audit-external-host.sh"
else
    ssh -o StrictHostKeyChecking=accept-new "${SSH_USER}@${TARGET}" 'bash -s' < "$(dirname "$0")/audit-external-host.sh"
fi
