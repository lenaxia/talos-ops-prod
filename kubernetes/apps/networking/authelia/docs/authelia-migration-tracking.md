# Authelia Helm Chart Migration Tracking
## Version 0.8.58 → 0.10.49

**Date:** 2026-01-22  
**Current Chart Version:** 0.8.58  
**Target Chart Version:** 0.10.49

---

## Executive Summary

### Major Schema Changes

1. **Domain Configuration Removed** - The top-level `domain` field has been removed. Domain is now configured per session cookie.
2. **Session Architecture Redesigned** - Session configuration now uses a `cookies` array instead of single domain configuration.
3. **Service Structure Changed** - Service configuration has been simplified with `enabled` field removed.
4. **LDAP Refactored** - LDAP configuration moved from `url` to `address` and attributes reorganized into `attributes` object.
5. **Storage Refactored** - Database configurations now use `address` instead of separate `host/port`.
6. **SMTP Refactored** - SMTP configuration now uses unified `address` with scheme instead of separate `host/port`.
7. **OIDC Major Refactor** - OIDC configuration completely restructured with new lifespan, claims, and client structures.
8. **Identity Validation Added** - New `identity_validation` section for reset password and elevated session configuration.
9. **Definitions Added** - New `definitions` section for network and user attribute definitions.
10. **Secret Management Changed** - Secrets now use nested objects with `disabled`, `secret_name`, `value`, and `path` properties.
11. **Duration Format Changed** - Time values now use human-readable format (e.g., "6 seconds" instead of "6s").
12. **Regulation Enhanced** - New `modes` field for regulation.
13. **NTP Address Changed** - NTP address now uses URI format with scheme.
14. **Authentication Backend Enhanced** - New `password_change` section added.
15. **Server Endpoints Added** - New `endpoints` section for authz configurations.
16. **WebAuthn Enhanced** - New filtering, selection criteria, and metadata options.
17. **TOTP Enhanced** - New `allowed_algorithms`, `allowed_digits`, `allowed_periods` fields.
18. **Access Control Simplified** - Networks moved to `definitions.network`.
19. **ConfigMap Structure** - New `filters` and `extraConfigs` options.
20. **Ingress Enhanced** - Gateway API and improved Traefik CRD support.
21. **Pod Configuration Enhanced** - New `disableRestartOnChanges`, `command`, `args`, `initContainers`, `autoscaling` options.

---

## Detailed Migration Table

### 1. TOP-LEVEL CONFIGURATION

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `domain` | **REMOVED** | `configMap.session.cookies[].domain` | Domain now configured per session cookie | ☐ |
| `versionOverride` | ✓ OK | `versionOverride` | No change | ☐ |
| `kubeVersionOverride` | ✓ OK | `kubeVersionOverride` | No change | ☐ |
| N/A | **NEW** | `kubeDNSDomainOverride` | New optional field for custom K8s DNS domain | ☐ |
| N/A | **NEW** | `enabled` | New field for dependency conditions | ☐ |

---

### 2. IMAGE CONFIGURATION

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `image.repository` | ✓ OK | `image.repository` | Currently: `ghcr.io/authelia/authelia` | ☐ |
| `image.tag` | ✓ OK | `image.tag` | Currently: `4.37.5` | ☐ |
| `image.pullPolicy` | ✓ OK | `image.pullPolicy` | Currently: `Always` | ☐ |

---

### 3. SERVICE CONFIGURATION

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `service.enabled` | **REMOVED** | N/A | Service is always created in new version | ☐ |
| `service.type` | ✓ OK | `service.type` | Currently: `LoadBalancer` | ☐ |
| `service.port` | ✓ OK | `service.port` | Currently: `80` | ☐ |
| `service.spec.loadBalancerIP` | **CHANGED** | Remove from spec | Should be in annotations or at service level | ☐ |
| `service.spec.externalTrafficPolicy` | **CHANGED** | `service.externalTrafficPolicy` | Move out of spec | ☐ |
| `service.annotations` | ✓ OK | `service.annotations` | Currently has metallb annotation | ☐ |
| N/A | **NEW** | `service.nodePort` | Default: 30091 | ☐ |
| N/A | **NEW** | `service.clusterIP` | Optional cluster IP | ☐ |

---

### 4. POD CONFIGURATION

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `pod.kind` | ✓ OK | `pod.kind` | Currently: `Deployment` | ☐ |
| `pod.replicas` | ✓ OK | `pod.replicas` | Currently: `1` | ☐ |
| `pod.selectors.nodeSelector` | ✓ OK | `pod.selectors.nodeSelector` | Currently has worker node selector | ☐ |
| N/A | **NEW** | `pod.disableRestartOnChanges` | New option to disable auto-restart | ☐ |
| N/A | **NEW** | `pod.command` | New option to override command | ☐ |
| N/A | **NEW** | `pod.args` | New option to override args | ☐ |
| N/A | **NEW** | `pod.initContainers` | New option for init containers | ☐ |
| N/A | **NEW** | `pod.autoscaling` | New HPA configuration | ☐ |
| N/A | **NEW** | `pod.extraContainers` | New option for sidecar containers | ☐ |
| `pod.strategy.rollingUpdate` | **CHANGED** | `pod.strategy.rollingUpdate` | Now includes `partition` field | ☐ |

---

### 5. ENVIRONMENT VARIABLES

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `envFrom` | **CHANGED** | `pod.env` | Use `pod.env` for individual vars; no direct `envFrom` in new schema | ☐ |

---

### 6. CONFIGMAP - LOGGING

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `configMap.enabled` | **CHANGED** | `configMap.disabled` | Logic inverted! `disabled: false` means enabled | ☐ |
| `configMap.log.level` | ✓ OK | `configMap.log.level` | Currently: `debug` | ☐ |
| `configMap.log.format` | ✓ OK | `configMap.log.format` | Currently: `text` | ☐ |
| `configMap.log.file_path` | ✓ OK | `configMap.log.file_path` | Currently: `/config/authelia.log` | ☐ |

