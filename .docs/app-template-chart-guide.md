# bjw-s/app-template Chart Configuration Guide

## Overview

This repository uses the [bjw-s/app-template](https://github.com/bjw-s/helm-charts/tree/main/charts/library/common) Helm chart for several applications including vllm. This chart uses **strict JSON Schema validation**, which means only explicitly documented and validated values are allowed.

## Schema Validation

The bjw-s/app-template chart version 4.3.0 (and later versions) enforces strict schema validation. Any values that are not part of the chart's documented schema will cause `helm template` to fail with errors like:

```
Error: values don't meet the specifications of the schema(s) in the following chart(s):
app-template:
- at '/controllers/app': 'allOf' failed
  - at '/controllers/app': additional properties 'propertyName' not allowed
```

## Common Unsupported Fields

### `progressDeadlineSeconds` for Deployments

The `progressDeadlineSeconds` is a Kubernetes Deployment spec field that controls how long Kubernetes waits for a deployment to progress. However, the bjw-s/app-template chart **does not expose this field** in its values schema.

#### Issue
Adding `progressDeadlineSeconds: 900` under `controllers.app` will fail validation:

```yaml
# ❌ INVALID - This will cause schema validation errors
controllers:
  app:
    type: deployment
    progressDeadlineSeconds: 900  # Not supported!
```

#### Alternatives for Long-Running Deployments

For ML/AI workloads that take a long time to start (like vllm loading large models), use these supported alternatives:

1. **Increase Startup Probe Settings** (Recommended)
   ```yaml
   controllers:
     app:
       containers:
         app:
           probes:
             startup:
               enabled: true
               custom: true
               spec:
                 initialDelaySeconds: 300  # 5 minutes before first check
                 periodSeconds: 10
                 timeoutSeconds: 10
                 failureThreshold: 60  # Allow 60 failed checks (10 minutes total)
   ```

2. **Increase Upgrade Timeout**
   ```yaml
   # In HelmRelease spec
   upgrade:
     timeout: 30m  # Give more time for upgrades
   ```

3. **Configure Liveness/Readiness Probes** (As shown in vllm configuration)
   ```yaml
   probes:
     liveness:
       enabled: false  # Disable if application takes too long to start
       custom: true
       spec:
         initialDelaySeconds: 120
         # ...
   ```

### Other Unsupported Fields

The chart may not expose all Kubernetes API fields. Before adding any configuration:

1. Check the [chart's values.yaml](https://raw.githubusercontent.com/bjw-s/helm-charts/main/charts/library/common/values.yaml)
2. Review the [chart documentation](https://bjw-s-labs.github.io/helm-charts/docs/common-library/common-library)
3. If a field isn't documented, it's likely not supported through values

## Valid Controller Configuration

```yaml
controllers:
  app:
    enabled: true
    type: deployment  # or: daemonset, statefulset, cronjob, job
    annotations:
      key: value
    labels:
      key: value
    replicas: 1
    strategy:  # For deployments
      type: RollingUpdate
      rollingUpdate:
        maxUnavailable: 1
        maxSurge: 1
    revisionHistoryLimit: 3
    # Other supported fields...
```

## Troubleshooting

### Schema Validation Failures

If you encounter schema validation errors:

1. Review the error message for the specific property name
2. Check if the property is documented in the chart's values.yaml
3. Look for alternative ways to achieve your goal using supported fields
4. Consider opening an issue in the [bjw-s/helm-charts repository](https://github.com/bjw-s/helm-charts/issues) if you believe a field should be supported

### Testing Locally

Before committing changes, test your configuration locally:

```bash
# Pull the chart
helm repo add bjw-s https://bjw-s.github.io/helm-charts/
helm repo update
helm pull bjw-s/app-template --version 4.3.0

# Test your values
helm template test ./app-template-4.3.0.tgz -f your-values.yaml
```

## References

- [bjw-s/helm-charts Repository](https://github.com/bjw-s/helm-charts)
- [Common Library Documentation](https://bjw-s-labs.github.io/helm-charts/docs/common-library/common-library)
- [Chart Values Reference](https://raw.githubusercontent.com/bjw-s/helm-charts/main/charts/library/common/values.yaml)
- [Kubernetes Deployment API](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
