# Authelia Secrets Configuration - Completed

## ✅ Status: COMPLETE

All secret references have been properly configured in the new schema format.

---

## Secret References Added

### 1. LDAP Password
**Location:** `configMap.authentication_backend.ldap.password`
```yaml
password:
  secret_name: authelia
  path: LDAP_PASSWORD
```

### 2. Session Encryption Key
**Location:** `configMap.session.encryption_key`
```yaml
encryption_key:
  secret_name: authelia
  path: SESSION_SECRET
```

### 3. Redis Password (if enabled)
**Location:** `configMap.session.redis.password`
```yaml
password:
  secret_name: authelia
  path: REDIS_PASSWORD
```

### 4. Storage Encryption Key
**Location:** `configMap.storage.encryption_key`
```yaml
encryption_key:
  secret_name: authelia
  path: STORAGE_ENCRYPTION_KEY
```

### 5. SMTP Password
**Location:** `configMap.notifier.smtp.password`
```yaml
password:
  secret_name: authelia
  path: SMTP_PASSWORD
```

### 6. Duo Secret Key
**Location:** `configMap.duo_api.secret`
```yaml
secret:
  secret_name: authelia
  path: DUO_SECRET_KEY
```

### 7. OIDC HMAC Secret
**Location:** `configMap.identity_providers.oidc.hmac_secret`
```yaml
hmac_secret:
  secret_name: authelia
  path: OIDC_HMAC_SECRET
```

### 8. Additional Secrets Declaration
**Location:** Top-level `secret.additionalSecrets`
```yaml
secret:
  disabled: false
  existingSecret: ""
  additionalSecrets:
    authelia:
      items:
        - key: LDAP_PASSWORD
        - key: SESSION_SECRET
        - key: STORAGE_ENCRYPTION_KEY
        - key: REDIS_PASSWORD
        - key: SMTP_PASSWORD
        - key: DUO_SECRET_KEY
        - key: OIDC_HMAC_SECRET
```

---

## Existing Kubernetes Secret

The existing secret `authelia` in namespace `networking` contains all required keys:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: authelia
  namespace: networking
type: Opaque
stringData:
  LDAP_PASSWORD: <encrypted>
  SESSION_SECRET: <encrypted>
  STORAGE_ENCRYPTION_KEY: <encrypted>
  REDIS_PASSWORD: <encrypted>
  SMTP_PASSWORD: ${SECRET_AWS_SMTP_PASSWORD}
  DUO_SECRET_KEY: <encrypted>
  OIDC_HMAC_SECRET: <encrypted>
  # Plus OIDC keys and other secrets...
```

---

## Validation Results

### ✅ Helm Template Validation: PASSED

```bash
helm template authelia authelia/authelia \
  --version 0.10.49 \
  --namespace networking \
  -f helm-release.yaml \
  --dry-run=client
```

**Result:** Schema validation successful!

**Note:** The only message is a recommendation to hash OIDC client secrets, which is a best practice warning, not an error.

---

## Key Differences from Old Schema

| Old Schema | New Schema |
|------------|------------|
| Centralized `secret.*` keys | Per-component secret objects |
| `secret.jwt.key: JWT_SECRET` | Individual secret references |
| `secret.mountPath: /secrets` | Automatic path handling |
| Single secret configuration | Distributed configuration |

---

## Migration Complete

The helm release is now fully migrated to version 0.10.49 with:

✅ All schema changes applied  
✅ All secret references configured  
✅ Helm template validation passing  
✅ Ready for deployment

---

## Deployment Steps

1. **Review the changes:**
   ```bash
   diff helm-release.yaml.backup helm-release.yaml
   ```

2. **Test in your environment:**
   ```bash
   helm template authelia authelia/authelia \
     --version 0.10.49 \
     --namespace networking \
     --values <(yq '.spec.values' helm-release.yaml)
   ```

3. **Deploy via Flux** (or manually):
   ```bash
   # Flux will automatically detect and apply changes
   # Or manually:
   kubectl apply -f helm-release.yaml
   ```

4. **Monitor the deployment:**
   ```bash
   kubectl get helmrelease authelia -n networking -w
   kubectl logs -n networking -l app.kubernetes.io/name=authelia
   ```

---

## Rollback Plan

If issues occur:

```bash
# Restore backup
cp helm-release.yaml.backup helm-release.yaml
kubectl apply -f helm-release.yaml

# Or use Helm rollback if deployed manually
helm rollback authelia -n networking
```

---

## Notes

- All environment variable substitutions (${SECRET_*}) will be resolved by Flux
- The existing `secret.sops.yaml` file remains unchanged
- OIDC client secrets can be optionally hashed for security (see tool_secret_hasher.py)
- The migration is backward compatible with your existing Kubernetes secret structure

