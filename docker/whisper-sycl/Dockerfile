# whisper.cpp server built with Intel oneAPI SYCL for Intel iGPU/Arc (Level-Zero).
# Used with the ghcr.io/ser/wyoming-whisper-api-client sidecar for Home Assistant.
FROM intel/oneapi:2025.0.1-0-devel-ubuntu24.04 AS builder
ARG WHISPER_CPP_VERSION=1.7.4
WORKDIR /app
RUN git clone --depth 1 --branch v${WHISPER_CPP_VERSION} https://github.com/ggerganov/whisper.cpp
WORKDIR /app/whisper.cpp
RUN cmake -B build -DGGML_SYCL=ON -DGGML_SYCL_F16=ON -DCMAKE_C_COMPILER=icx -DCMAKE_CXX_COMPILER=icpx \
    && cmake --build build --config Release -j"$(nproc)"
RUN ./models/download-ggml-model.sh base.en && ./models/download-ggml-model.sh small.en

FROM intel/oneapi:2025.0.1-0-runtime-ubuntu24.04
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates gnupg \
    && curl -fsSL https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB \
        | gpg --dearmor -o /usr/share/keyrings/intel-oneapi-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/intel-oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main" \
        > /etc/apt/sources.list.d/oneAPI.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        intel-opencl-icd intel-level-zero-gpu level-zero \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/whisper.cpp/build/bin/whisper-server .
COPY --from=builder /app/whisper.cpp/models/ggml-base.en.bin ./models/
COPY --from=builder /app/whisper.cpp/models/ggml-small.en.bin ./models/
ENV WHISPER_MODEL=small.en \
    SYCL_CACHE_PERSISTENT=1 \
    SYCL_DEVICE_ALLOWLIST=BackendName:level_zero
EXPOSE 8910
ENTRYPOINT ["/bin/sh", "-c", "exec ./whisper-server -m /app/models/ggml-${WHISPER_MODEL}.bin \
    --host 0.0.0.0 --port 8910 --suppress-nst -l en ${WHISPER_EXTRA_ARGS}"]
