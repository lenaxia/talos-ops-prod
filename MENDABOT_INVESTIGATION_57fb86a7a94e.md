# Mendabot Investigation: test-broken-image Deployment

## Finding
- **Fingerprint:** 57fb86a7a94e
- **Kind:** Pod
- **Resource:** test-broken-image-5b84cb9c9c-zqqjv
- **Namespace:** default

## Summary
The deployment `test-broken-image` is failing because it references a non-existent image (`ghcr.io/lenaxia/does-not-exist:v0.0.0`). This deployment is NOT managed by the GitOps repository and appears to be an intentional test deployment for the mendabot system.

## Investigation Details
- Deployment has label `mendabot-test: "true"`
- No Flux Kustomization manages this deployment
- No HelmRelease in namespace references it
- No manifest files found in GitOps repo
- Also found `test-crashloop` deployment with same label (intentionally exits with code 1)

## Recommended Actions
Since this is not managed by GitOps, remediation requires direct kubectl operations:
- Delete: `kubectl delete deployment test-broken-image -n default`
- Or fix image: `kubectl set image deployment/test-broken-image app=nginx:latest -n default`
- Or configure mendabot to ignore `mendabot-test: true` labeled resources

**Human review required** to determine desired handling.
