# Investigation: MutatingWebhookConfiguration mgpudeviceplugin.kb.io

## Summary

k8sgpt reported that the MutatingWebhookConfiguration `mgpudeviceplugin.kb.io` is pointing to inactive receiver pods. However, investigation shows this is a false positive - the webhook is correctly configured and functional.

## Finding

- **Kind:** MutatingWebhookConfiguration
- **Resource:** inteldeviceplugins-mutating-webhook-configuration (webhook: mgpudeviceplugin.kb.io)
- **Namespace:** kube-system
- **Parent:** intel-device-plugin-operator HelmRelease
- **k8sgpt fingerprint:** `9088084257989103042f2b1d04ae1bba1eaa4b4ba1da768b270cf9b0fecb8fdd`

## Evidence

### Webhook Configuration
The webhook `mgpudeviceplugin.kb.io` is configured to point to the Service `inteldeviceplugins-webhook-service` in the `kube-system` namespace:

```yaml
clientConfig:
  service:
    name: inteldeviceplugins-webhook-service
    namespace: kube-system
    path: /mutate-deviceplugin-intel-com-v1-gpudeviceplugin
    port: 443
```

### Service Endpoints
The Service has only one active endpoint pointing to the running pod:

```yaml
subsets:
- addresses:
  - ip: 10.69.5.77
    nodeName: cp-02
    targetRef:
      kind: Pod
      name: inteldeviceplugins-controller-manager-c5b6f7964-krpsb
      namespace: kube-system
```

### Pod Status
- Active pod: `inteldeviceplugins-controller-manager-c5b6f7964-krpsb` (1/1 Running, 9d old)
- Old completed pods:
  - `inteldeviceplugins-controller-manager-6bd5cc95bf-2kzwj` (0/1 Completed, 70d old)
  - `inteldeviceplugins-controller-manager-6bd5cc95bf-r9kzv` (0/1 Completed, 79d old)

The old pods are NOT endpoints of the service - they are just old ReplicaSets kept for revision history.

### Deployment Status
```bash
Name:                   inteldeviceplugins-controller-manager
Replicas:               1 desired | 1 updated | 1 total | 1 available | 0 unavailable
NewReplicaSet:          inteldeviceplugins-controller-manager-c5b6f7964 (1/1 replicas created)
```

### Active Pod Logs
The active pod shows normal operation with continuous reconciliation cycles and no errors.

## Root Cause

**This is a false positive from k8sgpt.** The webhook configuration is correct:

1. The webhook points to a Service (not directly to pods)
2. The Service has only the active pod as an endpoint
3. The old completed pods are old ReplicaSets kept by Kubernetes for revision history (`revisionHistoryLimit: 10`)
4. This is normal Kubernetes behavior and does not indicate a problem

The k8sgpt analysis likely detected the old ReplicaSet pods and incorrectly flagged them as being referenced by the webhook, when in fact they are not.

## Fix

**No fix is required.** The GitOps repository configuration is correct. The HelmRelease for `intel-device-plugin-operator` is healthy and functioning properly.

## Confidence

**High** - The investigation clearly shows:
- The webhook is correctly configured to point to a Service
- The Service has only the active pod as an endpoint
- The old pods are not referenced by the webhook
- The deployment is healthy with 1 available replica
- Pod logs show normal operation

## Notes

- The `revisionHistoryLimit: 10` on the deployment is causing old ReplicaSets to be kept, which is standard Kubernetes behavior
- The HelmRelease `maxHistory: 3` setting only affects Helm's release history, not the Kubernetes deployment's ReplicaSet history
- No action is needed in the GitOps repository
- The webhook is working correctly and processing admission requests normally

## Recommendation

No changes are needed. This k8sgpt finding can be safely dismissed as a false positive. If there are concerns about the old ReplicaSets consuming resources, the deployment's `revisionHistoryLimit` can be reduced, but this is not related to the webhook functionality.
