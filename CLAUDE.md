# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Todo List

Keep track of ideas and improvements to implement:

### Current Priority: MatchDeductor Refactoring

**Feuille de route de refactorisation MatchDeductor** :

1. **[x] Commit current changes** (validation probabiliste joueur-personnage)
2. **[x] Create new branch** "match-deductor-refacto" 
3. **[x] Refactor MatchDeductor** avec pattern "Pipeline with Feedback Loops"
   - ✅ Phase 1: Character Detection (highest confidence)
   - ✅ Phase 2: Timer Refinement (with character context)  
   - ✅ Phase 3: Player Detection (with character+timer context)
   - ✅ Phase 4: Match Deduction (with all contexts)
4. **[x] Prioriser la détection des personnages** (données les plus fiables)
   - ✅ Characters = highest confidence data 
   - ✅ Détectés en PREMIER pour guider timer et players
5. **[x] Organiser en méthodes phases claires** avec refinement
   - ✅ 4 phases distinctes avec feedback loops
   - ✅ Enhanced methods avec contexte personnage
   - ✅ Statistiques détaillées par phase
6. **[x] Maintenir la logique holistique** mais avec structure lisible
   - ✅ Pipeline orchestré mais interdépendances préservées

**Principe clé** : Les personnages ont la plus haute confiance et doivent guider la déduction des autres éléments.

### ✅ COMPLETED: Interactive Menu System

**Interface CLI interactive pour l'analyse de replays SF6** :

1. **[x] Système de navigation au clavier** implémenté
   - ✅ Navigation avec flèches ↑↓ et validation par Entrée
   - ✅ Annulation gracieuse avec Ctrl+C à tout moment
   - ✅ Interface utilisateur colorée avec émojis et formatage

2. **[x] Menus de sélection de source** implémentés
   - ✅ Choix entre fichier local et URL en ligne
   - ✅ Validation des extensions vidéo pour fichiers locaux
   - ✅ Test de résolution en temps réel pour URLs

3. **[x] Configuration interactive d'analyse** implémentée
   - ✅ Sélection fréquence extraction (frames/minute)
   - ✅ Choix pipeline asynchrone vs séquentiel
   - ✅ Configuration nombre de workers OCR
   - ✅ Options de sauvegarde des frames

4. **[x] Interface de modification ROI** implémentée
   - ✅ Visualisation des ROIs actuels
   - ✅ Modification interactive des coordonnées
   - ✅ Validation des coordonnées en temps réel
   - ✅ Sauvegarde automatique des modifications

5. **[x] Script d'entrée unifié** `interactive_export.py`
   - ✅ Intégration complète avec pipelines existants
   - ✅ Affichage récapitulatif de configuration
   - ✅ Gestion d'erreurs et suggestions étapes suivantes

**Usage :**
```bash
# Interface interactive complète (recommandé pour nouveaux utilisateurs)
python interactive_export.py

# L'interface guide à travers:
# 1. Sélection type de source (local/URL)
# 2. Saisie et validation de la source
# 3. Configuration des paramètres d'analyse
# 4. Modification optionnelle des ROIs
# 5. Confirmation et lancement automatique
```

**Avantages :**
- **User-friendly** : Plus besoin de connaître les paramètres CLI
- **Validation en temps réel** : Vérification des fichiers et URLs
- **Configuration guidée** : Questions contextuelles avec valeurs par défaut
- **Intégration seamless** : Utilise les pipelines existants sans modification
- **ROI management** : Interface intuitive pour ajuster les zones d'analyse

### ✅ COMPLETED: Async Pipeline Implementation

**Pipeline Asynchrone pour export.py** :

1. **[x] Architecture Producer/Consumer** implémentée
   - ✅ Frame Producer: Extraction async avec queue management
   - ✅ OCR Workers: Pool de workers parallèles avec timeout
   - ✅ JSON Writer: Écriture buffered par batch
   - ✅ Queue système: Communication non-bloquante entre étapes

