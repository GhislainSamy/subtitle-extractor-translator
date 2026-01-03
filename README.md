# 🎬 Subtitle Automation Suite

Pipeline automatisé d'extraction et de traduction de sous-titres pour films et séries. Extrait les sous-titres anglais des fichiers MKV et les traduit automatiquement en français via Google Gemini API.

## 📋 Vue d'ensemble

Ce projet combine deux agents Docker qui travaillent en tandem :

1. **🎯 Subtitle Extractor** : Extrait les sous-titres anglais des pistes MKV
2. **🌐 Subtitle Translator** : Traduit automatiquement EN → FR avec Google Gemini API

#### 🚀 Démarrage rapide
Prenez le fichier docker-compose situé à la racine du projet et configurez correctement les volumes et les variables en vous basant sur les exemples fournis.

### Multi-Folders Support

Les deux agents supportent le **traitement de plusieurs dossiers simultanément** :
- ✅ Configuration simple via JSON array : `SOURCE_FOLDERS=["/media/movies", "/media/series"]`
- ✅ Stats agrégées sur tous les dossiers
- ✅ Logs clairs indiquant le dossier en cours : `📂 [1/3] Traitement: /media/movies`
- ✅ Rétro-compatible avec la config single-folder (`SOURCE_FOLDER`)

### Workflow complet

```
Single-Folder (mode classique)
Film.mkv (piste EN intégrée)
         ↓
   [EXTRACTOR]
         ↓
Film.en.srt.tmp (fichier de travail)
         ↓
   [TRANSLATOR]
         ↓
Film.fr.srt (traduction finale)

Multi-Folders
/media/movies/Film1.mkv ──┐
/media/series/S01E01.mkv ─┤
/media/docs/Doc1.mkv ─────┘
         ↓
   [EXTRACTOR] → parcourt tous les dossiers
         ↓
Film1.en.srt.tmp
S01E01.en.ass.tmp
Doc1.en.srt.tmp
         ↓
   [TRANSLATOR] → parcourt tous les dossiers
         ↓
Film1.fr.srt
S01E01.fr.srt
Doc1.fr.srt

Résultat final :
  - Fichiers vidéo originaux (piste EN intégrée)
  - Traductions .fr.srt dans chaque dossier
  - Pas de fichiers temporaires (si nettoyage activé)
  - Pas de doublons dans le lecteur
```

### Pourquoi les fichiers .en.XXX.tmp ?

Lorsqu'un MKV contient déjà une piste de sous-titres anglais intégrée, extraire en `.en.srt` créerait un doublon visible dans les lecteurs vidéo comme **Plex, Jellyfin, Emby**, etc.

L'extension `.tmp` :
- ✅ Rend le fichier **invisible** pour les lecteurs média (pas détecté comme sous-titre)
- ✅ Permet la traduction par le script translator
- ✅ Est **automatiquement supprimée** une fois le `.fr.srt` créé (si `DELETE_SOURCE_AFTER=true`)

### Support des formats ASS/SSA

Les sous-titres **ASS** (Advanced SubStation Alpha) et **SSA** (SubStation Alpha) contiennent des styles avancés (polices, couleurs, positions). Le translator :

1. **Détecte automatiquement** les formats ASS/SSA extraits (`.en.ass.tmp`, `.en.ssa.tmp`)
2. **Convertit via ffmpeg** → format SRT temporaire (`.en.ssa.to.srt.tmp`)
3. **Nettoie les balises HTML** (`<font>`, `<b>`, `<i>`, etc.) qui restent après conversion
4. **Traduit** le texte propre → `.fr.srt`
5. **Supprime les fichiers temporaires** (si `DELETE_CONVERTED_AFTER=true`)

