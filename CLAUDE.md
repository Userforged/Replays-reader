# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

# Access OpenCV container for video processing
docker compose exec opencv bash

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
   - Extracts frames at configurable intervals (default: 12 frames/minute)
   - Supports both saving frames to disk and generating frames in-memory

2. **Image Analysis** (`src/image_analyzer.py`)
   - `ImageAnalyzer` class performs OCR on extracted frames
   - Supports dual OCR engines: TrOCR (Microsoft) and EasyOCR
   - Uses Region of Interest (ROI) system for targeted analysis
   - Configurable preprocessing pipelines

3. **ROI Management** (`src/roi_manager.py`)
   - `RoiManager` class centralizes ROI configuration
   - Handles loading/saving ROI configurations from JSON
   - Provides validation and preview capabilities

4. **Image Processing** (`src/image_converter.py`)
   - `ImageConverter` class handles preprocessing for OCR
   - Configurable enhancement pipelines using `PreprocessingStep` enum
   - Supports grayscale, denoising, CLAHE, thresholding, morphological operations

### Data Flow
1. Video input → `FrameExtractor` → Frame sequences
2. Frames → `ImageAnalyzer` → ROI extraction → OCR processing → Text detection
3. Results → JSON output with timestamps and detected data

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
# Analyze a video with frame saving (debug mode)
python export.py input/match_video.mp4 --save-frames

# Fast analysis without saving frames (production mode)
python export.py input/match_video.mp4

# Custom frame rate (frames per minute)
python export.py input/match_video.mp4 --frames-per-minute 6

# Output: video_name.export.json (raw OCR data)
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

#### Programmatic Usage
```python
# Step 1: Raw extraction
from export import analyze_video
analyze_video("path/to/video.mp4", frames_per_minute=12, save_frames=False)

# Step 2: Match deduction  
from src.match_deductor import MatchDeductor
deductor = MatchDeductor(debug=True)
with open("output/video.export.json") as f:
    frames_data = json.load(f)
results = deductor.analyze_frames(frames_data)
```

### Working with Notebooks
The project includes several Jupyter notebooks in `work/`:
- `ROIs_placer.ipynb`: Interactive ROI configuration
- `test-analyze.ipynb`: Analysis testing and debugging
- `dataset_building.ipynb`: Training data preparation
- `ocr_simple_test.ipynb`: OCR engine testing

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

### Commit Attribution
All commits should include proper attribution:
```
🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```