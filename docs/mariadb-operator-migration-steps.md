# MariaDB Operator Migration - Step-by-Step Guide

## Prerequisites

✅ Secrets encrypted and pushed to repository
✅ MariaDB operator enabled in Flux kustomization
✅ kubectl access to the cluster
✅ Backup storage available

## Migration Steps

### Step 1: Verify Operator Deployment

Wait for Flux to deploy the operator (usually 1-5 minutes after push):

```bash
# Check if operator kustomization exists
kubectl get kustomization -n flux-system | grep mariadb-operator

# Check operator helm release
kubectl get helmrelease -n databases mariadb-operator

# Wait for operator to be ready
kubectl wait --for=condition=ready helmrelease/mariadb-operator -n databases --timeout=5m

# Verify operator pod is running
kubectl get pods -n databases -l app.kubernetes.io/name=mariadb-operator
```

### Step 2: Verify MariaDB Instance Deployment

The operator should automatically create the MariaDB cluster:

```bash
# Check MariaDB CRD
kubectl get mariadb -n databases

# Check MariaDB pods (should see 3 pods for Galera cluster)
kubectl get pods -n databases -l app.kubernetes.io/instance=mariadb

# Wait for cluster to be ready
kubectl wait --for=condition=ready mariadb/mariadb -n databases --timeout=10m

# Check Galera cluster status
kubectl exec -n databases mariadb-0 -- \
  mysql -u root -p$(kubectl get secret -n databases mariadb-operator-secret -o jsonpath='{.data.root-password}' | base64 -d) \
  -e "SHOW STATUS LIKE 'wsrep_%';" | grep -E "wsrep_cluster_size|wsrep_cluster_status|wsrep_ready"
```

Expected output:
- `wsrep_cluster_size`: 3
- `wsrep_cluster_status`: Primary
- `wsrep_ready`: ON

### Step 3: Run Migration Script

Use the automated migration script:

```bash
cd /home/mikekao/personal/talos-ops-prod

# Run migration script
./scripts/mariadb-operator-migration.sh
```

The script will:
1. ✅ Check operator deployment
2. ✅ Backup current MariaDB data
3. ✅ Scale down dependent applications
4. ✅ Wait for new cluster to be ready
5. ✅ Restore data to new cluster
6. ✅ Verify data integrity
7. ✅ Test connectivity
8. ✅ Scale up applications

### Step 4: Manual Migration (Alternative)

If you prefer manual steps:

#### 4.1: Backup Current Data

```bash
# Create backup directory
mkdir -p ./mariadb-backups

# Get current root password
OLD_ROOT_PASSWORD=$(kubectl get secret -n databases mariadb-secret -o jsonpath='{.data.mariadb-root-password}' | base64 -d)

# Create full backup
kubectl exec -n databases mariadb-0 -- \
  mysqldump -u root -p"$OLD_ROOT_PASSWORD" \
  --all-databases \
  --single-transaction \
  --routines \
  --triggers \
  --events \
  --hex-blob \
  --skip-lock-tables \
  > ./mariadb-backups/mariadb-full-backup-$(date +%Y%m%d-%H%M%S).sql

# Compress backup
gzip ./mariadb-backups/mariadb-full-backup-*.sql
```

#### 4.2: Scale Down Applications

```bash
# Scale down ragnarok applications
kubectl scale deployment -n ragnarok --all --replicas=0

# Scale down hercules applications
kubectl scale deployment -n home --selector=app.kubernetes.io/name=hercules --replicas=0

# Wait for pods to terminate
sleep 10
```

#### 4.3: Restore Data

```bash
# Get new root password
NEW_ROOT_PASSWORD=$(kubectl get secret -n databases mariadb-operator-secret -o jsonpath='{.data.root-password}' | base64 -d)

# Restore data
gunzip -c ./mariadb-backups/mariadb-full-backup-*.sql.gz | \
  kubectl exec -i -n databases mariadb-0 -- \
  mysql -u root -p"$NEW_ROOT_PASSWORD"
```

#### 4.4: Verify Data

```bash
# Check databases
kubectl exec -n databases mariadb-0 -- \
  mysql -u root -p"$NEW_ROOT_PASSWORD" -e "SHOW DATABASES;"

# Check ragnarok database tables
kubectl exec -n databases mariadb-0 -- \
  mysql -u root -p"$NEW_ROOT_PASSWORD" -e "USE ragnarok; SHOW TABLES;"

# Verify Galera cluster
kubectl exec -n databases mariadb-0 -- \
  mysql -u root -p"$NEW_ROOT_PASSWORD" \
  -e "SHOW STATUS LIKE 'wsrep_%';" | grep -E "wsrep_cluster_size|wsrep_cluster_status|wsrep_ready"
```

