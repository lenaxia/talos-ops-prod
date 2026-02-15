#!/usr/bin/env bash
set -o errexit
set -o pipefail

KUBERNETES_DIR=$1

[[ -z "${KUBERNETES_DIR}" ]] && echo "Kubernetes location not specified" && exit 1

echo "=== Validating YAML syntax in CRDs ==="
find "${KUBERNETES_DIR}" -path "*/crds/*.yaml" -print0 | while IFS= read -r -d $'\0' file;
do
    echo "Checking ${file}"
    python3 -c "
import yaml
import sys
try:
    with open('${file}', 'r') as f:
        data = yaml.safe_load(f)
        print('  ✓ Valid YAML')
except yaml.YAMLError as e:
        print(f'  ✗ YAML Error: {e}', file=sys.stderr)
        sys.exit(1)
"
    if [[ ${PIPESTATUS[0]} != 0 ]]; then
        exit 1
    fi
done
