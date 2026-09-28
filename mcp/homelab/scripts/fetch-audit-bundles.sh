#!/usr/bin/env bash
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
mkdir -p "${REPO_ROOT}/infrastructure/external-hosts/web-server"
mkdir -p "${REPO_ROOT}/infrastructure/external-hosts/email-server"

echo "📥 Fetching web-server (theurer.dev) audit bundle..."
scp meek2100@theurer.dev:/tmp/audit_*.tar.gz "${REPO_ROOT}/infrastructure/external-hosts/web-server/" 2>/dev/null || echo "⚠️ Could not fetch from theurer.dev"

echo "📥 Fetching email-server (mail.theurer.dev / email.theurer.dev) audit bundle..."
scp meek2100@mail.theurer.dev:/tmp/audit_*.tar.gz "${REPO_ROOT}/infrastructure/external-hosts/email-server/" 2>/dev/null || \
scp meek2100@email.theurer.dev:/tmp/audit_*.tar.gz "${REPO_ROOT}/infrastructure/external-hosts/email-server/" 2>/dev/null || echo "⚠️ Could not fetch from email server"

echo "✅ Bundles downloaded to infrastructure/external-hosts/"
ls -lh "${REPO_ROOT}/infrastructure/external-hosts/web-server/" "${REPO_ROOT}/infrastructure/external-hosts/email-server/"