---

### 7. CONFIGMAP - SERVER

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `configMap.server.timeouts.read` | **CHANGED** | `configMap.server.timeouts.read` | Format changed: `6s` → `6 seconds` | ☐ |
| `configMap.server.timeouts.write` | **CHANGED** | `configMap.server.timeouts.write` | Format changed: `6s` → `6 seconds` | ☐ |
| `configMap.server.timeouts.idle` | **CHANGED** | `configMap.server.timeouts.idle` | Format changed: `30s` → `30 seconds` | ☐ |
| N/A | **NEW** | `configMap.server.endpoints` | New section for authz endpoints config | ☐ |
| N/A | **NEW** | `configMap.filters` | New option to disable template filters | ☐ |
| N/A | **NEW** | `configMap.extraConfigs` | New option for additional config files | ☐ |

---

### 8. CONFIGMAP - TELEMETRY

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `configMap.telemetry.metrics.enabled` | ✓ OK | `configMap.telemetry.metrics.enabled` | Currently: `true` | ☐ |
| `configMap.telemetry.metrics.port` | ✓ OK | `configMap.telemetry.metrics.port` | Currently: `9959` | ☐ |
| `configMap.telemetry.metrics.timeouts.read` | **CHANGED** | `configMap.telemetry.metrics.timeouts.read` | Format: `6s` → `6 seconds` | ☐ |
| `configMap.telemetry.metrics.timeouts.write` | **CHANGED** | `configMap.telemetry.metrics.timeouts.write` | Format: `6s` → `6 seconds` | ☐ |
| `configMap.telemetry.metrics.timeouts.idle` | **CHANGED** | `configMap.telemetry.metrics.timeouts.idle` | Format: `30s` → `30 seconds` | ☐ |
| `configMap.telemetry.metrics.serviceMonitor.enabled` | ✓ OK | `configMap.telemetry.metrics.serviceMonitor.enabled` | Currently: `true` | ☐ |

---

### 9. CONFIGMAP - DEFAULTS & THEME

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `configMap.default_redirection_url` | **REMOVED** | `configMap.session.cookies[].default_redirection_url` | Now per-cookie config | ☐ |
| `configMap.default_2fa_method` | ✓ OK | `configMap.default_2fa_method` | Currently: `mobile_push` | ☐ |
| `configMap.theme` | ✓ OK | `configMap.theme` | Currently: `light` | ☐ |

---

### 10. CONFIGMAP - IDENTITY VALIDATION (NEW)

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| N/A | **NEW** | `configMap.identity_validation.reset_password` | JWT-based password reset validation | ☐ |
| N/A | **NEW** | `configMap.identity_validation.elevated_session` | Elevated session for sensitive operations | ☐ |

---

### 11. CONFIGMAP - TOTP

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `configMap.totp.disable` | ✓ OK | `configMap.totp.disable` | Currently: `false` | ☐ |
| `configMap.totp.issuer` | ✓ OK | `configMap.totp.issuer` | Currently: `${SECRET_DEV_DOMAIN}` | ☐ |
| `configMap.totp.algorithm` | **CHANGED** | `configMap.totp.algorithm` | Format changed: `sha1` → `SHA1` (uppercase) | ☐ |
| `configMap.totp.digits` | ✓ OK | `configMap.totp.digits` | Currently: `6` | ☐ |
| `configMap.totp.period` | ✓ OK | `configMap.totp.period` | Currently: `30` | ☐ |
| `configMap.totp.skew` | ✓ OK | `configMap.totp.skew` | Currently: `1` | ☐ |
| N/A | **NEW** | `configMap.totp.secret_size` | Default: 32 | ☐ |
| N/A | **NEW** | `configMap.totp.allowed_algorithms` | Array of allowed algorithms | ☐ |
| N/A | **NEW** | `configMap.totp.allowed_digits` | Array of allowed digit counts | ☐ |
| N/A | **NEW** | `configMap.totp.allowed_periods` | Array of allowed periods | ☐ |

---

### 12. CONFIGMAP - WEBAUTHN

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `configMap.webauthn.disable` | ✓ OK | `configMap.webauthn.disable` | Currently: `false` | ☐ |
| `configMap.webauthn.timeout` | **CHANGED** | `configMap.webauthn.timeout` | Format: `60s` → `60 seconds` | ☐ |
| `configMap.webauthn.display_name` | ✓ OK | `configMap.webauthn.display_name` | Currently: `${SECRET_DEV_DOMAIN}` | ☐ |
| `configMap.webauthn.attestation_conveyance_preference` | ✓ OK | `configMap.webauthn.attestation_conveyance_preference` | Currently: `indirect` | ☐ |
| `configMap.webauthn.user_verification` | **CHANGED** | `configMap.webauthn.selection_criteria.user_verification` | Moved under selection_criteria | ☐ |
| N/A | **NEW** | `configMap.webauthn.enable_passkey_login` | Enable passkey login feature | ☐ |
| N/A | **NEW** | `configMap.webauthn.filtering` | AAGUID filtering options | ☐ |
| N/A | **NEW** | `configMap.webauthn.selection_criteria.attachment` | Authenticator attachment preference | ☐ |
| N/A | **NEW** | `configMap.webauthn.selection_criteria.discoverability` | Discoverability preference | ☐ |
| N/A | **NEW** | `configMap.webauthn.metadata` | Metadata service validation | ☐ |

---

