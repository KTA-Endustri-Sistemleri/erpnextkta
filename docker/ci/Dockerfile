# syntax=docker/dockerfile:1
FROM ubuntu:22.04

LABEL maintainer="KTA Endustri Sistemleri <dev@kta.com.tr>"
LABEL description="Pre-built Frappe v15 CI base image for erpnextkta automated tests"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PATH="/home/frappe/.local/bin:$PATH"

# 1. Temel Sistem Paketleri ve Node.js 20 Kurulumu
RUN echo 'Acquire::ForceIPv4 "true";' > /etc/apt/apt.conf.d/99force-ipv4 && \
    apt-get update && apt-get install -y --no-install-recommends \
    sudo \
    curl \
    git \
    build-essential \
    pkg-config \
    libmysqlclient-dev \
    python3-dev \
    python3-pip \
    python3-setuptools \
    python3-venv \
    cron \
    tzdata \
    mariadb-client \
    ca-certificates \
    gnupg && \
    ln -fs /usr/share/zoneinfo/UTC /etc/localtime && \
    dpkg-reconfigure --frontend noninteractive tzdata && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && apt-get install -y --no-install-recommends nodejs && \
    npm install -g yarn && \
    pip3 install --no-cache-dir frappe-bench && \
    useradd -m -s /bin/bash frappe && \
    echo "frappe ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

USER frappe
WORKDIR /home/frappe

# 2. Frappe Bench (v15) Başlatma ve Açık Bağımlılıkların Önceden Klonlanması
RUN bench init --frappe-branch version-15 --skip-redis-config-generation --skip-assets /home/frappe/frappe-bench && \
    cd /home/frappe/frappe-bench && \
    bench get-app payments --branch version-15 && \
    bench get-app hrms --branch version-15 && \
    bench get-app erpnext https://github.com/frappe/erpnext --branch version-15 && \
    bench get-app https://github.com/Framras/trtaxoffices.git --branch version-15 && \
    bench get-app https://github.com/Framras/trtcmb.git --branch version-15 && \
    bench get-app https://github.com/Framras/trebelge.git --branch version-15 && \
    bench setup requirements --dev && \
    ./env/bin/pip install --no-cache-dir --force-reinstall 'setuptools<81' && \
    ./env/bin/pip install --no-cache-dir tzdata && \
    git config --global --add safe.directory '*'

USER root
WORKDIR /home/frappe/frappe-bench

CMD ["/bin/bash"]
