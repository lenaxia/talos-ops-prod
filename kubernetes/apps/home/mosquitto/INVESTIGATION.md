# Investigation Summary: mosquitto Service Issue

## k8sgpt Finding
- **Fingerprint:** 7a9728133439bde09e2f577394235a6d9abf76bcb06f82757d48476d0ba38bd8
- **Reported Issue:** Service has no endpoints, expected labels missing on Pods
- **Reported Namespace:** utilities (INCORRECT - actual namespace is `home`)

## Actual Issue
The Service does NOT have a label mismatch problem. The actual issue is:

### Root Cause
The mosquitto pod is stuck in `ContainerCreating` state for 6+ days because the Longhorn PVC attachment is failing:

1. **Pod Status:** `mosquitto-5b544d5b57-skfq7` in namespace `home` is in `ContainerCreating` state
2. **Error:** `MountVolume.MountDevice failed for volume "pvc-aee07dd1-1cb8-4f98-9092-fbad28691c3b" : rpc error: code = InvalidArgument desc = volume pvc-aee07dd1-1cb8-4f98-9092-fbad28691c3b hasn't been attached yet`
3. **Volume State:** The Longhorn volume is stuck in `attaching` state with `shareState: starting`
4. **Engine State:** The Longhorn engine for this volume is in `stopped` state and won't start

### Evidence
```bash
# Pod status
$ kubectl get pod mosquitto-5b544d5b57-skfq7 -n home
NAME                                READY   STATUS              RESTARTS   AGE
mosquitto-5b544d5b57-skfq7          0/1     ContainerCreating   0          6d14h

# Endpoints
$ kubectl get endpoints mosquitto -n home
NAME        ENDPOINTS   AGE
mosquitto   <none>      105d

# Longhorn volume status
$ kubectl get volume pvc-aee07dd1-1cb8-4f98-9092-fbad28691c3b -n longhorn-system -o yaml
status:
  state: attaching
  shareState: starting
  robustness: unknown

# Engine status
$ kubectl get engine pvc-aee07dd1-1cb8-4f98-9092-fbad28691c3b-e-0 -n longhorn-system
NAME                                       STATE     NODE
pvc-aee07dd1-1cb8-4f98-9092-fbad28691c3b-e-0   stopped   worker-02
```

### Service and Pod Labels (CORRECT)
The Service selectors and Pod labels DO match:

**Service selectors:**
- app.kubernetes.io/controller: mosquitto
- app.kubernetes.io/instance: mosquitto
- app.kubernetes.io/name: mosquitto

**Pod labels:**
- app.kubernetes.io/controller: mosquitto ✓
- app.kubernetes.io/instance: mosquitto ✓
- app.kubernetes.io/name: mosquitto ✓

### k8sgpt Analysis Error
k8sgpt incorrectly diagnosed this as a label mismatch issue. The labels are correct. The real issue is a Longhorn volume attachment failure.

## Volume Configuration
- **PVC:** mosquitto-data (ReadWriteMany)
- **StorageClass:** longhorn
- **Volume Size:** 128Mi
- **Number of Replicas:** 3 (configured), but only 2 exist (degraded)
- **Replica Nodes:** worker-00, worker-02
- **Engine Node:** worker-02
- **Access Mode:** RWX with share enabled

## Impact
- The mosquitto MQTT broker is unavailable
- Service has no endpoints because the pod is not running (not because of labels)
- This affects any applications relying on the mosquitto broker

## Required Action
This is a Longhorn infrastructure issue, not a GitOps configuration issue. The volume is in a bad operational state and needs manual intervention:

1. Check Longhorn CSI driver logs on worker-02
2. Investigate why the engine won't start
3. May need to force-reattach the volume or recreate it (data backup first!)
4. Verify Longhorn system health

## GitOps Status
The GitOps manifests are correct. No changes are needed to:
- `/workspace/repo/kubernetes/apps/home/mosquitto/app/helm-release.yaml`
- `/workspace/repo/kubernetes/apps/home/mosquitto/app/pvc-config.yaml`
- `/workspace/repo/kubernetes/apps/home/mosquitto/app/kustomization.yaml`

The PVC correctly requests ReadWriteMany access mode and uses the longhorn storage class.