### 13. CONFIGMAP - DUO

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `configMap.duo_api.enabled` | ✓ OK | `configMap.duo_api.enabled` | Currently: `true` | ☐ |
| `configMap.duo_api.hostname` | ✓ OK | `configMap.duo_api.hostname` | Currently: `api-b68b8774.duosecurity.com` | ☐ |
| `configMap.duo_api.integration_key` | ✓ OK | `configMap.duo_api.integration_key` | Currently: `DI2IGENLJKFDHSKGWT1L` | ☐ |
| `configMap.duo_api.enable_self_enrollment` | ✓ OK | `configMap.duo_api.enable_self_enrollment` | Currently: `true` | ☐ |
| N/A | **NEW** | `configMap.duo_api.secret` | New secret object structure | ☐ |

---

### 14. CONFIGMAP - DEFINITIONS (NEW)

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| N/A | **NEW** | `configMap.definitions.network` | Named network definitions | ☐ |
| N/A | **NEW** | `configMap.definitions.user_attributes` | Custom user attributes via CEL | ☐ |

---

### 15. CONFIGMAP - AUTHENTICATION BACKEND

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `configMap.authentication_backend.password_reset.disable` | ✓ OK | `configMap.authentication_backend.password_reset.disable` | Currently: `false` | ☐ |
| `configMap.authentication_backend.password_reset.custom_url` | ✓ OK | `configMap.authentication_backend.password_reset.custom_url` | Currently: empty | ☐ |
| `configMap.authentication_backend.refresh_interval` | **CHANGED** | `configMap.authentication_backend.refresh_interval` | Format: `5m` → `5 minutes` | ☐ |
| N/A | **NEW** | `configMap.authentication_backend.password_change` | New password change configuration | ☐ |

---

### 16. CONFIGMAP - LDAP

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `configMap.authentication_backend.ldap.enabled` | ✓ OK | `configMap.authentication_backend.ldap.enabled` | Currently: `true` | ☐ |
| `configMap.authentication_backend.ldap.implementation` | ✓ OK | `configMap.authentication_backend.ldap.implementation` | Currently: `custom` | ☐ |
| `configMap.authentication_backend.ldap.url` | **CHANGED** | `configMap.authentication_backend.ldap.address` | Field renamed; value format same | ☐ |
| `configMap.authentication_backend.ldap.timeout` | **CHANGED** | `configMap.authentication_backend.ldap.timeout` | Format: `5s` → `5 seconds` | ☐ |
| `configMap.authentication_backend.ldap.start_tls` | ✓ OK | `configMap.authentication_backend.ldap.start_tls` | Currently: `false` | ☐ |
| `configMap.authentication_backend.ldap.tls.*` | ✓ OK | `configMap.authentication_backend.ldap.tls.*` | No changes to TLS config | ☐ |
| `configMap.authentication_backend.ldap.base_dn` | ✓ OK | `configMap.authentication_backend.ldap.base_dn` | Currently: `dc=kao,dc=family` | ☐ |
| `configMap.authentication_backend.ldap.username_attribute` | **CHANGED** | `configMap.authentication_backend.ldap.attributes.username` | Moved to attributes | ☐ |
| `configMap.authentication_backend.ldap.additional_users_dn` | ✓ OK | `configMap.authentication_backend.ldap.additional_users_dn` | Currently: `cn=users` | ☐ |
| `configMap.authentication_backend.ldap.users_filter` | ✓ OK | `configMap.authentication_backend.ldap.users_filter` | Complex filter string | ☐ |
| `configMap.authentication_backend.ldap.additional_groups_dn` | ✓ OK | `configMap.authentication_backend.ldap.additional_groups_dn` | Currently: `cn=groups` | ☐ |
| `configMap.authentication_backend.ldap.groups_filter` | ✓ OK | `configMap.authentication_backend.ldap.groups_filter` | Complex filter string | ☐ |
| `configMap.authentication_backend.ldap.group_name_attribute` | **CHANGED** | `configMap.authentication_backend.ldap.attributes.group_name` | Moved to attributes | ☐ |
| `configMap.authentication_backend.ldap.mail_attribute` | **CHANGED** | `configMap.authentication_backend.ldap.attributes.mail` | Moved to attributes | ☐ |
| `configMap.authentication_backend.ldap.display_name_attribute` | **CHANGED** | `configMap.authentication_backend.ldap.attributes.display_name` | Moved to attributes | ☐ |
| `configMap.authentication_backend.ldap.permit_referrals` | ✓ OK | `configMap.authentication_backend.ldap.permit_referrals` | Currently: `false` | ☐ |
| `configMap.authentication_backend.ldap.permit_unauthenticated_bind` | ✓ OK | `configMap.authentication_backend.ldap.permit_unauthenticated_bind` | Currently: `false` | ☐ |
| `configMap.authentication_backend.ldap.user` | ✓ OK | `configMap.authentication_backend.ldap.user` | LDAP bind user DN | ☐ |
| N/A | **NEW** | `configMap.authentication_backend.ldap.pooling` | Connection pooling configuration | ☐ |
| N/A | **NEW** | `configMap.authentication_backend.ldap.attributes.*` | Many new attribute mappings available | ☐ |
| N/A | **NEW** | `configMap.authentication_backend.ldap.password` | New secret object structure | ☐ |

---

### 17. CONFIGMAP - PASSWORD POLICY

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `configMap.password_policy.standard.*` | ✓ OK | `configMap.password_policy.standard.*` | All fields unchanged | ☐ |
| `configMap.password_policy.zxcvbn.*` | ✓ OK | `configMap.password_policy.zxcvbn.*` | All fields unchanged | ☐ |

---

### 18. CONFIGMAP - ACCESS CONTROL

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `configMap.access_control.secret.*` | ✓ OK | `configMap.access_control.secret.*` | No changes | ☐ |
| `configMap.access_control.default_policy` | ✓ OK | `configMap.access_control.default_policy` | Currently: `deny` | ☐ |
| `configMap.access_control.networks` | **CHANGED** | `configMap.definitions.network` | Moved to definitions section | ☐ |
| `configMap.access_control.rules` | ✓ OK | `configMap.access_control.rules` | Same structure; many rules defined | ☐ |