2. **[x] Performance Optimizations**
   - ✅ 3+ workers OCR en parallèle (configurable)
   - ✅ Queues avec backpressure (50 frames, 100 résultats)
   - ✅ Batch writing (20 frames par écriture JSON)
   - ✅ Thread executor pour I/O bloquantes

3. **[x] Nouveau fichier `async_export.py`**
   - ✅ Compatible avec toutes les options d'export.py
   - ✅ Gestion gracieuse des erreurs et timeouts
   - ✅ Métriques de performance intégrées
   - ✅ Configuration flexible des workers

**Usage :**
```bash
# Pipeline asynchrone (3-5x plus rapide)
python async_export.py input/video.mp4 --workers 5

# Avec configuration avancée
python async_export.py "https://youtube.com/watch?v=ID" --workers 3 --max-frames 200
```

**Gains de performance attendus :**
- **3-5x plus rapide** que export.py séquentiel
- **Utilisation CPU/GPU optimale** : OCR en parallèle pendant extraction
- **Mémoire contrôlée** : Queues avec taille limitée
- **I/O efficace** : Écriture JSON par batch au lieu de frame par frame

### Future Improvements

- [ ] Add support for multiple video resolutions and UI scaling
- [ ] Optimize OCR performance for real-time analysis
- [ ] Add match statistics export (win rates, character usage, etc.)
- [ ] Implement automated round winner detection
- [ ] Add support for tournament bracket tracking
- [ ] Create web interface for match analysis visualization

### Match Detection Issues to Fix

**Problème identifié avec EvoTop8 :** La logique de déduction des matches ne respecte pas parfaitement la structure SF6.

**Exemple concret - Match Kakeru vs Fuudo :**
- **Réalité** : 4 sets courts (2-3 rounds chacun)
  - Set 1 (00:00:54) : Kakeru (JP) vs Fuudo (ED) - 2 rounds
  - Set 2 (~00:03:15) : Kakeru (JP) vs Fuudo (BLANKA) - 2 rounds  
  - Set 3 (~00:05:31) : Kakeru (JP) vs Fuudo (DEE JAY) - 2 rounds
  - Set 4 (~00:07:07) : Kakeru (JP) vs Fuudo (DEE JAY) - 3 rounds
- **Détection actuelle** : 1 set long de 4 rounds + attribution erronée du match suivant

**Todo List pour correction :**
- [ ] Identifier pourquoi l'extraction des joueurs récupère les mauvais noms
- [ ] Vérifier que la logique de cohérence des joueurs fonctionne
- [ ] Analyser les gaps temporels entre Kakeru/Fuudo et MenaRD/Phenom  
- [ ] Créer un test pour valider la séparation des matches

**Root cause :** L'extraction des noms de joueurs attribue incorrectement "Kakeru/Fuudo" au match MenaRD (BLANKA) vs Phenom (CAMMY) à 00:11:14.

**✅ RÉSOLU :** Marges temporelles réduites (-30s, +2min au lieu de -1min, +5min) pour éviter les débordements.

## Flow de Déduction des Matches - Formats de Discussion

### Format 1 : Arbre de Décision (pour logique métier)

```
📊 PIPELINE CHARACTERS FIRST - DÉDUCTION MATCHES SF6

Phase 1: FRAME PROCESSING (Characters First)
├── Character Detection (Priorité 1 - Données les plus fiables)
├── Timer Refinement (Contexte personnages)
└── Player Detection (Contexte personnages + timers)

Phase 2: ROUND DETECTION
├── IF timer ∈ [95-99] ET gap_temporel > 30s → NOUVEAU ROUND (conf: 0.9)
├── ELSE IF timer_saut > 20 points → NOUVEAU ROUND (conf: 0.8)
├── ELSE IF timer < 50 PUIS timer ≥ 80 → NOUVEAU ROUND (conf: 0.95)
└── VALIDATION: durée ≥ 120s ET confiance ≥ 0.5

Phase 3: SET GROUPING
├── IF personnages_identiques ET gap_temporel ≤ 300s → MÊME SET
└── ELSE → NOUVEAU SET
└── VALIDATION: rounds_count ≥ 2 ET cohérence_personnages ≥ 0.5

Phase 4: MATCH GROUPING
├── IF gap_temporel ≤ 180s ET joueurs_cohérents ET 1_seul_perso_change → MÊME MATCH
├── ELSE IF 2_persos_changent → NOUVEAU MATCH (règle SF6)
└── ELSE → NOUVEAU MATCH
└── VALIDATION: (sets ≥ 2) OU (sets = 1 ET rounds ≥ 3)
```

