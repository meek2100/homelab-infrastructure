#!/usr/bin/env bash
TARGET="${1:-mail.theurer.dev}"
ssh -o StrictHostKeyChecking=accept-new "meek2100@${TARGET}" 'bash -s' < "$(dirname "$0")/audit-external-host.sh"
