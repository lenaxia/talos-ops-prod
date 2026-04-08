---
# Mechanic Agent Resource Limit Fix

## Problem

Mechanic-agent pods are being OOMKilled (exit code 137) due to insufficient memory limits.

### Evidence

- Multiple mechanic-agent pods show OOMKilled status:
  ```
  mechanic-agent-04c597ea2565-bqt6q   0/1   OOMKilled   0   24h
  mechanic-agent-04c597ea2565-t5kbf   0/1   OOMKilled   0   24h
  mechanic-agent-143b7af4336a-cbjm4   0/1   OOMKilled   0   35h
  mechanic-agent-143b7af4336a-tkwrz   0/1   OOMKilled   0   35h
  ```

- Pod describe shows: `State: Terminated, Reason: OOMKilled, Exit Code: 137`

- Mechanic deployment has empty `AGENT_MEM_LIMIT` and `AGENT_CPU_LIMIT` environment variables

- Default limits being applied: 512Mi memory, 500m CPU (insufficient for LLM agent workloads)

### Root Cause

The mechanic-watcher deployment configures mechanic-agent pods with default resource limits because the `AGENT_MEM_LIMIT` and `AGENT_CPU_LIMIT` environment variables are empty. The 512Mi memory limit is insufficient for running LLM-based agents, causing the OOM killer to terminate the pods.

## Solution

Increase `AGENT_MEM_LIMIT` to 2Gi and `AGENT_CPU_LIMIT` to 1000m in the mechanic deployment.

### Application Instructions

**Option 1: Apply patch directly via kubectl (recommended)**

```bash
kubectl patch deployment mechanic -n default \
  --type='json' \
  -p='[
    {"op": "add", "path": "/spec/template/spec/containers/0/env/-", "value": {"name": "AGENT_MEM_LIMIT", "value": "2Gi"}},
    {"op": "add", "path": "/spec/template/spec/containers/0/env/-", "value": {"name": "AGENT_CPU_LIMIT", "value": "1000m"}}
  ]'
```

**Option 2: Edit the deployment directly**

```bash
kubectl edit deployment mechanic -n default
```

Add these environment variables to the `watcher` container:

```yaml
env:
  - name: AGENT_MEM_LIMIT
    value: 2Gi
  - name: AGENT_CPU_LIMIT
    value: 1000m
```

**Option 3: Long-term solution - Create a HelmRelease**

Create a HelmRelease in this repo to manage mechanic with proper values. This requires:
1. Finding the mechanic Helm chart source
2. Extracting current values from the existing installation
3. Creating a values file with updated resource limits
4. Creating a HelmRelease that references the chart and values

Example structure:
```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: mechanic
  namespace: default
spec:
  chart:
    spec:
      chart: mechanic
      sourceRef:
        kind: HelmRepository
        name: <mechanic-chart-repo>
        namespace: flux-system
  values:
    agentMemoryLimit: 2Gi
    agentCpuLimit: 1000m
```

### Verification

After applying the fix, monitor the next few mechanic-agent pods to ensure they complete successfully:

```bash
# Watch for new agent pods
kubectl get pods -n default -l job-name --watch

# Check a specific pod's status
kubectl describe pod <mechanic-agent-pod-name> -n default
```

Successful pods should show:
- Status: `Completed` (not OOMKilled)
- Exit Code: `0`

### Confidence

**High** - The root cause is clearly identified (OOMKilled due to insufficient memory), and the fix is well-established (increase resource limits). The 2Gi limit is conservative and should be sufficient for most LLM agent workloads.

## Notes

- Mechanic is currently installed via Helm and not managed by this GitOps repository
- This is a temporary fix; consider migrating mechanic to be Flux-managed for better operational consistency
- Monitor memory usage after the fix to determine if 2Gi is sufficient or if further adjustment is needed
- If memory usage remains consistently below 1Gi, consider reducing to 1.5Gi for efficiency

## Correlated Finding

- **Fingerprint:** ea593f497b2c
- **Kind:** Pod
- **Resource:** mechanic-agent-04c597ea2565-bqt6q
- **Namespace:** default
- **Parent:** Job/mechanic-agent-04c597ea2565
- **Severity:** high