**Formats supportés :**
- ✅ **SRT** (SubRip) - Direct
- ✅ **ASS** (Advanced SubStation Alpha v4.00+) - Conversion auto
- ✅ **SSA** (SubStation Alpha v4.00) - Conversion auto
- ✅ **VTT** (WebVTT) - Conversion auto
- ❌ **SUP** (HDMV PGS - Blu-ray) - Format image, OCR requis
- ❌ **SUB** (VobSub - DVD) - Format image, OCR requis

---

## 📦 Projets

### 1️⃣ Subtitle Extractor

Agent d'extraction de sous-titres anglais depuis les fichiers MKV.

#### ✨ Fonctionnalités

**Extraction intelligente :**
- ✅ Extraction automatique des pistes de sous-titres anglais depuis les fichiers MKV
- ✅ Support de multiples formats vidéo : MKV, MP4, AVI, MOV, M4V, WEBM, FLV, WMV
- ✅ Support de multiples formats de sous-titres : SRT, ASS, SUP, SSA
- ✅ Détection et utilisation des fichiers de sous-titres externes existants

**Détection des sous-titres français :**
- 🇫🇷 Skip automatique si un fichier de sous-titre français externe est détecté
- 🇫🇷 Skip automatique si une piste de sous-titre français existe dans le MKV
- ⏩ Évite le traitement inutile des contenus déjà traduits

**Optimisations :**
- 🚀 Mode agent avec surveillance continue du dossier
- 📊 Statistiques détaillées après chaque cycle d'extraction
- 🔄 Reprise automatique en cas d'erreur
- ⏭️ Ignore automatiquement les fichiers trailers
- 💾 Pas de duplication : skip si le fichier de travail existe déjà

**Format de sortie :**
- 📝 Fichiers extraits au format `.en.FORMAT.txt` (ex: `.en.srt.txt`)
- 🎯 Extension `.txt` pour éviter les doublons dans les lecteurs vidéo
- 📄 Préserve le format original (SRT, ASS, SUP) dans le nom de fichier

#### ⚙️ Variables d'environnement

| Variable | Valeur par défaut | Description |
|----------|-------------------|-------------|
| `SOURCE_FOLDERS` | `[]` | Liste JSON des dossiers (ex: `["/media/movies", "/media/series"]`) |
| `SOURCE_FOLDER` | `/data` | Ancien format single-folder (ignoré si `SOURCE_FOLDERS` défini) |
| `WATCH_MODE` | `true` | Mode agent continu ou exécution unique |
| `WATCH_INTERVAL` | `3600` | Intervalle de vérification en secondes |
| `LOG_FILE` | `None` | Fichier de log (optionnel, None = console uniquement) |
| `LOG_FILE_MAX_SIZE_MB` | `10` | Taille max par fichier de log avant rotation |
| `LOG_FILE_BACKUP_COUNT` | `2` | Nombre de fichiers de backup à conserver |



#### 📊 Exemple de sortie

**Single-Folder:**
```
[2025-01-02 10:00:00] 🚀 DÉBUT DE L'EXTRACTION
[2025-01-02 10:00:00] 📂 Dossier: /data | Formats: mkv, mp4, avi
[2025-01-02 10:00:01] ✅ Film.mkv | Extrait: Film.en.srt.tmp
[2025-01-02 10:00:02] ⭐️ Film2.mkv | Déjà traduit (piste FR dans MKV)
[2025-01-02 10:00:05] ✅ EXTRACTION TERMINÉE | Total: 2 | Extraits: 1 | Skippés: 1 | Erreurs: 0
```

