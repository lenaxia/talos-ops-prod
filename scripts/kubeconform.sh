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
    kustomize build "${file/%$kustomize_config}" "${kustomize_args[@]}" | kubeconform "${kubeconform_args[@]}"
    if [[ ${PIPESTATUS[0]} != 0 ]]; then
        exit 1
    fi
done

echo "=== Validating kustomizations in ${KUBERNETES_DIR}/apps ==="

# Build array of app directories that are actually referenced by Flux Kustomization manifests
flux_ks_files=$(find "${KUBERNETES_DIR}/flux" -type f -name '*.yaml' -print0 | xargs -0 grep -l "kind: Kustomization" 2>/dev/null || true)
app_paths_to_validate=()

for ks_file in $flux_ks_files; do
    # Extract path from Flux Kustomization manifests that point to apps/
    app_path=$(yq eval '.spec.path // ""' "$ks_file" 2>/dev/null | grep "^${KUBERNETES_DIR}/apps" || true)
    if [[ -n "$app_path" ]]; then
        # Normalize the path (remove trailing slash if present)
        app_path="${app_path%/}"
        app_paths_to_validate+=("$app_path")
    fi
done

# Remove duplicates
app_paths_to_validate=($(echo "${app_paths_to_validate[@]}" | tr ' ' '\n' | sort -u))

echo "=== Found ${#app_paths_to_validate[@]} app directories referenced by Flux Kustomizations ==="

# Only validate kustomizations in directories that are actually used by Flux
for app_path in "${app_paths_to_validate[@]}"; do
    if [[ ! -d "$app_path" ]]; then
        echo "Warning: Referenced directory does not exist: $app_path"
        continue
    fi

    find "$app_path" -type f -name "$kustomize_config" -print0 | while IFS= read -r -d $'\0' file;
    do
        echo "=== Validating kustomizations in ${file/%$kustomize_config} ==="
        kustomize build "${file/%$kustomize_config}" "${kustomize_args[@]}" | kubeconform "${kubeconform_args[@]}"
        if [[ ${PIPESTATUS[0]} != 0 ]]; then
            exit 1
        fi
    done
done
