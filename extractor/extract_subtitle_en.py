import os
import subprocess
import json
import shutil
import time
from datetime import datetime
from dotenv import load_dotenv

# ==========================================
# extract_subtitle_en.py - V9 (Docker Ready)
# ==========================================
# Ajout détection sous-titres FR :
# - Skip si piste sous-titre FR dans MKV
# - Skip si fichier externe FR existe
# ==========================================

load_dotenv()
SOURCE_FOLDER = os.getenv("SOURCE_FOLDER")
WATCH_MODE = os.getenv("WATCH_MODE", "true").lower() == "true"
WATCH_INTERVAL = int(os.getenv("WATCH_INTERVAL", 3600))  # défaut: 1h

# Extensions vidéo supportées
VIDEO_EXTENSIONS = (".mkv", ".mp4", ".avi", ".mov", ".m4v", ".webm", ".flv", ".wmv")

# Extensions de sous-titres à chercher
SUBTITLE_EXTENSIONS = ["srt", "ass", "sup", "ssa"]


def log(msg):
    """Logger avec timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")


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
    Cherche un fichier .en.XXX.txt déjà extrait
    Retourne True si trouvé, False sinon
    """
    for ext in SUBTITLE_EXTENSIONS:
        extracted_file = f"{base_path}.en.{ext}.txt"
        if os.path.isfile(extracted_file):
            return True
    return False


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
            log(f"  🇫🇷 Piste sous-titre FR détectée : track {track['id']} | lang={lang} | name={name}")
            return True
    
    return False


def extract_from_mkv(mkv_path, base_path):
    """
    Extrait le sous-titre anglais du MKV vers un fichier .en.FORMAT.txt
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
        
        # DEBUG
        log(
            f"  track {track['id']} | "
            f"lang={lang or '∅'} | "
            f"name={name or '∅'} | "
            f"codec={track.get('codec')}"
        )
        
        is_english = (
            lang in ("en", "eng", "und") or
            "english" in name
        )
        
        if is_english:
            subtitle_tracks.append(track)
    
    if not subtitle_tracks:
        log("  ℹ️ aucun sous-titre anglais dans le MKV")
        return False
    
    track = subtitle_tracks[0]
    track_id = track["id"]
    codec = track.get("codec", "").lower()
    
    # Déterminer l'extension selon le codec
    if "ass" in codec:
        format_ext = "ass"
    elif "pgs" in codec:
        format_ext = "sup"
    elif "ssa" in codec:
        format_ext = "ssa"
    else:
        format_ext = "srt"
    
    temp_file = f"{base_path}.temp.{format_ext}"
    out_file = f"{base_path}.en.{format_ext}.txt"
    
    log(f"  → extraction sous-titre EN (track {track_id}) depuis MKV")
    
    try:
        # Extraire vers un fichier temporaire
        subprocess.run(
            ["mkvextract", "tracks", mkv_path, f"{track_id}:{temp_file}"],
            check=True
        )
        
        # Renommer en .en.FORMAT.txt
        shutil.move(temp_file, out_file)
        log(f"  ✅ extrait → {os.path.basename(out_file)}")
        return True
        
    except Exception as e:
        log(f"  ❌ erreur extraction : {e}")
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
    4. Fichier .en.XXX.txt déjà extrait → skip
    5. MKV → extraction piste EN → .en.FORMAT.txt
    6. Pas MKV → erreur
    """
    base, ext = os.path.splitext(video_path)
    is_mkv = ext.lower() == ".mkv"
    
    # 1. Vérifier si fichier FR externe existe
    if find_french_subtitle(base):
        log(f"  🇫🇷 Sous-titre français externe trouvé")
        log(f"  ↪ skip (déjà traduit)")
        return "french_external"
    
    # 2. Vérifier si piste sous-titre FR dans le MKV
    if is_mkv and has_french_subtitle_in_mkv(video_path):
        log(f"  ↪ skip (sous-titre français dans le MKV)")
        return "french_in_mkv"
    
    # 3. Vérifier si fichier EN externe existe
    external_file = find_external_subtitle(base)
    
    if external_file:
        log(f"  ✓ fichier externe anglais trouvé : {os.path.basename(external_file)}")
        log(f"  ↪ rien à faire (fichier déjà disponible)")
        return "external"
    
    # 4. Vérifier si déjà extrait (.en.XXX.txt)
    if find_extracted_subtitle(base):
        log(f"  ✓ fichier .en.XXX.txt déjà extrait")
        log(f"  ↪ rien à faire")
        return "extracted"
    
    # 5. Pas de fichier externe → extraire du MKV
    if is_mkv:
        log(f"  ℹ️ pas de fichier externe → extraction depuis MKV")
        if extract_from_mkv(video_path, base):
            return "mkv_extracted"
        else:
            log("  ❌ échec extraction MKV")
            return "failed"
    else:
        log("  ❌ pas de fichier externe et pas un MKV")
        return "no_source"