**Multi-Folders:**
```
[2025-01-02 10:00:00] 🚀 DÉBUT DE L'EXTRACTION
[2025-01-02 10:00:00] 📂 3 dossier(s) configuré(s) | Formats: mkv, mp4, avi
[2025-01-02 10:00:01] 📂 [1/3] Traitement: /media/movies
[2025-01-02 10:00:02]   ✅ Film1.mkv | Extrait: Film1.en.srt.tmp
[2025-01-02 10:00:03]   ⭐️ Film2.mkv | Déjà traduit (sous-titre FR externe)
[2025-01-02 10:00:04] 📂 [2/3] Traitement: /media/series
[2025-01-02 10:00:05]   ✅ S01E01.mkv | Extrait: S01E01.en.ass.tmp
[2025-01-02 10:00:06]   ✓ S01E02.mkv | Source externe trouvée: S01E02.en.srt
[2025-01-02 10:00:07] 📂 [3/3] Traitement: /media/documentaries
[2025-01-02 10:00:08]   ✅ Doc1.mkv | Extrait: Doc1.en.srt.tmp
[2025-01-02 10:00:09]   ❌ Doc2.mkv | Pas de piste sous-titre EN dans le MKV
[2025-01-02 10:00:10]   ❌ Doc3.mp4 | Pas de source (non-MKV)
[2025-01-02 10:00:11] ✅ EXTRACTION TERMINÉE | Total: 7 | Extraits: 4 | Skippés: 2 | Erreurs: 2
[2025-01-02 10:00:11]   ❌ MKV sans piste EN : 1
[2025-01-02 10:00:11]   ⚠️ Non-MKV sans source externe : 1
[2025-01-02 10:00:11] ============================================================
```

#### 🎯 Scénarios

**Film avec sous-titre externe :**
```
Input: Film.mkv + Film.en.srt
→ SKIP (fichier externe déjà disponible)
```

**Film MKV avec piste anglaise :**
```
Input: Film.mkv (piste EN intégrée)
→ Extraction → Film.en.srt.tmp
```

**Film déjà traduit :**
```
Input: Film.mkv + Film.fr.srt
→ SKIP (déjà traduit)
```

---

### 2️⃣ Subtitle Translator

Agent de traduction automatique EN → FR utilisant Google Gemini API.

#### ✨ Fonctionnalités

**Traduction intelligente :**
- ✅ Traduction par lots optimisée (50 lignes par batch)
- ✅ Support multi-formats source : `.en.srt.tmp`, `.en.ass.tmp`, `.en.ssa.tmp` (extraits) + `.en.srt`, `.srt` (externes)
- ✅ Conversion automatique ASS/SSA/VTT → SRT via ffmpeg
- ✅ Nettoyage des balises HTML (`<font>`, `<b>`, etc.) après conversion
- ✅ Gestion des chemins avec caractères spéciaux (conversion via /tmp)
- ✅ Output standardisé : `.fr.srt` (format universel)
- ✅ System instruction optimisée (~20% économie de tokens)
- ✅ Estimation temps restant dynamique avec heure de fin prévue

**Gestion avancée des quotas :**
- 🔑 Rotation automatique entre plusieurs clés API
- 🔄 Support multi-modèles avec quotas indépendants (Gemini 3 Flash + 2.5 Flash)
- ⏰ Cooldown intelligent jusqu'à 11h05 (reset quota quotidien)
- 🔁 Retry automatique sur réponse vide (2 tentatives)
- 💤 Mode veille automatique si tous les quotas épuisés

**Reprise et nettoyage :**
- 📊 Sauvegarde de progression (`.fr.progress.json`)
- ▶️ Reprise automatique après interruption
- 🗑️ Nettoyage automatique **configurable** (par défaut: tout garder)
- 🚀 Skip intelligent (fichiers déjà traduits)

**Logs et debugging :**
- 📝 Logs console avec timestamps (timezone Europe/Paris)
- 📄 Logs fichier optionnels (variable `LOG_FILE`)
- 🐛 Messages d'erreur détaillés pour debug

#### ⚙️ Variables d'environnement