#### 4.5: Scale Up Applications

```bash
# Scale up ragnarok applications
kubectl scale deployment -n ragnarok --all --replicas=1

# Scale up hercules applications
kubectl scale deployment -n home --selector=app.kubernetes.io/name=hercules --replicas=1
```

### Step 5: Verify Application Connectivity

Monitor application logs for database connections:

```bash
# Check ragnarok classic logs
kubectl logs -n ragnarok -l app.kubernetes.io/name=rathena-classic --tail=50

# Check ragnarok renewal logs
kubectl logs -n ragnarok -l app.kubernetes.io/name=rathena-renewal --tail=50

# Check hercules classic logs
kubectl logs -n home -l app.kubernetes.io/name=hercules-classic --tail=50

# Check hercules renewal logs
kubectl logs -n home -l app.kubernetes.io/name=hercules-renewal --tail=50
```

Look for successful database connections. If there are connection errors, check:
- Service endpoints: `kubectl get endpoints -n databases`
- Secret values: Ensure connection strings are correct
- Network policies: Verify pods can reach the database

### Step 6: Test Backup Functionality

```bash
# Check if backup CRD was created
kubectl get backup -n databases

# Manually trigger a backup to test
kubectl create -f - <<EOF
apiVersion: k8s.mariadb.com/v1alpha1
kind: Backup
metadata:
  name: mariadb-test-backup
  namespace: databases
spec:
  mariaDbRef:
    name: mariadb
  storage:
    persistentVolumeClaim:
      resources:
        requests:
          storage: 1Gi
      storageClassName: longhorn
      accessModes:
        - ReadWriteOnce
EOF

# Check backup status
kubectl get backup mariadb-test-backup -n databases -o yaml

# Check backup job
kubectl get jobs -n databases | grep backup
```

### Step 7: Update HAProxy Configuration (Optional)

If you're using the HAProxy load balancer, you may need to update it or remove it:

**Option A: Update HAProxy to point to new endpoints**

Edit `kubernetes/apps/databases/mariadb/lb/config/haproxy.cfg`:
```cfg
backend mariadb-primary
    balance first
    option mysql-check user haproxy_check
    server mariadb-0 mariadb-primary.databases.svc.cluster.local:3306 check
```

**Option B: Remove HAProxy (Recommended)**

The operator creates its own LoadBalancer service, so HAProxy may be redundant:

```bash
# Delete HAProxy deployment
kubectl delete helmrelease mariadb-lb -n databases

# Remove from git
git rm -r kubernetes/apps/databases/mariadb/lb/
git commit -m "feat(databases): remove mariadb haproxy lb (using operator service)"
```

### Step 8: Update Kyverno Secret Sync (Optional)

If applications need the new connection secrets, update the Kyverno policy:

Edit `kubernetes/apps/kyverno/policies/sync-mariadb-secrets.yaml`:

```yaml
---
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: sync-mariadb-operator-secrets
  namespace: kyverno
spec:
  mutateExistingOnPolicyUpdate: true
  rules:
    - name: sync-mariadb-operator-connection
      match:
        resources:
          kinds: ["Namespace"]
      exclude:
        resources:
          namespaces: ["databases"]
      generate:
        generateExisting: true
        apiVersion: v1
        kind: Secret
        name: mariadb-operator-connection
        namespace: "{{request.object.metadata.name}}"
        synchronize: true
        clone:
          namespace: databases
          name: mariadb-operator-connection
```

### Step 9: Monitor Cluster Health

```bash
# Check all MariaDB pods
kubectl get pods -n databases -l app.kubernetes.io/instance=mariadb

# Check services
kubectl get svc -n databases | grep mariadb

# Check Galera cluster status on all nodes
for i in 0 1 2; do
  echo "=== mariadb-$i ==="
  kubectl exec -n databases mariadb-$i -- \
    mysql -u root -p"$NEW_ROOT_PASSWORD" \
    -e "SHOW STATUS LIKE 'wsrep_cluster_size';"
done

# Check metrics
kubectl get servicemonitor -n databases | grep mariadb
```

### Step 10: Cleanup Old MariaDB

