#!/bin/bash
set -e
set -o pipefail

# Reads SMART health data from a Talos node's disk via a privileged kubectl debug pod.
#
# Why this exists: ad-hoc `kubectl debug node/...` attempts to read SMART data on
# Talos nodes keep failing because the Talos rootfs ships no shell and no package
# manager (so `chroot /host sh -c 'apk add ...; smartctl ...'` exits 127) and
# unprivileged containers get EPERM opening /host/dev/nvme* (smartctl exit 1/2).
# This wrapper always uses --profile=legacy (privileged) and installs smartmontools
# inside the debug container — never in the host. It prints the smartctl output and
# removes the debug pod afterwards (kubectl debug pods are never garbage-collected).
#
# See docs/smartctl-node-debugging-runbook.md for background.
#
# Usage: smartctl-node-debug.sh NODE [DEVICE] [NAMESPACE]
#   NODE       Talos node name (required)
#   DEVICE     disk device under /dev on the node (default: nvme0n1)
#   NAMESPACE  namespace for the debug pod (default: home)
#   KEEP=1     keep the debug pod after the run (default: deleted)

NODE="${1:?Usage: smartctl-node-debug.sh NODE [DEVICE] [NAMESPACE]}"
DEVICE="${2:-nvme0n1}"
NAMESPACE="${3:-home}"

POD_NAME=$(kubectl debug "node/${NODE}" -n "${NAMESPACE}" \
  --image=alpine:latest \
  --profile=legacy \
  -- sh -c "apk add --no-cache smartmontools >/dev/null 2>&1 && smartctl -H -A -i /host/dev/${DEVICE}" \
  | sed -n 's/^pod\/\([a-z0-9-]*\) created$/\1/p')

if [ -z "${POD_NAME}" ]; then
  echo "ERROR: failed to create debug pod on node ${NODE}" >&2
  exit 1
fi

cleanup() {
  if [ "${KEEP:-0}" = "1" ]; then
    echo "Debug pod kept: kubectl -n ${NAMESPACE} logs ${POD_NAME}"
  else
    kubectl -n "${NAMESPACE}" delete "pod/${POD_NAME}" --wait=false >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "=== Running SMART check on ${DEVICE} at node ${NODE} (pod ${POD_NAME}) ==="
for _ in $(seq 1 60); do
  STATE=$(kubectl -n "${NAMESPACE}" get "pod/${POD_NAME}" \
    -o jsonpath='{.status.containerStatuses[0].state.terminated.exitCode}' 2>/dev/null || true)
  [ -n "${STATE}" ] && break
  sleep 5
done

if [ -z "${STATE}" ]; then
  echo "ERROR: debug pod did not terminate within 300s" >&2
  exit 1
fi

kubectl -n "${NAMESPACE}" logs "${POD_NAME}"
if [ "${STATE}" != "0" ]; then
  echo "ERROR: smartctl exited with code ${STATE}" >&2
fi
exit "${STATE}"
