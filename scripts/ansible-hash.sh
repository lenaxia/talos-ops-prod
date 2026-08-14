#!/usr/bin/env bash
set -euo pipefail

ANSIBLE_DIR="${1:?Usage: ansible-hash.sh <ansible-dir>}"
find "$ANSIBLE_DIR" -type f -exec md5sum {} + | sort | md5sum | cut -c1-8