**⚠️ ONLY after verifying everything works for at least 24-48 hours!**

```bash
# Delete old MariaDB helm release
kubectl delete helmrelease mariadb -n databases

# Delete old PVC (after backing up!)
kubectl delete pvc mariadb-data-volume -n databases

# Remove from git
git rm -r kubernetes/apps/databases/mariadb/app/
git commit -m "feat(databases): remove old bitnami mariadb deployment"
```

## Troubleshooting

### Operator Not Deploying

```bash
# Check Flux kustomization status
kubectl describe kustomization cluster-databases-mariadb-operator -n flux-system

# Check helm repository
kubectl get helmrepository -n flux-system | grep mariadb

# Force reconciliation
flux reconcile kustomization cluster-databases-mariadb-operator
```

### MariaDB Cluster Not Starting

```bash
# Check MariaDB CRD status
kubectl describe mariadb mariadb -n databases

# Check pod logs
kubectl logs -n databases mariadb-0 -c mariadb
kubectl logs -n databases mariadb-0 -c agent

# Check events
kubectl get events -n databases --sort-by='.lastTimestamp' | grep mariadb
```

### Galera Cluster Split Brain

```bash
# Check cluster status on all nodes
for i in 0 1 2; do
  kubectl exec -n databases mariadb-$i -- \
    mysql -u root -p"$NEW_ROOT_PASSWORD" \
    -e "SHOW STATUS LIKE 'wsrep_%';" | grep -E "cluster_size|cluster_status|ready"
done

# Force bootstrap from mariadb-0
kubectl annotate mariadb mariadb k8s.mariadb.com/galera-bootstrap=mariadb-0 -n databases
```

### Data Restore Failed

```bash
# Check if backup file is valid
gunzip -t ./mariadb-backups/mariadb-full-backup-*.sql.gz

# Try restoring specific database
gunzip -c ./mariadb-backups/mariadb-full-backup-*.sql.gz | \
  grep -A 10000 "CREATE DATABASE.*ragnarok" | \
  kubectl exec -i -n databases mariadb-0 -- \
  mysql -u root -p"$NEW_ROOT_PASSWORD"
```

### Application Connection Issues

```bash
# Check service endpoints
kubectl get endpoints -n databases mariadb

# Test connection from application pod
kubectl exec -n ragnarok <pod-name> -- \
  mysql -h mariadb.databases.svc.cluster.local -u ragnarok -p"$USER_PASSWORD" -e "SELECT 1;"

# Check network policies
kubectl get networkpolicies -n databases
kubectl get networkpolicies -n ragnarok
```

## Rollback Procedure

If migration fails and you need to rollback:

```bash
# 1. Scale down applications
kubectl scale deployment -n ragnarok --all --replicas=0
kubectl scale deployment -n home --selector=app.kubernetes.io/name=hercules --replicas=0

# 2. Disable operator in Flux
# Remove ./mariadb-operator/ks.yaml from kubernetes/apps/databases/kustomization.yaml
git add kubernetes/apps/databases/kustomization.yaml
git commit -m "rollback: disable mariadb-operator"
git push

# 3. Wait for operator to be removed
kubectl delete mariadb mariadb -n databases
kubectl delete helmrelease mariadb-operator -n databases

# 4. Old MariaDB should still be running
kubectl get pods -n databases | grep mariadb

# 5. Scale up applications
kubectl scale deployment -n ragnarok --all --replicas=1
kubectl scale deployment -n home --selector=app.kubernetes.io/name=hercules --replicas=1
```

## Success Criteria

- ✅ Operator deployed and healthy
- ✅ 3-node Galera cluster running
- ✅ All data migrated successfully
- ✅ Applications connecting to new database
- ✅ Backups configured and tested
- ✅ Monitoring metrics available
- ✅ No errors in application logs
- ✅ Old MariaDB can be safely removed

## Post-Migration Tasks

1. Monitor cluster for 24-48 hours
2. Verify automated backups are running
3. Test restore procedure
4. Update documentation
5. Remove old MariaDB deployment
6. Update runbooks and procedures
7. Train team on new operator management

## References

- [Migration Script](../scripts/mariadb-operator-migration.sh)
- [Migration Plan](./mariadb-operator-migration-plan.md)
- [Operator README](../kubernetes/apps/databases/mariadb-operator/README.md)
- [MariaDB Operator Docs](https://github.com/mariadb-operator/mariadb-operator)