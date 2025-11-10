# Authelia Helm Chart Configuration Migration (v3 to v4)

**Date:** 2025-11-09  
**Current Chart:** v0.8.58 (uses v3 structure)  
**Target Chart:** v0.10.49 (uses v4 structure)

## Overview

The current Authelia helm release is using the **old v3 chart structure** which has been significantly refactored in v4. This requires a comprehensive configuration migration.

## Key Structural Changes

### 1. Top-Level Structure Changes

#### OLD (v3 - Current):
```yaml
values:
  image:
    repository: ghcr.io/authelia/authelia
    tag: 4.37.5
  
  redis:
    enabled: true
    architecture: replication
  
  service:
    enabled: true
    type: LoadBalancer
  
  pod:
    kind: Deployment
    replicas: 1
  
  configMap:
    enabled: true
    log:
      level: debug
    # ... all config under configMap
  
  secret:
    existingSecret: authelia
    jwt:
      key: JWT_SECRET
    # ... flat secret structure
```

#### NEW (v4 - Target):
```yaml
values:
  image:
    registry: ghcr.io
    repository: authelia/authelia
    tag: 4.39.14
  
  service:
    type: LoadBalancer
    port: 80
  
  pod:
    kind: Deployment
    replicas: 1
  
  configMap:
    disabled: false
    key: configuration.yaml
    
    # All config now directly under configMap (not nested)
    log:
      level: debug
    
    server:
      port: 9091
      path: ''
    
    session:
      name: authelia_session
      cookies:
        - domain: example.com
          authelia_url: https://auth.example.com
    
    authentication_backend:
      ldap:
        enabled: true
    
    storage:
      local:
        enabled: true
  
  secret:
    existingSecret: ''
    mountPath: /secrets
    
    # Secrets now use nested structure with value/path
```

### 2. Secret Structure Migration

#### OLD Structure (v3):
```yaml
secret:
  existingSecret: authelia
  jwt:
    key: JWT_SECRET
  ldap:
    key: LDAP_PASSWORD
  storage:
    key: STORAGE_PASSWORD
  storageEncryptionKey:
    key: STORAGE_ENCRYPTION_KEY
  session:
    key: SESSION_SECRET
  duo:
    key: DUO_SECRET_KEY
  redis:
    key: REDIS_PASSWORD
    value: ${SECRET_REDIS_PASSWORD}
  redisSentinel:
    key: REDIS_SENTINEL_PASSWORD
  smtp:
    key: SMTP_PASSWORD
  oidcPrivateKey:
    key: OIDC_ISSUER_PRIVATE_KEY
  oidcHMACSecret:
    key: OIDC_HMAC_SECRET
```

#### NEW Structure (v4):
Secrets are now configured **within each section** of the config:

```yaml
configMap:
  identity_validation:
    reset_password:
      secret:
        disabled: false
        secret_name: ~  # Uses generated secret
        value: ''       # Or provide value here
        path: 'identity_validation.reset_password.jwt.hmac.key'
  
  authentication_backend:
    ldap:
      password:
        disabled: false
        secret_name: ~
        value: ''
        path: 'authentication.ldap.password.txt'
  
  session:
    encryption_key:
      disabled: false
      secret_name: ~
      value: ''
      path: 'session.encryption.key'
    
    redis:
      password:
        disabled: false
        secret_name: ~
        value: ''
        path: 'session.redis.password.txt'
      
      high_availability:
        password:
          disabled: false
          secret_name: ~
          value: ''
          path: 'session.redis.sentinel.password.txt'
  
  storage:
    encryption_key:
      disabled: false
      secret_name: ~
      value: ''
      path: 'storage.encryption.key'
    
    mysql:
      password:
        disabled: false
        secret_name: ~
        value: ''
        path: 'storage.mysql.password.txt'
    
    postgres:
      password:
        disabled: false
        secret_name: ~
        value: ''
        path: 'storage.postgres.password.txt'
  
  notifier:
    smtp:
      password:
        disabled: false
        secret_name: ~
        value: ''
        path: 'notifier.smtp.password.txt'
  
  identity_providers:
    oidc:
      hmac_secret:
        disabled: false
        secret_name: ~
        value: ''
        path: 'identity_providers.oidc.hmac.key'
  
  duo_api:
    secret:
      disabled: false
      secret_name: ~
      value: ''
      path: 'duo.key'

secret:
  existingSecret: ''  # Can still use existing secret
  mountPath: /secrets
```

### 3. Redis Configuration Changes

