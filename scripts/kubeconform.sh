#!/usr/bin/env bash
set -o errexit
set -o pipefail

# SOPS-encrypted files (.sops.yaml) contain encryption metadata that is not part of
# standard Kubernetes schema. These files are meant to be decrypted before being applied
# to the cluster, so we strip the 'sops' field from kustomize build output
# before validation to avoid schema validation errors.

KUBERNETES_DIR=$1

[[ -z "${KUBERNETES_DIR}" ]] && echo "Kubernetes location not specified" && exit 1

# Function to strip SOPS metadata from YAML output
# SOPS adds a 'sops:' field that is not part of Kubernetes schema
# This function removes the entire sops block and any associated metadata
strip_sops_metadata() {
    local temp_file
    temp_file=$(mktemp)

    # Process YAML and remove sops field along with its children
    # This handles the case where sops can appear at any indentation level
    awk '
    BEGIN { in_sops = 0; sops_indent = "" }
    {
        # Check if this line starts with sops field
        if ($0 ~ /^[[:space:]]*sops:/) {
            in_sops = 1
            sops_indent = match($0, /[^[:space:]]/) - 1
            next
        }

        # If we are in sops block
        if (in_sops) {
            # Check if this line is at the same or less indentation than sops start
            current_indent = match($0, /[^[:space:]]/)

            # Print empty lines or lines at same/less indentation (exit sops block)
            if (current_indent == 0 || current_indent <= sops_indent) {
                in_sops = 0
                print $0
            }
            # Otherwise, skip this line (it is part of sops block)
            next
        }

        # Not in sops block, print the line
        print $0
    }
    ' > "$temp_file"

    cat "$temp_file"
    rm -f "$temp_file"
}

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

echo "=== Validating standalone manifests in ${KUBERNETES_DIR}/flux ==="
find "${KUBERNETES_DIR}/flux" -maxdepth 1 -type f -name '*.yaml' ! -name '*.sops.yaml' -print0 | while IFS= read -r -d $'\0' file;
do
    kubeconform "${kubeconform_args[@]}" "${file}"
    if [[ ${PIPESTATUS[0]} != 0 ]]; then
        exit 1
    fi
done

echo "=== Validating kustomizations in ${KUBERNETES_DIR}/flux ==="
find "${KUBERNETES_DIR}/flux" -type f -name $kustomize_config -print0 | while IFS= read -r -d $'\0' file;
do
    echo "=== Validating kustomizations in ${file/%$kustomize_config} ==="
    kustomize build "${file/%$kustomize_config}" "${kustomize_args[@]}" 2>/dev/null | strip_sops_metadata | kubeconform "${kubeconform_args[@]}"
    if [[ ${PIPESTATUS[0]} != 0 ]]; then
        exit 1
    fi
done

echo "=== Validating kustomizations in ${KUBERNETES_DIR}/apps ==="
find "${KUBERNETES_DIR}/apps" -type f -name $kustomize_config -print0 | while IFS= read -r -d $'\0' file;
do
    echo "=== Validating kustomizations in ${file/%$kustomize_config} ==="
    kustomize build "${file/%$kustomize_config}" "${kustomize_args[@]}" 2>/dev/null | strip_sops_metadata | kubeconform "${kubeconform_args[@]}"
    if [[ ${PIPESTATUS[0]} != 0 ]]; then
        exit 1
    fi
done
