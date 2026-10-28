FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    novnc \
    websockify \
    x11-utils \
    x11vnc \
    xvfb \
    && python -m pip install --no-cache-dir "playwright==1.63.0" \
    && rm -rf /var/lib/apt/lists/*

COPY ha_tang/nas_flow_login/dang_nhap_flow.py /app/dang_nhap_flow.py
COPY cong_cu_tu_dong/flow_bridge/profile_guard.py /app/profile_guard.py
COPY ha_tang/nas_flow_login/khoi_dong.sh /usr/local/bin/khoi_dong.sh

RUN groupadd --gid 10001 prj069 && \
    useradd --uid 10001 --gid prj069 --create-home --shell /usr/sbin/nologin prj069 && \
    mkdir -p /var/lib/prj069/flow_profiles && \
    chown -R 10001:10001 /app /var/lib/prj069 /usr/local/bin/khoi_dong.sh && \
    chmod 0755 /app /usr/local/bin/khoi_dong.sh && \
    chmod 0644 /app/dang_nhap_flow.py /app/profile_guard.py

ENV DISPLAY=:99
USER 10001:10001

ENTRYPOINT ["/usr/local/bin/khoi_dong.sh"]
