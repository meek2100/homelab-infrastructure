#!/usr/bin/env bash
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
mkdir -p "${REPO_ROOT}/infrastructure/external-hosts/web-server"
mkdir -p "${REPO_ROOT}/infrastructure/external-hosts/email-server"

echo "📥 Fetching web-server (theurer.dev) audit bundle..."
scp meek2100@theurer.dev:/tmp/audit_*.tar.gz "${REPO_ROOT}/infrastructure/external-hosts/web-server/" 2>/dev/null || echo "⚠️ Could not fetch from theurer.dev"

echo "📥 Fetching email-server (mail.theurer.dev) audit bundle..."
SSH_USER="${1:-meek2100}"
SSH_KEY="${2:-${HOME}/.ssh/free-email-server_id_ed25519}"
if [ ! -f "${SSH_KEY}" ]; then
    SSH_KEY="${HOME}/.ssh/id_ed25519"
fi
SCP_OPT=""
if [ -f "${SSH_KEY}" ]; then
    SCP_OPT="-i ${SSH_KEY} -o IdentitiesOnly=yes"
fi

scp ${SCP_OPT} "${SSH_USER}@mail.theurer.dev:/tmp/audit_*.tar.gz" "${REPO_ROOT}/infrastructure/external-hosts/email-server/" 2>/dev/null || \
scp ${SCP_OPT} "${SSH_USER}@35.212.229.212:/tmp/audit_*.tar.gz" "${REPO_ROOT}/infrastructure/external-hosts/email-server/" 2>/dev/null || \
echo "⚠️ Could not fetch from email server (verify SSH credentials on mail.theurer.dev)"

echo "✅ Bundles downloaded to infrastructure/external-hosts/"
ls -lh "${REPO_ROOT}/infrastructure/external-hosts/web-server/" "${REPO_ROOT}/infrastructure/external-hosts/email-server/"
