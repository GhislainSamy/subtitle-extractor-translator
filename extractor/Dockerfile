FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

# Installer mkvtoolnix
RUN apt-get update && \
    apt-get install -y mkvtoolnix && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Créer le répertoire de travail
WORKDIR /app

# Copier les fichiers requirements
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le script
COPY extract_subtitle.py .

# Variables d'environnement par défaut
ENV WATCH_MODE=true
ENV WATCH_INTERVAL=3600
ENV SOURCE_FOLDER=/data

# Lancer le script
CMD ["python", "-u", "extract_subtitle_en.py"]