### Format 5 : État-Transition (pour flow temporel)

```
MACHINE À ÉTATS - DÉTECTION MATCHES SF6

┌─────────────────┐  timer~99 détecté   ┌─────────────────┐
│   IDLE_VIDEO    │ ──────────────────► │  POTENTIAL_ROUND│
│ (aucun timer)   │     après gap       │ (timer élevé +  │
└─────────────────┘                     │  personnages)   │
        ▲                               └─────────────────┘
        │                                        │
        │ timeout (60s sans timer)               │ validation OK
        │                                        ▼
┌─────────────────┐                   ┌─────────────────┐
│ INTER_MATCH_GAP │                   │   ROUND_ACTIVE  │◄──┐
│(entre 2 matchs)│                   │ (timer 99→0...) │   │
└─────────────────┘                   └─────────────────┘   │
        ▲                                      │            │
        │                                      │ nouveau    │ même
        │ joueurs différents                   │ timer~99   │ perso
        │ OU gap > 180s                        ▼            │
┌─────────────────┐               ┌─────────────────┐       │
│   MATCH_END     │               │   ROUND_END     │───────┘
│ (fin confirmée) │               │ (timer→bas)     │
└─────────────────┘               └─────────────────┘
        ▲                                  │
        │                                  │ analyse changements
        │                                  ▼
        │                       ┌─────────────────┐
        │                       │ CHARACTER_CHECK │
        │                       │ (règle SF6)     │
        │                       └─────────────────┘
        │                            │         │
        │ 2 persos changent          │         │ 0-1 perso change
        │ (nouveau match)            ▼         ▼
        │                  ┌─────────────────┐
        │                  │    SET_END      │
        │                  │ (nouveau set)   │
        │                  └─────────────────┘
        │                           │
        └───────────────────────────┘
```

**Usage des formats :**
- **Format 1 (Arbre)** : Affiner seuils, conditions, priorités, debug
- **Format 5 (États)** : Gérer transitions temporelles, timeouts, retours aux états d'attente

- [ ] Add support for other fighting games (Tekken, Mortal Kombat)

*Note: When an item is completed, remove it from this list. Add new ideas as they come up.*

## Project Overview

This is a **Street Fighter 6 replay analysis tool** that extracts game data from video replays using computer vision and OCR. The system can analyze match videos to detect:
- Timer values during matches
- Character names for both players
- Match progression data

## Street Fighter 6 Match Structure

Understanding SF6 match hierarchy is crucial for proper analysis:

### Hierarchy
```
MATCH
├── SET 1 (e.g. RYU vs CHUN-LI)
│   ├── Round 1 (timer: 99→0)
│   ├── Round 2 (timer: 99→0)
│   └── Round 3 (timer: 99→0)
├── SET 2 (e.g. KEN vs CAMMY - character switch)
│   ├── Round 1 (timer: 99→0)
│   └── Round 2 (timer: 99→0)
└── SET 3 (e.g. RYU vs CHUN-LI - back to original)
    ├── Round 1 (timer: 99→0)
    └── Round 2 (timer: 99→0)
```

### Business Rules

#### Timer Logic
- **Timer countdown**: Each round starts at 99 seconds and counts down to 0
- **Real start time calculation**: If timer detected at value X, real round start = detection_time - (99-X) - 1 second
- **Round detection**: Look for timer transitions from low values (<50) to high values (≥80)
- **Pattern variations**: Timer may start at 99, 98, 97, or other high values depending on detection timing

#### Character Mechanics  
- **Set definition**: Same character matchup (character1 vs character2)
- **Character switches**: Players can change characters between sets within same match
- **Consistency**: Within a set, characters remain constant across all rounds

