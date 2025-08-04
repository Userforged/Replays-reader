FROM python:3.10-slim

# Installation des dépendances système
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libglib2.0-0 \
    libgl1 \
    libgtk-3-0 \
    libavif-dev \
    && rm -rf /var/lib/apt/lists/*

# Installation des dépendances Python
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Créer l'utilisateur nayte avec UID/GID 1000
RUN groupadd -g 1000 nayte && \
    useradd -u 1000 -g 1000 -s /bin/bash -m nayte

WORKDIR /app