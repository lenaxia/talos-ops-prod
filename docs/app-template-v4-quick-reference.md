# App-Template v4 Quick Reference Guide

Quick reference for the bjw-s app-template v4.x chart upgrade.

---

## What Changed in v4

### Major Changes
1. **Default Controller Type:** Now defaults to `deployment` (no need to specify)
2. **Service Auto-Inference:** Services automatically infer controller names
3. **Simplified Configuration:** Reduced boilerplate for common patterns
4. **Better Defaults:** More sensible defaults out of the box

### Breaking Changes
- None for basic configurations
- Most v3 configs work as-is in v4
- Redundant fields can be removed for cleaner configs

---

## Quick Upgrade Checklist

### Before Upgrade
- [ ] Backup current configuration
- [ ] Review application dependencies
- [ ] Check for custom configurations
- [ ] Note current version

### During Upgrade
- [ ] Update chart version to 4.3.0
- [ ] Remove redundant `type: deployment` if present
- [ ] Remove redundant `controller: <name>` from services
- [ ] Validate YAML syntax
- [ ] Test in non-production first

### After Upgrade
- [ ] Monitor pod status
- [ ] Check application logs
- [ ] Verify ingress working
- [ ] Test application functionality
- [ ] Confirm persistent data intact

---

## Common Configuration Patterns

### Basic Application

**Before (v3):**
```yaml
spec:
  chart:
    spec:
      chart: app-template
      version: 3.1.0
  values:
    controllers:
      myapp:
        type: deployment  # Can be removed in v4
        containers:
          app:
            image:
              repository: myapp/image
              tag: latest
    
    service:
      app:
        controller: myapp  # Auto-inferred in v4
        ports:
          http:
            port: 8080
```

**After (v4):**
```yaml
spec:
  chart:
    spec:
      chart: app-template
      version: 4.3.0
  values:
    controllers:
      myapp:
        # type: deployment is default, removed
        containers:
          app:
            image:
              repository: myapp/image
              tag: latest
    
    service:
      app:
        # controller auto-inferred, removed
        ports:
          http:
            port: 8080
```

### With Ingress

```yaml
ingress:
  app:
    className: internal
    hosts:
      - host: myapp.example.com
        paths:
          - path: /
            service:
              identifier: app
              port: http
```

### With Persistence

```yaml
persistence:
  config:
    type: persistentVolumeClaim
    existingClaim: myapp-config
    globalMounts:
      - path: /config
  
  data:
    type: emptyDir
    globalMounts:
      - path: /data
```

---

## Common Issues and Solutions

### Issue: Pod Not Starting
**Symptoms:** Pod stuck in `Pending` or `CrashLoopBackOff`

**Solutions:**
1. Check pod logs: `kubectl logs -n <namespace> <pod-name>`
2. Describe pod: `kubectl describe pod -n <namespace> <pod-name>`
3. Verify image exists and is accessible
4. Check resource requests/limits
5. Verify persistent volume claims exist

### Issue: Service Not Accessible
**Symptoms:** Cannot reach application via service

**Solutions:**
1. Verify service exists: `kubectl get svc -n <namespace>`
2. Check service endpoints: `kubectl get endpoints -n <namespace>`
3. Verify pod labels match service selector
4. Check network policies
5. Test from within cluster: `kubectl run -it --rm debug --image=busybox -- wget -O- http://service-name:port`

### Issue: Ingress Not Working
**Symptoms:** Cannot access application via domain

**Solutions:**
1. Verify ingress exists: `kubectl get ingress -n <namespace>`
2. Check ingress class: `kubectl describe ingress -n <namespace> <ingress-name>`
3. Verify DNS resolution
4. Check certificate if using TLS
5. Review ingress controller logs

### Issue: Persistent Data Lost
**Symptoms:** Application data missing after upgrade

**Solutions:**
1. Check PVC status: `kubectl get pvc -n <namespace>`
2. Verify PVC is bound: `kubectl describe pvc -n <namespace> <pvc-name>`
3. Check mount paths in pod spec
4. Verify storage class exists
5. Review volume claim templates

### Issue: Configuration Not Applied
**Symptoms:** Changes not taking effect

**Solutions:**
1. Force Flux reconciliation: `flux reconcile helmrelease -n <namespace> <release-name>`
2. Check Flux logs: `kubectl logs -n flux-system deployment/helm-controller`
3. Verify HelmRelease status: `kubectl get helmrelease -n <namespace>`
4. Check for validation errors in HelmRelease
5. Manually trigger helm upgrade if needed

---

## Useful Commands

### Monitoring

```bash
# Watch all helm releases
flux get helmreleases -A --watch

# Check specific release
flux get helmrelease -n <namespace> <release-name>

# View release history
helm history -n <namespace> <release-name>

# Get pod status
kubectl get pods -n <namespace>

# Watch pod status
kubectl get pods -n <namespace> -w

# Check pod logs
kubectl logs -n <namespace> <pod-name>

# Follow pod logs
kubectl logs -n <namespace> <pod-name> -f

# Describe pod for events
kubectl describe pod -n <namespace> <pod-name>
```

### Debugging

