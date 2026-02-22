# Investigation Report: HPA Metrics Issue for subgen-worker

## Finding Details

- **Kind:** Service
- **Resource:** media/subgen-worker
- **Namespace:** utilities (as reported by k8sgpt - INCORRECT)
- **Actual problematic resource:** HorizontalPodAutoscaler/subgen-worker in namespace **default**
- **k8sgpt fingerprint:** `ccf00f4bb75bba8bc57c2ec1c6c64ad23044956e24fb4df1f3906af6080f066b`

## Summary

The HorizontalPodAutoscaler (HPA) `subgen-worker` in the `default` namespace is unable to retrieve CPU and memory metrics. This is causing HPA scaling events to fail, though the application itself continues to run correctly.

## Evidence

### HPA Status
```
NAME            REFERENCE                  TARGETS                                     MINPODS   MAXPODS   REPLICAS   AGE
subgen-worker   Deployment/subgen-worker   cpu: <unknown>/70%, memory: <unknown>/80%   1         10        2          45h
```

### HPA Conditions
```
Type            Status  Reason                   Message
----            ------  ------                   -------
AbleToScale     True    SucceededGetScale        the HPA controller was able to get the target's current scale
ScalingActive   False   FailedGetResourceMetric  the HPA was unable to compute the replica count: failed to get cpu utilization: unable to get metrics for resource cpu: no metrics returned from resource metrics API
ScalingLimited  False   DesiredWithinRange       the desired count is within the acceptable range
```

### Metrics API Queries
- **Default namespace:** Returns empty list - `{"kind":"PodMetricsList","apiVersion":"metrics.k8s.io/v1beta1","metadata":{},"items":[]}`
- **Media namespace:** Returns metrics for all pods including subgen-worker

### Metrics-Server Logs
The metrics-server is experiencing authentication errors when scraping some nodes:
```
E0222 16:45:39.885422       1 scraper.go:149] "Failed to scrape node" err="request failed, status: \"401 Unauthorized\"" node="worker-01"
E0222 16:45:39.901244       1 scraper.go:149] "Failed to scrape node" err="request failed, status: \"401 Unauthorized\"" node="cp-01"
```

### Duplicate Deployments Discovery
There are TWO separate `subgen-worker` deployments in the cluster:

1. **Media namespace (GitOps-managed) - WORKING:**
   - Deployment: `subgen-worker` in `media` namespace
   - Managed via HelmRelease: `/workspace/repo/kubernetes/apps/media/subgen/app/worker-helm-release.yaml`
   - Pods returning metrics correctly
   - Image: `ghcr.io/lenaxia/subgen-worker:v0.2.20-cpu`
   - Resources: 2 CPU request, 4 CPU limit; 4Gi memory request, 8Gi limit
   - Pods: Running on worker-00 and worker-01

2. **Default namespace (manually created) - NOT WORKING:**
   - Deployment: `subgen-worker` in `default` namespace
   - Created via kubectl (not GitOps)
   - Pods NOT returning metrics
   - Image: `ghcr.io/lenaxia/subgen-worker:v0.2.21-cpu`
   - Resources: 500m CPU request, 1 CPU limit; 2Gi memory request, 4Gi limit
   - Pods: Running on worker-01 and cp-01
   - HPA: `subgen-worker` targeting this deployment with metrics failures

### Pod Distribution
- **Media namespace pods:**
  - `subgen-worker-5c876c5f8-j9vjj` → worker-00 (192.168.3.20)
  - `subgen-worker-5c876c5f8-krrtr` → worker-01 (192.168.3.21)

- **Default namespace pods:**
  - `subgen-worker-7f578c8795-67r8x` → worker-01 (192.168.3.21)
  - `subgen-worker-7f578c8795-9gpl4` → cp-01 (192.168.3.11)

## Root Cause

1. **Namespace Confusion:** The k8sgpt finding incorrectly identifies the Service in the `media` namespace as having issues, when the actual problem is with the HPA in the `default` namespace.

2. **Duplicate Deployments:** There are two separate subgen-worker deployments:
   - One properly managed via GitOps in the `media` namespace (working correctly)
   - One manually created in the `default` namespace (HPA not working)

3. **Metrics Collection Inconsistency:** While the metrics-server can collect metrics for pods in the `media` namespace on nodes worker-00 and worker-01, it cannot collect metrics for the manually created pods in the `default` namespace on nodes worker-01 and cp-01.

4. **Authentication Issues:** The metrics-server is experiencing intermittent 401 Unauthorized errors when scraping some nodes (worker-01, cp-01), though this doesn't explain why media namespace pods on the same nodes have metrics while default namespace pods don't.

5. **Not GitOps-Managed:** The problematic resources (Deployment and HPA in default namespace) were created manually via kubectl and are not managed by the GitOps repository.

## Proposed Fix

### Option 1: Remove Manually Created Resources (RECOMMENDED)
Delete the manually created resources in the default namespace since they are duplicates and not managed by GitOps:

```bash
kubectl delete hpa subgen-worker -n default
kubectl delete deployment subgen-worker -n default
```

This would:
- Eliminate the duplicate deployment
- Remove the broken HPA
- Leave only the GitOps-managed deployment in the media namespace
- Stop the error events being generated

### Option 2: Fix Metrics-Server Authentication (Infrastructure Fix)
Investigate and fix the 401 Unauthorized errors between metrics-server and kubelet on worker-01 and cp-01. This is a cluster-level infrastructure issue that requires:
- Reviewing Talos machine configuration
- Checking kubelet TLS certificates
- Verifying metrics-server RBAC permissions
- Potentially updating Talos to a newer version if this is a known issue

This fix is NOT something that can be done via the GitOps repository.

### Option 3: Migrate Default Namespace Resources to GitOps
If the default namespace deployment is intentionally separate and should be kept:
1. Create proper GitOps manifests for it
2. Add an HPA configuration
3. Investigate why metrics aren't being collected (likely requires Option 2 as well)

## Confidence

**Low** - The root cause involves cluster-level infrastructure issues (metrics-server authentication to kubelet) and manually created resources outside of GitOps control. The investigation shows clear symptoms but the underlying fix requires access to Talos configuration and possibly infrastructure changes beyond the GitOps repository.

## Notes

1. The GitOps-managed `subgen-worker` in the `media` namespace is working correctly and returning metrics.

2. The k8sgpt finding appears to have incorrectly identified the Service as the problematic resource when the issue is actually with an HPA in a different namespace.

3. The manually created deployment in the default namespace uses a different image tag (v0.2.21-cpu) than the GitOps-managed one (v0.2.20-cpu), suggesting they may serve different purposes or this is an old leftover deployment.

4. Before removing the default namespace deployment, verify whether it's still needed or if it was meant to be replaced by the GitOps-managed version.

5. A human reviewer should check with the cluster administrators to:
   - Confirm whether the default namespace subgen-worker deployment is still needed
   - Coordinate any metrics-server authentication fixes
   - Determine if cleanup of the default namespace resources is appropriate

## Investigation Timeline

1. Checked for existing PRs - None found
2. Inspected Service `media/subgen-worker` - Found it's in media namespace, not utilities
3. Discovered the actual problem is with HPA in default namespace
4. Investigated metrics-server logs showing 401 errors
5. Found duplicate deployments across namespaces
6. Confirmed metrics work for media namespace but not default namespace
7. Determined manually created resources are outside GitOps control