#### Match Validation Rules
- **Round validation**: 
  - Timer coverage ≥70% of round duration
  - Timer pattern shows decreasing trend
  - Timer starts ≥80 (flexible threshold)
- **Set validation**: Minimum 2 rounds per set
- **Match validation**: Either ≥2 sets OR 1 set with ≥3 rounds

#### Transition Periods
- **Between rounds**: 5-30 seconds of camera transitions, replays, UI screens
- **Between sets**: Character selection screens, longer transitions
- **Between matches**: Several minutes gap, commentary, analysis

### Detection Strategy

The system uses **timer pattern coherency** rather than fixed time gaps:
- Detects timer transitions: low→high, significant jumps (>20 points), moderate increases (≥85)
- Groups consecutive rounds with same characters into sets
- Groups sets with reasonable temporal proximity into matches
- Handles OCR gaps during transitions gracefully by continuing character context

## Development Environment

### Container-based Development
The project uses Docker containers for consistent development environments:

```bash
# Start development environment
docker compose up -d

# Access backend container for video processing
docker compose exec backend bash

# IMPORTANT: Python execution must be done inside containers
# DO NOT run python directly on host - use container instead:
docker compose exec backend python script.py
docker compose exec backend python3 script.py

# Access Jupyter notebook environment for analysis
docker compose up notebook
# Then access http://localhost:8888
```

### Python Environment
```bash
# Install dependencies directly (if not using containers)
pip install -r system/backend/requirements.txt
```

## Core Architecture

### Main Components

1. **Frame Extraction** (`src/frame_extractor.py`)
   - `FrameExtractor` class handles video processing
   - Supports both local video files and online video streams (via yt-dlp)
   - Extracts frames at configurable intervals (default: 12 frames/minute)
   - Supports both saving frames to disk and generating frames in-memory

2. **Video Resolution** (`src/video_resolver.py`)
   - `VideoResolver` class handles automatic detection of local files vs URLs
   - Integrates yt-dlp for online stream resolution
   - Extracts metadata (title, duration) from online videos
   - Provides direct stream URLs for OpenCV processing

3. **Image Analysis** (`src/image_analyzer.py`)
   - `ImageAnalyzer` class performs OCR on extracted frames
   - Supports dual OCR engines: TrOCR (Microsoft) and EasyOCR
   - Uses Region of Interest (ROI) system for targeted analysis
   - Configurable preprocessing pipelines

4. **ROI Management** (`src/roi_manager.py`)
   - `RoiManager` class centralizes ROI configuration
   - Handles loading/saving ROI configurations from JSON
   - Provides validation and preview capabilities

5. **Image Processing** (`src/image_converter.py`)
   - `ImageConverter` class handles preprocessing for OCR
   - Configurable enhancement pipelines using `PreprocessingStep` enum
   - Supports grayscale, denoising, CLAHE, thresholding, morphological operations

### Data Flow
1. Video input (local file or URL) → `VideoResolver` → Direct stream URL or validated file path
2. Resolved source → `FrameExtractor` → Frame sequences (streaming or file-based)
3. Frames → `ImageAnalyzer` → ROI extraction → OCR processing → Text detection
4. Results → JSON output with timestamps and detected data

## Key Configuration Files

### ROI Configuration (`rois_config.json`)
Defines regions of interest for analysis:
- `timer`: Game timer detection (uses TrOCR)
- `character1`: Player 1 character name (uses EasyOCR)  
- `character2`: Player 2 character name (uses EasyOCR)

Each ROI specifies:
- Boundary coordinates (as percentages: 0.0-1.0)
- OCR model to use (`trocr` or `easyocr`)
- Display colors for visualization
- Whitelist characters for text filtering

### Character Database (`characters.json`)
Contains list of valid SF6 character names for matching detected text against known characters.

## Common Commands

### Video Analysis Pipeline

