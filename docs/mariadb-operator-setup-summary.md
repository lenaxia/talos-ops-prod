# MariaDB Operator Setup Summary

## Completed Tasks

### 1. Analysis Phase ✅
- Analyzed current Bitnami MariaDB setup (standalone, 5Gi storage)
- Identified dependent applications: ragnarok (classic + renewal), hercules (classic + renewal)
- Reviewed CloudNative-PG operator pattern for reference
- Documented current architecture and dependencies

### 2. Helm Repository ✅
Created [`kubernetes/flux/repositories/helm/mariadb-operator-charts.yaml`](../kubernetes/flux/repositories/helm/mariadb-operator-charts.yaml)
- Repository URL: https://mariadb-operator.github.io/mariadb-operator
- Added to helm repository kustomization

### 3. Operator Deployment ✅
Created [`kubernetes/apps/databases/mariadb-operator/operator/`](../kubernetes/apps/databases/mariadb-operator/operator/)
- `helm-release.yaml`: MariaDB Operator v0.35.0 with HA, metrics, webhooks
- `kustomization.yaml`: Operator kustomization

### 4. MariaDB Instance Configuration ✅
Created [`kubernetes/apps/databases/mariadb-operator/instances/`](../kubernetes/apps/databases/mariadb-operator/instances/)
- `mariadb.yaml`: 3-node Galera cluster, 10Gi storage, LoadBalancer service
- `database.yaml`: ragnarok database with UTF8MB4
- `user.yaml`: ragnarok user with 100 max connections
- `grant.yaml`: ALL PRIVILEGES on ragnarok database
- `backup.yaml`: Daily S3/Minio backups with 30-day retention
- `secret.sops.yaml`: Template for encrypted secrets
- `kustomization.yaml`: Instance resources kustomization

### 5. Flux Integration ✅
Created [`kubernetes/apps/databases/mariadb-operator/ks.yaml`](../kubernetes/apps/databases/mariadb-operator/ks.yaml)
- Two-phase deployment: operator → instances
- Health checks and dependencies configured

### 6. Documentation ✅
- [`kubernetes/apps/databases/mariadb-operator/README.md`](../kubernetes/apps/databases/mariadb-operator/README.md): Comprehensive operator guide
- [`docs/mariadb-operator-migration-plan.md`](./mariadb-operator-migration-plan.md): Detailed migration strategy

## Architecture

### New Setup (MariaDB Operator)
- **Cluster**: 3-node Galera cluster for HA
- **Storage**: 10Gi Longhorn per node (30Gi total)
- **Backup**: Daily automated backups to Minio with 30-day retention
- **Monitoring**: Prometheus metrics via ServiceMonitor
- **Failover**: Automatic with Galera cluster recovery

### Services Created
- `mariadb`: LoadBalancer (external access)
- `mariadb-primary`: ClusterIP (primary node)
- `mariadb-secondary`: ClusterIP (read replicas)
- `mariadb-internal`: Headless (cluster communication)

## Next Steps (Manual Actions Required)

### 1. Encrypt Secrets
```bash
# Edit secret.sops.yaml with actual passwords
# Encrypt with SOPS
sops -e -i kubernetes/apps/databases/mariadb-operator/instances/secret.sops.yaml
```

### 2. Enable in Flux
Add to `kubernetes/apps/databases/kustomization.yaml`:
```yaml
resources:
  - ./mariadb-operator/ks.yaml
```

### 3. Backup Current Data
```bash
kubectl exec -n databases mariadb-0 -- \
  mysqldump -u root -p<password> --all-databases > backup.sql
```

### 4. Deploy and Migrate
- Wait for operator deployment
- Wait for MariaDB cluster ready
- Restore data to new cluster
- Update dependent applications
- Test connectivity
- Remove old deployment

## Important Notes

⚠️ **NOT YET ENABLED** - The operator configuration is ready but not active in the cluster.

🔒 **Secrets Required** - Must encrypt secrets before deployment.

📊 **Monitoring** - ServiceMonitor requires Prometheus Operator.

🔄 **Migration** - Plan for 15-30 minute downtime window.

## Files Created

```
kubernetes/
├── flux/repositories/helm/
│   ├── mariadb-operator-charts.yaml (new)
│   └── kustomization.yaml (modified)
└── apps/databases/mariadb-operator/
    ├── ks.yaml
    ├── README.md
    ├── operator/
    │   ├── helm-release.yaml
    │   └── kustomization.yaml
    └── instances/
        ├── mariadb.yaml
        ├── database.yaml
        ├── user.yaml
        ├── grant.yaml
        ├── backup.yaml
        ├── secret.sops.yaml
        └── kustomization.yaml

docs/
├── mariadb-operator-migration-plan.md
└── mariadb-operator-setup-summary.md (this file)
```

## References

- [MariaDB Operator](https://github.com/mariadb-operator/mariadb-operator)
- [Migration Plan](./mariadb-operator-migration-plan.md)
- [Operator README](../kubernetes/apps/databases/mariadb-operator/README.md)