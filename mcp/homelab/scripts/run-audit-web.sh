#!/usr/bin/env bash
ssh -o StrictHostKeyChecking=accept-new meek2100@theurer.dev 'bash -s' < "$(dirname "$0")/audit-external-host.sh"
