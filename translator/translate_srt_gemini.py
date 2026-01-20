import os
import json
import time
import sys
import subprocess
import shutil
import re
import pysrt
import pytz
from dotenv import load_dotenv
from google import genai
from google.genai import types
from datetime import datetime, timedelta

# ==========================================
# translate_srt_gemini.py - V7 (Multi-Folders)
# ==========================================
# Nouvelles fonctionnalités V7 :
# - Support multi-folders via SOURCE_FOLDERS (JSON array)
# - Rétro-compatible avec SOURCE_FOLDER (single)
# - Stats agrégées sur tous les folders
# - Log du folder en cours de traitement
# ==========================================

load_dotenv()

# =========================
# CONFIG
# =========================
SOURCE_FOLDERS_JSON = os.getenv("SOURCE_FOLDERS", "[]")
SOURCE_FOLDER_LEGACY = os.getenv("SOURCE_FOLDER")
PAUSE_SECONDS = int(os.getenv("PAUSE_SECONDS", 10))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 50))
WATCH_MODE = os.getenv("WATCH_MODE", "true").lower() == "true"
WATCH_INTERVAL = int(os.getenv("WATCH_INTERVAL", 3600))
LOG_FILE = os.getenv("LOG_FILE", None)  # None = console uniquement
LOG_FILE_MAX_SIZE_MB = int(os.getenv("LOG_FILE_MAX_SIZE_MB", 10))  # Taille max par fichier (MB)
LOG_FILE_BACKUP_COUNT = int(os.getenv("LOG_FILE_BACKUP_COUNT", 2))  # Nombre de backups

# Parse SOURCE_FOLDERS
try:
    SOURCE_FOLDERS = json.loads(SOURCE_FOLDERS_JSON)
    if not SOURCE_FOLDERS and SOURCE_FOLDER_LEGACY:
        # Rétro-compatibilité : si SOURCE_FOLDERS vide, utiliser SOURCE_FOLDER
        SOURCE_FOLDERS = [SOURCE_FOLDER_LEGACY]
except json.JSONDecodeError:
    if SOURCE_FOLDER_LEGACY:
        SOURCE_FOLDERS = [SOURCE_FOLDER_LEGACY]
    else:
        SOURCE_FOLDERS = []

# Variables de nettoyage (défaut: false = on garde tout)
DELETE_PROGRESS_AFTER = os.getenv("DELETE_PROGRESS_AFTER", "false").lower() == "true"
DELETE_SOURCE_AFTER = os.getenv("DELETE_SOURCE_AFTER", "false").lower() == "true"
DELETE_CONVERTED_AFTER = os.getenv("DELETE_CONVERTED_AFTER", "false").lower() == "true"
DELETE_NO_SUBTITLE_MARKER = os.getenv("DELETE_NO_SUBTITLE_MARKER", "false").lower() == "true"

API_KEYS = json.loads(os.getenv("GEMINI_API_KEYS") or "[]")
MODELS = json.loads(os.getenv("GEMINI_MODELS") or "[]")

COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", 3600))
RETRY_EMPTY_RESPONSE_DELAY = 10

if not API_KEYS or not MODELS:
    raise RuntimeError("GEMINI_API_KEYS ou GEMINI_MODELS manquant dans .env")

VIDEO_EXTENSIONS = (".mkv", ".mp4", ".avi", ".mov", ".m4v", ".webm", ".flv", ".wmv")
SUBTITLE_EXTENSIONS = ["srt", "ass", "sup", "ssa", "vtt", "sub"]

PARIS_TZ = pytz.timezone('Europe/Paris')

# Configuration du logger
import logging
from logging.handlers import RotatingFileHandler

logger = None

