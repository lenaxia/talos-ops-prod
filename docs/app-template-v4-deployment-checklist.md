# App-Template v4.3.0 Deployment Validation Checklist

Use this checklist to validate the deployment of app-template v4.3.0 upgrades.

---

## Pre-Deployment Validation

### Code Review
- [x] All 33 helm releases upgraded to v4.3.0
- [x] YAML syntax validated (0 errors)
- [x] Git commits reviewed (be68f3a, 8985628)
- [x] Documentation complete
- [ ] Changes reviewed by team (if applicable)

### Backup Verification
- [ ] Persistent volume snapshots created (if applicable)
- [ ] Configuration backups available
- [ ] Rollback procedure documented and understood
- [ ] Recovery time objectives (RTO) defined

### Environment Check
- [ ] Flux is running and healthy
- [ ] Cluster has sufficient resources
- [ ] Network policies reviewed
- [ ] Storage classes available

---

## Deployment Phase

### Initial Deployment
- [ ] Push changes to git repository
- [ ] Verify Flux detects changes
  ```bash
  flux get sources git
  ```
- [ ] Monitor Flux reconciliation
  ```bash
  flux get helmreleases -A --watch
  ```

### Phase 1: Canary Applications (3 apps)
Monitor these low-risk applications first:

#### imaginary (media)
- [ ] Pod status: `kubectl get pods -n media -l app.kubernetes.io/name=imaginary`
- [ ] Pod logs: `kubectl logs -n media -l app.kubernetes.io/name=imaginary`
- [ ] Service accessible: `kubectl get svc -n media imaginary`
- [ ] Ingress working (if applicable)
- [ ] Application functional

#### browserless (home)
- [ ] Pod status: `kubectl get pods -n home -l app.kubernetes.io/name=browserless`
- [ ] Pod logs: `kubectl logs -n home -l app.kubernetes.io/name=browserless`
- [ ] Service accessible: `kubectl get svc -n home browserless`
- [ ] Ingress working (if applicable)
- [ ] Application functional

#### redlib (home)
- [ ] Pod status: `kubectl get pods -n home -l app.kubernetes.io/name=redlib`
- [ ] Pod logs: `kubectl logs -n home -l app.kubernetes.io/name=redlib`
- [ ] Service accessible: `kubectl get svc -n home redlib`
- [ ] Ingress working (if applicable)
- [ ] Application functional

**Canary Phase Decision:**
- [ ] All canary apps healthy (proceed to Phase 2)
- [ ] Issues detected (investigate and fix before proceeding)

---

### Phase 2: Stateless Applications (15 apps)

#### Media Applications (7 apps)
- [ ] bazarr - Pod running, logs clean, service accessible
- [ ] tautulli - Pod running, logs clean, service accessible
- [ ] plexmetamanager - Pod running, logs clean, service accessible
- [ ] ersatztv - Pod running, logs clean, service accessible
- [ ] komga - Pod running, logs clean, service accessible
- [ ] fmd2 - Pod running, logs clean, service accessible
- [ ] metube - Pod running, logs clean, service accessible

#### Networking Applications (2 apps)
- [ ] webfinger - Pod running, logs clean, service accessible
- [ ] cloudflare-ddns - Pod running, logs clean, DNS updates working

#### Utilities Applications (6 apps)
- [ ] uptimekuma - Pod running, logs clean, monitoring functional
- [ ] librespeed - Pod running, logs clean, speed test working
- [ ] changedetection - Pod running, logs clean, monitoring active
- [ ] brother-ql-web - Pod running, logs clean, printer accessible
- [ ] openldap - Pod running, logs clean, LDAP queries working
- [ ] vaultwarden-ldap - Pod running, logs clean, sync working

**Phase 2 Validation:**
```bash
# Check all Phase 2 pods
kubectl get pods -n media | grep -E "(bazarr|tautulli|plexmetamanager|ersatztv|komga|fmd2|metube)"
kubectl get pods -n networking | grep -E "(webfinger|cloudflare-ddns)"
kubectl get pods -n utilities | grep -E "(uptimekuma|librespeed|changedetection|brother-ql-web|openldap|vaultwarden-ldap)"
```

---

### Phase 3: Stateful Applications (9 apps)

#### Home Applications (4 apps)
- [ ] esphome - Pod running, config intact, devices accessible
- [ ] frigate - Pod running, recordings intact, cameras working
- [ ] mosquitto - Pod running, MQTT working, clients connected
- [ ] stirling-pdf - Pod running, PDFs accessible, processing working

#### Media Applications (2 apps)
- [ ] jellyfin - Pod running, media library intact, playback working
- [ ] plex - Pod running, media library intact, playback working

