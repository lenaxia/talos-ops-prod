# MariaDB Operator Migration Plan

## Current Setup Analysis

### Existing MariaDB Configuration

**Location**: `kubernetes/apps/databases/mariadb/`

**Current Implementation**:
- **Helm Chart**: Bitnami MariaDB v23.2.4
- **Architecture**: Standalone (with secondary replicas configured but not actively used)
- **Storage**: 5Gi Longhorn PVC (`mariadb-data-volume`)
- **Database**: `ragnarok`
- **User**: `ragnarok`
- **Secrets**: `mariadb-secret` (contains root password, replication password, user password, IP, port)

**Network Configuration**:
- Primary service: LoadBalancer with IP `${SVC_MARIADB_PRIMARY_ADDR}`
- Load balancer: HAProxy-based LB at `${SVC_MARIADB_ADDR}` (port 3306)
- HAProxy backend: `mariadb-0.mariadb.databases.svc.cluster.local`
- Metrics: Enabled with ServiceMonitor

**Secondary Replicas** (Currently Configured):
- Count: 3
- Storage: openebs-hostpath
- Note: Architecture is set to "standalone" so replicas may not be active

### Dependent Applications

1. **Ragnarok rAthena** (2 instances):
   - Classic: `kubernetes/apps/ragnarok/rathena/classic/`
   - Renewal: `kubernetes/apps/ragnarok/rathena/renewal/`
   - Uses: `mariadb-secret` for IP, port, and credentials

2. **Hercules** (2 instances):
   - Classic: `kubernetes/apps/home/hercules/classic/`
   - Renewal: `kubernetes/apps/home/hercules/renewal/`
   - Uses: `mariadb-secret` for host, root password, IP, and port

### Secret Management

**Kyverno Policy**: `sync-mariadb-secrets`
- Automatically syncs `mariadb-secret` from `databases` namespace to all new namespaces
- Location: `kubernetes/apps/kyverno/policies/sync-mariadb-secrets.yaml`

### Operator Pattern Reference: CloudNative-PG

The repository already uses the operator pattern for PostgreSQL:

**Structure**:
```
kubernetes/apps/databases/cloudnative-pg/
├── ks.yaml                    # Two Kustomizations: operator + clusters
├── app/
│   ├── helm-release.yaml      # Operator installation
│   ├── kustomization.yaml
│   └── secret.sops.yaml
└── clusters/
    ├── defaultpg.yaml         # Cluster CRD instance
    ├── backup.yaml
    ├── manualbackup.yaml
    └── kustomization.yaml
```

**Key Features**:
- Operator installed via Helm chart
- Separate Kustomization for operator vs. cluster instances
- CRD-based cluster management
- Built-in backup to S3 (Minio)
- Scheduled backups
- Recovery from backups
- 3 instances with replication
- Monitoring with PodMonitor

## MariaDB Operator Overview

**Repository**: https://github.com/mariadb-operator/mariadb-operator

**Key Features**:
- Kubernetes-native MariaDB management
- High availability with Galera clustering
- Automated backups and restores
- Point-in-time recovery
- Connection pooling with MaxScale
- Monitoring and metrics
- Declarative configuration via CRDs

**Main CRDs**:
- `MariaDB`: Main database cluster resource
- `Backup`: Backup configuration
- `Restore`: Restore operations
- `MaxScale`: Connection pooling/load balancing
- `User`: User management
- `Grant`: Permission management
- `Database`: Database management

## Migration Strategy

### Phase 1: Preparation and Research
- [x] Analyze current MariaDB setup
- [ ] Review mariadb-operator documentation
- [ ] Study operator examples and best practices
- [ ] Identify all dependent applications
- [ ] Document current database schema and data

### Phase 2: Operator Installation
- [ ] Create Helm repository for mariadb-operator
- [ ] Create operator helm release configuration
- [ ] Create operator Kustomization
- [ ] Install mariadb-operator
- [ ] Verify operator installation and CRDs

### Phase 3: New MariaDB Instance Design
- [ ] Design MariaDB CRD configuration:
  - Storage: Longhorn (matching current setup)
  - Replication: Galera cluster (3 nodes for HA)
  - Backup: S3/Minio integration (like CloudNative-PG)
  - Monitoring: ServiceMonitor/PodMonitor
  - Resources: Match or improve current allocation
- [ ] Design MaxScale configuration for load balancing
- [ ] Design backup schedule and retention policy
- [ ] Create secret structure for operator

### Phase 4: Data Migration Planning
- [ ] Backup current MariaDB data using mysqldump
- [ ] Store backup in safe location (S3/Minio)
- [ ] Create restore procedure for operator-managed instance
- [ ] Plan for minimal downtime migration window
- [ ] Create rollback procedure

