# Multi-stage Dockerfile cho SIN Content API (PRJ_069)
# Giai quyet P01-04: Xay dung container chuan production bao mat voi non-root user

FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY sin_content_api/requirements.txt sin_content_api/yeu_cau_tts_vieneu.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt -r yeu_cau_tts_vieneu.txt

# Final stage
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/sin_content_api:/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Tao non-root user bao mat
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser && \
    mkdir -p /home/appuser/.cache/prj069-vieneu && \
    chown -R appuser:appgroup /home/appuser/.cache

COPY --from=builder /install /usr/local

# Trình duyệt cho Google Flow (tùy chọn, bật bằng build-arg CAI_TRINH_DUYET=1). Phiên bản khớp image đăng nhập Flow.
ARG CAI_TRINH_DUYET=0
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN if [ "$CAI_TRINH_DUYET" = "1" ]; then \
        pip install --no-cache-dir "playwright==1.63.0" && \
        python -m playwright install --with-deps chromium && \
        chmod -R a+rX /ms-playwright && \
        rm -rf /var/lib/apt/lists/*; \
    fi

COPY sin_content_api /app/sin_content_api
COPY baha_auth/src /app/baha_auth/src
COPY cong_cu_tu_dong/flow_bridge/*.py /app/cong_cu_tu_dong/flow_bridge/
COPY 09_kiem_thu_quyen/PERMISSION_REGISTRY.json 09_kiem_thu_quyen/ROLE_PERMISSION_MATRIX.csv /09_kiem_thu_quyen/

# NAS có thể giữ mode 000 từ tệp nguồn; appuser cần đọc được mã API.
RUN chown -R appuser:appgroup /app && \
    chmod -R u+rwX /app/sin_content_api/src

WORKDIR /app/sin_content_api

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