| Variable | Valeur par défaut | Description |
|----------|-------------------|-------------|
| `SOURCE_FOLDERS` | `[]` | Liste JSON des dossiers (ex: `["/media/movies", "/media/series"]`) |
| `SOURCE_FOLDER` | `/data` | Ancien format single-folder (ignoré si `SOURCE_FOLDERS` défini) |
| `WATCH_MODE` | `true` | Mode agent continu ou exécution unique |
| `WATCH_INTERVAL` | `3600` | Intervalle de vérification (secondes) |
| `LOG_FILE` | `None` | Fichier de log (optionnel, None = console uniquement) |
| `LOG_FILE_MAX_SIZE_MB` | `10` | Taille max par fichier de log avant rotation |
| `LOG_FILE_BACKUP_COUNT` | `2` | Nombre de fichiers de backup à conserver |
| `PAUSE_SECONDS` | `10` | Pause entre chaque lot traduit |
| `BATCH_SIZE` | `50` | Nombre de lignes par lot |
| `GEMINI_API_KEYS` | `[]` | Clés API Gemini (JSON array) |
| `GEMINI_MODELS` | `[]` | Modèles Gemini (JSON array) |
| `DELETE_PROGRESS_AFTER` | `false` | Supprimer .fr.progress.json après traduction |
| `DELETE_SOURCE_AFTER` | `false` | Supprimer .en.XXX.tmp après traduction |
| `DELETE_CONVERTED_AFTER` | `false` | Supprimer .to.srt.tmp après traduction |

**Configuration optimale :**

```yaml
environment:
  # Multi-Folders Support
  # Configuration single-folder (classique)
  - SOURCE_FOLDER=/data
  
  # OU configuration multi-folders
  - SOURCE_FOLDERS=["/media/movies", "/media/series", "/media/documentaries"]
  
  # Performance optimisée : ~18 minutes pour 1945 lignes
  - PAUSE_SECONDS=10
  - BATCH_SIZE=50
  
  # Clés API (créer sur https://aistudio.google.com/app/apikey)
  - GEMINI_API_KEYS=["clé-1", "clé-2", "clé-3"]
  
  # Quotas INDÉPENDANTS par modèle
  # Flash 3: 15 RPM, 1000 RPD (prioritaire)
  # Flash 2.5: 10 RPM, 250 RPD (fallback)
  # Total par clé : 25 RPM, 1250 RPD
  - GEMINI_MODELS=["gemini-2.0-flash-exp", "gemini-1.5-flash-8b"]
  
  # Nettoyage automatique (défaut: false = on garde tout)
  # Mettre à true pour supprimer les fichiers temporaires
  - DELETE_PROGRESS_AFTER=false   # Garder .fr.progress.json
  - DELETE_SOURCE_AFTER=false     # Garder .en.XXX.tmp
  - DELETE_CONVERTED_AFTER=false  # Garder .to.srt.tmp
```

**Gestion du nettoyage :**

Par défaut (`false`), tous les fichiers temporaires sont conservés :
- ✅ `.fr.progress.json` → reprise possible après interruption
- ✅ `.en.ssa.tmp` → source originale gardée
- ✅ `.en.ssa.to.srt.tmp` → conversion SRT gardée

Pour un nettoyage automatique (mode production), mettre à `true` :
```yaml
  - DELETE_PROGRESS_AFTER=true    # Supprimer .fr.progress.json
  - DELETE_SOURCE_AFTER=true      # Supprimer .en.XXX.tmp
  - DELETE_CONVERTED_AFTER=true   # Supprimer .to.srt.tmp
```

Résultat final : uniquement `Film.fr.srt` conservé.

#### 📊 Exemple de sortie

**Single-Folder:**
```
[2025-01-02 10:00:00] 🚀 DÉBUT DE LA TRADUCTION
[2025-01-02 10:00:00] 📂 Dossier: /data | Formats: SRT, ASS, SSA, VTT | Modèles: gemini-2.0-flash-exp
[2025-01-02 10:00:00] 🎬 Film.mkv | Source: Film.en.srt.tmp (1945 lignes)
[2025-01-02 10:00:00] 🔑 utilisation clé #1 | modèle gemini-2.0-flash-exp
[2025-01-02 10:00:16] ⏳ Film.mkv | 1-50/1945 (2.6%) | ETA: ~18m (fin: 10:18)
[2025-01-02 10:00:30] ⏳ Film.mkv | 51-100/1945 (5.1%) | ETA: ~17m (fin: 10:17)
...
[2025-01-02 10:17:45] ✅ Film.mkv | Terminé en 17m 45s | Output: Film.fr.srt
[2025-01-02 10:17:45] ✅ TRADUCTION TERMINÉE | Total: 1 | Complétés: 1 | Déjà faits: 0 | Warnings: 0 | Erreurs: 0
```