#### OLD (v3):
```yaml
redis:
  enabled: true
  architecture: replication
  sentinel:
    enabled: true
  replica:
    replicaCount: 2
  auth:
    enabled: false

configMap:
  session:
    redis:
      enabled: true
      enabledSecret: true
      host: authelia-redis-master.networking.svc.cluster.local
      port: 6379
      high_availability:
        enabled: true
        enabledSecret: false
        sentinel_name: mymaster
        nodes:
          - host: authelia-redis-replicas.networking.svc.cluster.local
            port: 26379
```

#### NEW (v4):
```yaml
# Redis subchart (if deploying)
redis:
  architecture: standalone  # or replication
  auth:
    enabled: false
    sentinel: true
  master:
    persistence:
      enabled: false
  replica:
    replicaCount: 3
    persistence:
      enabled: false

# Session redis config
configMap:
  session:
    redis:
      enabled: true
      deploy: false  # Set to true to deploy subchart
      host: redis.databases.svc.cluster.local
      port: 6379
      username: ''
      password:
        disabled: false
        secret_name: ~
        value: ''
        path: 'session.redis.password.txt'
      database_index: 0
      maximum_active_connections: 8
      minimum_idle_connections: 0
      
      high_availability:
        enabled: true
        sentinel_name: mysentinel
        username: ''
        password:
          disabled: false
          secret_name: ~
          value: ''
          path: 'session.redis.sentinel.password.txt'
        nodes:
          - host: sentinel-0.databases.svc.cluster.local
            port: 26379
        route_by_latency: false
        route_randomly: false
```

### 4. Storage Configuration Changes

#### OLD (v3):
```yaml
configMap:
  storage:
    local:
      enabled: true
      path: /config/db.sqlite3
    
    mysql:
      enabled: false
      host: ${RURI_ADDR}
      port: 3306
      database: authelia-k3s
      username: authelia-k3s
      password: authelia
      timeout: 10s
    
    postgres:
      enabled: false
      host: defaultpg-rw.databases.svc.cluster.local
      port: 5432
      database: authelia
      schema: public
      username: authelia
      password: authelia
      ssl:
        mode: disable
```

#### NEW (v4):
```yaml
configMap:
  storage:
    encryption_key:
      disabled: false
      secret_name: ~
      value: ''
      path: 'storage.encryption.key'
    
    local:
      enabled: true
      path: /config/db.sqlite3
    
    mysql:
      enabled: false
      deploy: false
      address: 'tcp://mysql.databases.svc.cluster.local:3306'
      timeout: '5 seconds'
      database: authelia
      username: authelia
      password:
        disabled: false
        secret_name: ~
        value: ''
        path: 'storage.mysql.password.txt'
      tls:
        enabled: false
        server_name: ''
        skip_verify: false
        minimum_version: TLS1.2
        maximum_version: TLS1.3
    
    postgres:
      enabled: false
      deploy: false
      address: 'tcp://postgres.databases.svc.cluster.local:5432'
      servers: []
      timeout: '5 seconds'
      database: authelia
      schema: public
      username: authelia
      password:
        disabled: false
        secret_name: ~
        value: ''
        path: 'storage.postgres.password.txt'
      tls:
        enabled: false
        server_name: ''
        skip_verify: false
        minimum_version: TLS1.2
        maximum_version: TLS1.3
```

### 5. OIDC Configuration Changes

#### OLD (v3):
```yaml
configMap:
  identity_providers:
    oidc:
      enabled: true
      access_token_lifespan: 1h
      authorize_code_lifespan: 1m
      id_token_lifespan: 1h
      refresh_token_lifespan: 90m
      
      clients:
      - id: myapp
        secret: ${SECRET}
        authorization_policy: one_factor
```

#### NEW (v4):
```yaml
configMap:
  identity_providers:
    oidc:
      enabled: true
      
      hmac_secret:
        disabled: false
        secret_name: ~
        value: ''
        path: 'identity_providers.oidc.hmac.key'
      
      lifespans:
        access_token: '1 hour'
        refresh_token: '1 hour and 30 minutes'
        id_token: '1 hour'
        authorize_code: '1 minute'
        device_code: '10 minutes'
        custom: {}
      
      claims_policies: {}
      scopes: {}
      
      enforce_pkce: 'public_clients_only'
      enable_pkce_plain_challenge: false
      
      clients:
      - client_id: myapp
        client_name: My Application
        client_secret:
          value: '${SECRET}'
          # OR path: '/secrets/oidc.client.myapp.value'
        authorization_policy: one_factor
        consent_mode: implicit
        pre_configured_consent_duration: '30 days'
```

### 6. LDAP Configuration Changes

