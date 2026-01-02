# 🎬 Subtitle Automation Suite

Pipeline automatisé d'extraction et de traduction de sous-titres pour films et séries. Extrait les sous-titres anglais des fichiers MKV et les traduit automatiquement en français via Google Gemini API.

## 📋 Vue d'ensemble

Ce projet combine deux agents Docker qui travaillent en tandem :

1. **🎯 Subtitle Extractor** : Extrait les sous-titres anglais des pistes MKV
2. **🌐 Subtitle Translator** : Traduit automatiquement EN → FR avec Google Gemini API

### Workflow complet

```
Film.mkv (piste EN intégrée)
         ↓
   [EXTRACTOR]
         ↓
Film.en.srt.txt (fichier de travail)
         ↓
   [TRANSLATOR]
         ↓
Film.fr.srt (traduction finale)

Résultat final :
  - Film.mkv (piste EN intégrée)
  - Film.fr.srt (traduction externe)
  - Pas de fichiers temporaires
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

1. **Détecte automatiquement** les formats ASS/SSA extraits (`.en.ass.txt`, `.en.ssa.txt`)
2. **Convertit via ffmpeg** → format SRT temporaire (`.en.ssa.to.srt.txt`)
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
| `SOURCE_FOLDER` | `/data` | Chemin vers le dossier contenant les vidéos |
| `WATCH_MODE` | `true` | Mode agent continu ou exécution unique |
| `WATCH_INTERVAL` | `3600` | Intervalle de vérification en secondes |
| `LOG_FILE` | `None` | Fichier de log (optionnel, None = console uniquement) |

#### 🚀 Démarrage rapide

```bash
cd extractor/

# 1. Build de l'image Docker
docker build -t subtitle-extractor-auto .

# 2. Adapter le chemin dans docker-compose.yml
# Éditer volumes: pour pointer vers vos films

# 3. Démarrer le service
docker-compose up -d

# 4. Voir les logs
docker-compose logs -f
```

#### 📊 Exemple de sortie

```
[2025-12-31 10:00:00] 🎬 Traitement : Film.mkv
[2025-12-31 10:00:00]   track 2 | lang=en | name=english | codec=SubRip/SRT
[2025-12-31 10:00:00]   → extraction sous-titre EN (track 2) depuis MKV
[2025-12-31 10:00:05]   ✅ extrait → Film.en.srt.txt
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
→ Extraction → Film.en.srt.txt
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
- ✅ Support multi-formats source : `.en.srt.txt`, `.en.ass.txt`, `.en.ssa.txt` (extraits) + `.en.srt`, `.srt` (externes)
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
| `SOURCE_FOLDER` | `/data` | Chemin vers les vidéos |
| `WATCH_MODE` | `true` | Mode agent continu ou exécution unique |
| `WATCH_INTERVAL` | `3600` | Intervalle de vérification (secondes) |
| `LOG_FILE` | `None` | Fichier de log (optionnel, None = console uniquement) |
| `PAUSE_SECONDS` | `10` | Pause entre chaque lot traduit |
| `BATCH_SIZE` | `50` | Nombre de lignes par lot |
| `GEMINI_API_KEYS` | `[]` | Clés API Gemini (JSON array) |
| `GEMINI_MODELS` | `[]` | Modèles Gemini (JSON array) |
| `DELETE_PROGRESS_AFTER` | `false` | Supprimer .fr.progress.json après traduction |
| `DELETE_SOURCE_AFTER` | `false` | Supprimer .en.XXX.txt après traduction |
| `DELETE_CONVERTED_AFTER` | `false` | Supprimer .to.srt.txt après traduction |

**Configuration optimale :**

```yaml
environment:
  # Performance optimisée : ~18 minutes pour 1945 lignes
  - PAUSE_SECONDS=10
  - BATCH_SIZE=50
  
  # Clés API (créer sur https://aistudio.google.com/app/apikey)
  - GEMINI_API_KEYS=["clé-1", "clé-2", "clé-3"]
  
  # Quotas INDÉPENDANTS par modèle
  # Flash 3: 15 RPM, 1000 RPD (prioritaire)
  # Flash 2.5: 10 RPM, 250 RPD (fallback)
  # Total par clé : 25 RPM, 1250 RPD
  - GEMINI_MODELS=["gemini-3-flash-preview", "gemini-2.5-flash"]
  
  # Nettoyage automatique (défaut: false = on garde tout)
  # Mettre à true pour supprimer les fichiers temporaires
  - DELETE_PROGRESS_AFTER=false   # Garder .fr.progress.json
  - DELETE_SOURCE_AFTER=false     # Garder .en.XXX.txt
  - DELETE_CONVERTED_AFTER=false  # Garder .to.srt.txt
```

**Gestion du nettoyage :**

Par défaut (`false`), tous les fichiers temporaires sont conservés :
- ✅ `.fr.progress.json` → reprise possible après interruption
- ✅ `.en.ssa.txt` → source originale gardée
- ✅ `.en.ssa.to.srt.txt` → conversion SRT gardée