def run_extraction():
    """Exécution d'un cycle d'extraction complet"""
    if not SOURCE_FOLDER or not os.path.isdir(SOURCE_FOLDER):
        log("❌ SOURCE_FOLDER manquant ou n'existe pas dans .env")
        return
    
    log("=" * 60)
    log("🚀 DÉBUT DE L'EXTRACTION")
    log("=" * 60)
    log(f"📂 Dossier source : {SOURCE_FOLDER}")
    log(f"🎬 Extensions supportées : {', '.join(VIDEO_EXTENSIONS)}")
    log(f"🚫 Ignore les fichiers contenant : '-trailer'")
    log(f"📝 Format extraction : .en.FORMAT.txt")
    log(f"🇫🇷 Skip si sous-titre français détecté")
    
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
    
    for root, _, files in os.walk(SOURCE_FOLDER):
        for file in files:
            # Vérifier l'extension
            if not file.lower().endswith(VIDEO_EXTENSIONS):
                continue
            
            # Ignorer les trailers
            if is_trailer(file):
                stats["trailers_skipped"] += 1
                log(f"\n🚫 Ignoré (trailer) : {file}")
                continue
            
            video_path = os.path.join(root, file)
            
            log(f"\n{'='*60}")
            log(f"🎬 Traitement : {file}")
            log('='*60)
            
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
    
    log(f"\n{'='*60}")
    log(f"✅ EXTRACTION TERMINÉE")
    log(f"📊 Statistiques :")
    log(f"  Total fichiers traités : {stats['total']}")
    if stats["french_external"] > 0:
        log(f"  🇫🇷 FR externe trouvé : {stats['french_external']}")
    if stats["french_in_mkv"] > 0:
        log(f"  🇫🇷 FR dans MKV : {stats['french_in_mkv']}")
    if stats["external_found"] > 0:
        log(f"  📄 EN externe trouvé : {stats['external_found']}")
    if stats["already_extracted"] > 0:
        log(f"  ✓ Déjà extrait (.en.XXX.txt) : {stats['already_extracted']}")
    if stats["mkv_extracted"] > 0:
        log(f"  🎬 Extraction MKV réussie : {stats['mkv_extracted']}")
    if stats["failed"] > 0:
        log(f"  ❌ Extraction échouée : {stats['failed']}")
    if stats["no_source"] > 0:
        log(f"  ⚠️ Aucune source trouvée : {stats['no_source']}")
    if stats["trailers_skipped"] > 0:
        log(f"  🚫 Trailers ignorés : {stats['trailers_skipped']}")
    log('='*60)


def main():
    log(f"🐳 Mode : {'WATCH (agent continu)' if WATCH_MODE else 'RUN ONCE (exécution unique)'}")
    
    if WATCH_MODE:
        log(f"⏰ Intervalle : {WATCH_INTERVAL}s ({WATCH_INTERVAL/3600:.1f}h)")
        log(f"🔄 Agent démarré - CTRL+C pour arrêter\n")
        
        while True:
            try:
                run_extraction()
                log(f"\n💤 Prochaine vérification dans {WATCH_INTERVAL}s ({WATCH_INTERVAL/3600:.1f}h)...\n")
                time.sleep(WATCH_INTERVAL)
            except KeyboardInterrupt:
                log("\n👋 Arrêt de l'agent demandé")
                break
            except Exception as e:
                log(f"\n❌ Erreur inattendue : {e}")
                log(f"⏳ Nouvelle tentative dans {WATCH_INTERVAL}s...\n")
                time.sleep(WATCH_INTERVAL)
    else:
        run_extraction()


if __name__ == "__main__":
    main()