---

### 19. CONFIGMAP - SESSION

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `configMap.session.name` | **CHANGED** | `configMap.session.name` (default) OR `cookies[].name` | Can override per cookie | ☐ |
| `configMap.session.same_site` | **CHANGED** | `configMap.session.same_site` (default) OR `cookies[].same_site` | Can override per cookie | ☐ |
| `configMap.session.expiration` | **CHANGED** | `configMap.session.expiration` | Format: `1h` → `1 hour` | ☐ |
| `configMap.session.inactivity` | **CHANGED** | `configMap.session.inactivity` | Format: `5m` → `5 minutes` | ☐ |
| `configMap.session.remember_me_duration` | **CHANGED** | `configMap.session.remember_me` | Field renamed & format changed | ☐ |
| N/A | **NEW** | `configMap.session.encryption_key` | New secret object for session encryption | ☐ |
| N/A | **REQUIRED** | `configMap.session.cookies[]` | Array of cookie configs (REQUIRED!) | ☐ |

---

### 20. CONFIGMAP - REDIS

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `configMap.session.redis.enabled` | **CHANGED** | `configMap.session.redis.enabled` | Currently: `false` (must evaluate) | ☐ |
| `configMap.session.redis.enabledSecret` | **REMOVED** | N/A | Use new secret structure instead | ☐ |
| `configMap.session.redis.host` | ✓ OK | `configMap.session.redis.host` | Currently: `redis-lb.databases.svc.cluster.local` | ☐ |
| `configMap.session.redis.port` | ✓ OK | `configMap.session.redis.port` | Currently: `6379` | ☐ |
| `configMap.session.redis.username` | ✓ OK | `configMap.session.redis.username` | Currently: empty | ☐ |
| `configMap.session.redis.database_index` | ✓ OK | `configMap.session.redis.database_index` | Currently: `0` | ☐ |
| `configMap.session.redis.maximum_active_connections` | ✓ OK | `configMap.session.redis.maximum_active_connections` | Currently: `8` | ☐ |
| `configMap.session.redis.minimum_idle_connections` | ✓ OK | `configMap.session.redis.minimum_idle_connections` | Currently: `0` | ☐ |
| `configMap.session.redis.tls.*` | ✓ OK | `configMap.session.redis.tls.*` | No changes | ☐ |
| `configMap.session.redis.high_availability.*` | ✓ OK | `configMap.session.redis.high_availability.*` | Mostly unchanged | ☐ |
| N/A | **NEW** | `configMap.session.redis.deploy` | Deploy Redis chart option | ☐ |
| N/A | **NEW** | `configMap.session.redis.password` | New secret object structure | ☐ |

---

### 21. CONFIGMAP - REGULATION

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `configMap.regulation.max_retries` | ✓ OK | `configMap.regulation.max_retries` | Currently: `3` | ☐ |
| `configMap.regulation.find_time` | **CHANGED** | `configMap.regulation.find_time` | Format: `2m` → `2 minutes` | ☐ |
| `configMap.regulation.ban_time` | **CHANGED** | `configMap.regulation.ban_time` | Format: `5m` → `5 minutes` | ☐ |
| N/A | **NEW** | `configMap.regulation.modes` | Array of modes (e.g., ['user', 'ip']) | ☐ |

---

### 22. CONFIGMAP - STORAGE

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `configMap.storage.local.enabled` | ✓ OK | `configMap.storage.local.enabled` | Currently: `true` | ☐ |
| `configMap.storage.local.path` | ✓ OK | `configMap.storage.local.path` | Currently: `/config/db.sqlite3` | ☐ |
| `configMap.storage.mysql.enabled` | ✓ OK | `configMap.storage.mysql.enabled` | Currently: `false` | ☐ |
| `configMap.storage.mysql.host` | **CHANGED** | `configMap.storage.mysql.address` | Format: `tcp://host:port` | ☐ |
| `configMap.storage.mysql.port` | **REMOVED** | N/A | Merged into address | ☐ |
| `configMap.storage.mysql.database` | ✓ OK | `configMap.storage.mysql.database` | No change | ☐ |
| `configMap.storage.mysql.username` | ✓ OK | `configMap.storage.mysql.username` | No change | ☐ |
| `configMap.storage.mysql.timeout` | **CHANGED** | `configMap.storage.mysql.timeout` | Format: `10s` → `10 seconds` | ☐ |
| `configMap.storage.postgres.enabled` | ✓ OK | `configMap.storage.postgres.enabled` | Currently: `false` | ☐ |
| `configMap.storage.postgres.host` | **CHANGED** | `configMap.storage.postgres.address` | Format: `tcp://host:port` | ☐ |
| `configMap.storage.postgres.port` | **REMOVED** | N/A | Merged into address | ☐ |
| `configMap.storage.postgres.database` | ✓ OK | `configMap.storage.postgres.database` | No change | ☐ |
| `configMap.storage.postgres.schema` | ✓ OK | `configMap.storage.postgres.schema` | No change | ☐ |
| `configMap.storage.postgres.username` | ✓ OK | `configMap.storage.postgres.username` | No change | ☐ |
| `configMap.storage.postgres.timeout` | **CHANGED** | `configMap.storage.postgres.timeout` | Format: `5s` → `5 seconds` | ☐ |
| `configMap.storage.postgres.ssl` | **CHANGED** | `configMap.storage.postgres.tls` | Renamed section | ☐ |
| N/A | **NEW** | `configMap.storage.encryption_key` | New secret object for encryption key | ☐ |
| N/A | **NEW** | `configMap.storage.mysql.deploy` | Deploy MySQL chart option | ☐ |
| N/A | **NEW** | `configMap.storage.mysql.password` | New secret object structure | ☐ |
| N/A | **NEW** | `configMap.storage.postgres.deploy` | Deploy PostgreSQL chart option | ☐ |
| N/A | **NEW** | `configMap.storage.postgres.servers` | Fallback server list | ☐ |
| N/A | **NEW** | `configMap.storage.postgres.password` | New secret object structure | ☐ |

