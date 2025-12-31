import os
import json
import time
import sys
import pysrt
import pytz
from dotenv import load_dotenv
from google import genai
from google.genai import types
from datetime import datetime, timedelta

# ==========================================
# translate_srt_gemini.py - V5 (Production Ready)
# ==========================================
# Optimisations finales :
# - system_instruction pour économie tokens
# - Cooldown intelligent 11h05 FR
# - Retry sur réponse vide (2 tentatives)
# - Nettoyage automatique progress.json + .en.XXX.txt
# - Support multi-modèles avec quotas indépendants
# - Mode watch Docker ready
# ==========================================

load_dotenv()

# =========================
# CONFIG
# =========================
SOURCE_FOLDER = os.getenv("SOURCE_FOLDER")
PAUSE_SECONDS = int(os.getenv("PAUSE_SECONDS", 10))  # Optimisé : 10s au lieu de 30s
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 50))  # Optimisé : 50 au lieu de 10
WATCH_MODE = os.getenv("WATCH_MODE", "true").lower() == "true"
WATCH_INTERVAL = int(os.getenv("WATCH_INTERVAL", 3600))

API_KEYS = json.loads(os.getenv("GEMINI_API_KEYS") or "[]")
MODELS = json.loads(os.getenv("GEMINI_MODELS") or "[]")

COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", 3600))
RETRY_EMPTY_RESPONSE_DELAY = 10  # Délai entre 2 tentatives si réponse vide

if not API_KEYS or not MODELS:
    raise RuntimeError("GEMINI_API_KEYS ou GEMINI_MODELS manquant dans .env")

# Extensions vidéo supportées
VIDEO_EXTENSIONS = (".mkv", ".mp4", ".avi", ".mov", ".m4v", ".webm", ".flv", ".wmv")

# Extensions de sous-titres
SUBTITLE_EXTENSIONS = ["srt", "ass", "sup", "ssa"]

# Timezone France
PARIS_TZ = pytz.timezone('Europe/Paris')


