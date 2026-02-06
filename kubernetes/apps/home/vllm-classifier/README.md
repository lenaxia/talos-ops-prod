# vLLM Classifier Deployment

This is a vLLM deployment optimized for high-speed text classification with the following characteristics:

## Optimization Details

- **Max sequences**: 30 (for high parallelism)
- **Max model length**: 1000 tokens (optimized for short text)
- **GPU memory utilization**: 95% (aggressive for 3090 24GB)
- **Tensor parallel size**: 1 (single GPU deployment)
- **Torch compile**: Enabled (for performance)

## Required Configuration

Before deploying, you must update the following values in `helm-release.yaml`:

### 1. Model Name (Line 47)
Replace `YOUR_MODEL_NAME_HERE` with your actual 3B model from Hugging Face.
Example models for classification:
- `BAAI/bge-large-en-v1.5` (text embeddings)
- `intfloat/e5-large-v2` (text embeddings)
- `microsoft/DialoGPT-large` (conversational)
- `facebook/opt-1.3b` (general purpose)
- Any other 3B parameter model

### 2. GPU UUID (Line 77)
Replace `YOUR_3090_GPU_UUID_HERE` with your actual 3090 GPU UUID.

Get the UUID by running:
```bash
nvidia-smi -L
```

Example output: `GPU-755d8528-c8c7-5fd4-f441-f061368f4547`

### 3. Service IP (Line 109)
Update `${SVC_VLLM_CLASSIFIER_IP}` in your config.yaml or cluster secrets if you want a specific LoadBalancer IP.

## Performance Tuning

The current configuration is optimized for:
- 20-30 parallel sequences
- 150 tokens or less per sequence
- < 500 tokens of context

If you need to adjust performance:

### Increase throughput (but higher latency):
- Increase `--max-num-seqs` (e.g., 50)
- Increase `--max-model-len` if needed

### Decrease latency (but lower throughput):
- Decrease `--max-num-seqs` (e.g., 15-20)
- Keep `--max-model-len` as low as possible

### Memory issues:
- Reduce `--gpu-memory-utilization` (e.g., 0.85)
- Reduce `--max-num-seqs`
- Increase memory limits in the resources section

## API Usage

Once deployed, the vLLM OpenAI-compatible API will be available at:

```
http://<SERVICE-IP>:8000/v1
```

Example usage:
```bash
curl http://<SERVICE-IP>:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "classifier",
    "messages": [{"role": "user", "content": "Your text here"}]
  }'
```

## Storage

- 20Gi PVC for Hugging Face model cache
- 8Gi /dev/shm for CUDA operations