#### Storage Applications (1 app)
- [ ] minio - Pod running, buckets accessible, data intact

#### Utilities Applications (2 apps)
- [ ] pgadmin - Pod running, database connections working
- [ ] guacamole - Pod running, remote connections working

**Phase 3 Critical Checks:**
```bash
# Verify persistent volumes
kubectl get pvc -n home | grep -E "(esphome|frigate|mosquitto|stirling-pdf)"
kubectl get pvc -n media | grep -E "(jellyfin|plex)"
kubectl get pvc -n storage | grep minio
kubectl get pvc -n utilities | grep -E "(pgadmin|guacamole)"

# Check volume mounts
kubectl describe pod -n home <pod-name> | grep -A 5 "Mounts:"
```

---

### Phase 4: Critical Applications (6 apps)

#### Database Applications (1 app)
- [ ] redis - Pod running, connections working, data intact
  ```bash
  kubectl exec -n databases deployment/redis -- redis-cli ping
  ```

#### Home Applications (4 apps)
- [ ] monica - Pod running, contacts accessible, data intact
- [ ] fasten - Pod running, health records accessible
- [ ] linkwarden - Pod running, bookmarks accessible
- [ ] stablediffusion - Pod running, generation working

#### Ragnarok Applications (1 app)
- [ ] roskills - Pod running, game data accessible

**Phase 4 Critical Validation:**
```bash
# Test redis connectivity
kubectl run -it --rm redis-test --image=redis:alpine --restart=Never -- redis-cli -h redis.databases.svc.cluster.local ping

# Check critical app health
kubectl get pods -n databases -l app.kubernetes.io/name=redis
kubectl get pods -n home | grep -E "(monica|fasten|linkwarden|stablediffusion)"
kubectl get pods -n ragnarok -l app.kubernetes.io/name=roskills
```

---

### Phase 5: Special Cases (1 app)

#### magicmirror (v2→v4 direct upgrade)
- [ ] Pod running (check for any v2→v4 compatibility issues)
- [ ] Configuration loaded correctly
- [ ] Modules working
- [ ] Display rendering correctly
- [ ] No errors in logs

**Special Validation:**
```bash
kubectl logs -n home deployment/magicmirror --tail=100
kubectl describe pod -n home -l app.kubernetes.io/name=magicmirror
```

---

## Post-Deployment Validation

### System Health (Day 1)
- [ ] All 33 pods running and healthy
- [ ] No CrashLoopBackOff or Error states
- [ ] No excessive restarts
- [ ] Resource usage normal
- [ ] No OOM kills

### Application Functionality (Day 1-2)
- [ ] All ingress routes accessible
- [ ] Authentication working
- [ ] Data persistence verified
- [ ] Inter-service communication working
- [ ] External integrations functional

### Monitoring (Day 2-7)
- [ ] No error spikes in logs
- [ ] Response times normal
- [ ] Resource usage stable
- [ ] No memory leaks detected
- [ ] No performance degradation

### User Validation (Day 3-7)
- [ ] No user-reported issues
- [ ] All features working as expected
- [ ] Performance acceptable
- [ ] Data integrity confirmed

---

## Validation Commands

### Quick Health Check
```bash
# All app-template releases
flux get helmreleases -A | grep -E "(imaginary|browserless|redlib|bazarr|tautulli|plexmetamanager|ersatztv|komga|fmd2|metube|webfinger|cloudflare-ddns|uptimekuma|librespeed|changedetection|brother-ql-web|openldap|vaultwarden-ldap|esphome|frigate|mosquitto|stirling-pdf|jellyfin|plex|minio|pgadmin|guacamole|redis|monica|fasten|linkwarden|stablediffusion|roskills|magicmirror)"

# Pod status
kubectl get pods -A | grep -E "(imaginary|browserless|redlib|bazarr|tautulli|plexmetamanager|ersatztv|komga|fmd2|metube|webfinger|cloudflare-ddns|uptimekuma|librespeed|changedetection|brother-ql-web|openldap|vaultwarden-ldap|esphome|frigate|mosquitto|stirling-pdf|jellyfin|plex|minio|pgadmin|guacamole|redis|monica|fasten|linkwarden|stablediffusion|roskills|magicmirror)"

# Check for issues
kubectl get pods -A | grep -v "Running\|Completed"
```

