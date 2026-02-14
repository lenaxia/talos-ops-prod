#!/usr/bin/env bash
set -o errexit
set -o pipefail

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

validate_kustomize_build() {
    local dir=$1
    local base_dir=$(dirname "$dir")
    
    # Validate that all referenced resources in kustomization exist
    if [[ -f "${dir}/${kustomize_config}" ]]; then
        # Check for relative path resources
        while IFS= read -r line; do
            if [[ "$line" =~ ^[[:space:]]*-+[[:space:]]+\.\.\/ ]]; then
                local resource_path=$(echo "$line" | sed -E 's/^[[:space:]]*-+[[:space:]]+//')
                local resolved_path="${base_dir}/${resource_path}"
                if [[ ! -e "$resolved_path" ]]; then
                    echo "ERROR: Referenced resource '${resource_path}' in ${dir}/${kustomize_config} does not exist at ${resolved_path}"
                    return 1
                fi
            fi
        done < "${dir}/${kustomize_config}"
    fi
    
    kustomize build "${dir}" "${kustomize_args[@]}" | kubeconform "${kubeconform_args[@]}"
    if [[ ${PIPESTATUS[0]} != 0 ]]; then
        return 1
    fi
    return 0
}

echo "=== Validating standalone manifests in ${KUBERNETES_DIR}/flux ==="
find "${KUBERNETES_DIR}/flux" -maxdepth 1 -type f -name '*.yaml' -print0 | while IFS= read -r -d $'\0' file;
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
    validate_kustomize_build "${file/%$kustomize_config}" || exit 1
done

echo "=== Validating kustomizations in ${KUBERNETES_DIR}/apps ==="
find "${KUBERNETES_DIR}/apps" -type f -name $kustomize_config -print0 | while IFS= read -r -d $'\0' file;
do
    echo "=== Validating kustomizations in ${file/%$kustomize_config} ==="
    validate_kustomize_build "${file/%$kustomize_config}" || exit 1
done