def setup_logger():
    """Configure le logger avec rotation automatique si LOG_FILE est défini"""
    global logger
    
    logger = logging.getLogger('subtitle_translator')
    logger.setLevel(logging.INFO)
    
    # Format du log
    formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    
    # Handler console (toujours actif)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Handler fichier avec rotation (si LOG_FILE configuré)
    if LOG_FILE:
        try:
            # Rotation automatique selon configuration
            # backupCount = nombre de backups (total fichiers = backupCount + 1)
            # maxBytes en bytes (config en MB)
            file_handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=LOG_FILE_MAX_SIZE_MB * 1024 * 1024,  # Conversion MB → bytes
                backupCount=LOG_FILE_BACKUP_COUNT,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
            # Log de config au démarrage
            total_files = LOG_FILE_BACKUP_COUNT + 1
            max_space_mb = total_files * LOG_FILE_MAX_SIZE_MB
            logger.info(f"📝 Log fichier activé: {LOG_FILE}")
            logger.info(f"   Rotation: {LOG_FILE_MAX_SIZE_MB} MB/fichier, {total_files} fichiers max ({max_space_mb} MB total)")
        except Exception as e:
            print(f"[ERROR] Impossible de créer le fichier de log {LOG_FILE}: {e}")


def log(msg):
    """Logger avec timestamp et rotation automatique"""
    if logger is None:
        setup_logger()
    logger.info(msg)


# =========================
# COOLDOWN MANAGEMENT
# =========================
cooldowns = {}


def now():
    return time.time()


def is_available(model, key_index):
    return now() >= cooldowns.get((model, key_index), 0)


def block_key(model, key_index):
    cooldowns[(model, key_index)] = now() + COOLDOWN_SECONDS
    log(f"🔒 clé #{key_index + 1} ({model}) bloquée → retry dans {COOLDOWN_SECONDS}s")


def any_key_available():
    for model in MODELS:
        for idx in range(len(API_KEYS)):
            if is_available(model, idx):
                return True
    return False


def calculate_next_quota_reset():
    """Calcule le prochain reset de quota : 11h05 heure de France"""
    now_paris = datetime.now(PARIS_TZ)
    
    if now_paris.hour > 11 or (now_paris.hour == 11 and now_paris.minute >= 5):
        next_reset = (now_paris + timedelta(days=1)).replace(hour=11, minute=5, second=0, microsecond=0)
    else:
        next_reset = now_paris.replace(hour=11, minute=5, second=0, microsecond=0)
    
    sleep_seconds = (next_reset - now_paris).total_seconds()
    return next_reset, sleep_seconds


def wait_for_quota_reset():
    """Attend jusqu'à 11h05 (reset du quota API Gemini)"""
    next_reset, sleep_seconds = calculate_next_quota_reset()
    
    log("❌ Toutes les clés API bloquées (quota dépassé)")
    log(f"⏰ Prochaine tentative : {next_reset.strftime('%d/%m/%Y à %H:%M')} (heure de France)")
    log(f"💤 Agent en veille pendant {sleep_seconds/3600:.1f}h...")
    
    time.sleep(sleep_seconds)
    log("✨ Réveil de l'agent - Quota API réinitialisé")
    cooldowns.clear()


# =========================
# GEMINI CALL
# =========================
def call_gemini(model, api_key, text, retry_count=0):
    """Appelle l'API Gemini avec system_instruction optimisé"""
    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=model,
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction=(
                "Tu es un traducteur professionnel de sous-titres. "
                "Traduis de l'anglais vers le français naturel. "
                "Une ligne traduite par ligne. "
                "Ne numérote pas."
            )
        )
    )

    if not response or not response.text or response.text.strip() == "":
        if retry_count < 1:
            log(f"  ⚠️ Réponse vide, nouvelle tentative dans {RETRY_EMPTY_RESPONSE_DELAY}s...")
            time.sleep(RETRY_EMPTY_RESPONSE_DELAY)
            return call_gemini(model, api_key, text, retry_count + 1)
        else:
            raise RuntimeError("Réponse vide après 2 tentatives")

    return response.text


# =========================
# TRANSLATE BATCH
# =========================
def translate_batch(texts):
    while True:
        for model in MODELS:
            for key_index, api_key in enumerate(API_KEYS):
                if not is_available(model, key_index):
                    continue

                log(f"🔑 utilisation clé #{key_index + 1} | modèle {model}")

                try:
                    translated = call_gemini(model, api_key, "\n".join(texts))
                    return translated, model, key_index

                except Exception as e:
                    msg = str(e).lower()

                    if "quota" in msg or "429" in msg or "rate" in msg:
                        log(f"  ⚠️ Quota dépassé pour clé #{key_index + 1}")
                        block_key(model, key_index)
                    elif "réponse vide" in msg:
                        log(f"  ⚠️ Réponse vide après 2 tentatives - clé #{key_index + 1}")
                        block_key(model, key_index)
                    else:
                        log(f"  ⚠️ erreur clé #{key_index + 1} ({model}) : {e}")
                        block_key(model, key_index)

        if not any_key_available():
            if WATCH_MODE:
                wait_for_quota_reset()
                continue
            else:
                log("\n❌ Toutes les clés sont en cooldown.")
                log("👉 Arrêt du programme.\n")
                sys.exit(1)

        time.sleep(2)