### Detailed Health Check
```bash
# Check events for errors
kubectl get events -A --sort-by='.lastTimestamp' | grep -i error | tail -20

# Check pod restarts
kubectl get pods -A --sort-by='.status.containerStatuses[0].restartCount' | tail -20

# Check resource usage
kubectl top pods -A | grep -E "(imaginary|browserless|redlib|bazarr|tautulli|plexmetamanager|ersatztv|komga|fmd2|metube|webfinger|cloudflare-ddns|uptimekuma|librespeed|changedetection|brother-ql-web|openldap|vaultwarden-ldap|esphome|frigate|mosquitto|stirling-pdf|jellyfin|plex|minio|pgadmin|guacamole|redis|monica|fasten|linkwarden|stablediffusion|roskills|magicmirror)"
```

### Persistence Validation
```bash
# Check all PVCs
kubectl get pvc -A

# Check PVC usage
kubectl exec -n <namespace> <pod-name> -- df -h

# Verify data integrity (example for jellyfin)
kubectl exec -n media deployment/jellyfin -- ls -lh /config
```

### Service Validation
```bash
# Check all services
kubectl get svc -A | grep -E "(imaginary|browserless|redlib|bazarr|tautulli|plexmetamanager|ersatztv|komga|fmd2|metube|webfinger|cloudflare-ddns|uptimekuma|librespeed|changedetection|brother-ql-web|openldap|vaultwarden-ldap|esphome|frigate|mosquitto|stirling-pdf|jellyfin|plex|minio|pgadmin|guacamole|redis|monica|fasten|linkwarden|stablediffusion|roskills|magicmirror)"

# Check service endpoints
kubectl get endpoints -A | grep -E "(imaginary|browserless|redlib|bazarr|tautulli|plexmetamanager|ersatztv|komga|fmd2|metube|webfinger|cloudflare-ddns|uptimekuma|librespeed|changedetection|brother-ql-web|openldap|vaultwarden-ldap|esphome|frigate|mosquitto|stirling-pdf|jellyfin|plex|minio|pgadmin|guacamole|redis|monica|fasten|linkwarden|stablediffusion|roskills|magicmirror)"
```

### Ingress Validation
```bash
# Check all ingress
kubectl get ingress -A

# Test ingress connectivity (from within cluster)
kubectl run -it --rm curl-test --image=curlimages/curl --restart=Never -- curl -I http://<service>.<namespace>.svc.cluster.local
```

---

## Issue Response

### If Issues Detected

#### Minor Issues (Non-Critical)
1. Document the issue
2. Check application logs
3. Review configuration
4. Apply fix if available
5. Monitor for 24 hours
6. Continue with deployment

#### Major Issues (Critical)
1. **STOP** further deployments
2. Document the issue thoroughly
3. Assess impact and scope
4. Consider rollback if:
   - Data loss risk
   - Service unavailable
   - Multiple applications affected
   - Security concerns
5. Implement fix or rollback
6. Re-validate before proceeding

### Rollback Triggers
Initiate rollback if:
- [ ] Critical application unavailable >15 minutes
- [ ] Data corruption detected
- [ ] Multiple applications failing
- [ ] Security vulnerability introduced
- [ ] Performance degradation >50%
- [ ] Persistent volume issues

---

## Sign-Off

### Phase Completion
- [ ] Phase 1 (Canary) - Completed: ___/___/___ by: _______
- [ ] Phase 2 (Stateless) - Completed: ___/___/___ by: _______
- [ ] Phase 3 (Stateful) - Completed: ___/___/___ by: _______
- [ ] Phase 4 (Critical) - Completed: ___/___/___ by: _______
- [ ] Phase 5 (Special) - Completed: ___/___/___ by: _______

### Final Validation
- [ ] All 33 applications healthy
- [ ] No outstanding issues
- [ ] Monitoring in place
- [ ] Documentation updated
- [ ] Team notified

### Deployment Sign-Off
- [ ] Deployment successful
- [ ] All validation passed
- [ ] Ready for production use

**Signed:** _________________ **Date:** ___/___/___

---

## Notes

### Issues Encountered
```
Document any issues encountered during deployment:

Issue #1:
- Application: 
- Description: 
- Resolution: 
- Time to resolve: 

Issue #2:
- Application: 
- Description: 
- Resolution: 
- Time to resolve: 
```

### Observations
```
Document any observations or recommendations:

1. 

2. 

3. 
```

---

## References

- [Final Summary Report](./app-template-v4-upgrade-final-summary.md)
- [Quick Reference Guide](./app-template-v4-quick-reference.md)
- [Upgrade Strategy](./app-template-v4-upgrade-strategy.md)
- [Validation Script](../scripts/validate-app-template-v4-upgrades.sh)

---

**Checklist Version:** 1.0  
**Last Updated:** November 9, 2025  
**Chart Version:** 4.3.0