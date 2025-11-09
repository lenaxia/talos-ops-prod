#!/bin/bash
set -euo pipefail

# MariaDB Operator Migration Script
# This script helps migrate from Bitnami MariaDB to MariaDB Operator

NAMESPACE="databases"
OLD_MARIADB_POD="mariadb-0"
NEW_MARIADB_POD="mariadb-0"
BACKUP_DIR="./mariadb-backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Step 1: Check operator deployment
check_operator() {
    log_info "Checking MariaDB operator deployment..."
    
    if ! kubectl get helmrelease mariadb-operator -n $NAMESPACE &>/dev/null; then
        log_error "MariaDB operator not found. Please ensure Flux has deployed it."
        exit 1
    fi
    
    log_info "Waiting for operator to be ready..."
    kubectl wait --for=condition=ready helmrelease/mariadb-operator -n $NAMESPACE --timeout=5m || {
        log_error "Operator failed to become ready"
        exit 1
    }
    
    log_info "Operator is ready!"
}

# Step 2: Backup current MariaDB data
backup_current_data() {
    log_info "Creating backup of current MariaDB data..."
    
    # Get root password
    ROOT_PASSWORD=$(kubectl get secret mariadb-secret -n $NAMESPACE -o jsonpath='{.data.mariadb-root-password}' | base64 -d)
    
    # Create full backup
    BACKUP_FILE="$BACKUP_DIR/mariadb-full-backup-$TIMESTAMP.sql"
    log_info "Backing up to: $BACKUP_FILE"
    
    kubectl exec -n $NAMESPACE $OLD_MARIADB_POD -- \
        mysqldump -u root -p"$ROOT_PASSWORD" \
        --all-databases \
        --single-transaction \
        --routines \
        --triggers \
        --events \
        --hex-blob \
        --skip-lock-tables \
        > "$BACKUP_FILE"
    
    if [ $? -eq 0 ]; then
        log_info "Backup completed successfully: $BACKUP_FILE"
        log_info "Backup size: $(du -h "$BACKUP_FILE" | cut -f1)"
    else
        log_error "Backup failed!"
        exit 1
    fi
    
    # Compress backup
    log_info "Compressing backup..."
    gzip "$BACKUP_FILE"
    log_info "Compressed backup: ${BACKUP_FILE}.gz"
}

# Step 3: Scale down dependent applications
scale_down_apps() {
    log_info "Scaling down dependent applications..."
    
    # Scale down ragnarok applications
    kubectl scale deployment -n ragnarok --all --replicas=0 || true
    kubectl scale deployment -n home --selector=app.kubernetes.io/name=hercules --replicas=0 || true
    
    log_info "Waiting for pods to terminate..."
    sleep 10
}

# Step 4: Wait for new MariaDB cluster
wait_for_new_cluster() {
    log_info "Waiting for new MariaDB cluster to be ready..."
    
    # Wait for MariaDB CRD to be ready
    kubectl wait --for=condition=ready mariadb/mariadb -n $NAMESPACE --timeout=10m || {
        log_error "MariaDB cluster failed to become ready"
        log_info "Check status with: kubectl get mariadb -n $NAMESPACE"
        log_info "Check pods with: kubectl get pods -n $NAMESPACE -l app.kubernetes.io/instance=mariadb"
        exit 1
    }
    
    log_info "MariaDB cluster is ready!"
}

# Step 5: Restore data to new cluster
restore_data() {
    log_info "Restoring data to new MariaDB cluster..."
    
    # Get new root password
    NEW_ROOT_PASSWORD=$(kubectl get secret mariadb-operator-secret -n $NAMESPACE -o jsonpath='{.data.root-password}' | base64 -d)
    
    # Find the most recent backup
    LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/mariadb-full-backup-*.sql.gz | head -1)
    
    if [ -z "$LATEST_BACKUP" ]; then
        log_error "No backup file found!"
        exit 1
    fi
    
    log_info "Restoring from: $LATEST_BACKUP"
    
    # Decompress and restore
    gunzip -c "$LATEST_BACKUP" | kubectl exec -i -n $NAMESPACE $NEW_MARIADB_POD -- \
        mysql -u root -p"$NEW_ROOT_PASSWORD"
    
    if [ $? -eq 0 ]; then
        log_info "Data restored successfully!"
    else
        log_error "Data restore failed!"
        exit 1
    fi
}

# Step 6: Verify data
verify_data() {
    log_info "Verifying data in new cluster..."
    
    NEW_ROOT_PASSWORD=$(kubectl get secret mariadb-operator-secret -n $NAMESPACE -o jsonpath='{.data.root-password}' | base64 -d)
    
    # Check databases
    log_info "Databases in new cluster:"
    kubectl exec -n $NAMESPACE $NEW_MARIADB_POD -- \
        mysql -u root -p"$NEW_ROOT_PASSWORD" -e "SHOW DATABASES;"
    
    # Check ragnarok database
    log_info "Tables in ragnarok database:"
    kubectl exec -n $NAMESPACE $NEW_MARIADB_POD -- \
        mysql -u root -p"$NEW_ROOT_PASSWORD" -e "USE ragnarok; SHOW TABLES;"
    
    # Check Galera cluster status
    log_info "Galera cluster status:"
    kubectl exec -n $NAMESPACE $NEW_MARIADB_POD -- \
        mysql -u root -p"$NEW_ROOT_PASSWORD" -e "SHOW STATUS LIKE 'wsrep_%';" | grep -E "wsrep_cluster_size|wsrep_cluster_status|wsrep_ready"
}

# Step 7: Scale up applications
scale_up_apps() {
    log_info "Scaling up dependent applications..."
    
    # Scale up ragnarok applications
    kubectl scale deployment -n ragnarok --all --replicas=1 || true
    kubectl scale deployment -n home --selector=app.kubernetes.io/name=hercules --replicas=1 || true
    
    log_info "Applications scaled up. Monitor their logs for connection issues."
}

# Step 8: Test connectivity
test_connectivity() {
    log_info "Testing database connectivity..."
    
    NEW_ROOT_PASSWORD=$(kubectl get secret mariadb-operator-secret -n $NAMESPACE -o jsonpath='{.data.root-password}' | base64 -d)
    
    # Test connection
    kubectl exec -n $NAMESPACE $NEW_MARIADB_POD -- \
        mysql -u root -p"$NEW_ROOT_PASSWORD" -e "SELECT 1;" &>/dev/null
    
    if [ $? -eq 0 ]; then
        log_info "Database connectivity test passed!"
    else
        log_error "Database connectivity test failed!"
        exit 1
    fi
}

# Main execution
main() {
    log_info "Starting MariaDB migration to operator..."
    log_info "Timestamp: $TIMESTAMP"
    
    # Confirm before proceeding
    read -p "This will migrate MariaDB to the operator. Continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_warn "Migration cancelled."
        exit 0
    fi
    
    check_operator
    backup_current_data
    scale_down_apps
    wait_for_new_cluster
    restore_data
    verify_data
    test_connectivity
    scale_up_apps
    
    log_info "Migration completed successfully!"
    log_info "Backup location: $BACKUP_DIR"
    log_info ""
    log_info "Next steps:"
    log_info "1. Monitor application logs for any connection issues"
    log_info "2. Verify application functionality"
    log_info "3. Test backup procedures"
    log_info "4. Once verified, remove old MariaDB deployment"
    log_info ""
    log_info "To remove old MariaDB:"
    log_info "  kubectl delete helmrelease mariadb -n $NAMESPACE"
    log_info "  kubectl delete pvc mariadb-data-volume -n $NAMESPACE"
}

# Run main function
main "$@"