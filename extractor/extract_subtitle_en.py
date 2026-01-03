import os
import subprocess
import json
import shutil
import time
from datetime import datetime
from dotenv import load_dotenv

# ==========================================
# extract_subtitle_en.py - V10 (Multi-Folders)
# ==========================================
# Nouvelles fonctionnalités V10 :
# - Support multi-folders via SOURCE_FOLDERS (JSON array)
# - Rétro-compatible avec SOURCE_FOLDER (single)
# - Stats agrégées sur tous les folders
# - Log du folder en cours de traitement
# ==========================================

load_dotenv()

# Configuration multi-folders
SOURCE_FOLDERS_JSON = os.getenv("SOURCE_FOLDERS", "[]")
SOURCE_FOLDER_LEGACY = os.getenv("SOURCE_FOLDER")
WATCH_MODE = os.getenv("WATCH_MODE", "true").lower() == "true"
WATCH_INTERVAL = int(os.getenv("WATCH_INTERVAL", 3600))  # défaut: 1h
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

# Extensions vidéo supportées
VIDEO_EXTENSIONS = (".mkv", ".mp4", ".avi", ".mov", ".m4v", ".webm", ".flv", ".wmv")

# Extensions de sous-titres à chercher
SUBTITLE_EXTENSIONS = ["srt", "ass", "sup", "ssa"]

# Configuration du logger
import logging
from logging.handlers import RotatingFileHandler

logger = None

def setup_logger():
    """Configure le logger avec rotation automatique si LOG_FILE est défini"""
    global logger
    
    logger = logging.getLogger('subtitle_extractor')
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


def is_trailer(filename):
    """Vérifie si le fichier est un trailer (contient '-trailer')"""
    return "-trailer" in filename.lower()


def find_french_subtitle(base_path):
    """
    Cherche un fichier de sous-titre français externe
    Patterns : .fr.srt, .fra.srt, .fre.srt, .french.srt
    
    Retourne True si trouvé, False sinon
    """
    lang_codes = ["fr", "fra", "fre", "french"]
    
    for lang in lang_codes:
        for ext in SUBTITLE_EXTENSIONS:
            french_file = f"{base_path}.{lang}.{ext}"
            if os.path.isfile(french_file):
                return True
    
    return False


def find_external_subtitle(base_path):
    """
    Cherche un fichier de sous-titre anglais externe dans l'ordre de priorité :
    1. Avec langue explicite (.en.srt, .eng.srt, .en.ass, etc.)
    2. Sans langue (.srt, .ass, .sup)
    
    Retourne le chemin du fichier trouvé ou None
    """
    lang_codes = ["en", "eng"]
    
    # Priorité 1 : fichiers avec langue explicite
    for lang in lang_codes:
        for ext in SUBTITLE_EXTENSIONS:
            external_file = f"{base_path}.{lang}.{ext}"
            if os.path.isfile(external_file):
                return external_file
    
    # Priorité 2 : fichiers sans langue
    for ext in SUBTITLE_EXTENSIONS:
        external_file = f"{base_path}.{ext}"
        if os.path.isfile(external_file):
            return external_file
    
    return None


def find_extracted_subtitle(base_path):
    """
    Cherche un fichier .en.XXX.tmp déjà extrait
    Retourne le chemin du fichier trouvé ou None
    """
    for ext in SUBTITLE_EXTENSIONS:
        extracted_file = f"{base_path}.en.{ext}.tmp"
        if os.path.isfile(extracted_file):
            return extracted_file
    return None


def get_tracks(mkv_path):
    """
    Récupère les pistes du fichier MKV
    Retourne une liste vide en cas d'erreur
    """
    try:
        result = subprocess.run(
            ["mkvmerge", "-J", mkv_path],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)["tracks"]
    except Exception as e:
        log(f"  ⚠️ erreur lecture MKV : {e}")
        return []


def has_french_subtitle_in_mkv(mkv_path):
    """
    Vérifie si le MKV contient une piste de sous-titre français
    Retourne True si trouvé, False sinon
    """
    tracks = get_tracks(mkv_path)
    if not tracks:
        return False
    
    for track in tracks:
        if track["type"] != "subtitles":
            continue
        
        props = track.get("properties", {})
        lang = (props.get("language") or "").lower()
        name = (props.get("track_name") or "").lower()
        
        is_french = (
            lang in ("fr", "fra", "fre") or
            "french" in name or
            "français" in name or
            "francais" in name
        )
        
        if is_french:
            return True
    
    return False