---

### 23. CONFIGMAP - NOTIFIER

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `configMap.notifier.disable_startup_check` | ✓ OK | `configMap.notifier.disable_startup_check` | Currently: `true` | ☐ |
| `configMap.notifier.smtp.enabled` | ✓ OK | `configMap.notifier.smtp.enabled` | Currently: `true` | ☐ |
| `configMap.notifier.smtp.enabledSecret` | **REMOVED** | N/A | Use new secret structure | ☐ |
| `configMap.notifier.smtp.host` | **CHANGED** | `configMap.notifier.smtp.address` | Format: `scheme://host:port` | ☐ |
| `configMap.notifier.smtp.port` | **REMOVED** | N/A | Merged into address | ☐ |
| `configMap.notifier.smtp.timeout` | **CHANGED** | `configMap.notifier.smtp.timeout` | Format: `5s` → `5 seconds` | ☐ |
| `configMap.notifier.smtp.username` | ✓ OK | `configMap.notifier.smtp.username` | Environment variable | ☐ |
| `configMap.notifier.smtp.sender` | ✓ OK | `configMap.notifier.smtp.sender` | Environment variable | ☐ |
| `configMap.notifier.smtp.identifier` | ✓ OK | `configMap.notifier.smtp.identifier` | Currently: `thekao.cloud` | ☐ |
| `configMap.notifier.smtp.subject` | ✓ OK | `configMap.notifier.smtp.subject` | Currently: `[TheKaoCloud] {title}` | ☐ |
| N/A | **NEW** | `configMap.notifier.smtp.startup_check_address` | Email for startup check | ☐ |
| N/A | **NEW** | `configMap.notifier.smtp.disable_html_emails` | Option to disable HTML | ☐ |
| N/A | **NEW** | `configMap.notifier.smtp.disable_require_tls` | Option to disable TLS requirement | ☐ |
| N/A | **NEW** | `configMap.notifier.smtp.disable_starttls` | Option to disable STARTTLS | ☐ |
| N/A | **NEW** | `configMap.notifier.smtp.password` | New secret object structure | ☐ |
| N/A | **NEW** | `configMap.notifier.smtp.tls` | TLS configuration object | ☐ |

---

### 24. CONFIGMAP - NTP

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| N/A (not in current) | **NEW** | `configMap.ntp.address` | Format: `udp://time.cloudflare.com:123` | ☐ |
| N/A | **NEW** | `configMap.ntp.version` | NTP version (default: 4) | ☐ |
| N/A | **NEW** | `configMap.ntp.max_desync` | Max time offset allowed | ☐ |
| N/A | **NEW** | `configMap.ntp.disable_startup_check` | Disable NTP check | ☐ |
| N/A | **NEW** | `configMap.ntp.disable_failure` | Continue on NTP failure | ☐ |

---

### 25. CONFIGMAP - OIDC (MAJOR REFACTOR)

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `configMap.identity_providers.oidc.enabled` | ✓ OK | `configMap.identity_providers.oidc.enabled` | Currently: `true` | ☐ |
| `configMap.identity_providers.oidc.access_token_lifespan` | **CHANGED** | `configMap.identity_providers.oidc.lifespans.access_token` | Moved & format changed | ☐ |
| `configMap.identity_providers.oidc.authorize_code_lifespan` | **CHANGED** | `configMap.identity_providers.oidc.lifespans.authorize_code` | Moved & format changed | ☐ |
| `configMap.identity_providers.oidc.id_token_lifespan` | **CHANGED** | `configMap.identity_providers.oidc.lifespans.id_token` | Moved & format changed | ☐ |
| `configMap.identity_providers.oidc.refresh_token_lifespan` | **CHANGED** | `configMap.identity_providers.oidc.lifespans.refresh_token` | Moved & format changed | ☐ |
| `configMap.identity_providers.oidc.enable_client_debug_messages` | ✓ OK | `configMap.identity_providers.oidc.enable_client_debug_messages` | No change | ☐ |
| `configMap.identity_providers.oidc.cors.endpoints` | ✓ OK | `configMap.identity_providers.oidc.cors.endpoints` | Currently has 5 endpoints | ☐ |
| `configMap.identity_providers.oidc.cors.allowed_origins_from_client_redirect_uris` | ✓ OK | `configMap.identity_providers.oidc.cors.allowed_origins_from_client_redirect_uris` | Currently: `true` | ☐ |
| `configMap.identity_providers.oidc.clients[].id` | **CHANGED** | `configMap.identity_providers.oidc.clients[].client_id` | Field renamed | ☐ |
| `configMap.identity_providers.oidc.clients[].description` | **CHANGED** | `configMap.identity_providers.oidc.clients[].client_name` | Field renamed | ☐ |
| `configMap.identity_providers.oidc.clients[].secret` | **CHANGED** | `configMap.identity_providers.oidc.clients[].client_secret` | Now object with value/path | ☐ |
| `configMap.identity_providers.oidc.clients[].consent_mode` | **REMOVED** | `configMap.identity_providers.oidc.clients[].consent.mode` | Moved to consent object | ☐ |
| `configMap.identity_providers.oidc.clients[].pre_configured_consent_duration` | **REMOVED** | `configMap.identity_providers.oidc.clients[].consent.duration` | Moved to consent object | ☐ |
| `configMap.identity_providers.oidc.clients[].redirect_uris` | ✓ OK | `configMap.identity_providers.oidc.clients[].redirect_uris` | No change | ☐ |
| `configMap.identity_providers.oidc.clients[].grant_types` | ✓ OK | `configMap.identity_providers.oidc.clients[].grant_types` | No change | ☐ |
| `configMap.identity_providers.oidc.clients[].userinfo_signing_algorithm` | ✓ OK | `configMap.identity_providers.oidc.clients[].userinfo_signed_response_alg` | Field renamed | ☐ |
| `configMap.identity_providers.oidc.clients[].token_endpoint_auth_method` | ✓ OK | `configMap.identity_providers.oidc.clients[].token_endpoint_auth_method` | No change | ☐ |
| N/A | **NEW** | `configMap.identity_providers.oidc.hmac_secret` | New secret object structure | ☐ |
| N/A | **NEW** | `configMap.identity_providers.oidc.lifespans.device_code` | Device code lifespan | ☐ |
| N/A | **NEW** | `configMap.identity_providers.oidc.lifespans.custom` | Per-client lifespan configs | ☐ |
| N/A | **NEW** | `configMap.identity_providers.oidc.claims_policies` | Custom claims policies | ☐ |
| N/A | **NEW** | `configMap.identity_providers.oidc.scopes` | Custom scope definitions | ☐ |
| N/A | **NEW** | `configMap.identity_providers.oidc.authorization_policies` | OIDC-specific authz policies | ☐ |
| N/A | **NEW** | `configMap.identity_providers.oidc.jwks` | JWK configuration array | ☐ |
| N/A | **NEW** | `configMap.identity_providers.oidc.pushed_authorizations` | PAR configuration | ☐ |
| N/A | **NEW** | `configMap.identity_providers.oidc.clients[].lifespan` | Per-client lifespan reference | ☐ |
| N/A | **NEW** | `configMap.identity_providers.oidc.clients[].claims_policy` | Per-client claims policy | ☐ |
| N/A | **NEW** | `configMap.identity_providers.oidc.clients[].request_uris` | Request object URIs | ☐ |
| N/A | **NEW** | `configMap.identity_providers.oidc.clients[].sector_identifier_uri` | Renamed from sector_identifier | ☐ |

