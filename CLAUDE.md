# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Street Fighter 6 replay analysis tool** that extracts game data from video replays using computer vision and OCR. The system can analyze match videos to detect:
- Timer values during matches
- Character names for both players
- Match progression data

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

### Video Analysis
```bash
# Analyze a video with frame saving (default)
python export.py input/match_video.mp4

# Fast analysis without saving frames  
python export.py input/match_video.mp4 --no-frames

# Custom frame rate (frames per minute)
python export.py input/match_video.mp4 --frames-per-minute 6

# Direct function call in code
from export import process_street_fighter_video_for_data_extraction
process_street_fighter_video_for_data_extraction("path/to/video.mp4")
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

## Output Format

Analysis results are saved as JSON with structure:
```json
[
  {
    "timestamp": "00:05:30",
    "timer_value": "89",
    "character1": "RYU", 
    "character2": "CHUN-LI"
  }
]
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