# =========================
# FORMAT CONVERSION
# =========================
def clean_html_tags(srt_file):
    """
    Nettoie les balises HTML du fichier SRT
    (balises qui restent après conversion ASS → SRT)
    """
    import re
    
    try:
        subs = pysrt.open(srt_file, encoding='utf-8')
        modified = False
        
        for sub in subs:
            # Supprimer toutes les balises HTML
            clean_text = re.sub(r'<[^>]+>', '', sub.text)
            if clean_text != sub.text:
                sub.text = clean_text
                modified = True
        
        if modified:
            subs.save(srt_file, encoding='utf-8')
            return True
        return False
    except Exception as e:
        log(f"  ⚠️ Erreur nettoyage HTML: {e}")
        return False


def convert_to_srt_if_needed(subtitle_file):
    """
    Convertit ASS/SSA/VTT en SRT temporaire pour traduction
    Retourne (fichier_srt, needs_cleanup)
    """
    # Déjà SRT → pas de conversion
    if '.srt.tmp' in subtitle_file or subtitle_file.endswith('.srt'):
        return subtitle_file, False
    
    # Formats bitmap → impossible
    if any(ext in subtitle_file for ext in ['.sup.tmp', '.sub.tmp']):
        return None, False
    
    # Besoin conversion
    if '.ass.tmp' in subtitle_file:
        temp_srt = subtitle_file.replace('.ass.tmp', '.ass.to.srt.tmp')
    elif '.ssa.tmp' in subtitle_file:
        temp_srt = subtitle_file.replace('.ssa.tmp', '.ssa.to.srt.tmp')
    elif '.vtt.tmp' in subtitle_file:
        temp_srt = subtitle_file.replace('.vtt.tmp', '.vtt.to.srt.tmp')
    elif subtitle_file.endswith('.ass'):
        temp_srt = subtitle_file.replace('.ass', '.ass.to.srt.tmp')
    elif subtitle_file.endswith('.ssa'):
        temp_srt = subtitle_file.replace('.ssa', '.ssa.to.srt.tmp')
    elif subtitle_file.endswith('.vtt'):
        temp_srt = subtitle_file.replace('.vtt', '.vtt.to.srt.tmp')
    else:
        # Autre format
        base = subtitle_file.rsplit('.', 1)[0]
        temp_srt = f"{base}.to.srt.tmp"
    
    # Convertir avec ffmpeg si pas déjà fait
    if not os.path.exists(temp_srt):
        try:
            import uuid
            
            # Utiliser /tmp pour éviter les problèmes de chemins avec caractères spéciaux
            tmp_input = f"/tmp/{uuid.uuid4()}.ass"
            tmp_output = f"/tmp/{uuid.uuid4()}.srt"
            
            # Copier fichier source vers /tmp
            shutil.copy(subtitle_file, tmp_input)
            
            # Déterminer le format d'entrée
            input_format = None
            if '.ass.tmp' in subtitle_file or '.ssa.tmp' in subtitle_file:
                input_format = 'ass'  # Force format ASS/SSA
            elif '.vtt.tmp' in subtitle_file:
                input_format = 'webvtt'
            
            # Construire la commande ffmpeg
            cmd = ['ffmpeg']
            if input_format:
                cmd.extend(['-f', input_format])
            cmd.extend(['-i', tmp_input, '-c:s', 'srt', tmp_output, '-y'])
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # Copier le résultat vers la destination finale
            shutil.move(tmp_output, temp_srt)
            
            # Nettoyer /tmp
            if os.path.exists(tmp_input):
                os.remove(tmp_input)
            
            # Nettoyer les balises HTML qui restent après conversion
            clean_html_tags(temp_srt)
            
        except subprocess.CalledProcessError as e:
            # Nettoyer /tmp en cas d'erreur
            for f in [tmp_input, tmp_output]:
                if os.path.exists(f):
                    os.remove(f)
            return None, False
        except Exception as e:
            return None, False
    
    return temp_srt, True  # Fichier temp, à nettoyer