---

### 26. SECRET CONFIGURATION (MAJOR CHANGES)

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| `secret.existingSecret` | ✓ OK | N/A (use per-secret secret_name) | Currently: `authelia` | ☐ |
| `secret.mountPath` | **REMOVED** | N/A | Secrets use absolute paths or default | ☐ |
| `secret.jwt.key` | **REMOVED** | N/A | Use secret_name + path in JWT config | ☐ |
| `secret.ldap.key` | **REMOVED** | N/A | Use new LDAP password secret object | ☐ |
| `secret.storage.key` | **REMOVED** | N/A | Use new storage password secret object | ☐ |
| `secret.storageEncryptionKey.key` | **REMOVED** | N/A | Use new storage encryption_key object | ☐ |
| `secret.session.key` | **REMOVED** | N/A | Use new session encryption_key object | ☐ |
| `secret.duo.key` | **REMOVED** | N/A | Use new duo secret object | ☐ |
| `secret.redis.key` | **REMOVED** | N/A | Use new redis password object | ☐ |
| `secret.redis.value` | **REMOVED** | N/A | Secrets should not have inline values | ☐ |
| `secret.redisSentinel.key` | **REMOVED** | N/A | Use new sentinel password object | ☐ |
| `secret.redisSentinel.value` | **REMOVED** | N/A | Secrets should not have inline values | ☐ |
| `secret.smtp.key` | **REMOVED** | N/A | Use new smtp password object | ☐ |
| `secret.oidcPrivateKey.key` | **REMOVED** | N/A | Use jwks configuration | ☐ |
| `secret.oidcHMACSecret.key` | **REMOVED** | N/A | Use new hmac_secret object | ☐ |

**IMPORTANT:** The new secret structure is per-configuration item. Each secret-using configuration now has a nested object with:
- `disabled`: bool (disable secret management)
- `secret_name`: string or `~` (use generated secret)
- `value`: string (inline value, not recommended)
- `path`: string (file path in pod)

---

### 27. INGRESS CONFIGURATION

| Current Key Path | Status | New Key Path | Notes | Completed |
|------------------|--------|--------------|-------|-----------|
| N/A (not configured) | **NEW** | `ingress.enabled` | Enable ingress resources | ☐ |
| N/A | **NEW** | `ingress.rulesOverride` | Override ingress rules | ☐ |
| N/A | **NEW** | `ingress.className` | Ingress class name | ☐ |
| N/A | **NEW** | `ingress.gatewayAPI` | Gateway API configuration | ☐ |
| N/A | **ENHANCED** | `ingress.traefikCRD` | Enhanced Traefik CRD support | ☐ |

---

## Migration Steps

### Phase 1: Preparation (Pre-Migration)

1. ☐ **Backup Current Configuration**
   - Export current helm values: `helm get values authelia -n networking > authelia-current-values.yaml`
   - Backup secrets: `kubectl get secret authelia -n networking -o yaml > authelia-secret-backup.yaml`
   - Document all environment variables
   - Take database backup if using MySQL/PostgreSQL

2. ☐ **Review Environment Variables**
   - Document all secrets currently in the `authelia` secret
   - Note which secrets are referenced via environment variables
   - Plan secret migration strategy

3. ☐ **Test Environment Setup**
   - Create test namespace
   - Deploy test instance with new chart version
   - Validate configuration changes

### Phase 2: Configuration File Updates

1. ☐ **Update Top-Level Configuration**
   - Remove `domain` field
   - Add domain to session cookies array

2. ☐ **Update Service Configuration**
   - Remove `service.enabled`
   - Move `service.spec.loadBalancerIP` to annotations or service level
   - Move `service.spec.externalTrafficPolicy` to `service.externalTrafficPolicy`