def log(msg):
    """Logger avec timestamp"""
    timestamp = datetime.now(PARIS_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")


# =========================
# COOLDOWN MANAGEMENT
# =========================
cooldowns = {}  # {(model, key_index): timestamp}


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
    """
    Calcule le prochain reset de quota : 11h05 heure de France
    Retourne (datetime, seconds_to_wait)
    """
    now_paris = datetime.now(PARIS_TZ)
    
    # Vérifier si on est déjà passé 11h05 aujourd'hui
    if now_paris.hour > 11 or (now_paris.hour == 11 and now_paris.minute >= 5):
        # Déjà passé → demain 11h05
        next_reset = (now_paris + timedelta(days=1)).replace(hour=11, minute=5, second=0, microsecond=0)
    else:
        # Pas encore passé → aujourd'hui 11h05
        next_reset = now_paris.replace(hour=11, minute=5, second=0, microsecond=0)
    
    sleep_seconds = (next_reset - now_paris).total_seconds()
    
    return next_reset, sleep_seconds


def wait_for_quota_reset():
    """
    Attend jusqu'à 11h05 (reset du quota API Gemini)
    """
    next_reset, sleep_seconds = calculate_next_quota_reset()
    
    log("❌ Toutes les clés API bloquées (quota dépassé)")
    log(f"⏰ Prochaine tentative : {next_reset.strftime('%d/%m/%Y à %H:%M')} (heure de France)")
    log(f"💤 Agent en veille pendant {sleep_seconds/3600:.1f}h...")
    
    time.sleep(sleep_seconds)
    
    log("✨ Réveil de l'agent - Quota API réinitialisé")
    
    # Réinitialiser tous les cooldowns
    cooldowns.clear()


# =========================
# GEMINI CALL
# =========================
def call_gemini(model, api_key, text, retry_count=0):
    """
    Appelle l'API Gemini avec system_instruction optimisé
    Gère les réponses vides avec retry (max 2 tentatives)
    """
    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=model,
        contents=text,  # Juste le batch de sous-titres
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
        if retry_count < 1:  # Première tentative ratée, on réessaye
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

        # 🔥 Toutes les clés sont bloquées
        if not any_key_available():
            if WATCH_MODE:
                # Mode agent : attendre jusqu'à 11h05
                wait_for_quota_reset()
                # Après le réveil, on continue la boucle
                continue
            else:
                # Mode run once : arrêter
                log("\n❌ Toutes les clés sont en cooldown.")
                log("👉 Arrêt du programme.\n")
                sys.exit(1)

        time.sleep(2)


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
    """Supprime le fichier de progression"""
    if os.path.exists(path):
        os.remove(path)
        log(f"  🗑️ Nettoyage : {os.path.basename(path)} supprimé")


def delete_extracted_subtitle(base_path):
    """
    Supprime les fichiers .en.XXX.txt (fichiers extraits du MKV)
    Ne touche PAS aux fichiers externes (.en.srt, .srt, etc.)
    """
    for ext in SUBTITLE_EXTENSIONS:
        extracted_file = f"{base_path}.en.{ext}.txt"
        if os.path.isfile(extracted_file):
            os.remove(extracted_file)
            log(f"  🗑️ Nettoyage : {os.path.basename(extracted_file)} supprimé")
            return True
    return False


# =========================
# FILE DETECTION
# =========================
def find_english_subtitle(base_path):
    """
    Cherche un fichier source anglais dans l'ordre de priorité :
    1. .en.srt.txt, .en.ass.txt, .en.sup.txt, .en.ssa.txt (fichiers extraits)
    2. .en.srt, .en.ass, .en.sup, .en.ssa (fichiers externes avec langue)
    3. .srt, .ass, .sup, .ssa (fichiers externes sans langue)
    
    Retourne le chemin du fichier ou None
    """
    # Priorité 1 : fichiers extraits .en.XXX.txt
    for ext in SUBTITLE_EXTENSIONS:
        extracted_file = f"{base_path}.en.{ext}.txt"
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
    """
    Traduit un fichier de sous-titre
    Retourne le statut : "completed", "already_done", "no_source", "error"
    """
    base, _ = os.path.splitext(video_path)
    output_path = f"{base}.fr.srt"
    progress_path = f"{base}.fr.progress.json"
    
    # 1. Vérifier si .fr.srt existe
    if os.path.isfile(output_path):
        # a. Si progress.json n'existe pas → déjà terminé
        if not os.path.exists(progress_path):
            log(f"  ✓ Traduction déjà terminée (pas de progress.json)")
            return "already_done"
        
        # b. Si progress.json existe → vérifier si terminé
        try:
            subs_check = pysrt.open(output_path, encoding="utf-8")
            total_lines = len(subs_check)
            last_index = load_progress(progress_path)
            
            if last_index >= total_lines:
                log(f"  ✓ Traduction terminée ({last_index}/{total_lines})")
                delete_progress(progress_path)
                delete_extracted_subtitle(base)
                return "already_done"
            else:
                log(f"  ↪ Reprise traduction à {last_index + 1}/{total_lines}")
        except Exception as e:
            log(f"  ⚠️ Erreur vérification progress : {e}")
    
    # 2. Chercher fichier source anglais
    source_file = find_english_subtitle(base)
    
    if not source_file:
        log(f"  ❌ Aucune source anglaise trouvée")
        return "no_source"
    
    log(f"  📄 Source : {os.path.basename(source_file)}")
    
    # 3. Charger le fichier source
    try:
        subs = pysrt.open(source_file, encoding="utf-8")
    except Exception as e:
        log(f"  ❌ Erreur lecture source : {e}")
        return "error"
    
    total = len(subs)
    last_done = load_progress(progress_path)
    
    if os.path.exists(output_path):
        translated = pysrt.open(output_path, encoding="utf-8")
    else:
        translated = subs[:]
    
    log(f"  📊 Lignes : {total}")
    log(f"  ▶ Début à : {last_done + 1}")
    
    # Suivi du temps pour estimation
    batch_times = []  # Stocke les temps des derniers batches
    start_translation = time.time()
    
    # 4. Traduction par lots
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
        
        # Calculer progression
        current_index = i + len(batch)
        percent = current_index / total * 100
        
        log(f"  ✅ {i+1}-{current_index} / {total} ({percent:.1f}%)")
        
        # Pause avant de mesurer le temps total
        if current_index < total:  # Pas de pause après le dernier batch
            log(f"  ⏳ pause {PAUSE_SECONDS}s\n")
            time.sleep(PAUSE_SECONDS)
        
        # Calculer le temps TOTAL du batch (traduction + pause)
        batch_end = time.time()
        batch_duration = batch_end - batch_start
        batch_times.append(batch_duration)
        
        # Garder seulement les 5 derniers temps pour moyenne mobile
        if len(batch_times) > 5:
            batch_times.pop(0)
        
        # Calculer temps restant (seulement si pas le dernier batch)
        if current_index < total and len(batch_times) > 0:
            avg_batch_time = sum(batch_times) / len(batch_times)
            remaining_lines = total - current_index
            remaining_batches = remaining_lines / BATCH_SIZE
            estimated_seconds = remaining_batches * avg_batch_time
            
            # Formater le temps restant
            if estimated_seconds < 60:
                time_str = f"{int(estimated_seconds)}s"
            elif estimated_seconds < 3600:
                minutes = int(estimated_seconds / 60)
                seconds = int(estimated_seconds % 60)
                time_str = f"{minutes}m {seconds}s"
            else:
                hours = int(estimated_seconds / 3600)
                minutes = int((estimated_seconds % 3600) / 60)
                time_str = f"{hours}h {minutes}m"
            
            # Calculer l'heure de fin prévue
            end_time = datetime.now(PARIS_TZ) + timedelta(seconds=estimated_seconds)
            end_time_str = end_time.strftime("%H:%M")
            
            log(f"  ⏱️ Restant : ~{time_str} (fin prévue : {end_time_str})\n")
    
    # 5. Traduction terminée → nettoyage
    log(f"  🎉 Traduction terminée")
    delete_progress(progress_path)
    delete_extracted_subtitle(base)
    
    return "completed"


# =========================
# RUN CYCLE
# =========================
def run_translation():
    """Exécution d'un cycle de traduction complet"""
    if not SOURCE_FOLDER or not os.path.isdir(SOURCE_FOLDER):
        log("❌ SOURCE_FOLDER manquant ou n'existe pas")
        return
    
    log("=" * 60)
    log("🚀 DÉBUT DE LA TRADUCTION")
    log("=" * 60)
    log(f"📂 Dossier source : {SOURCE_FOLDER}")
    log(f"🎬 Extensions vidéo : {', '.join(VIDEO_EXTENSIONS)}")
    log(f"📝 Recherche : .en.XXX.txt + fichiers externes")
    log(f"🇫🇷 Output : .fr.srt")
    log(f"⏰ Reset quota API : 11h05 heure de France")
    log(f"🤖 Modèles : {', '.join(MODELS)}")
    
    stats = {
        "total": 0,
        "already_done": 0,
        "completed": 0,
        "in_progress": 0,
        "no_source": 0,
        "error": 0
    }
    
    for root, _, files in os.walk(SOURCE_FOLDER):
        for file in files:
            # Vérifier l'extension vidéo
            if not file.lower().endswith(VIDEO_EXTENSIONS):
                continue
            
            video_path = os.path.join(root, file)
            
            log(f"\n{'='*60}")
            log(f"🎬 Traitement : {file}")
            log('='*60)
            
            result = translate_subtitle(video_path)
            
            if result in stats:
                stats[result] += 1
            
            stats["total"] += 1
    
    log(f"\n{'='*60}")
    log(f"✅ TRADUCTION TERMINÉE")
    log(f"📊 Statistiques :")
    log(f"  Total fichiers traités : {stats['total']}")
    if stats["already_done"] > 0:
        log(f"  ✓ Déjà traduits : {stats['already_done']}")
    if stats["completed"] > 0:
        log(f"  🎉 Traductions complétées : {stats['completed']}")
    if stats["in_progress"] > 0:
        log(f"  ↪ En cours : {stats['in_progress']}")
    if stats["no_source"] > 0:
        log(f"  ❌ Aucune source : {stats['no_source']}")
    if stats["error"] > 0:
        log(f"  ⚠️ Erreurs : {stats['error']}")
    log('='*60)


# =========================
# MAIN
# =========================
def main():
    log(f"🐳 Mode : {'WATCH (agent continu)' if WATCH_MODE else 'RUN ONCE (exécution unique)'}")
    
    if WATCH_MODE:
        log(f"⏰ Intervalle : {WATCH_INTERVAL}s ({WATCH_INTERVAL/3600:.1f}h)")
        log(f"🔄 Agent démarré - CTRL+C pour arrêter\n")
        
        while True:
            try:
                run_translation()
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
        run_translation()


if __name__ == "__main__":
    main()