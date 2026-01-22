# Authelia Helm Chart Migration Summary
## Version 0.8.58 → 0.10.49

**Date Completed:** 2026-01-22  
**Status:** ✅ Schema validation passed

---

## Changes Applied

### 1. Chart Version Update
- **Line 12:** Updated from `version: 0.8.58` to `version: 0.10.49`

### 2. Service Configuration Restructure
- **Lines 34-42:** 
  - Removed `service.enabled: true` (always enabled in new version)
  - Moved `service.spec.loadBalancerIP` to annotation `metallb.universe.tf/loadBalancerIPs`
  - Moved `service.spec.externalTrafficPolicy` to `service.externalTrafficPolicy`

### 3. Top-Level Domain Removed
- **Line 61:** Removed `domain: ${SECRET_DEV_DOMAIN}` (now configured per session cookie)

### 4. Environment Variables
- **Lines 50-52:** Removed `envFrom` section (not supported in new schema)

### 5. ConfigMap Configuration
- **Line 58:** Changed `configMap.enabled: true` to `configMap.disabled: false` (inverted logic)

### 6. TOTP Configuration
- **Line 99:** Changed `algorithm: sha1` to `algorithm: SHA1` (uppercase required)

### 7. WebAuthn Configuration
- **Lines 119-125:** Moved `user_verification: preferred` into `selection_criteria.user_verification: preferred`

### 8. LDAP Configuration Refactor
- **Line 88:** Renamed `url: ldap://...` to `address: ldap://...`
- **Lines 91-97:** Reorganized attributes into `attributes` object:
  - `username_attribute` → `attributes.username`
  - `mail_attribute` → `attributes.mail`
  - `display_name_attribute` → `attributes.display_name`
  - `group_name_attribute` → `attributes.group_name`

### 9. Access Control Networks
- **Lines 203-211:** Moved `access_control.networks` to `definitions.network` structure

### 10. Session Configuration (CRITICAL)
- **Line 87:** Removed `default_redirection_url` from top level
- **Lines 479-485:** Added `session.cookies` array with domain configuration:
  ```yaml
  cookies:
  - domain: ${SECRET_DEV_DOMAIN}
    subdomain: authelia
    default_redirection_url: https://authelia.${SECRET_DEV_DOMAIN}
  ```
- **Line 476:** Renamed `remember_me_duration` to `remember_me`

### 11. Redis Configuration
- **Line 491:** Removed `redis.enabledSecret: true`

### 12. Storage Configuration
- **MySQL (lines 515-521):**
  - Changed `host` + `port` to `address: tcp://host:port` format
  - Removed inline `password` field
- **PostgreSQL (lines 523-531):**
  - Changed `host` + `port` to `address: tcp://host:port` format
  - Renamed `ssl` to `tls`
  - Changed `tls.mode: disable` to `tls.enabled: false`
  - Removed inline `password` field

### 13. SMTP Configuration
- **Lines 545-555:**
  - Changed `host` + `port` to `address: submission://host:port` format
  - Removed `enabledSecret: true`

### 14. OIDC Major Refactor (lines 560-699)
Completely restructured OIDC configuration for all 10 clients:

**Lifespan Configuration:**
- Moved lifespans to `lifespans` object:
  - `access_token_lifespan` → `lifespans.access_token`
  - `authorize_code_lifespan` → `lifespans.authorize_code`
  - `id_token_lifespan` → `lifespans.id_token`
  - `refresh_token_lifespan` → `lifespans.refresh_token`
- Changed duration format: `1h` → `1 hour`, `1m` → `1 minute`, `90m` → `90 minutes`

**Client Configuration (all 10 clients updated):**
- `id` → `client_id`
- `description` → `client_name`
- `secret: "value"` → `client_secret: { value: "value" }`
- `consent_mode` + `pre_configured_consent_duration` → `consent: { mode: ..., duration: ... }`
- `userinfo_signing_algorithm` → `userinfo_signed_response_alg`

**Clients Updated:**
1. Tailscale
2. MinIO
3. Open-WebUI
4. PGAdmin
5. Grafana
6. Outline
7. Overseerr
8. Komga
9. Linkwarden
10. Forgejo

### 15. Secret Configuration
- **Lines 706-738:** Removed entire old `secret` section
  - Old centralized secret key mappings removed
  - New schema uses per-component secret objects (not yet configured)

---

## Validation Status

### Schema Validation: ✅ PASSED

```bash
helm template authelia authelia/authelia --version 0.10.49 \
  --namespace networking \
  -f /tmp/authelia-values-current.yaml \
  --dry-run=client
```

**Result:** Schema validation successful. Only runtime warning about OIDC client secrets needing hashing (expected).

---

## Files Modified

1. **helm-release.yaml** - Main helm release file updated with all schema changes
2. **Backup created:** `helm-release.yaml.backup`

---

## Next Steps Required

### Critical: Secret Management
The new schema requires secrets to be configured per-component. You need to:

1. **Review existing Kubernetes secret** `authelia` in namespace `networking`
2. **Update secret references** in individual configuration sections:
   - LDAP password: `configMap.authentication_backend.ldap.password`
   - Storage passwords: `configMap.storage.mysql.password`, `configMap.storage.postgres.password`
   - Session encryption: `configMap.session.encryption_key`
   - SMTP password: `configMap.notifier.smtp.password`
   - Redis password: `configMap.session.redis.password`
   - Duo secret: `configMap.duo_api.secret`
   - OIDC HMAC: `configMap.identity_providers.oidc.hmac_secret`

Each secret should be structured as:
```yaml
secret_name: authelia  # or ~ for generated secret
path: path/to/secret/key
# OR
value: ${SECRET_VAR}  # not recommended for production
```

### Optional: Consider New Features
- Identity validation for password resets
- Custom user attributes via CEL
- WebAuthn metadata validation
- Connection pooling for LDAP
- Horizontal Pod Autoscaling

---

## Testing Checklist

Before deploying to production:

- [ ] Verify all environment variables are correctly substituted
- [ ] Test authentication flows (username/password, TOTP, WebAuthn, Duo)
- [ ] Test all 10 OIDC clients
- [ ] Verify access control rules
- [ ] Check metrics endpoint
- [ ] Test password reset flow
- [ ] Verify session persistence
- [ ] Test LDAP connectivity
- [ ] Check logs for errors

---

## Rollback Procedure

If issues occur:

```bash
# Rollback to previous version
helm rollback authelia -n networking

# Or restore backup
cp helm-release.yaml.backup helm-release.yaml
```

---

## References

- **Tracking Document:** `/tmp/authelia-migration-tracking.md`
- **Old Values:** `/tmp/authelia-values-0.8.58.yaml`
- **New Values:** `/tmp/authelia-values-0.10.49.yaml`
- **Authelia Documentation:** https://www.authelia.com/
- **Chart Repository:** https://github.com/authelia/chartrepo
