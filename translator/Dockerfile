FROM python:3.12-slim

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
ENV PAUSE_SECONDS=30
ENV BATCH_SIZE=10
ENV COOLDOWN_SECONDS=3600

# Lancer le script
CMD ["python", "-u", "translate_srt_gemini.py"]
