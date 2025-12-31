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

### Pourquoi les fichiers .en.srt.txt ?

Lorsqu'un MKV contient déjà une piste de sous-titres anglais intégrée, extraire en `.en.srt` créerait un doublon visible dans les lecteurs vidéo. L'extension `.txt` rend le fichier invisible pour les lecteurs tout en permettant la traduction, puis il est automatiquement supprimé une fois le `.fr.srt` créé.

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
- ✅ Support multi-formats source : `.en.srt.txt`, `.en.ass.txt` (extraits) + `.en.srt`, `.srt` (externes)
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
- 🗑️ Nettoyage automatique des fichiers temporaires (`.progress.json` + `.en.srt.txt`)
- 🚀 Skip intelligent (fichiers déjà traduits)

#### ⚙️ Variables d'environnement

| Variable | Valeur par défaut | Description |
|----------|-------------------|-------------|
| `SOURCE_FOLDER` | `/data` | Chemin vers les vidéos |
| `WATCH_MODE` | `true` | Mode agent continu ou exécution unique |
| `WATCH_INTERVAL` | `3600` | Intervalle de vérification (secondes) |
| `PAUSE_SECONDS` | `10` | Pause entre chaque lot traduit |
| `BATCH_SIZE` | `50` | Nombre de lignes par lot |
| `GEMINI_API_KEYS` | `[]` | Clés API Gemini (JSON array) |
| `GEMINI_MODELS` | `[]` | Modèles Gemini (JSON array) |

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

**Fichier extrait du MKV :**
```
Input: Film.en.srt.txt
→ Traduction → Film.fr.srt
→ Nettoyage → Film.en.srt.txt supprimé
```

**Fichier externe :**
```
Input: Film.en.srt (externe)
→ Traduction → Film.fr.srt
→ Film.en.srt préservé
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
→ Nettoyage automatique
```

**Quotas épuisés (Mode WATCH) :**
```
Toutes clés bloquées
→ Calcul next reset : 11h05
→ Sleep jusqu'à 11h05
→ Réveil et reprise automatique
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
git clone https://github.com/GhislainSamy/AI-AutoSubtitleTranslator.git
# Terminal 1 - Extractor
cd extractor/
docker build -t subtitle-extractor .

# Terminal 2 - Translator
cd ../translator/
docker build -t subtitle-translator .

# ensuite utilisé le docker-compose à la racine du projet.
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
   → Nettoie → Film.en.srt.txt + .fr.progress.json supprimé
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
- **mkvtoolnix** : Extraction pistes MKV (mkvmerge, mkvextract)
- **Docker** : Conteneurisation

### Translator
- **Python 3.12** : Langage principal
- **Google Gemini API** : Traduction (Flash 3 + Flash 2.5)
- **pysrt** : Manipulation fichiers SRT
- **pytz** : Gestion timezone (Europe/Paris)
- **Docker** : Conteneurisation

---

## 📝 Notes importantes

- ✅ Les fichiers originaux ne sont **jamais modifiés**
- ✅ Les fichiers externes (`.en.srt`, `.srt`) sont **préservés**
- ✅ Les fichiers temporaires (`.en.srt.txt` et `.fr.progress.json` ) sont **supprimés après traduction**
- ✅ Format de sortie : `.fr.srt` (standard universel)
- ✅ Les trailers sont **automatiquement ignorés** (nom contenant `-trailer`)
- ✅ Les films avec sous-titres français sont **automatiquement skippés**
- ✅ Quotas par modèle indépendants (Flash 3 + Flash 2.5 = cumulatif)
- ✅ Reprise automatique après interruption
- ✅ Logs avec timestamps (timezone Europe/Paris)

---

## 📄 Licence

MIT
