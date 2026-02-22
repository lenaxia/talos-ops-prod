# Investigation Report: MutatingWebhookConfiguration Issue

## Finding Details

- **Kind:** MutatingWebhookConfiguration
- **Resource:** /mdatabase.cnpg.io (webhook name within cnpg-mutating-webhook-configuration)
- **Namespace:** utilities
- **Parent:** <none>
- **k8sgpt fingerprint:** `2b7bed30e2dc6ada852cea925631e17c695dcebd694dbcd805c45c27b0f7ac1e`

## Investigation Summary

### Current State (Working Correctly)

1. **MutatingWebhookConfiguration:** `cnpg-mutating-webhook-configuration` exists with 4 webhooks, including `mdatabase.cnpg.io`
2. **Service Reference:** Webhook correctly points to `cnpg-webhook-service` in `databases` namespace (port 443)
3. **Active Pod:** `postgres-operator-cloudnative-pg-5944496f6b-jfxjs` is Running at IP `10.69.1.177:9443`
4. **Service Endpoints:** Confirmed via EndpointSlice - only the active pod is in endpoints
5. **Health Check:** Webhook responds correctly to `/readyz` endpoint (returns "OK")

### Anomaly Found

- **Old Pod:** `postgres-operator-cloudnative-pg-5b544f6f84-gfp6c` exists in Completed status for 70 days
- **Labels:** Old pod has same labels as active pod (matches service selector)
- **Version:** Old pod was running cloudnative-pg v1.27.1, current pod is v1.28.1
- **Routing:** Kubernetes Services do NOT route to Completed pods - confirmed via EndpointSlice

### Evidence

```bash
# Webhook service is healthy
$ curl -k https://10.96.98.246/readyz
OK

# Only active pod in endpoints
$ kubectl get endpointslice -n databases -l kubernetes.io/service-name=cnpg-webhook-service
- addresses: [10.69.1.177]
  targetRef.name: postgres-operator-cloudnative-pg-5944496f6b-jfxjs
  conditions.ready: true

# Deployment status
$ kubectl get deployment postgres-operator-cloudnative-pg -n databases
READY   UP-TO-DATE   AVAILABLE   AGE
1/1     1            1           203d
```

## Root Cause Assessment

**High Confidence - k8sgpt False Positive**

The k8sgpt finding states: "Mutating Webhook (mdatabase.cnpg.io) is pointing to an inactive receiver pod (postgres-operator-cloudnative-pg-5b544f6f84-gfp6c)"

However, the actual configuration:
1. Webhook points to a **Service** (`cnpg-webhook-service`), not directly to a pod
2. Service correctly routes to the **active pod** via standard Kubernetes endpoint selection
3. The old completed pod is **not receiving traffic** - confirmed by EndpointSlice inspection

The k8sgpt analyzer likely:
- Found the old completed pod with matching labels
- Incorrectly inferred that the webhook is "pointing to" this inactive pod
- Did not properly trace the service → endpoint selection → actual pod routing

## Recommended Actions

### Immediate (Manual)

1. **Delete the old completed pod:**
   ```bash
   kubectl delete pod postgres-operator-cloudnative-pg-5b544f6f84-gfp6c -n databases
   ```

2. **Verify cleanup:**
   ```bash
   kubectl get pods -n databases -l app.kubernetes.io/name=cloudnative-pg
   ```

### Long-term (Optional)

Consider adding a monitoring alert for:
- Pods in Completed status with Deployment ownerReferences
- Stale completed pods older than X days
- This would help catch similar situations early

## GitOps Changes Required

**None** - This is an operational issue that requires manual intervention. The GitOps manifests in `/workspace/repo/kubernetes/apps/databases/cloudnative-pg/app/helm-release.yaml` are correct.

## Confidence Level

**High** - The investigation conclusively shows:
- Webhook is functioning correctly (verified via direct health check)
- Service routing is correct (verified via EndpointSlice)
- Old pod is not receiving traffic (confirmed by endpoint inspection)
- The finding is a false positive caused by k8sgpt detection logic limitations

## Notes

1. This old completed pod has been present for 70 days without causing any issues
2. The webhook service has been working correctly throughout this period
3. The deployment was upgraded from v1.27.1 to v1.28.1 approximately 15 days ago (2026-02-07)
4. The old ReplicaSet `postgres-operator-cloudnative-pg-5b544f6f84` has 0/0 replicas according to deployment spec
5. The pod likely entered Completed status due to a transient condition during a previous deployment cycle

---

*Investigation completed on 2026-02-22*
*Opened automatically by mendabot*