**Multi-Folders:**
```
[2025-01-02 10:00:00] 🚀 DÉBUT DE LA TRADUCTION
[2025-01-02 10:00:00] 📂 3 dossier(s) configuré(s) | Formats: SRT, ASS, SSA, VTT | Modèles: gemini-2.0-flash-exp
[2025-01-02 10:00:01] 📂 [1/3] Traitement: /media/movies
[2025-01-02 10:00:02]   ⏭️ Film1.mkv | Déjà traduit (Film.fr.srt existe)
[2025-01-02 10:00:03]   🎬 Film2.mkv | Source: Film2.en.srt.tmp (500 lignes)
[2025-01-02 10:00:04]   🔑 utilisation clé #1 | modèle gemini-2.0-flash-exp
[2025-01-02 10:00:20]   ⏳ Film2.mkv | 1-50/500 (10.0%) | ETA: ~8m (fin: 10:08)
...
[2025-01-02 10:08:00]   ✅ Film2.mkv | Terminé en 8m 0s | Output: Film2.fr.srt
[2025-01-02 10:08:01] 📂 [2/3] Traitement: /media/series
[2025-01-02 10:08:02]   🎬 S01E01.mkv | Source: S01E01.en.ass.tmp (300 lignes) | Converting ASS→SRT
[2025-01-02 10:08:03]   🔑 utilisation clé #1 | modèle gemini-2.0-flash-exp
...
[2025-01-02 10:14:00]   ✅ S01E01.mkv | Terminé en 6m 0s | Output: S01E01.fr.srt
[2025-01-02 10:14:01] 📂 [3/3] Traitement: /media/documentaries
[2025-01-02 10:14:02]   ⚠️ Doc1.mkv | Rien à traiter
[2025-01-02 10:14:03]   ⚠️ Doc2.mkv | Format bitmap (SUP/SUB) non supporté sans OCR
[2025-01-02 10:14:04] ✅ TRADUCTION TERMINÉE | Total: 5 | Complétés: 2 | Déjà faits: 1 | Warnings: 2 | Erreurs: 0
[2025-01-02 10:14:04]   ⚠️ Warnings :
[2025-01-02 10:14:04]     - Rien à traiter : 1
[2025-01-02 10:14:04]     - Format non supporté (SUP/SUB) : 1
[2025-01-02 10:14:04] ============================================================
```

#### 🎯 Scénarios

**Fichier extrait du MKV (SRT) :**
```
Input: Film.en.srt.tmp
→ Traduction directe → Film.fr.srt
→ Nettoyage (si DELETE_SOURCE_AFTER=true) → Film.en.srt.tmp supprimé
```

**Fichier extrait du MKV (ASS/SSA) :**
```
Input: Film.en.ssa.tmp (contenu ASS v4.00+)
→ Conversion via /tmp → Film.en.ssa.to.srt.tmp
→ Nettoyage balises HTML (<font>, <b>, etc.)
→ Traduction → Film.fr.srt
→ Nettoyage (si DELETE_*=true) :
   - Film.en.ssa.tmp supprimé
   - Film.en.ssa.to.srt.tmp supprimé
```

**Fichier externe :**
```
Input: Film.en.srt (externe)
→ Traduction → Film.fr.srt
→ Film.en.srt préservé (toujours)
```

**Traduction déjà terminée :**
```
Input: Film.fr.srt (pas de .progress.json)
→ SKIP
```