### Phase 5: Implementation
- [ ] Deploy new MariaDB instance using operator
- [ ] Verify cluster health and replication
- [ ] Configure MaxScale for connection pooling
- [ ] Set up backup schedule
- [ ] Test backup and restore procedures

### Phase 6: Data Migration
- [ ] Scale down dependent applications
- [ ] Perform final backup of old MariaDB
- [ ] Restore data to new operator-managed instance
- [ ] Verify data integrity
- [ ] Update connection strings/secrets

### Phase 7: Application Updates
- [ ] Update HAProxy configuration for new endpoints
- [ ] Update mariadb-secret with new connection details
- [ ] Update ragnarok applications (classic + renewal)
- [ ] Update hercules applications (classic + renewal)
- [ ] Verify Kyverno secret sync still works

### Phase 8: Testing and Validation
- [ ] Test database connectivity from all applications
- [ ] Verify application functionality
- [ ] Test backup procedures
- [ ] Test restore procedures
- [ ] Monitor cluster health and metrics
- [ ] Performance testing

### Phase 9: Cleanup
- [ ] Remove old MariaDB helm release
- [ ] Remove old PVC (after data verification)
- [ ] Update documentation
- [ ] Remove old HAProxy configuration if needed

## Directory Structure (Proposed)

```
kubernetes/apps/databases/mariadb/
├── ks.yaml                           # Two Kustomizations: operator + instances
├── operator/
│   ├── helm-release.yaml             # mariadb-operator installation
│   ├── kustomization.yaml
│   └── secret.sops.yaml              # Operator secrets if needed
├── instances/
│   ├── mariadb.yaml                  # MariaDB CRD
│   ├── maxscale.yaml                 # MaxScale CRD for load balancing
│   ├── backup.yaml                   # Backup CRD
│   ├── scheduled-backup.yaml         # Scheduled backup
│   ├── database.yaml                 # Database CRD for ragnarok DB
│   ├── user.yaml                     # User CRD for ragnarok user
│   ├── grant.yaml                    # Grant CRD for permissions
│   ├── secret.sops.yaml              # Database credentials
│   └── kustomization.yaml
└── lb/                               # Keep or modify HAProxy LB
    ├── helm-release.yaml
    ├── kustomization.yaml
    └── config/
        └── haproxy.cfg
```

## Key Decisions Needed

1. **Replication Strategy**:
   - Current: Standalone with unused replicas
   - Proposed: Galera cluster (3 nodes) for true HA
   - Alternative: Keep standalone if HA not needed

2. **Backup Strategy**:
   - Use S3/Minio like CloudNative-PG
   - Retention policy: 30 days (match PostgreSQL)
   - Scheduled backups: Daily

3. **Load Balancing**:
   - Keep HAProxy or migrate to MaxScale
   - MaxScale provides better MariaDB-specific features
   - HAProxy is simpler and already working

4. **Migration Approach**:
   - Blue-Green: Run both systems, switch over
   - In-place: Backup, destroy, restore
   - Recommended: Blue-Green for safety

5. **Downtime Window**:
   - Estimate: 15-30 minutes for data migration
   - Schedule during low-usage period
   - Have rollback plan ready

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Data loss during migration | High | Multiple backups, test restore before migration |
| Application downtime | Medium | Blue-green deployment, quick rollback plan |
| Operator bugs/issues | Medium | Test in non-prod first, have old setup ready |
| Connection string changes | Low | Update secrets before scaling up apps |
| Performance degradation | Medium | Monitor metrics, tune configuration |
| Backup failures | Medium | Test backup/restore before going live |

## Success Criteria

- [ ] MariaDB operator successfully installed
- [ ] New MariaDB instance running with replication
- [ ] All data migrated successfully
- [ ] All dependent applications working
- [ ] Backups configured and tested
- [ ] Monitoring and metrics working
- [ ] No data loss
- [ ] Minimal downtime (< 30 minutes)
- [ ] Old resources cleaned up
- [ ] Documentation updated

## References

- MariaDB Operator: https://github.com/mariadb-operator/mariadb-operator
- MariaDB Operator Docs: https://github.com/mariadb-operator/mariadb-operator/tree/main/docs
- Helm Chart: https://github.com/mariadb-operator/mariadb-operator/tree/main/deploy/charts/mariadb-operator
- CloudNative-PG Pattern: `kubernetes/apps/databases/cloudnative-pg/`
- Current Setup: `kubernetes/apps/databases/mariadb/`

## Next Steps

1. Research mariadb-operator documentation in detail
2. Create helm repository configuration
3. Design MariaDB CRD configuration
4. Create operator installation files
5. Test in development environment if available