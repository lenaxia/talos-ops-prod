# MariaDB Operator Troubleshooting

## Issue: Operator CRD Error on Startup

### Symptom
```
{"level":"error","ts":1762675373.9216065,"logger":"setup","msg":"Unable to create controller","controller":"MariaDB","error":"error watching '.spec.myCnfConfigMapKeyRef.name': error indexing '.spec.myCnfConfigMapKeyRef.name' field: no matches for kind \"MariaDB\" in version \"k8s.mariadb.com/v1alpha1\""}
```

### Root Cause
The operator is trying to set up watchers for MariaDB CRDs before they are fully registered with the Kubernetes API server. This is a timing issue during initial installation.

### Solution Applied
1. Disabled webhook (which requires cert-manager and can cause startup delays)
2. Explicitly enabled CRDs in values
3. Added `createNamespace: true` to ensure namespace exists

### Fix Committed
```bash
git commit 1ba548a "fix(mariadb-operator): disable webhook and ensure CRDs are enabled"
```

### To Apply the Fix

```bash
# Pull the latest changes
git pull

# Force Flux to reconcile
flux reconcile kustomization cluster-databases-mariadb-operator --with-source

# Or delete the helm release to force reinstall
kubectl delete helmrelease mariadb-operator -n databases

# Wait for Flux to recreate it
kubectl wait --for=condition=ready helmrelease/mariadb-operator -n databases --timeout=5m
```

### Verification

After applying the fix, verify the operator starts correctly:

```bash
# Check operator pod logs
kubectl logs -n databases -l app.kubernetes.io/name=mariadb-operator --tail=50

# Should see successful startup without CRD errors
# Look for:
# - "Starting manager"
# - "Starting workers"
# - No error messages about missing CRDs
```

### Check CRDs are Installed

```bash
# List MariaDB CRDs
kubectl get crds | grep mariadb

# Should see:
# backups.k8s.mariadb.com
# connections.k8s.mariadb.com
# databases.k8s.mariadb.com
# grants.k8s.mariadb.com
# mariadbs.k8s.mariadb.com
# maxscales.k8s.mariadb.com
# restores.k8s.mariadb.com
# sqljobs.k8s.mariadb.com
# users.k8s.mariadb.com
```

### Alternative: Manual CRD Installation

If the issue persists, you can manually install CRDs first:

```bash
# Download and apply CRDs from the operator repository
kubectl apply -f https://raw.githubusercontent.com/mariadb-operator/mariadb-operator/main/config/crd/bases/k8s.mariadb.com_mariadbs.yaml
kubectl apply -f https://raw.githubusercontent.com/mariadb-operator/mariadb-operator/main/config/crd/bases/k8s.mariadb.com_backups.yaml
kubectl apply -f https://raw.githubusercontent.com/mariadb-operator/mariadb-operator/main/config/crd/bases/k8s.mariadb.com_databases.yaml
kubectl apply -f https://raw.githubusercontent.com/mariadb-operator/mariadb-operator/main/config/crd/bases/k8s.mariadb.com_users.yaml
kubectl apply -f https://raw.githubusercontent.com/mariadb-operator/mariadb-operator/main/config/crd/bases/k8s.mariadb.com_grants.yaml
kubectl apply -f https://raw.githubusercontent.com/mariadb-operator/mariadb-operator/main/config/crd/bases/k8s.mariadb.com_restores.yaml
kubectl apply -f https://raw.githubusercontent.com/mariadb-operator/mariadb-operator/main/config/crd/bases/k8s.mariadb.com_connections.yaml
kubectl apply -f https://raw.githubusercontent.com/mariadb-operator/mariadb-operator/main/config/crd/bases/k8s.mariadb.com_maxscales.yaml
kubectl apply -f https://raw.githubusercontent.com/mariadb-operator/mariadb-operator/main/config/crd/bases/k8s.mariadb.com_sqljobs.yaml

# Then restart the operator
kubectl rollout restart deployment mariadb-operator -n databases
```

## Next Steps After Fix

Once the operator is running successfully:

1. **Verify Operator Health**
   ```bash
   kubectl get pods -n databases -l app.kubernetes.io/name=mariadb-operator
   kubectl logs -n databases -l app.kubernetes.io/name=mariadb-operator
   ```

2. **Check MariaDB Instance Deployment**
   ```bash
   # The instances kustomization should deploy automatically
   kubectl get kustomization -n flux-system | grep mariadb-instances
   
   # Check MariaDB CRD
   kubectl get mariadb -n databases
   
   # Check pods
   kubectl get pods -n databases -l app.kubernetes.io/instance=mariadb
   ```

3. **Monitor Galera Cluster Formation**
   ```bash
   # Wait for all 3 pods to be ready
   kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=mariadb -n databases --timeout=10m
   
   # Check cluster status
   kubectl exec -n databases mariadb-0 -- \
     mysql -u root -p$(kubectl get secret -n databases mariadb-operator-secret -o jsonpath='{.data.root-password}' | base64 -d) \
     -e "SHOW STATUS LIKE 'wsrep_cluster_size';"
   ```

4. **Proceed with Migration**
   Once the cluster is healthy, run the migration script:
   ```bash
   ./scripts/mariadb-operator-migration.sh
   ```

## Common Issues

### Issue: Pods Stuck in Init

**Symptom**: MariaDB pods stuck in Init:0/1 or Init:1/2

**Check**:
```bash
kubectl describe pod mariadb-0 -n databases
kubectl logs mariadb-0 -n databases -c init
```

**Common Causes**:
- Storage class not available
- PVC not binding
- Init container image pull issues

### Issue: Galera Cluster Not Forming

**Symptom**: Pods running but cluster size is 1 or 0

**Check**:
```bash
kubectl exec -n databases mariadb-0 -- \
  mysql -u root -p<password> \
  -e "SHOW STATUS LIKE 'wsrep_%';" | grep -E "cluster_size|cluster_status|ready"
```

**Solution**:
```bash
# Force bootstrap from mariadb-0
kubectl annotate mariadb mariadb k8s.mariadb.com/galera-bootstrap=mariadb-0 -n databases
```

### Issue: Secret Not Found

**Symptom**: Pods failing with "secret not found" errors

**Check**:
```bash
kubectl get secret mariadb-operator-secret -n databases
kubectl get secret mariadb-operator-s3-secret -n databases
```

**Solution**: Ensure secrets are properly encrypted and deployed

## Rollback if Needed

If the operator continues to have issues:

```bash
# Disable operator
kubectl scale deployment mariadb-operator -n databases --replicas=0

# Or remove from Flux
# Edit kubernetes/apps/databases/kustomization.yaml
# Comment out: # - ./mariadb-operator/ks.yaml

# Old MariaDB should still be running
kubectl get pods -n databases | grep mariadb
```

## References

- [MariaDB Operator Issues](https://github.com/mariadb-operator/mariadb-operator/issues)
- [Migration Steps](./mariadb-operator-migration-steps.md)
- [Setup Summary](./mariadb-operator-setup-summary.md)