def extract_from_mkv(mkv_path, base_path):
    """
    Extrait le sous-titre anglais du MKV vers un fichier .en.FORMAT.tmp
    Retourne True si extraction réussie, False sinon
    """
    tracks = get_tracks(mkv_path)
    if not tracks:
        return False
    
    subtitle_tracks = []
    
    for track in tracks:
        if track["type"] != "subtitles":
            continue
        
        props = track.get("properties", {})
        lang = (props.get("language") or "").lower()
        name = (props.get("track_name") or "").lower()
        
        is_english = (
            lang in ("en", "eng", "und") or
            "english" in name
        )
        
        if is_english:
            subtitle_tracks.append(track)
    
    if not subtitle_tracks:
        return False
    
    track = subtitle_tracks[0]
    track_id = track["id"]
    codec = track.get("codec", "").lower()
    
    # Déterminer l'extension selon le codec
    if "s_text/ass" in codec or "advanced" in codec or ("ass" in codec and "substation" not in codec):
        format_ext = "ass"
    elif "substation" in codec or "s_text/ssa" in codec or "ssa" in codec:
        format_ext = "ssa"
    elif "s_hdmv/pgs" in codec or "hdmv" in codec or "pgs" in codec:
        format_ext = "sup"
    elif "s_vobsub" in codec or "vobsub" in codec:
        format_ext = "sub"
    elif "webvtt" in codec or "s_text/webvtt" in codec:
        format_ext = "vtt"
    else:
        format_ext = "srt"  # Fallback (SubRip, S_TEXT/UTF8)
    
    temp_file = f"{base_path}.temp.{format_ext}"
    out_file = f"{base_path}.en.{format_ext}.tmp"
    
    try:
        # Extraire vers un fichier temporaire
        subprocess.run(
            ["mkvextract", "tracks", mkv_path, f"{track_id}:{temp_file}"],
            check=True,
            capture_output=True
        )
        
        # Renommer en .en.FORMAT.tmp
        shutil.move(temp_file, out_file)
        return True
        
    except Exception as e:
        # Nettoyer le fichier temporaire si présent
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return False


def process_video_file(video_path):
    """
    Processus principal avec détection FR :
    1. Fichier FR externe existe → skip (déjà traduit)
    2. Piste sous-titre FR dans MKV → skip (déjà traduit)
    3. Fichier EN externe existe → skip (source dispo)
    4. Fichier .en.XXX.tmp déjà extrait → skip
    5. MKV → extraction piste EN → .en.FORMAT.tmp
    6. Pas MKV → erreur
    """
    base, ext = os.path.splitext(video_path)
    video_name = os.path.basename(video_path)
    is_mkv = ext.lower() == ".mkv"
    
    # 1. Vérifier si fichier FR externe existe
    if find_french_subtitle(base):
        log(f"⭐️ {video_name} | Déjà traduit (sous-titre FR externe)")
        return "french_external"
    
    # 2. Vérifier si piste sous-titre FR dans le MKV
    if is_mkv and has_french_subtitle_in_mkv(video_path):
        log(f"⭐️ {video_name} | Déjà traduit (piste FR dans MKV)")
        return "french_in_mkv"
    
    # 3. Vérifier si fichier EN externe existe
    external_file = find_external_subtitle(base)
    
    if external_file:
        log(f"✓ {video_name} | Source externe trouvée: {os.path.basename(external_file)}")
        return "external"
    
    # 4. Vérifier si déjà extrait (.en.XXX.txt)
    extracted = find_extracted_subtitle(base)
    if extracted:
        log(f"✓ {video_name} | Déjà extrait: {os.path.basename(extracted)}")
        return "extracted"
    
    # 5. Pas de fichier externe → extraire du MKV
    if is_mkv:
        if extract_from_mkv(video_path, base):
            # Trouver le fichier extrait pour afficher son nom
            extracted = find_extracted_subtitle(base)
            extracted_name = os.path.basename(extracted) if extracted else "fichier"
            log(f"✅ {video_name} | Extrait: {extracted_name}")
            return "mkv_extracted"
        else:
            log(f"❌ {video_name} | Pas de piste sous-titre EN dans le MKV")
            return "failed"
    else:
        log(f"❌ {video_name} | Pas de source (non-MKV)")
        return "no_source"


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
        "french_external": 0,
        "french_in_mkv": 0,
        "external_found": 0,
        "already_extracted": 0,
        "mkv_extracted": 0,
        "failed": 0,
        "no_source": 0
    }
    
    for root, _, files in os.walk(folder_path):
        for file in files:
            # Vérifier l'extension
            if not file.lower().endswith(VIDEO_EXTENSIONS):
                continue
            
            # Ignorer les trailers
            if is_trailer(file):
                stats["trailers_skipped"] += 1
                continue
            
            video_path = os.path.join(root, file)
            
            try:
                result = process_video_file(video_path)
                
                if result == "french_external":
                    stats["french_external"] += 1
                elif result == "french_in_mkv":
                    stats["french_in_mkv"] += 1
                elif result == "external":
                    stats["external_found"] += 1
                elif result == "extracted":
                    stats["already_extracted"] += 1
                elif result == "mkv_extracted":
                    stats["mkv_extracted"] += 1
                elif result == "failed":
                    stats["failed"] += 1
                elif result == "no_source":
                    stats["no_source"] += 1
                
                stats["total"] += 1
            except Exception as e:
                log(f"❌ {file} | Erreur inattendue: {e}")
                stats["failed"] += 1
                stats["total"] += 1
    
    return stats