def cleanup_converted_files(base_path):
    """Supprime tous les fichiers .to.srt.tmp si DELETE_CONVERTED_AFTER=true"""
    if not DELETE_CONVERTED_AFTER:
        return
    
    for ext in SUBTITLE_EXTENSIONS:
        converted = f"{base_path}.en.{ext}.to.srt.tmp"
        if os.path.exists(converted):
            os.remove(converted)


# =========================
# PROGRESS
# =========================
def load_progress(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f).get("last_index", 0)
    return 0


def save_progress(path, index):
    with open(path, "w") as f:
        json.dump({"last_index": index}, f)


def delete_progress(path):
    """Supprime le fichier de progression si DELETE_PROGRESS_AFTER=true"""
    if not DELETE_PROGRESS_AFTER:
        return
    
    if os.path.exists(path):
        os.remove(path)


def delete_extracted_subtitle(base_path):
    """Supprime les fichiers .en.XXX.tmp (fichiers extraits du MKV) si DELETE_SOURCE_AFTER=true"""
    deleted = False

    if DELETE_SOURCE_AFTER:
        for ext in SUBTITLE_EXTENSIONS:
            extracted_file = f"{base_path}.en.{ext}.tmp"
            if os.path.isfile(extracted_file):
                os.remove(extracted_file)
                deleted = True

    # Supprimer le fichier marqueur .en.nosubtitle.tmp si DELETE_NO_SUBTITLE_MARKER=true
    if DELETE_NO_SUBTITLE_MARKER:
        marker_file = f"{base_path}.en.nosubtitle.tmp"
        if os.path.isfile(marker_file):
            os.remove(marker_file)
            deleted = True

    return deleted


# =========================
# FILE DETECTION
# =========================
def find_english_subtitle(base_path):
    """Cherche un fichier source anglais dans l'ordre de priorité"""
    # Priorité 1 : fichiers extraits .en.XXX.tmp
    for ext in SUBTITLE_EXTENSIONS:
        extracted_file = f"{base_path}.en.{ext}.tmp"
        if os.path.isfile(extracted_file):
            return extracted_file
    
    # Priorité 2 : fichiers externes avec langue
    lang_codes = ["en", "eng"]
    for lang in lang_codes:
        for ext in SUBTITLE_EXTENSIONS:
            external_file = f"{base_path}.{lang}.{ext}"
            if os.path.isfile(external_file):
                return external_file
    
    # Priorité 3 : fichiers sans langue
    for ext in SUBTITLE_EXTENSIONS:
        external_file = f"{base_path}.{ext}"
        if os.path.isfile(external_file):
            return external_file
    
    return None