#### Step 1: Extract Raw Data
```bash
# LOCAL FILES
# Analyze a local video file with frame saving (debug mode)
python export.py input/match_video.mp4 --save-frames

# Fast analysis without saving frames (production mode)  
python export.py input/match_video.mp4

# Custom frame rate (frames per minute)
python export.py input/match_video.mp4 --frames-per-minute 6

# ONLINE VIDEOS (URLs)
# Analyze YouTube/Twitch/online video directly
python export.py "https://www.youtube.com/watch?v=VIDEO_ID" --save-frames

# Stream analysis with custom frame rate
python export.py "https://www.twitch.tv/videos/VIDEO_ID" --frames-per-minute 6

# Output: video_name.export.json (raw OCR data with sanitized filename)
```

#### Step 2: Deduce Matches Structure
```bash
# Analyze export.json to detect matches, sets, and rounds
python deduct.py output/video_name.export.json

# With debug logging to understand detection process
python deduct.py output/video_name.export.json --debug

# Custom parameters for match detection
python deduct.py output/video_name.export.json \
    --min-match-gap 180 \
    --timer-tolerance 0.4

# Output: video_name.matches.json (structured match data)
```

#### Complete Pipeline Example
```bash
# 1. Extract raw data from video
python export.py input/EVODay2.mp4 --frames-per-minute 12

# 2. Deduce match structure  
python deduct.py output/EVODay2.export.json --debug

# Results:
# - output/EVODay2.export.json (8000+ raw frames)
# - output/EVODay2.matches.json (50+ structured matches)
```

#### Async Pipeline (High Performance)

**NEW: Asynchronous video analysis for 3-5x speed improvement**

```bash
# Basic async analysis (recommended)
python async_export.py input/match_video.mp4

# High-performance configuration
python async_export.py input/match_video.mp4 --workers 5 --frames-per-minute 15

# Online videos with async pipeline
python async_export.py "https://www.youtube.com/watch?v=VIDEO_ID" --workers 3

# Limited analysis for testing
python async_export.py input/test.mp4 --max-frames 200 --workers 2

# Performance comparison
time python export.py input/video.mp4           # Sequential: ~10 minutes
time python async_export.py input/video.mp4     # Async: ~2-3 minutes (3-5x faster)
```

**Async Architecture:**
- **Frame Producer**: Extracts frames asynchronously from video
- **OCR Workers**: 3-5 parallel workers process frames simultaneously  
- **JSON Writer**: Buffers and writes results in batches
- **Queue Management**: Non-blocking communication with backpressure

**Performance Gains:**
- **CPU/GPU Utilization**: OCR workers run in parallel during frame extraction
- **Memory Efficiency**: Fixed-size queues prevent memory overflow
- **I/O Optimization**: Batch JSON writing instead of per-frame writes
- **Graceful Handling**: Timeouts and error recovery for robust processing

**Configuration Options:**
- `--workers N`: Number of parallel OCR workers (default: 3, recommended: 3-5)
- `--max-frames N`: Limit analysis for testing (useful for development)
- All standard export.py options supported (--save-frames, --format, etc.)

#### Programmatic Usage
```python
# Step 1: Sequential extraction (standard)
from export import analyze_video
analyze_video("path/to/video.mp4", frames_per_minute=12, save_frames=False)

# Step 1: Async extraction (high performance)
import asyncio
from async_export import analyze_video_async

async def main():
    await analyze_video_async(
        video_source="path/to/video.mp4", 
        frames_per_minute=12, 
        ocr_workers=3
    )

asyncio.run(main())

# Step 2: Match deduction (same for both pipelines)
from src.match_deductor import MatchDeductor
deductor = MatchDeductor(debug=True)
with open("output/video.export.json") as f:
    frames_data = json.load(f)
results = deductor.analyze_frames(frames_data)
```

### Working with Notebooks

**Important: Notebooks serve as both tests and business specifications in this project.**

The project includes several Jupyter notebooks in `work/`:

#### Core Specifications (`work/global/`)
- **`test-deduct.ipynb`**: **Business logic documentation for match detection**
  - Complete design reasoning and architectural decisions
  - Step-by-step analysis of SF6 match structure requirements
  - Real data testing with export.json files
  - Edge cases and validation of business rules
  - **This is the definitive specification for the MatchDeductor system**
