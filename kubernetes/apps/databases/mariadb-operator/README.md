# MariaDB Operator

This directory contains the MariaDB Operator deployment and MariaDB instance configurations.

## Structure

```
mariadb-operator/
├── ks.yaml                           # Flux Kustomizations (operator + instances)
├── operator/                         # Operator installation
│   ├── helm-release.yaml            # MariaDB Operator Helm chart
│   └── kustomization.yaml
└── instances/                        # MariaDB instances and resources
    ├── mariadb.yaml                 # MariaDB cluster (3-node Galera)
    ├── database.yaml                # Database CRD (ragnarok)
    ├── user.yaml                    # User CRD (ragnarok)
    ├── grant.yaml                   # Grant CRD (permissions)
    ├── backup.yaml                  # Backup CRD (S3/Minio)
    ├── secret.sops.yaml             # Encrypted secrets
    └── kustomization.yaml
```

## Features

### High Availability
- 3-node Galera cluster for automatic failover
- Pod anti-affinity to spread across nodes
- Automatic recovery and bootstrapping
- PodDisruptionBudget for safe maintenance

### Backup & Recovery
- Daily automated backups to S3/Minio
- 30-day retention policy
- Compressed backups with gzip
- Point-in-time recovery support

### Monitoring
- Prometheus metrics via mysqld-exporter
- ServiceMonitor for automatic scraping
- Galera cluster health monitoring

### Storage
- Longhorn persistent storage
- 10Gi data volume per node
- Automatic volume resizing support

## Services

The MariaDB operator creates multiple services:

- `mariadb`: LoadBalancer service (external access)
- `mariadb-primary`: ClusterIP service (primary node)
- `mariadb-secondary`: ClusterIP service (read replicas)
- `mariadb-internal`: Headless service (cluster communication)

## Connection Secrets

The operator automatically creates connection secrets:

- `mariadb-operator-connection`: General connection DSN
- `mariadb-operator-primary-connection`: Primary node connection
- `mariadb-operator-secondary-connection`: Secondary nodes connection

## Configuration

### Secrets Required

Before deploying, encrypt and configure these secrets in `instances/secret.sops.yaml`:

```yaml
mariadb-operator-secret:
  root-password: <root password>
  user-password: <ragnarok user password>

mariadb-operator-s3-secret:
  access-key-id: <minio access key>
  secret-access-key: <minio secret key>
```

### Environment Variables

Set these in your cluster configuration:

- `SVC_MARIADB_ADDR`: LoadBalancer IP for MariaDB service
- `SECRET_DEV_DOMAIN`: Domain for DNS registration
- `S3_MARIADB_BACKUP`: S3 bucket name for backups

## Deployment

The deployment happens in two phases via Flux:

1. **Operator Phase**: Installs the MariaDB operator
   - Depends on: Longhorn, Minio
   - Path: `./kubernetes/apps/databases/mariadb-operator/operator`

2. **Instances Phase**: Deploys MariaDB cluster and resources
   - Depends on: MariaDB operator
   - Path: `./kubernetes/apps/databases/mariadb-operator/instances`

## Migration from Bitnami MariaDB

See the [Migration Plan](../../../docs/mariadb-operator-migration-plan.md) for detailed migration steps.

### Quick Migration Steps

1. Backup current MariaDB data:
   ```bash
   kubectl exec -n databases mariadb-0 -- \
     mysqldump -u root -p<password> --all-databases > backup.sql
   ```

2. Deploy operator (already done via Flux)

3. Update secrets with current passwords

4. Deploy MariaDB instance (will create empty cluster)

5. Restore data:
   ```bash
   kubectl exec -n databases mariadb-0 -- \
     mysql -u root -p<password> < backup.sql
   ```

6. Update dependent applications to use new service

7. Remove old MariaDB deployment

## Maintenance

### Manual Backup

Create a one-time backup:

```yaml
apiVersion: k8s.mariadb.com/v1alpha1
kind: Backup
metadata:
  name: mariadb-manual-backup
  namespace: databases
spec:
  mariaDbRef:
    name: mariadb
  storage:
    s3:
      bucket: ${S3_MARIADB_BACKUP}
      endpoint: minio.storage.svc.cluster.local:9000
      prefix: mariadb/manual/
```

### Restore from Backup

```yaml
apiVersion: k8s.mariadb.com/v1alpha1
kind: Restore
metadata:
  name: mariadb-restore
  namespace: databases
spec:
  mariaDbRef:
    name: mariadb
  backupRef:
    name: mariadb-backup
```

### Scale Cluster

Edit `mariadb.yaml` and change `replicas`:

```yaml
spec:
  replicas: 5  # Scale to 5 nodes
```

### Check Cluster Status

```bash
# Check MariaDB pods
kubectl get pods -n databases -l app.kubernetes.io/instance=mariadb

# Check Galera cluster status
kubectl exec -n databases mariadb-0 -- \
  mysql -u root -p<password> -e "SHOW STATUS LIKE 'wsrep_%';"

# Check backups
kubectl get backups -n databases
```

## Troubleshooting

### Cluster Won't Bootstrap

If the Galera cluster fails to bootstrap:

```bash
# Check logs
kubectl logs -n databases mariadb-0

# Force bootstrap from specific node
kubectl annotate mariadb mariadb \
  k8s.mariadb.com/galera-bootstrap=mariadb-0
```

### Backup Failures

Check backup job logs:

```bash
kubectl get jobs -n databases
kubectl logs -n databases job/mariadb-backup-<timestamp>
```

### Connection Issues

Verify services and endpoints:

```bash
kubectl get svc -n databases
kubectl get endpoints -n databases
```

## References

- [MariaDB Operator Documentation](https://github.com/mariadb-operator/mariadb-operator)
- [Galera Cluster Documentation](https://galeracluster.com/library/documentation/)
- [Migration Plan](../../../docs/mariadb-operator-migration-plan.md)