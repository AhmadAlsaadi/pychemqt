FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    PYCHEMQT_APP=/workspace/pychemqt \
    PYCHEMQT_VENV=/opt/pychemqt-venv

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        dbus-x11 \
        fonts-dejavu-core \
        git \
        libasound2 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcairo2 \
        libcups2 \
        libdrm2 \
        libegl1 \
        libgbm1 \
        libgl1 \
        libgl1-mesa-dri \
        libnss3 \
        libpango-1.0-0 \
        libx11-xcb1 \
        libxcb-cursor0 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-randr0 \
        libxcb-render-util0 \
        libxcb-shape0 \
        libxcb-sync1 \
        libxcb-xfixes0 \
        libxcb-xinerama0 \
        libxcb-xkb1 \
        libxcomposite1 \
        libxdamage1 \
        libxkbcommon-x11-0 \
        libxrandr2 \
        libxshmfence1 \
        libxtst6 \
        novnc \
        openbox \
        pkg-config \
        procps \
        python3 \
        python3-dev \
        python3-pip \
        python3-venv \
        ripgrep \
        websockify \
        x11-utils \
        x11vnc \
        xauth \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv "$PYCHEMQT_VENV" \
    && "$PYCHEMQT_VENV/bin/pip" install --no-cache-dir --upgrade pip \
    && "$PYCHEMQT_VENV/bin/pip" install --no-cache-dir \
        CoolProp==8.0.0 \
        PyQt6==6.12.0 \
        PyQt6-WebEngine==6.140.0 \
        iapws==1.5.5 \
        matplotlib==3.11.2 \
        numdifftools==0.11.2 \
        numpy==2.4.6 \
        scipy==1.17.1

COPY start-desktop.sh /opt/pychemqt/start-desktop.sh
COPY stop-desktop.sh /opt/pychemqt/stop-desktop.sh
COPY entrypoint.sh /opt/pychemqt/entrypoint.sh

RUN chmod +x /opt/pychemqt/*.sh

WORKDIR /workspace

EXPOSE 6080

CMD ["/opt/pychemqt/entrypoint.sh"]