#### OLD (v3):
```yaml
configMap:
  authentication_backend:
    ldap:
      enabled: true
      implementation: custom
      url: ldap://${NAS_ADDR}
      timeout: 5s
      base_dn: dc=kao,dc=family
      username_attribute: uid
      additional_users_dn: cn=users
      users_filter: (&({username_attribute}={input})(objectClass=posixAccount))
      additional_groups_dn: cn=groups
      groups_filter: (&(member={dn})(objectclass=posixGroup))
      group_name_attribute: cn
      mail_attribute: mail
      display_name_attribute: displayName
      user: uid=autheliauser,cn=users,dc=kao,dc=family
```

#### NEW (v4):
```yaml
configMap:
  authentication_backend:
    password_reset:
      disable: false
      custom_url: ''
    
    password_change:
      disable: false
    
    refresh_interval: '5 minutes'
    
    ldap:
      enabled: true
      implementation: custom
      address: 'ldap://${NAS_ADDR}'
      timeout: '5 seconds'
      start_tls: false
      
      tls:
        server_name: ''
        skip_verify: false
        minimum_version: TLS1.2
        maximum_version: TLS1.3
      
      pooling:
        enable: false
        count: 5
        retries: 2
        timeout: '10 seconds'
      
      base_dn: dc=kao,dc=family
      additional_users_dn: cn=users
      users_filter: '(&({username_attribute}={input})(objectClass=posixAccount))'
      additional_groups_dn: cn=groups
      groups_filter: '(&(member={dn})(objectclass=posixGroup))'
      
      permit_referrals: false
      permit_unauthenticated_bind: false
      permit_feature_detection_failure: false
      
      user: uid=autheliauser,cn=users,dc=kao,dc=family
      
      password:
        disabled: false
        secret_name: ~
        value: ''
        path: 'authentication.ldap.password.txt'
      
      attributes:
        distinguished_name: ''
        username: ''
        display_name: ''
        mail: ''
        member_of: ''
        group_name: ''
        extra: {}
```

### 7. Session Configuration Changes

#### OLD (v3):
```yaml
configMap:
  session:
    name: authelia_auth_session
    same_site: lax
    expiration: 1h
    inactivity: 5m
    remember_me_duration: 1M
```

#### NEW (v4):
```yaml
configMap:
  session:
    name: authelia_session
    same_site: lax
    expiration: '1 hour'
    inactivity: '5 minutes'
    remember_me: '1 month'
    
    encryption_key:
      disabled: false
      secret_name: ~
      value: ''
      path: 'session.encryption.key'
    
    cookies:
      - domain: 'example.com'
        subdomain: 'auth'
        path: ''
        default_redirection_url: 'https://www.example.com'
        name: ''
        same_site: ''
        expiration: ''
        inactivity: ''
```

### 8. Notifier Configuration Changes

#### OLD (v3):
```yaml
configMap:
  notifier:
    disable_startup_check: true
    smtp:
      enabled: true
      enabledSecret: true
      host: ${SECRET_AWS_SMTP_HOST}
      port: ${SECRET_AWS_SMTP_PORT}
      timeout: 5s
      username: ${SECRET_AWS_SMTP_USERNAME}
      sender: ${SECRET_AWS_SMTP_FROM_ADDR}
      identifier: thekao.cloud
      subject: "[TheKaoCloud] {title}"
```

#### NEW (v4):
```yaml
configMap:
  notifier:
    disable_startup_check: true
    
    smtp:
      enabled: true
      address: 'submission://smtp.mail.svc.cluster.local:587'
      timeout: '5 seconds'
      sender: 'Authelia <admin@example.com>'
      identifier: localhost
      subject: '[Authelia] {title}'
      startup_check_address: 'test@authelia.com'
      disable_html_emails: false
      disable_require_tls: false
      disable_starttls: false
      username: ''
      password:
        disabled: false
        secret_name: ~
        value: ''
        path: 'notifier.smtp.password.txt'
      tls:
        server_name: ''
        skip_verify: false
        minimum_version: TLS1.2
        maximum_version: TLS1.3
```

### 9. Server Configuration

#### OLD (v3):
```yaml
# No explicit server config in v3, used defaults
```

#### NEW (v4):
```yaml
configMap:
  server:
    port: 9091
    path: ''  # Single level path, alphanumeric only
    asset_path: ''
    
    headers:
      csp_template: ''
    
    buffers:
      read: 4096
      write: 4096
    
    timeouts:
      read: '6 seconds'
      write: '6 seconds'
      idle: '30 seconds'
    
    endpoints:
      enable_pprof: false
      enable_expvars: false
      
      # NEW: Automatic authz endpoint configuration
      automatic_authz_implementations: []
      # - 'AuthRequest'
      # - 'ExtAuthz'
      # - 'ForwardAuth'
      
      # OR manual configuration
      authz: {}
```

