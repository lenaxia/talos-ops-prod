# Mechanic Agent OOMKill Investigation

## Issue
The mechanic-agent pod `mechanic-agent-9823433ab1f4-5p8cq` was terminated with exit code 137 (OOMKilled).

## Root Cause
The mechanic-watcher deployment configures agent jobs with a memory limit of 512Mi via the `AGENT_MEM_LIMIT` environment variable. During investigation of a critical severity finding (Deployment/pgadmin in utilities namespace), the AI agent operations exceeded this memory limit, causing the container to be killed by the OOM killer.

## Current Configuration
```yaml
AGENT_CPU_REQUEST: 100m
AGENT_MEM_REQUEST: 128Mi
AGENT_CPU_LIMIT: 500m
AGENT_MEM_LIMIT: 512Mi  # Too low for AI agent operations
```

## Why This Cannot Be Fixed via GitOps
The mechanic-watcher deployment is NOT managed through the GitOps repository at `/workspace/repo/kubernetes/`. Evidence:
- No mechanic-related manifests found in the kubernetes directory
- No mechanic HelmRelease or Kustomization found in flux configuration
- The deployment was installed directly via helm outside of the GitOps workflow

## Required Fix
The mechanic-watcher deployment needs to be updated to increase `AGENT_MEM_LIMIT` to at least 1Gi (or higher depending on the complexity of the investigations being performed). This must be done by:
1. Finding the helm release values used to install mechanic-watcher
2. Updating the `agentMemoryLimit` value in the Helm chart
3. Running `helm upgrade mechanic <chart-ref> -f <values-file>` to apply the change

## Recommended Action
This finding requires human intervention to:
1. Locate the mechanic-watcher Helm release configuration (likely in a separate repo or documentation)
2. Update the agent memory limit configuration
3. Apply the change via helm upgrade
