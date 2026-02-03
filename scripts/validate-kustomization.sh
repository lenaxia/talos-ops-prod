#!/usr/bin/env bash
set -o errexit
set -o pipefail

KUBERNETES_DIR=$1

[[ -z "${KUBERNETES_DIR}" ]] && echo "Kubernetes location not specified" && exit 1

echo "=== Checking kustomization.yaml files for invalid fields ==="
find "${KUBERNETES_DIR}" -type f -name "kustomization.yaml" -print0 | while IFS= read -r -d $'\0' file;
do
  api_version=$(yq eval '.apiVersion' "${file}" 2>/dev/null || echo "")
  
  if [[ "${api_version}" == "kustomize.config.k8s.io/v1beta1" ]]; then
    if yq eval '.spec' "${file}" &>/dev/null; then
      echo "❌ ERROR: Invalid 'spec' field in ${file}"
      echo "   kustomize.config.k8s.io/v1beta1 Kustomization does not support 'spec' field."
      echo "   This field belongs to kustomize.toolkit.fluxcd.io/v1 Kustomization resources."
      exit 1
    fi
  fi
done

echo "✅ No invalid kustomization.yaml files found"