## Critical Migration Steps

### Step 1: Update Secret Management

The current configuration uses `existingSecret: authelia` with flat key structure. In v4, you have two options:

**Option A: Use existing secret with new paths**
```yaml
secret:
  existingSecret: 'authelia'
  mountPath: /secrets

configMap:
  # For each secret, reference the existing secret
  authentication_backend:
    ldap:
      password:
        disabled: true  # Manage externally
```

**Option B: Let chart manage secrets (recommended for shadow)**
```yaml
secret:
  existingSecret: ''
  mountPath: /secrets

configMap:
  authentication_backend:
    ldap:
      password:
        disabled: false
        secret_name: ~  # Auto-generate
        value: '${LDAP_PASSWORD}'  # Or provide value
        path: 'authentication.ldap.password.txt'
```

### Step 2: Update Redis Configuration

```yaml
# If using embedded Redis (deploy: true)
redis:
  architecture: standalone
  auth:
    enabled: false
    sentinel: true
  master:
    persistence:
      enabled: false
  replica:
    replicaCount: 2
    persistence:
      enabled: false

configMap:
  session:
    redis:
      enabled: true
      deploy: true  # Deploy embedded Redis
      host: '{{ include "authelia.redis.host" . }}'
      port: 6379
      high_availability:
        enabled: true
        sentinel_name: mymaster
```

### Step 3: Update Session Cookies

The new v4 chart requires the `cookies` array:

```yaml
configMap:
  session:
    name: authelia_auth_session
    same_site: lax
    expiration: '1 hour'
    inactivity: '5 minutes'
    remember_me: '1 month'
    
    cookies:
      - domain: '${SECRET_DEV_DOMAIN}'
        subdomain: 'authelia'
        default_redirection_url: 'https://authelia.${SECRET_DEV_DOMAIN}'
```

### Step 4: Update OIDC Clients

```yaml
configMap:
  identity_providers:
    oidc:
      enabled: true
      
      hmac_secret:
        disabled: false
        secret_name: ~
        value: ''
        path: 'identity_providers.oidc.hmac.key'
      
      lifespans:
        access_token: '1 hour'
        authorize_code: '1 minute'
        id_token: '1 hour'
        refresh_token: '90 minutes'
      
      cors:
        endpoints:
          - authorization
          - token
          - revocation
          - introspection
          - userinfo
        allowed_origins_from_client_redirect_uris: true
      
      clients:
        - client_id: tailscale
          client_name: Tailscale
          client_secret:
            value: '${SECRET_TAILSCALE_OAUTH_CLIENT_SECRET}'
          authorization_policy: one_factor
          consent_mode: implicit
          pre_configured_consent_duration: '1 year'
          scopes:
            - openid
            - profile
            - email
          redirect_uris:
            - https://login.tailscale.com/a/oauth_response
          userinfo_signed_response_alg: none
```

## Migration Checklist

- [ ] Review all secret paths and update secret management strategy
- [ ] Update Redis configuration to new structure
- [ ] Add session cookies array
- [ ] Update OIDC client configuration format
- [ ] Update storage configuration (address format)
- [ ] Update LDAP configuration (address format, new options)
- [ ] Update notifier configuration (address format)
- [ ] Add server configuration section
- [ ] Update duration formats (add units: '1 hour' not '1h')
- [ ] Test with shadow instance before production

## Compatibility Notes

1. **Backward Compatibility:** The v4 chart can still use `existingSecret` for secrets
2. **Duration Format:** New format requires units ('1 hour' vs '1h')
3. **Address Format:** Many services now use full address format: `tcp://host:port` or `ldap://host`
4. **Secret Paths:** All secrets now have explicit path configuration
5. **OIDC:** Client configuration uses `client_id`, `client_name`, `client_secret` structure

## Testing Strategy

1. Create shadow instance with new v4 configuration
2. Validate all secrets are properly mounted
3. Test LDAP authentication
4. Test Redis session storage
5. Test OIDC clients
6. Verify access control rules
7. Test 2FA flows

## References

- [Authelia Helm Chart v4 Values](https://github.com/authelia/chartrepo/blob/master/charts/authelia/values.yaml)
- [Authelia Configuration Reference](https://www.authelia.com/configuration/prologue/introduction/)
- [Authelia v4.38 Breaking Changes](https://www.authelia.com/blog/release-notes-4.38/)