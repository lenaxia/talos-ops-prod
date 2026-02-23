#!/usr/bin/env bash
set -o errexit
set -o pipefail

# SOPS-encrypted files (.sops.yaml) contain encryption metadata that is not part of the
# standard Kubernetes schema. These files are meant to be decrypted before being applied
# to the cluster, so we filter them out during validation to avoid schema validation errors.

KUBERNETES_DIR=$1

[[ -z "${KUBERNETES_DIR}" ]] && echo "Kubernetes location not specified" && exit 1

kustomize_args=("--load-restrictor=LoadRestrictionsNone")
kustomize_config="kustomization.yaml"
kubeconform_args=(
    "-strict"
    "-ignore-missing-schemas"
    "-schema-location"
    "default"
    "-schema-location"
    "https://kubernetes-schemas.pages.dev/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json"
    "-verbose"
)

# Filter out SOPS-encrypted resources from kustomize output
# SOPS resources contain a 'sops' field that is not part of the Kubernetes schema
filter_sops_resources() {
    # Use yq to split documents and filter out those containing sops metadata
    # We check both metadata.sops and sops fields to handle all SOPS resource formats
    yq eval 'select(.sops == null and .metadata.sops == null)' -
}

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
    kustomize build "${file/%$kustomize_config}" "${kustomize_args[@]}" 2>/dev/null | filter_sops_resources | kubeconform "${kubeconform_args[@]}"
    if [[ ${PIPESTATUS[0]} != 0 ]]; then
        exit 1
    fi
done

echo "=== Validating kustomizations in ${KUBERNETES_DIR}/apps ==="
find "${KUBERNETES_DIR}/apps" -type f -name $kustomize_config -print0 | while IFS= read -r -d $'\0' file;
do
    echo "=== Validating kustomizations in ${file/%$kustomize_config} ==="
    kustomize build "${file/%$kustomize_config}" "${kustomize_args[@]}" 2>/dev/null | filter_sops_resources | kubeconform "${kubeconform_args[@]}"
    if [[ ${PIPESTATUS[0]} != 0 ]]; then
        exit 1
    fi
done