**Reprise après interruption :**
```
Input: Film.fr.srt + Film.fr.progress.json (last_index: 500)
→ Reprise à ligne 501
→ Continue jusqu'à la fin
→ Nettoyage automatique (si configuré)
```

**Quotas épuisés (Mode WATCH) :**
```
Toutes clés bloquées
→ Calcul next reset : 11h05
→ Sleep jusqu'à 11h05
→ Réveil et reprise automatique
```

**Formats non supportés :**
```
Input: Film.en.sup.tmp (bitmap PGS)
→ SKIP (nécessite OCR)
```

#### 📊 Performance

**Film typique (1945 lignes) :**
- Configuration optimisée (BATCH_SIZE=50, PAUSE=10s) : **~20 minutes**
- Configuration conservatrice (BATCH_SIZE=10, PAUSE=30s) : **~50 minutes**
- **Gain : 2.5x plus rapide !**

**Consommation de quota :**
- Requêtes par film : 1945 / 50 = **39 requêtes**
- Tokens consommés : ~39,000 tokens
- Coût Gemini 3 Flash : ~$0.02 USD/film

**Capacité quotidienne (3 clés) :**
- Quota total : 3 × 1250 RPD = **3750 requêtes/jour**
- Films traduisibles : **~96 films/jour**

---

### Pipeline automatique

```
1. Nouveau film ajouté : Film.mkv
   ↓
2. EXTRACTOR détecte (cycle toutes les heures)
   → Extrait piste EN → Film.en.srt.txt
   ↓
3. TRANSLATOR détecte (cycle toutes les heures)
   → Traduit → Film.fr.srt
   → Nettoie → Film.en.srt.txt supprimé
   ↓
4. Résultat final :
   - Film.mkv (piste EN intégrée)
   - Film.fr.srt (traduction externe)
   ✅ Prêt pour le lecteur vidéo !
```

---

## 🏗️ Structure du projet

```
subtitle-automation/
├── README.md                      # Ce fichier
│
├── extractor/
│   ├── extract_subtitle_en.py    # Script extraction
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements_extractor.txt
│   └── .env.example
│
└── translator/
    ├── translate_srt_gemini.py   # Script traduction
    ├── Dockerfile
    ├── docker-compose.yml
    ├── requirements_translator.txt
    └── .env.example
```

---

## 📊 Technologies utilisées

### Extractor
- **Python 3.12** : Langage principal
- **mkvtoolnix (mkvmerge, mkvextract)** : Extraction pistes MKV et analyse des codecs
- **Docker** : Conteneurisation

### Translator
- **Python 3.12** : Langage principal
- **Google Gemini API** : Traduction (Flash 3 + Flash 2.5)
- **ffmpeg** : Conversion ASS/SSA/VTT → SRT
- **pysrt** : Manipulation fichiers SRT
- **pytz** : Gestion timezone (Europe/Paris)
- **Docker** : Conteneurisation

---

## 📝 Notes importantes

- ✅ Les fichiers originaux ne sont **jamais modifiés**
- ✅ Les fichiers externes (`.en.srt`, `.srt`) sont **préservés**
- ✅ Nettoyage automatique **configurable** via variables (défaut: tout garder)
- ✅ Format de sortie : `.fr.srt` (standard universel)
- ✅ Support ASS/SSA avec **conversion automatique** et **nettoyage HTML**
- ✅ Gestion des **chemins avec caractères spéciaux** (Unicode, tirets, apostrophes)
- ✅ Les trailers sont **automatiquement ignorés** (nom contenant `-trailer`)
- ✅ Les films avec sous-titres français sont **automatiquement skippés**
- ✅ Quotas par modèle indépendants (Flash 2.0 + Flash 1.5 = cumulatif)
- ✅ Reprise automatique après interruption
- ✅ Logs avec timestamps (timezone Europe/Paris)
- ✅ Logs fichier optionnels via `LOG_FILE` avec **rotation automatique**
- ✅ Messages d'erreur détaillés pour debugging
- ✅ **Support multi-folders** pour traiter plusieurs collections simultanément
- ✅ **Rétro-compatibilité** avec l'ancien format `SOURCE_FOLDER`
- ✅ **Stats agrégées** sur tous les dossiers configurés