3. ☐ **Update ConfigMap Structure**
   - Change `configMap.enabled: true` to `configMap.disabled: false`
   - Add `configMap.filters.disabled: false`
   - Update all duration formats from short (6s) to long (6 seconds)

4. ☐ **Update Server Configuration**
   - Review and add `configMap.server.endpoints` if needed for custom authz

5. ☐ **Update TOTP Configuration**
   - Change `algorithm: sha1` to `algorithm: SHA1`
   - Add `allowed_algorithms: [SHA1]`
   - Add `allowed_digits: [6]`
   - Add `allowed_periods: [30]`

6. ☐ **Update WebAuthn Configuration**
   - Move `user_verification` to `selection_criteria.user_verification`
   - Add new WebAuthn features as needed

7. ☐ **Update LDAP Configuration**
   - Rename `url` to `address` (value stays same)
   - Move `username_attribute` to `attributes.username`
   - Move `group_name_attribute` to `attributes.group_name`
   - Move `mail_attribute` to `attributes.mail`
   - Move `display_name_attribute` to `attributes.display_name`
   - Add new LDAP password secret object structure

8. ☐ **Update Access Control**
   - Move `networks` section to `configMap.definitions.network`
   - Update rules to reference network names

9. ☐ **Update Session Configuration** (CRITICAL)
   - Create `session.cookies` array
   - Add cookie with domain from old `domain` field
   - Add `default_redirection_url` to cookie
   - Rename `remember_me_duration` to `remember_me`
   - Update duration formats
   - Add `encryption_key` secret object

10. ☐ **Update Redis Configuration**
    - If using Redis, ensure `enabled: true`
    - Remove `enabledSecret: true` 
    - Add new password secret object

11. ☐ **Update Regulation Configuration**
    - Add `modes: [user]` (or include 'ip' if desired)

12. ☐ **Update Storage Configuration**
    - If using MySQL: change `host/port` to `address: tcp://host:port`
    - If using PostgreSQL: change `host/port` to `address: tcp://host:port`
    - Rename `ssl` to `tls` for PostgreSQL
    - Add encryption_key secret object
    - Add password secret objects

13. ☐ **Update Notifier Configuration**
    - Change `host/port` to `address` with scheme (e.g., `submission://host:port`)
    - Remove `enabledSecret`
    - Add password secret object

14. ☐ **Update OIDC Configuration** (COMPLEX)
    - Move lifespans to `lifespans` object
    - Update lifespan formats
    - Add `lifespans.device_code`
    - For each client:
      - Rename `id` to `client_id`
      - Rename `description` to `client_name`
      - Change `secret: string` to `client_secret: { value: string }`
      - Move consent fields to `consent` object
      - Rename `userinfo_signing_algorithm` to `userinfo_signed_response_alg`
    - Add `hmac_secret` secret object
    - Consider adding `jwks` if using certificate chains

15. ☐ **Update Secret References**
    - Create external secret or manual secret with all keys
    - Ensure secret name matches what's expected
    - Remove all inline secret values

### Phase 3: Deployment

1. ☐ **Validate Configuration**
   - Run `helm template` with new values
   - Check for any validation errors
   - Review generated manifests

2. ☐ **Deploy to Test Environment**
   - Deploy with new chart version
   - Test authentication flows
   - Test OIDC clients
   - Verify access control rules

3. ☐ **Production Deployment**
   - Schedule maintenance window
   - Deploy updated configuration
   - Monitor logs for errors
   - Test all integrations

### Phase 4: Post-Migration

1. ☐ **Verification**
   - Test all authentication methods (TOTP, WebAuthn, Duo)
   - Test all OIDC clients
   - Verify access control rules work as expected
   - Check metrics and monitoring

2. ☐ **Cleanup**
   - Remove old backup files
   - Document changes made
   - Update runbooks

3. ☐ **Optimization**
   - Review new features (e.g., identity validation, definitions)
   - Consider enabling new capabilities
   - Optimize configuration

---

## Critical Breaking Changes Summary

### ⚠️ MUST FIX (Breaking Changes)

1. **Session Cookies Array is REQUIRED**
   - Old: `domain: example.com` + `default_redirection_url: ...`
   - New: `session.cookies[].domain` + `session.cookies[].default_redirection_url`
   - **Impact:** Application will not start without this

2. **ConfigMap Enabled Logic Inverted**
   - Old: `configMap.enabled: true`
   - New: `configMap.disabled: false`
   - **Impact:** ConfigMap will not generate if wrong

3. **LDAP URL → Address**
   - Old: `url: ldap://...`
   - New: `address: ldap://...`
   - **Impact:** LDAP authentication will fail

4. **LDAP Attributes Restructured**
   - Multiple fields moved to `attributes.*`
   - **Impact:** User/group lookups will fail

5. **Storage Host/Port → Address**
   - Old: `host: postgres` + `port: 5432`
   - New: `address: tcp://postgres:5432`
   - **Impact:** Database connections will fail

6. **SMTP Host/Port → Address**
   - Old: `host: smtp.server` + `port: 587`
   - New: `address: submission://smtp.server:587`
   - **Impact:** Email notifications will fail

7. **OIDC Client Structure**
   - `id` → `client_id`
   - `description` → `client_name`
   - `secret` → `client_secret` (object)
   - Lifespan fields moved and renamed
   - **Impact:** All OIDC integrations will break

8. **Secret Management Completely Changed**
   - All secret keys must be reorganized
   - Each config section now has own secret object
   - **Impact:** All secrets must be remapped

9. **Duration Format Changed**
   - Old: `6s`, `5m`, `1h`
   - New: `6 seconds`, `5 minutes`, `1 hour`
   - **Impact:** Invalid durations will cause errors