```bash
# Get all resources in namespace
kubectl get all -n <namespace>

# Check events
kubectl get events -n <namespace> --sort-by='.lastTimestamp'

# Execute command in pod
kubectl exec -n <namespace> <pod-name> -- <command>

# Get shell in pod
kubectl exec -it -n <namespace> <pod-name> -- /bin/sh

# Port forward to pod
kubectl port-forward -n <namespace> <pod-name> 8080:8080

# Check resource usage
kubectl top pods -n <namespace>
```

### Flux Operations

```bash
# Reconcile git source
flux reconcile source git flux-system

# Reconcile specific helmrelease
flux reconcile helmrelease -n <namespace> <release-name>

# Suspend reconciliation
flux suspend helmrelease -n <namespace> <release-name>

# Resume reconciliation
flux resume helmrelease -n <namespace> <release-name>

# Export helmrelease
flux export helmrelease -n <namespace> <release-name>
```

### Rollback

```bash
# Rollback via git
git revert <commit-hash>
git push

# Force Flux sync
flux reconcile source git flux-system

# Manual helm rollback (if needed)
helm rollback -n <namespace> <release-name> <revision>
```

---

## Validation Scripts

### Check All App-Template Versions
```bash
./scripts/validate-app-template-v4-upgrades.sh
```

### Analyze Version Distribution
```bash
./scripts/analyze-app-template-versions.sh
```

### Quick Version Check
```bash
./scripts/analyze-app-template-simple.sh
```

---

## Configuration Examples

### Stateless Application
```yaml
controllers:
  app:
    containers:
      app:
        image:
          repository: nginx
          tag: alpine

service:
  app:
    ports:
      http:
        port: 80

ingress:
  app:
    className: internal
    hosts:
      - host: app.example.com
        paths:
          - path: /
            service:
              identifier: app
              port: http
```

### Stateful Application
```yaml
controllers:
  app:
    containers:
      app:
        image:
          repository: postgres
          tag: "16"
        env:
          POSTGRES_DB: mydb
          POSTGRES_USER: user
          POSTGRES_PASSWORD:
            valueFrom:
              secretKeyRef:
                name: postgres-secret
                key: password

service:
  app:
    ports:
      postgres:
        port: 5432

persistence:
  data:
    type: persistentVolumeClaim
    existingClaim: postgres-data
    globalMounts:
      - path: /var/lib/postgresql/data
```

### Application with Init Container
```yaml
controllers:
  app:
    initContainers:
      init:
        image:
          repository: busybox
          tag: latest
        command:
          - sh
          - -c
          - "echo 'Initializing...'"
    
    containers:
      app:
        image:
          repository: myapp/image
          tag: latest
```

### Application with Sidecar
```yaml
controllers:
  app:
    containers:
      app:
        image:
          repository: myapp/image
          tag: latest
      
      sidecar:
        image:
          repository: sidecar/image
          tag: latest
```

---

## Best Practices

### Configuration
1. ✅ Use explicit image tags (avoid `latest`)
2. ✅ Set resource requests and limits
3. ✅ Use secrets for sensitive data
4. ✅ Enable probes for health checks
5. ✅ Use persistent volumes for stateful apps

### Deployment
1. ✅ Test in non-production first
2. ✅ Deploy in phases (canary → full)
3. ✅ Monitor after deployment
4. ✅ Have rollback plan ready
5. ✅ Document changes

### Monitoring
1. ✅ Check pod status regularly
2. ✅ Review logs for errors
3. ✅ Monitor resource usage
4. ✅ Set up alerts for failures
5. ✅ Track application metrics

---

## Troubleshooting Flowchart

```
Issue Detected
    ↓
Check Pod Status
    ↓
Pod Running? ─No→ Check Events/Logs → Fix Image/Config
    ↓ Yes
Check Service
    ↓
Service OK? ─No→ Check Endpoints → Fix Service Config
    ↓ Yes
Check Ingress
    ↓
Ingress OK? ─No→ Check DNS/TLS → Fix Ingress Config
    ↓ Yes
Check Application
    ↓
App Working? ─No→ Check App Logs → Fix App Config
    ↓ Yes
✅ Issue Resolved
```

---

## Quick Links

### Documentation
- [Full Summary Report](./app-template-v4-upgrade-final-summary.md)
- [Upgrade Strategy](./app-template-v4-upgrade-strategy.md)
- [Phase 1 Report](./phase1-canary-upgrade-report.md)
- [Complete Upgrade Report](./app-template-v4-upgrade-complete.md)

### Scripts
- [Upgrade Script](../hack/app-template-upgrade-v4.py)
- [Validation Script](../scripts/validate-app-template-v4-upgrades.sh)
- [Analysis Script](../scripts/analyze-app-template-versions.sh)

### External Resources
- [bjw-s app-template Docs](https://bjw-s.github.io/helm-charts/docs/app-template/)
- [bjw-s GitHub](https://github.com/bjw-s/helm-charts)
- [Flux Documentation](https://fluxcd.io/docs/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)

---

## Support

### Getting Help
1. Check this quick reference
2. Review full documentation
3. Check application logs
4. Search GitHub issues
5. Ask in community channels

### Reporting Issues
Include:
- Application name and namespace
- Chart version
- Error messages
- Pod/service/ingress status
- Relevant logs
- Steps to reproduce

---

**Last Updated:** November 9, 2025  
**Chart Version:** 4.3.0  
**Status:** Production Ready