- `test-analyze.ipynb`: Analysis testing and debugging
- `test-export.ipynb`: Export pipeline testing
- `test-extract.ipynb`: Frame extraction testing

#### Development Tools (`work/`)
- `ROIs_placer.ipynb`: Interactive ROI configuration
- `dataset_building.ipynb`: Training data preparation
- `check_env.ipynb`: Environment validation

#### Notebook Philosophy

**Notebooks as Living Documentation:**
- **Specification**: Document business requirements and design decisions
- **Testing**: Load real data and validate system behavior
- **Knowledge Preservation**: Capture reasoning process for future maintenance
- **Debugging**: Provide interactive environment for troubleshooting

**Best Practices:**
- Keep business logic in notebooks for traceability
- Test with real export.json files, not synthetic data
- Document edge cases and their handling
- Include performance and accuracy metrics

### ROI Management
```python
from src.roi_manager import RoiManager

# Load existing configuration
roi_manager = RoiManager('rois_config.json')
roi_manager.load()

# Get ROI for ImageAnalyzer
timer_roi = roi_manager.get_roi_for_image_analyzer('timer')

# Update ROI boundaries
roi_manager.update_roi_boundaries('timer', {
    'left': 0.46, 'top': 0.04, 'right': 0.54, 'bottom': 0.18
})
```

### Video Source Resolution
```python
from src.video_resolver import VideoResolver

# Initialize resolver
resolver = VideoResolver(preferred_quality="best[height<=1080]")

# Test source type
url = "https://www.youtube.com/watch?v=VIDEO_ID"
if resolver.is_url(url):
    print("This is a URL")
elif resolver.is_local_file(url):
    print("This is a local file")

# Resolve any source to processable format
result = resolver.resolve_source(url)
print(f"Direct stream URL: {result['path']}")
print(f"Is stream: {result['is_stream']}")
print(f"Title: {result['metadata']['title']}")
```

### Image Analysis
```python
from src.image_analyzer import ImageAnalyzer
from src.preprocessing_steps import PreprocessingStep

# Initialize analyzer
analyzer = ImageAnalyzer(
    config_file='rois_config.json',
    characters_file='characters.json',
    debug=True,
    debug_save_dir='output/debug'
)

# Analyze frame with preprocessing
results = analyzer.analyze_frame(
    frame, 
    rois_to_analyze=['timer', 'character1', 'character2'],
    preprocessing=PreprocessingStep.STANDARD
)
```

## File Structure

- `src/`: Core analysis modules
- `input/`: Video files and extracted frames
- `output/`: Analysis results and debug images
- `work/`: Jupyter notebooks for development
- `system/`: Container configurations
- `characters.json`: Valid character names database
- `rois_config.json`: ROI boundary definitions

## OCR Configuration

The system supports two OCR engines:
- **TrOCR**: Better for timer digits, requires GPU for optimal performance
- **EasyOCR**: Better for character names, more robust text detection

Configure per ROI in `rois_config.json` using the `"model"` field (`"trocr"` or `"easyocr"`).

## Preprocessing Options

Use `PreprocessingStep` enum for configurable image enhancement:
- `NONE`: No preprocessing
- `LIGHT`: Basic grayscale + normalization
- `STANDARD`: Recommended preset (grayscale + CLAHE + threshold + upscale)
- `AGGRESSIVE`: Full pipeline with denoising and morphological operations

Individual steps can be combined using bitwise OR: `PreprocessingStep.GRAYSCALE | PreprocessingStep.THRESHOLD`

## Output Formats

The system generates two types of output files:

### Raw Export Data (*.export.json)
Frame-by-frame OCR results from video analysis:
```json
[
  {
    "timestamp": "00:05:30",
    "timer_value": "89",
    "character1": "RYU", 
    "character2": "CHUN-LI"
  },
  {
    "timestamp": "00:05:35", 
    "timer_value": "84",
    "character1": "RYU",
    "character2": "CHUN-LI"
  }
]
```