10. **Service Structure Changed**
    - `service.enabled` removed
    - `service.spec.*` fields moved up
    - **Impact:** Service may not configure correctly

---

## Testing Checklist

### Authentication Tests
- ☐ Username/password login
- ☐ TOTP second factor
- ☐ WebAuthn second factor  
- ☐ Duo Push second factor
- ☐ Password reset flow
- ☐ Session persistence
- ☐ Remember me functionality

### LDAP Tests
- ☐ User authentication
- ☐ Group membership resolution
- ☐ Attribute mapping (email, display name)
- ☐ Connection pooling (if enabled)

### OIDC Tests
- ☐ Tailscale OIDC login
- ☐ MinIO OIDC login
- ☐ Open-WebUI OIDC login
- ☐ PGAdmin OIDC login
- ☐ Grafana OIDC login
- ☐ Outline OIDC login
- ☐ Overseerr OIDC login
- ☐ Komga OIDC login
- ☐ Linkwarden OIDC login
- ☐ Forgejo OIDC login

### Access Control Tests
- ☐ Default deny policy
- ☐ Network-based rules (private network)
- ☐ Domain-specific rules
- ☐ Resource-based rules
- ☐ Domain regex rules
- ☐ Public bypass rules
- ☐ Admin two-factor rules

### Storage Tests
- ☐ User preferences saved
- ☐ TOTP secrets stored
- ☐ WebAuthn credentials stored
- ☐ Session data persisted

### Notifier Tests
- ☐ Password reset email sent
- ☐ TOTP registration email sent
- ☐ Email formatting correct

### Monitoring Tests
- ☐ Metrics endpoint accessible
- ☐ ServiceMonitor scraping metrics
- ☐ Health check endpoint responding
- ☐ Logs being generated

---

## Rollback Plan

### If Issues Occur During Migration

1. **Immediate Rollback Steps**
   ```bash
   # Rollback to previous release
   helm rollback authelia -n networking
   
   # Verify services restored
   kubectl get pods -n networking -l app.kubernetes.io/name=authelia
   kubectl logs -n networking -l app.kubernetes.io/name=authelia
   ```

2. **Restore Secrets if Needed**
   ```bash
   kubectl apply -f authelia-secret-backup.yaml
   ```

3. **Restore Database if Needed**
   - Follow database-specific restore procedures
   - Test authentication after restore

4. **Verify All Services**
   - Test authentication flows
   - Test OIDC clients
   - Check access control

### Root Cause Analysis
- Review helm upgrade logs
- Check pod logs for errors
- Verify configuration differences
- Document issues for retry

---

## Additional Notes

### New Features to Consider

1. **Identity Validation**
   - `identity_validation.reset_password`: JWT-based password reset
   - `identity_validation.elevated_session`: Elevated session for sensitive ops

2. **Definitions**
   - `definitions.network`: Named network definitions (cleaner than inline)
   - `definitions.user_attributes`: Custom attributes via CEL

3. **Server Endpoints**
   - `server.endpoints.authz`: Custom authz endpoint configurations
   - `server.endpoints.enable_pprof`: Developer profiling
   - `server.endpoints.enable_expvars`: Developer metrics

4. **WebAuthn Enhancements**
   - Passkey login support
   - AAGUID filtering (allow/deny specific authenticators)
   - Metadata service validation
   - Enhanced selection criteria

5. **TOTP Enhancements**
   - Allow users to choose from multiple algorithms/digits/periods
   - Better user flexibility

6. **OIDC Enhancements**
   - Per-client lifespans
   - Claims policies for custom claims
   - Custom scope definitions
   - Authorization policies per client
   - JWK-based signing
   - Pushed Authorization Requests (PAR)

7. **Pod Enhancements**
   - Horizontal Pod Autoscaling
   - Init containers support
   - Sidecar containers support
   - Command/args override for debugging

8. **Connection Pooling**
   - LDAP connection pooling for better performance

9. **Storage Enhancements**
   - PostgreSQL fallback servers
   - Encryption key management

10. **Regulation Enhancements**
    - IP-based regulation in addition to user-based

### Environment Variables to Document

From current config:
- `${SVC_AUTHELIA_ADDR}` - LoadBalancer IP
- `${SECRET_DEV_DOMAIN}` - Domain name
- `${NAS_ADDR}` - LDAP server address
- `${SECRET_AWS_SMTP_HOST}` - SMTP host
- `${SECRET_AWS_SMTP_PORT}` - SMTP port
- `${SECRET_AWS_SMTP_USERNAME}` - SMTP username
- `${SECRET_AWS_SMTP_FROM_ADDR}` - SMTP sender
- Various OIDC client secrets

All secrets are stored in the `authelia` Kubernetes secret.

### Chart Repository Update

Current:
```yaml
chart: authelia
version: 0.8.58
sourceRef:
  kind: HelmRepository
  name: authelia-charts
  namespace: flux-system
```

Update to:
```yaml
chart: authelia
version: 0.10.49
sourceRef:
  kind: HelmRepository
  name: authelia-charts
  namespace: flux-system
```

---

## Estimated Timeline

- **Phase 1 (Preparation):** 2-4 hours
- **Phase 2 (Configuration Updates):** 4-8 hours
- **Phase 3 (Deployment):** 2-4 hours
- **Phase 4 (Post-Migration):** 2-4 hours

**Total Estimated Time:** 10-20 hours

---

## Resources

- [Authelia Documentation](https://www.authelia.com/)
- [Authelia Helm Chart Repository](https://github.com/authelia/chartrepo)
- [Authelia Configuration Reference](https://www.authelia.com/configuration/prologue/introduction/)
- [Chart Changelog](https://github.com/authelia/chartrepo/releases)

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-22  
**Author:** OpenCode Migration Assistant
