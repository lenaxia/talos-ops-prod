#!/usr/bin/env bash
set -o errexit
set -o pipefail

# SOPS-encrypted files (.sops.yaml) contain encryption metadata that is not part of the
# standard Kubernetes schema. These files are meant to be decrypted before being applied
# to the cluster, so we skip them during validation to avoid schema validation errors.

KUBERNETES_DIR=$1

[[ -z "${KUBERNETES_DIR}" ]] && echo "Kubernetes location not specified" && exit 1

kustomize_args=("--load-restrictor=LoadRestrictionsNone")
kustomize_config="kustomization.yaml"
kubeconform_args=(
    "-strict"
    "-ignore-missing-schemas"
    "-skip"
    "Secret"
    "-schema-location"
    "default"
    "-schema-location"
    "https://kubernetes-schemas.pages.dev/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json"
    "-verbose"
)

# Function to check if a file is SOPS-encrypted
is_sops_encrypted() {
    local file=$1
    # Check if filename ends with .sops.yaml
    if [[ "$file" == *.sops.yaml ]]; then
        return 0
    fi
    # Check if file contains SOPS encryption metadata
    if grep -q "^sops:" "$file" 2>/dev/null; then
        return 0
    fi
    return 1
}

echo "=== Validating standalone manifests in ${KUBERNETES_DIR}/flux ==="
find "${KUBERNETES_DIR}/flux" -maxdepth 1 -type f -name '*.yaml' -print0 | while IFS= read -r -d $'\0' file;
do
    if is_sops_encrypted "$file"; then
        echo "Skipping SOPS-encrypted file: $file"
        continue
    fi
    kubeconform "${kubeconform_args[@]}" "${file}"
    if [[ ${PIPESTATUS[0]} != 0 ]]; then
        exit 1
    fi
done

echo "=== Validating kustomizations in ${KUBERNETES_DIR}/flux ==="
find "${KUBERNETES_DIR}/flux" -type f -name $kustomize_config -print0 | while IFS= read -r -d $'\0' file;
do
    echo "=== Validating kustomizations in ${file/%$kustomize_config} ==="
    kustomize build "${file/%$kustomize_config}" "${kustomize_args[@]}" 2>/dev/null | while IFS= read -r -d $'\0' manifest;
    do
        if is_sops_encrypted "$manifest"; then
            echo "Skipping SOPS-encrypted manifest"
            continue
        fi
        kubeconform "${kubeconform_args[@]}" <(echo "$manifest")
        if [[ ${PIPESTATUS[0]} != 0 ]]; then
            exit 1
        fi
    done
done

echo "=== Validating kustomizations in ${KUBERNETES_DIR}/apps ==="
find "${KUBERNETES_DIR}/apps" -type f -name $kustomize_config -print0 | while IFS= read -r -d $'\0' file;
do
    echo "=== Validating kustomizations in ${file/%$kustomize_config} ==="
    kustomize build "${file/%$kustomize_config}" "${kustomize_args[@]}" 2>/dev/null | while IFS= read -r -d $'\0' manifest;
    do
        if is_sops_encrypted "$manifest"; then
            echo "Skipping SOPS-encrypted manifest"
            continue
        fi
        kubeconform "${kubeconform_args[@]}" <(echo "$manifest")
        if [[ ${PIPESTATUS[0]} != 0 ]]; then
            exit 1
        fi
    done
done
