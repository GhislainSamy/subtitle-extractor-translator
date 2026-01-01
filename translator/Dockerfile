FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

# Installer ffmpeg pour conversion ASS/SSA → SRT
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Créer le répertoire de travail
WORKDIR /app

# Copier les fichiers requirements
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le script
COPY translate_srt_gemini.py .

# Variables d'environnement par défaut
ENV WATCH_MODE=true
ENV WATCH_INTERVAL=3600
ENV SOURCE_FOLDER=/data
ENV PAUSE_SECONDS=10
ENV BATCH_SIZE=50
ENV COOLDOWN_SECONDS=3600

# Variables de nettoyage (défaut: false = on garde tout)
ENV DELETE_PROGRESS_AFTER=false
ENV DELETE_SOURCE_AFTER=false
ENV DELETE_CONVERTED_AFTER=false

# Lancer le script
CMD ["python", "-u", "translate_srt_gemini.py"]