Pour un nettoyage automatique (mode production), mettre à `true` :
```yaml
  - DELETE_PROGRESS_AFTER=true    # Supprimer .fr.progress.json
  - DELETE_SOURCE_AFTER=true      # Supprimer .en.XXX.txt
  - DELETE_CONVERTED_AFTER=true   # Supprimer .to.srt.txt
```

Résultat final : uniquement `Film.fr.srt` conservé.

#### 🚀 Démarrage rapide

```bash
cd translator/

# 1. Build de l'image Docker
docker build -t subtitle-translator-auto .

# 2. Configurer docker-compose.yml
# Éditer volumes + GEMINI_API_KEYS

# 3. Démarrer le service
docker-compose up -d

# 4. Voir les logs
docker-compose logs -f
```

#### 📊 Exemple de sortie

```
[2025-12-31 10:00:00] 🎬 Traitement : Film.mkv
[2025-12-31 10:00:00]   📄 Source : Film.en.srt.txt
[2025-12-31 10:00:00]   📊 Lignes : 1945
[2025-12-31 10:00:00]   ▶ Début à : 1
[2025-12-31 10:00:16]   ✅ 1-50 / 1945 (2.6%)
[2025-12-31 10:00:16]   ⏳ pause 10s
[2025-12-31 10:00:26]   ⏱️ Restant : ~18m (fin prévue : 10:18)
...
[2025-12-31 10:18:00]   🎉 Traduction terminée
[2025-12-31 10:18:00]   🗑️ Nettoyage : Film.fr.progress.json supprimé
[2025-12-31 10:18:00]   🗑️ Nettoyage : Film.en.srt.txt supprimé
```

#### 🎯 Scénarios

**Fichier extrait du MKV (SRT) :**
```
Input: Film.en.srt.txt
→ Traduction directe → Film.fr.srt
→ Nettoyage (si DELETE_SOURCE_AFTER=true) → Film.en.srt.txt supprimé
```

**Fichier extrait du MKV (ASS/SSA) :**
```
Input: Film.en.ssa.txt (contenu ASS v4.00+)
→ Conversion via /tmp → Film.en.ssa.to.srt.txt
→ Nettoyage balises HTML (<font>, <b>, etc.)
→ Traduction → Film.fr.srt
→ Nettoyage (si DELETE_*=true) :
   - Film.en.ssa.txt supprimé
   - Film.en.ssa.to.srt.txt supprimé
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
Input: Film.en.sup.txt (bitmap PGS)
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

## 🚀 Workflow complet

### Lancer les 2 agents en parallèle

```bash
# Terminal 1 - Extractor
cd extractor/
docker build -t subtitle-extractor-auto .

# Terminal 2 - Translator
cd translator/
docker build -t subtitle-translator-auto .

# Utiliser le docker-compose à la racine du projet
```

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
- ✅ Quotas par modèle indépendants (Flash 3 + Flash 2.5 = cumulatif)
- ✅ Reprise automatique après interruption
- ✅ Logs avec timestamps (timezone Europe/Paris)
- ✅ Logs fichier optionnels via `LOG_FILE`
- ✅ Messages d'erreur détaillés pour debugging

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

**Extractor :**
```
[2026-01-01 10:00:00] 🚀 DÉBUT DE L'EXTRACTION
[2026-01-01 10:00:00] 📂 Dossier: /data | Formats: mkv, mp4, avi | Ignore: trailers
[2026-01-01 10:00:01] ✅ Film.mkv | Extrait: Film.en.ssa.txt
[2026-01-01 10:00:02] ⏭️ Film2.mkv | Déjà traduit (piste FR dans MKV)
[2026-01-01 10:00:05] ✅ EXTRACTION TERMINÉE | Total: 10 | Extraits: 5 | Skippés: 3 | Erreurs: 2
```

**Translator :**
```
[2026-01-01 10:00:00] 🚀 DÉBUT DE LA TRADUCTION
[2026-01-01 10:00:00] 📂 Dossier: /data | Formats: SRT, ASS, SSA, VTT | Modèles: gemini-3-flash-preview
[2026-01-01 10:00:00] 🎬 Film.mkv | Source: Film.en.ssa.txt (1945 lignes) | Converting ASS→SRT
[2026-01-01 10:00:15] ⏳ Film.mkv | 1-50/1945 (2.6%) | ETA: ~18m (fin: 10:18)
[2026-01-01 10:00:30] ⏳ Film.mkv | 51-100/1945 (5.1%) | ETA: ~17m (fin: 10:17)
...
[2026-01-01 10:17:45] ✅ Film.mkv | Terminé en 17m 45s | Output: Film.fr.srt
[2026-01-01 10:17:45] ✅ TRADUCTION TERMINÉE | Total: 1 | Complétés: 1 | Erreurs: 0
```

**Avantages :**
- 📉 **~30% de lignes en moins** par rapport à l'ancien format
- 🔍 **Facile à grep/filtrer** (tout sur une ligne)
- 📊 **Statistiques en fin de cycle** (pas de détails intermédiaires)
- ⚡ **Rapide à lire** (pas de séparateurs ni lignes vides)

---

## 📄 Licence

MIT