# =========================
# MAIN TRANSLATION
# =========================
def translate_subtitle(video_path):
    """Traduit un fichier de sous-titre"""
    base, _ = os.path.splitext(video_path)
    video_name = os.path.basename(video_path)
    output_path = f"{base}.fr.srt"
    progress_path = f"{base}.fr.progress.json"
    
    # 1. Vérifier si .fr.srt existe
    if os.path.isfile(output_path):
        if not os.path.exists(progress_path):
            log(f"⏭️ {video_name} | Déjà traduit (Film.fr.srt existe)")
            return "already_done"
        
        try:
            subs_check = pysrt.open(output_path, encoding="utf-8")
            total_lines = len(subs_check)
            last_index = load_progress(progress_path)
            
            if last_index >= total_lines:
                log(f"⏭️ {video_name} | Traduction complète ({last_index}/{total_lines})")
                delete_progress(progress_path)
                delete_extracted_subtitle(base)
                cleanup_converted_files(base)
                return "already_done"
        except Exception as e:
            log(f"⚠️ {video_name} | Erreur vérification progress: {e}")
    
    # 2. Chercher fichier source anglais
    source_file = find_english_subtitle(base)
    
    if not source_file:
        log(f"❌ {video_name} | Aucune source anglaise trouvée")
        return "no_source"
    
    # 3. Convertir en SRT si nécessaire
    srt_file, needs_cleanup = convert_to_srt_if_needed(source_file)
    
    if not srt_file:
        log(f"❌ {video_name} | Format bitmap (image) non traduisible sans OCR")
        return "unsupported_format"
    
    # 4. Charger le fichier SRT
    try:
        subs = pysrt.open(srt_file, encoding="utf-8")
    except Exception as e:
        log(f"❌ {video_name} | Erreur lecture source: {e}")
        return "error"
    
    total = len(subs)
    last_done = load_progress(progress_path)
    
    if os.path.exists(output_path):
        translated = pysrt.open(output_path, encoding="utf-8")
    else:
        translated = subs[:]
    
    # Log de début compact
    source_name = os.path.basename(source_file)
    conversion_info = ""
    if needs_cleanup or '.ssa.txt' in source_file or '.ass.txt' in source_file:
        conversion_info = " | Converting ASS→SRT"
    
    if last_done > 0:
        log(f"🎬 {video_name} | Source: {source_name} ({total} lignes) | Reprise à {last_done + 1}{conversion_info}")
    else:
        log(f"🎬 {video_name} | Source: {source_name} ({total} lignes){conversion_info}")
    
    # 5. Suivi du temps pour estimation
    batch_times = []
    start_time = time.time()
    
    # 6. Traduction par lots
    for i in range(last_done, total, BATCH_SIZE):
        batch_start = time.time()
        
        batch = subs[i:i + BATCH_SIZE]
        texts = [s.text.replace("\n", " ") for s in batch]
        
        translated_result = translate_batch(texts)
        translated_text, used_model, used_key_index = translated_result
        
        lines = [l.strip() for l in translated_text.split("\n") if l.strip()]
        
        for j, sub in enumerate(batch):
            if j < len(lines):
                translated[i + j].text = lines[j]
        
        translated.save(output_path, encoding="utf-8")
        save_progress(progress_path, i + len(batch))
        
        current_index = i + len(batch)
        percent = current_index / total * 100
        
        # Pause avant de mesurer le temps total
        if current_index < total:
            time.sleep(PAUSE_SECONDS)
        
        # Calculer le temps TOTAL du batch (traduction + pause)
        batch_end = time.time()
        batch_duration = batch_end - batch_start
        batch_times.append(batch_duration)
        
        if len(batch_times) > 5:
            batch_times.pop(0)
        
        # Log de progression compact
        if current_index < total and len(batch_times) > 0:
            avg_batch_time = sum(batch_times) / len(batch_times)
            remaining_lines = total - current_index
            remaining_batches = remaining_lines / BATCH_SIZE
            estimated_seconds = remaining_batches * avg_batch_time
            
            if estimated_seconds < 60:
                time_str = f"{int(estimated_seconds)}s"
            elif estimated_seconds < 3600:
                minutes = int(estimated_seconds / 60)
                time_str = f"{minutes}m"
            else:
                hours = int(estimated_seconds / 3600)
                minutes = int((estimated_seconds % 3600) / 60)
                time_str = f"{hours}h{minutes}m"
            
            end_time = datetime.now(PARIS_TZ) + timedelta(seconds=estimated_seconds)
            end_time_str = end_time.strftime("%H:%M")
            
            log(f"⏳ {video_name} | {i+1}-{current_index}/{total} ({percent:.1f}%) | ETA: ~{time_str} (fin: {end_time_str})")
        else:
            # Dernier batch
            log(f"⏳ {video_name} | {i+1}-{current_index}/{total} ({percent:.1f}%)")
    
    # 7. Traduction terminée → nettoyage
    total_duration = time.time() - start_time
    if total_duration < 60:
        duration_str = f"{int(total_duration)}s"
    elif total_duration < 3600:
        minutes = int(total_duration / 60)
        seconds = int(total_duration % 60)
        duration_str = f"{minutes}m {seconds}s"
    else:
        hours = int(total_duration / 3600)
        minutes = int((total_duration % 3600) / 60)
        duration_str = f"{hours}h {minutes}m"
    
    delete_progress(progress_path)
    delete_extracted_subtitle(base)
    cleanup_converted_files(base)
    
    log(f"✅ {video_name} | Terminé en {duration_str} | Output: {os.path.basename(output_path)}")
    
    return "completed"


