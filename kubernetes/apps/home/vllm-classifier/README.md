# vLLM Classifier Deployment

This is a vLLM deployment optimized for high-speed text classification with the following characteristics:

## Optimization Details

- **Max sequences**: 30 (for high parallelism)
- **Max model length**: 1000 tokens (optimized for short text)
- **GPU memory utilization**: 95% (aggressive for 3090 24GB)
- **Tensor parallel size**: 1 (single GPU deployment)
- **Torch compile**: Enabled (for performance)
- **Model**: Qwen/Qwen2.5-3B-Instruct (3B parameters)
- **GPU allocation**: Automatically uses any available GPU

## Required Configuration

Before deploying, you must update the following values in `helm-release.yaml`:

### Service IP (Line 109)
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
