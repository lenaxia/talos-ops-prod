#!/usr/bin/env bash
set -euo pipefail

ANSIBLE_DIR="${1:?Usage: ansible-bump.sh <ansible-dir> <job-yaml>}"
JOB_YAML="${2:?Usage: ansible-bump.sh <ansible-dir> <job-yaml>}"

REV=$(find "$ANSIBLE_DIR" -type f -exec md5sum {} + | sort | md5sum | cut -c1-8)

sed -i "s|ansible.talos-ops/revision: .*|ansible.talos-ops/revision: \"${REV}\"|g" "$JOB_YAML"

echo "Revision bumped to: ${REV}"