def merge_stats(global_stats, folder_stats):
    """Fusionne les stats d'un folder dans les stats globales"""
    if folder_stats is None:
        return
    
    for key in folder_stats:
        global_stats[key] += folder_stats[key]


def run_extraction():
    """Exécution d'un cycle d'extraction complet sur tous les folders"""
    if not SOURCE_FOLDERS:
        log("❌ Aucun dossier configuré")
        log("   Configuration multi-folders : SOURCE_FOLDERS=[\"/path/1\", \"/path/2\"]")
        log("   OU configuration legacy : SOURCE_FOLDER=/path")
        log(f"   Debug: SOURCE_FOLDERS_JSON='{SOURCE_FOLDERS_JSON}'")
        log(f"   Debug: SOURCE_FOLDER_LEGACY='{SOURCE_FOLDER_LEGACY}'")
        log(f"   Debug: Parsed SOURCE_FOLDERS={SOURCE_FOLDERS}")
        return
    
    log("🚀 DÉBUT DE L'EXTRACTION")
    log(f"📂 {len(SOURCE_FOLDERS)} dossier(s) configuré(s) | Formats: {', '.join(VIDEO_EXTENSIONS)}")
    
    # Stats globales
    global_stats = {
        "total": 0,
        "trailers_skipped": 0,
        "french_external": 0,
        "french_in_mkv": 0,
        "external_found": 0,
        "already_extracted": 0,
        "mkv_extracted": 0,
        "failed": 0,
        "no_source": 0
    }
    
    # Traiter chaque folder
    total_folders = len(SOURCE_FOLDERS)
    for index, folder in enumerate(SOURCE_FOLDERS, start=1):
        folder_stats = process_folder(folder, index, total_folders)
        merge_stats(global_stats, folder_stats)
    
    # Stats compactes globales
    french_total = global_stats["french_external"] + global_stats["french_in_mkv"]
    skipped = french_total + global_stats["external_found"] + global_stats["already_extracted"]
    
    log(f"✅ EXTRACTION TERMINÉE | Total: {global_stats['total']} | Extraits: {global_stats['mkv_extracted']} | Skippés: {skipped} | Erreurs: {global_stats['failed'] + global_stats['no_source']}")
    if global_stats["failed"] > 0:
        log(f"  ❌ MKV sans piste EN : {global_stats['failed']}")
    if global_stats["no_source"] > 0:
        log(f"  ⚠️ Non-MKV sans source externe : {global_stats['no_source']}")
    log('='*60)


def main():
    mode = "WATCH (agent continu)" if WATCH_MODE else "RUN ONCE (exécution unique)"
    log(f"🐳 Mode: {mode}")
    
    if WATCH_MODE:
        interval_hours = WATCH_INTERVAL / 3600
        log(f"⏰ Intervalle: {WATCH_INTERVAL}s ({interval_hours:.1f}h) | CTRL+C pour arrêter")
        
        while True:
            try:
                run_extraction()
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
        run_extraction()


if __name__ == "__main__":
    main()