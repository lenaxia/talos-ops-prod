# Mechanic Agent OOM Issue

## Finding Details

- **Fingerprint:** 637257a1070b
- **Affected Resource:** Pod/mechanic-agent-c91e062572c3-wllm9
- **Namespace:** default
- **Parent:** Job/mechanic-agent-c91e062572c3
- **Error:** Container mechanic-agent: terminated with exit code 137 (OOMKilled)

## Root Cause

The mechanic-agent pod is being terminated with exit code 137, which indicates an OOM (Out of Memory) kill. The pod has a memory limit of 512Mi, which is insufficient for the opencode agent's memory requirements when processing complex investigations.

## Current Configuration

From the `mechanic` Deployment in the `default` namespace:

```yaml
env:
  - name: AGENT_MEM_REQUEST
    value: 128Mi
  - name: AGENT_MEM_LIMIT
    # Empty - defaults to 512Mi
```

The `AGENT_MEM_LIMIT` environment variable is empty, causing the agent pods to default to a 512Mi memory limit. The opencode agent can consume more memory than this limit when:
- Processing large or complex findings
- Investigating multiple correlated findings
- Analyzing extensive logs and manifests
- Running tools that require significant memory (e.g., kubectl logs with large output)

## Recommended Fix

The mechanic deployment is not managed by this GitOps repository (it is a bootstrap tool that manages this repository). To fix this issue, the mechanic deployment needs to be updated directly:

1. Edit the `mechanic` Deployment:
   ```bash
   kubectl edit deployment mechanic -n default
   ```

2. Update the `AGENT_MEM_LIMIT` environment variable to increase the memory limit:
   ```yaml
   - name: AGENT_MEM_LIMIT
     value: 1Gi  # Recommended: increase from default 512Mi to 1Gi
   ```

3. Optionally, also increase the memory request for better resource allocation:
   ```yaml
   - name: AGENT_MEM_REQUEST
     value: 256Mi  # Increase from 128Mi to 256Mi
   ```

## Alternative Fix

If the mechanic is installed via Helm, update the values file and reinstall:

```bash
helm upgrade mechanic <mechanic-chart-repo> \
  --namespace default \
  --set agent.memLimit=1Gi \
  --set agent.memRequest=256Mi
```

## Verification

After applying the fix, verify that the mechanic-agent pods no longer get OOMKilled:

```bash
kubectl get pods -n default -l job-name=mechanic-agent-* -w
kubectl describe pod <mechanic-agent-pod> -n default | grep -A 5 "State:"
```

## Notes

- This is a self-referential issue: the mechanic-agent that was investigating a finding itself failed due to insufficient memory
- The fix requires modifying the mechanic deployment directly, which is outside the scope of this GitOps repository
- Consider monitoring the mechanic-agent pod memory usage to determine the optimal memory limit
