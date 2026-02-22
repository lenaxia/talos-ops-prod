# Investigation Report: MutatingWebhookConfiguration kyverno-policy-mutating-webhook-cfg

## Finding

- **Kind:** MutatingWebhookConfiguration
- **Resource:** /mutate-policy.kyverno.svc
- **Namespace:** utilities (incorrect - actual namespace is kyverno)
- **Parent:** <none>
- **k8sgpt fingerprint:** 1e5ac37884ab87da49d17e48b7081ff29881ee08a2798ebdd6fd9379618cfd77

## Evidence

### Service Endpoints (Correctly Pointing to Active Pod)
```
kubectl get endpoints kyverno-svc -n kyverno
- Pod: kyverno-admission-controller-758c794c9-6pfm7 (IP: 10.69.5.51, Ready: true)
```

### Old Inactive Pods (Not in Service Endpoints)
```
kubectl get pods -n kyverno
- kyverno-admission-controller-5db7f89bb5-mgg79 (Succeeded, 70d old, node shutdown termination)
- kyverno-admission-controller-5db7f89bb5-vg87t (Succeeded, 82d old, node shutdown termination)
```

### ReplicaSet Status
```
Old ReplicaSets: kyverno-admission-controller-5db7f89bb5 (0/0 replicas created)
New ReplicaSet: kyverno-admission-controller-758c794c9 (1/1 replicas created)
```

### Deployment Configuration Mismatch
- HelmRelease values: replicaCount: 3
- Actual deployment: spec.replicas: 1

## Root Cause

k8sgpt is detecting old, inactive pods that match the service selector and flagging them as being "pointed to" by the webhook. However, these pods are NOT in the service endpoints - the webhook is correctly pointing to the active pod.

The old pods from ReplicaSet `5db7f89bb5` (82 days old) are in "Succeeded" status because they were terminated during a node shutdown. These pods should have been automatically cleaned up when the ReplicaSet was scaled down, but they remain in the cluster.

Additionally, there's a configuration drift: the GitOps repository specifies `replicaCount: 3` but the actual deployment has only 1 replica, suggesting manual intervention outside of GitOps.

## Required Actions (Cluster Write Access Required)

1. **Clean up old pods:**
   ```bash
   kubectl delete pod kyverno-admission-controller-5db7f89bb5-mgg79 -n kyverno
   kubectl delete pod kyverno-admission-controller-5db7f89bb5-vg87t -n kyverno
   ```

2. **Reconcile the HelmRelease to sync replica count:**
   ```bash
   flux reconcile helmrelease kyverno -n kyverno
   ```
   OR manually scale if the current count is intentional:
   ```bash
   kubectl scale deployment kyverno-admission-controller -n kyverno --replicas=3
   ```

3. **Investigate why the ReplicaSet controller did not clean up the old pods** - this may indicate a bug or manual intervention that bypassed normal cleanup processes.

## Confidence

Medium - The webhook itself is functioning correctly, but the presence of old pods and configuration drift indicates an operational issue that needs human intervention.

## GitOps Changes Needed

No GitOps changes are required at this time. The HelmRelease configuration is correct. The issue requires manual cluster operations to clean up the old pods and reconcile the deployment state.

If the intentional replica count is 1 (not 3), then update:
```yaml
# /workspace/repo/kubernetes/apps/kyverno/app/helm-release.yaml
replicaCount: 1  # Change from 3 to 1
```