---

## 📊 Logs

### Rotation automatique

Les logs fichier (si `LOG_FILE` configuré) utilisent une **rotation automatique** pour éviter de remplir le disque :

```yaml
# Configuration par défaut
LOG_FILE=/data/translator.log
LOG_FILE_MAX_SIZE_MB=10        # Taille max par fichier
LOG_FILE_BACKUP_COUNT=2        # Nombre de backups
```

**Résultat :**
```
translator.log       (0-10 MB)   ← Fichier actuel
translator.log.1     (10 MB)     ← Backup 1
translator.log.2     (10 MB)     ← Backup 2
Total: 3 fichiers max, 30 MB
```

Quand `translator.log` atteint 10 MB → rotation automatique.

### Format compact

Les logs sont **compacts et sur une seule ligne** pour faciliter la lecture et réduire l'espace disque :

**Extractor (single-folder):**
```
[2026-01-01 10:00:00] 🚀 DÉBUT DE L'EXTRACTION
[2026-01-01 10:00:00] 📂 Dossier: /data | Formats: mkv, mp4, avi
[2026-01-01 10:00:01] ✅ Film.mkv | Extrait: Film.en.ssa.tmp
[2026-01-01 10:00:02] ⏭️ Film2.mkv | Déjà traduit (piste FR dans MKV)
[2026-01-01 10:00:03] ❌ Film3.mkv | Pas de piste sous-titre EN dans le MKV
[2026-01-01 10:00:05] ✅ EXTRACTION TERMINÉE | Total: 10 | Extraits: 5 | Skippés: 3 | Erreurs: 2
[2026-01-01 10:00:05]   ❌ MKV sans piste EN : 1
[2026-01-01 10:00:05]   ⚠️ Non-MKV sans source externe : 1
```

**Extractor (multi-folders):**
```
[2026-01-01 10:00:00] 🚀 DÉBUT DE L'EXTRACTION
[2026-01-01 10:00:00] 📂 3 dossier(s) configuré(s) | Formats: mkv, mp4, avi
[2026-01-01 10:00:01] 📂 [1/3] Traitement: /media/movies
[2026-01-01 10:00:02]   ✅ Film1.mkv | Extrait: Film1.en.srt.tmp
[2026-01-01 10:00:03]   ⭐️ Film2.mkv | Déjà traduit (sous-titre FR externe)
[2026-01-01 10:00:04] 📂 [2/3] Traitement: /media/series
[2026-01-01 10:00:05]   ✅ S01E01.mkv | Extrait: S01E01.en.ass.tmp
[2026-01-01 10:00:06]   ❌ S01E02.mkv | Pas de piste sous-titre EN dans le MKV
[2026-01-01 10:00:10] ✅ EXTRACTION TERMINÉE | Total: 25 | Extraits: 15 | Skippés: 8 | Erreurs: 2
[2026-01-01 10:00:10]   ❌ MKV sans piste EN : 1
[2026-01-01 10:00:10]   ⚠️ Non-MKV sans source externe : 1
[2026-01-01 10:00:10] ============================================================
```

**Translator (single-folder):**
```
[2026-01-01 10:00:00] 🚀 DÉBUT DE LA TRADUCTION
[2026-01-01 10:00:00] 📂 Dossier: /data | Formats: SRT, ASS, SSA, VTT | Modèles: gemini-2.0-flash-exp
[2026-01-01 10:00:00] 🎬 Film.mkv | Source: Film.en.ssa.tmp (1945 lignes) | Converting ASS→SRT
[2026-01-01 10:00:15] ⏳ Film.mkv | 1-50/1945 (2.6%) | ETA: ~18m (fin: 10:18)
[2026-01-01 10:00:30] ⏳ Film.mkv | 51-100/1945 (5.1%) | ETA: ~17m (fin: 10:17)
...
[2026-01-01 10:17:45] ✅ Film.mkv | Terminé en 17m 45s | Output: Film.fr.srt
[2026-01-01 10:17:45] ✅ TRADUCTION TERMINÉE | Total: 1 | Complétés: 1 | Warnings: 0 | Erreurs: 0
```