### Structured Match Data (*.matches.json)
Hierarchical analysis with detected matches, sets, and rounds:
```json
{
  "matches": [
    {
      "start_time": "00:13:59",
      "sets_count": 1,
      "player1": "LUKE",
      "player2": "DEE JAY", 
      "winner": null,
      "sets": [
        {
          "set_number": 2,
          "start_time": "00:13:59",
          "character1": "LUKE",
          "character2": "DEE JAY",
          "rounds_count": 5,
          "rounds": [
            {
              "start_time": "00:13:59",
              "confidence": 0.87
            },
            {
              "start_time": "00:15:12",
              "confidence": 0.71
            }
          ]
        }
      ]
    }
  ],
  "stats": {
    "total_frames_analyzed": 8261,
    "total_matches_detected": 57,
    "total_sets_detected": 65,
    "total_rounds_detected": 314,
    "timer_detection_rate": 0.557
  }
}
```

## Coding Style Guidelines

Apply **Clean Code principles** (Robert C. Martin) and **PEP 8** standards:

### Core Principles

- **Single Responsibility**: Each function/class does one thing well
- **Guard patterns**: Early returns to reduce nesting and improve readability
- **Intention-revealing names**: `user_count` not `uc`, `calculate_total_price()` not `calc()`
- **Small functions**: < 20 lines ideally, max 3 parameters
- **No side effects**: Functions do what their name implies, nothing more
- **DRY principle**: Extract common functionality, avoid duplication

### Python Standards

- **Line length**: 79 characters maximum
- **Indentation**: 4 spaces (no tabs)  
- **Naming**: `snake_case` functions/variables, `PascalCase` classes, `UPPER_CASE` constants
- **Imports**: Group by type (standard, third-party, local) with blank lines between

### Comments

**Only comment what is NOT self-explanatory:**
- Complex algorithms or business logic
- Non-obvious parameter choices or thresholds
- Workarounds for bugs or limitations
- Performance considerations

**Example:**
```python
def _match_character_name(self, detected_text, similarity_threshold=0.6):
    """Uses fuzzy matching to handle OCR errors in character detection."""
    
    # Use 0.6 threshold - balances false positives vs missed matches
    close_matches = get_close_matches(text, names, cutoff=0.6)
```

### Code Edit Reports

After each code modification, provide a summary report with:

**Edit Summary:**
- **Lines added**: X
- **Lines removed**: Y  
- **Net change**: +/- Z lines
- **File impact**: N% of total file modified

Example format:
```
📊 Edit Summary:
- Lines added: 15
- Lines removed: 8
- Net change: +7 lines
- File impact: 12.3% of file modified (142 total lines)
```

This helps track the scope and impact of each modification for better code review and change management.

## Git Workflow and Commit Standards

### Git Best Practices (Linus Torvalds Style)

Follow these principles for clean, maintainable git history:

#### Commit Philosophy
- **Atomic commits**: Each commit should represent one logical change
- **Bisectable history**: Each commit should leave the codebase in a working state
- **Tell a story**: Commit sequence should narrate the development process
- **No WIP commits**: Squash/fixup incomplete work before pushing

#### Commit Frequency
- **Commit early, commit often** during development
- **Clean up before sharing**: Use interactive rebase to polish commit history
- **One concern per commit**: Don't mix refactoring with feature additions
- **Separate formatting from logic**: Pure whitespace/formatting changes in separate commits

### Conventional Commits Standard

All commit messages must follow the [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) specification:

#### Format
```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

#### Types
- **feat**: New feature for users
- **fix**: Bug fix for users  
- **docs**: Documentation changes
- **style**: Formatting, missing semicolons, etc (no code change)
- **refactor**: Code change that neither fixes bug nor adds feature
- **perf**: Performance improvements
- **test**: Adding/updating tests
- **build**: Changes to build system or dependencies
- **ci**: Changes to CI configuration
- **chore**: Maintenance tasks, tooling changes

#### Scopes (when applicable)
- **ocr**: OCR engine changes
- **match**: Match detection logic
- **export**: Raw data extraction
- **deduct**: Match structure deduction
- **roi**: ROI management
- **ui**: User interface changes

#### Examples

**Good commit messages:**
```bash
feat(match): implement timer pattern coherency detection