# =========================
# FOLDER PROCESSING
# =========================
def process_folder(folder_path, folder_index, total_folders):
    """
    Traite un dossier spécifique et retourne les stats
    """
    log(f"📂 [{folder_index}/{total_folders}] Traitement: {folder_path}")
    
    if not os.path.isdir(folder_path):
        log(f"  ⚠️ Dossier inexistant, ignoré")
        return None
    
    stats = {
        "total": 0,
        "trailers_skipped": 0,
        "already_done": 0,
        "completed": 0,
        "no_source": 0,
        "unsupported_format": 0,
        "error": 0
    }
    
    for root, _, files in os.walk(folder_path):
        for file in files:
            if not file.lower().endswith(VIDEO_EXTENSIONS):
                continue
            
            # Ignorer les trailers (silencieux)
            if "-trailer" in file.lower():
                stats["trailers_skipped"] += 1
                continue
            
            video_path = os.path.join(root, file)
            
            try:
                result = translate_subtitle(video_path)
                
                if result in stats:
                    stats[result] += 1
                
                stats["total"] += 1
            except Exception as e:
                log(f"❌ {file} | Erreur inattendue: {e}")
                stats["error"] += 1
                stats["total"] += 1
    
    return stats


def merge_stats(global_stats, folder_stats):
    """Fusionne les stats d'un folder dans les stats globales"""
    if folder_stats is None:
        return
    
    for key in folder_stats:
        global_stats[key] += folder_stats[key]


# =========================
# RUN CYCLE
# =========================
def run_translation():
    """Exécution d'un cycle de traduction complet sur tous les folders"""
    if not SOURCE_FOLDERS:
        log("❌ Aucun dossier configuré (SOURCE_FOLDERS vide)")
        log("   Configurez SOURCE_FOLDERS dans .env : SOURCE_FOLDERS=[\"/path/1\", \"/path/2\"]")
        return
    
    log("🚀 DÉBUT DE LA TRADUCTION")
    log(f"📂 {len(SOURCE_FOLDERS)} dossier(s) configuré(s) | Formats: SRT, ASS, SSA, VTT | Modèles: {', '.join(MODELS)}")
    
    # Stats globales
    global_stats = {
        "total": 0,
        "trailers_skipped": 0,
        "already_done": 0,
        "completed": 0,
        "no_source": 0,
        "unsupported_format": 0,
        "error": 0
    }
    
    # Traiter chaque folder
    total_folders = len(SOURCE_FOLDERS)
    for index, folder in enumerate(SOURCE_FOLDERS, start=1):
        folder_stats = process_folder(folder, index, total_folders)
        merge_stats(global_stats, folder_stats)
    
    log(f"✅ TRADUCTION TERMINÉE | Total: {global_stats['total']} | Complétés: {global_stats['completed']} | Déjà faits: {global_stats['already_done']} | Erreurs: {global_stats['error'] + global_stats['no_source'] + global_stats['unsupported_format']}")
    log('='*60)


# =========================
# MAIN
# =========================
def main():
    mode = "WATCH (agent continu)" if WATCH_MODE else "RUN ONCE (exécution unique)"
    log(f"🐳 Mode: {mode}")
    
    if WATCH_MODE:
        interval_hours = WATCH_INTERVAL / 3600
        log(f"⏰ Intervalle: {WATCH_INTERVAL}s ({interval_hours:.1f}h) | CTRL+C pour arrêter")
        
        while True:
            try:
                run_translation()
                log(f"💤 Prochaine vérification dans {interval_hours:.1f}h...")
                time.sleep(WATCH_INTERVAL)
            except KeyboardInterrupt:
                log("👋 Arrêt de l'agent demandé")
                break
            except Exception as e:
                log(f"❌ Erreur inattendue: {e}")
                log(f"⏳ Nouvelle tentative dans {interval_hours:.1f}h...")
                time.sleep(WATCH_INTERVAL)
    else:
        run_translation()


if __name__ == "__main__":
    main()