**Translator (multi-folders):**
```
[2026-01-01 10:00:00] 🚀 DÉBUT DE LA TRADUCTION
[2026-01-01 10:00:00] 📂 3 dossier(s) configuré(s) | Formats: SRT, ASS, SSA, VTT | Modèles: gemini-2.0-flash-exp
[2026-01-01 10:00:01] 📂 [1/3] Traitement: /media/movies
[2026-01-01 10:00:02]   🎬 Film1.mkv | Source: Film1.en.srt.tmp (500 lignes)
[2026-01-01 10:00:20]   ⏳ Film1.mkv | 1-50/500 (10.0%) | ETA: ~8m (fin: 10:08)
...
[2026-01-01 10:08:00]   ✅ Film1.mkv | Terminé en 8m 0s | Output: Film1.fr.srt
[2026-01-01 10:08:01] 📂 [2/3] Traitement: /media/series
[2026-01-01 10:08:02]   ⚠️ S01E01.mkv | Rien à traiter
[2026-01-01 10:08:03]   ⚠️ S01E02.mkv | Format bitmap (SUP/SUB) non supporté sans OCR
...
[2026-01-01 10:20:00] ✅ TRADUCTION TERMINÉE | Total: 12 | Complétés: 8 | Déjà faits: 2 | Warnings: 2 | Erreurs: 0
[2026-01-01 10:20:00]   ⚠️ Warnings :
[2026-01-01 10:20:00]     - Rien à traiter : 1
[2026-01-01 10:20:00]     - Format non supporté (SUP/SUB) : 1
[2026-01-01 10:20:00] ============================================================
```

**Avantages :**
- 📉 **~30% de lignes en moins** par rapport à l'ancien format
- 🔍 **Facile à grep/filtrer** (tout sur une ligne)
- 📊 **Statistiques en fin de cycle** (pas de détails intermédiaires)
- ⚡ **Rapide à lire** (pas de séparateurs ni lignes vides)
- ✅ **Indicateur de progression multi-folders** : `[1/3]`, `[2/3]`, etc.

---

## 🔄 Migration vers Multi-Folders

### Pourquoi migrer ?

Le support multi-folders permet de :
- ✅ Gérer plusieurs collections de médias (films, séries, documentaires)
- ✅ Centraliser les logs et stats de tous les dossiers
- ✅ Simplifier la gestion Docker (un seul conteneur au lieu d'un par dossier)
- ✅ Réduire la consommation de ressources

### Comment migrer ?

**Avant (single-folder) :**
```yaml
# .env
SOURCE_FOLDER=/media/movies
```

**Après (multi-folders) :**
```yaml
# .env
SOURCE_FOLDERS=["/media/movies", "/media/series", "/media/documentaries"]
```

**Docker volumes :**
```yaml
# docker-compose.yml
volumes:
  - /path/to/movies:/media/movies
  - /path/to/series:/media/series
  - /path/to/docs:/media/documentaries
```

### Rétro-compatibilité

Pas besoin de migrer immédiatement ! Les deux formats fonctionnent :
- **`SOURCE_FOLDER`** : Ancien format, toujours supporté
- **`SOURCE_FOLDERS`** : Nouveau format, prioritaire si défini

**Migration progressive :**
1. Tester avec un seul dossier : `SOURCE_FOLDERS=["/media/movies"]`
2. Ajouter progressivement : `SOURCE_FOLDERS=["/media/movies", "/media/series"]`
3. Supprimer `SOURCE_FOLDER` une fois validé

---

## 📄 Licence

MIT
