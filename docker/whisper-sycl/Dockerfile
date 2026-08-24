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

FROM intel/oneapi:2025.0.1-0-devel-ubuntu24.04
WORKDIR /app
COPY --from=builder /app/whisper.cpp/build/src/libwhisper.so* /usr/local/lib/
COPY --from=builder /app/whisper.cpp/build/ggml/src/libggml.so* /usr/local/lib/
COPY --from=builder /app/whisper.cpp/build/ggml/src/ggml-sycl/libggml-sycl.so* /usr/local/lib/
COPY --from=builder /app/whisper.cpp/build/ggml/src/ggml-base/libggml-base.so* /usr/local/lib/
COPY --from=builder /app/whisper.cpp/build/ggml/src/ggml-cpu/libggml-cpu.so* /usr/local/lib/
RUN ldconfig
COPY --from=builder /app/whisper.cpp/build/bin/whisper-server .
COPY --from=builder /app/whisper.cpp/models/ggml-base.en.bin ./models/
COPY --from=builder /app/whisper.cpp/models/ggml-small.en.bin ./models/
ENV WHISPER_MODEL=small.en \
    SYCL_CACHE_PERSISTENT=1 \
    SYCL_DEVICE_ALLOWLIST=BackendName:level_zero
EXPOSE 8910
ENTRYPOINT ["/bin/sh", "-c", "exec ./whisper-server -m /app/models/ggml-${WHISPER_MODEL}.bin \
    --host 0.0.0.0 --port 8910 --suppress-nst -l en ${WHISPER_EXTRA_ARGS}"]