- Add flexible timer transition detection (low→high, jumps >20pts)
- Support moderate timer starts (≥85 instead of ≥90) 
- Handle OCR gaps during camera transitions gracefully

Fixes issue where LUKE vs DEE JAY match was filtered out due to
missed round transitions at 00:15:15 (timer 97).

fix(ocr): correct character detection for Mai and M.Bison

style(deduct): apply PEP8 formatting to match_deductor.py

docs: add SF6 match structure and business rules to CLAUDE.md

refactor(export): extract frame analysis to separate method

perf(roi): optimize character matching with early termination
```

**Bad commit messages:**
```bash
# Too vague
fix: stuff

# Not conventional format  
Fixed the timer bug and added new feature

# Multiple concerns
feat: add new detection + fix OCR bug + update docs

# No description
feat(match): 

# Present tense instead of imperative
feat: adds new feature
```

#### Commit Body Guidelines
- **Why over what**: Explain motivation and context, not implementation details
- **Wrap at 72 characters** for proper display in git tools
- **Use bullet points** for multiple changes within single logical commit
- **Reference issues**: Include "Fixes #123" or "Closes #456" when applicable

#### Interactive Rebase Workflow
```bash
# Clean up last 3 commits before pushing
git rebase -i HEAD~3

# Common operations:
# pick   = keep commit as-is
# reword = change commit message  
# edit   = amend commit content
# squash = merge into previous commit
# fixup  = like squash but discard commit message
# drop   = remove commit entirely
```

#### Branch Naming
- **Feature branches**: `feat/timer-coherency-detection`
- **Bug fixes**: `fix/ocr-character-detection`  
- **Docs**: `docs/update-sf6-business-rules`
- **Refactor**: `refactor/extract-frame-analysis`

### Pre-Commit Requirements

**CRITICAL: Before committing, ALWAYS follow this procedure:**

1. **Code Quality Analysis - Run AST Analysis Script:**
```bash
# Run this in container to detect unused imports and variables
docker compose exec backend python -c "
import ast
import os
from typing import Set, List

def analyze_file(filepath: str):
    print(f'\\n=== Analyse de {filepath} ===')
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        
        tree = ast.parse(source)
        
        # Variables définies vs utilisées
        defined_vars = set()
        used_vars = set()
        imported_modules = set()
        used_modules = set()
        
        # Parcourir l'AST
        for node in ast.walk(tree):
            # Imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name != '*':
                        imported_modules.add(alias.name)
            
            # Variables assignées
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined_vars.add(target.id)
            
            # Variables utilisées
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used_vars.add(node.id)
            
            # Modules utilisés (attributs)
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    used_modules.add(node.value.id)
        
        # Chercher imports non utilisés
        unused_imports = imported_modules - used_modules - used_vars
        if unused_imports:
            for imp in unused_imports:
                print(f'  ⚠️  Import non utilisé: {imp}')
        
        # Chercher variables non utilisées (sauf celles qui commencent par _)
        unused_vars = defined_vars - used_vars
        unused_vars = {v for v in unused_vars if not v.startswith('_')}
        if unused_vars:
            for var in unused_vars:
                print(f'  ⚠️  Variable non utilisée: {var}')
        
        if not unused_imports and not unused_vars:
            print('  ✅ Aucun problème détecté')
            
    except Exception as e:
        print(f'  ❌ Erreur: {str(e)}')

# Analyser tous les fichiers Python
import glob
python_files = glob.glob('src/*.py') + glob.glob('*.py')
for file in python_files:
    if os.path.exists(file):
        analyze_file(file)
"
```

2. **Fix Issues:** Correct any unused imports or variables detected by the script

3. **Run Tests:** Test the classes that were impacted by the code cleaning

4. **Git Operations:** Proceed with standard git workflow

### Commit Attribution
All commits should include proper attribution:
```
🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```