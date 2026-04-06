# Mechanic-Watcher Configuration Issue

## Problem

Mechanic-agent pods are being OOMKilled due to insufficient memory limits.

## Evidence

From investigation of pod `mechanic-agent-143b7af4336a-tkwrz`:
- Pod terminated with exit code 137 (OOMKilled)
- Container memory limit: 512Mi
- Container ran for ~66 seconds before being killed
- State: `Terminated` with `Reason: OOMKilled`

## Root Cause

The mechanic-watcher deployment currently has:
```yaml
- name: AGENT_MEM_LIMIT
  value: ""  # Empty - uses default of 512Mi
```

When `AGENT_MEM_LIMIT` is empty, the mechanic-watcher uses a default memory limit of 512Mi, which is insufficient for agent pods during investigations.

## Fix Required

The mechanic-watcher deployment needs to be configured with a higher `AGENT_MEM_LIMIT` value:

```yaml
- name: AGENT_MEM_LIMIT
  value: "2Gi"  # Recommended value
```

## Implementation

**Important:** The mechanic-watcher deployment is NOT currently managed by the GitOps repository at `/workspace/repo/kubernetes/`. 

To fix this issue:
1. Add the mechanic-watcher HelmRelease to the GitOps repository
2. Configure the `AGENT_MEM_LIMIT` environment variable to "2Gi" (or higher based on workload analysis)
3. Commit and apply the changes

## Alternative Workaround

If adding mechanic-watcher to GitOps is not immediately possible:
- Manually update the mechanic-watcher deployment:
  ```bash
  kubectl set env deployment/mechanic AGENT_MEM_LIMIT=2Gi -n default
  ```
- This will require the deployment to be manually re-synced on future updates

## Confidence

**High confidence** - The pod was clearly OOMKilled and increasing the memory limit is the correct fix.

## Safety

**Safe** - Increasing memory limits does not introduce breaking changes. It may increase cluster memory usage during mechanic-agent executions, which is acceptable for remediation workloads.
