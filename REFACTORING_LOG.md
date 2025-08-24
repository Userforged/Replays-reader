# Refactoring Log - ImageViewer & Frame Extraction

## Summary
Complete refactoring of ROI management and visual editing capabilities.

## Phase 1: ImageViewer Extraction (2024-12-XX)

### Problem
- `RoiManager` had mixed responsibilities (data management + OpenCV display)
- ROI visual editing only available in notebook (`ROIs_placer.ipynb`) 
- Interactive CLI menu had basic text-based ROI editing only (TODO line 507)

### Solution
- **Created `ImageViewer` class** for all OpenCV operations
- **Refactored `RoiManager`** to use composition pattern
- **Implemented visual ROI editor** in interactive CLI menu

### Changes Made

#### New Files
- `src/image_viewer.py` - OpenCV display and ROI editing logic
  - `ImageViewer` class for display operations
  - `ROIEditor` class for interactive editing (extracted from notebook)

#### Modified Files
- `src/roi_manager.py`:
  - Added composition with `ImageViewer`  
  - `update_roi_boundaries()` → `update_roi()`
  - Added `delete_roi()` for complete CRUD
  - Added `edit_roi_on_image()` method
  - `preview_rois_on_image()` now delegates to `ImageViewer`
  - `get_roi_info_summary()` marked as deprecated

- `src/interactive_menu.py`:
  - **Resolved TODO line 507** with `_visual_roi_modification()`
  - Users can now visually edit ROIs in CLI menu

#### Import Fixes
- Fixed relative imports across multiple files for container compatibility

### API Changes

#### New Methods (RoiManager)
```python
def delete_roi(name: str) -> bool              # DELETE operation
def update_roi(name, boundaries)               # Renamed from update_roi_boundaries  
def edit_roi_on_image(image, roi_name) -> bool # Visual editing integration
```

#### Backward Compatibility
- All existing methods preserved
- `get_roi_info_summary()` marked deprecated but functional
- `ImageAnalyzer` integration maintained

## Phase 2: Frame Extraction Refactoring (2024-12-XX)

### Problem
- Duplicate frame extraction logic in `preview_rois_on_random_frame()` and `_visual_roi_modification()`
- Potential inconsistency between preview and ROI editing frame selection
- Code duplication (~50 lines replicated)

### Solution
- **Extracted common method** `_extract_random_frame_from_video()`
- **Ensured consistency** between preview and editing workflows
- **Added metadata** for better debugging and user feedback

### Changes Made

#### Refactored Methods (interactive_menu.py)
```python
def _extract_random_frame_from_video(self, video_source, purpose) -> Tuple[frame, metadata]:
    """
    Centralized frame extraction logic used by both:
    - preview_rois_on_random_frame()
    - _visual_roi_modification()
    
    Returns frame + metadata (frame_number, timestamp, fps, etc.)
    """

def preview_rois_on_random_frame(self, video_source):
    """Now uses _extract_random_frame_from_video() - 15 lines instead of 50"""

def _visual_roi_modification(self, roi_name, video_source):
    """Now uses _extract_random_frame_from_video() - guaranteed same logic as preview"""
```

### Benefits
- **DRY Principle**: Single source of truth for frame extraction
- **Consistency**: Preview and ROI editing use identical frame selection
- **Maintainability**: Only one place to modify frame selection logic  
- **Rich Metadata**: Better user feedback with frame numbers, timestamps
- **Debuggability**: Same behavior for preview and editing modes

## Results

### User Experience
- **CLI users**: Can now visually edit ROIs with drag & drop interface
- **Notebook users**: Same familiar interface, now backed by reusable components
- **Consistent behavior**: Preview and editing always show same type of random frame

### Architecture
- **Clean separation**: Data management vs Visual operations
- **Composition over inheritance**: RoiManager delegates to ImageViewer
- **SOLID principles**: Single responsibility, extensible design

### Code Quality
- **-100 lines**: Removed duplicate frame extraction logic
- **+350 lines**: Added comprehensive ImageViewer functionality
- **Backward compatible**: All existing code continues to work
- **Type hints**: Better IDE support and documentation

## Validation
- ✅ All imports work in Docker container environment
- ✅ InteractiveMenu instantiates correctly with new dependencies
- ✅ RoiManager CRUD operations function properly
- ✅ Frame extraction produces consistent results with same random seed
- ✅ ImageAnalyzer integration preserved (format conversion works)
- ✅ Backward compatibility verified (deprecated methods still functional)

## Phase 3: Enhanced Frame Selection UX (2024-12-XX)

### Problem  
- Users stuck with randomly selected frame for entire ROI editing session
- No way to get a better reference frame if initial selection was poor
- Each ROI modification used different random frames (inconsistent)

### Solution
- **Frame caching system**: Same frame used for all ROI operations in a session
- **"Tirer une nouvelle image" option**: Force selection of new random frame
- **Consistent editing experience**: All ROI modifications use same reference frame

### Changes Made

#### Frame Caching System (interactive_menu.py)
```python
class InteractiveMenu:
    def __init__(self):
        # Frame caching for consistent ROI editing session
        self._cached_frame = None
        self._cached_frame_metadata = None  
        self._current_video_source = None

    def _extract_random_frame_from_video(self, video_source, purpose, force_new=False):
        # Check cache first, extract new frame only if needed
        # Update cache with new frame when force_new=True
```

#### Enhanced Menu Options
- **Unified**: `🎲 Tirer une nouvelle image au hasard` (replaces "Voir les ROIs sur une image au hasard")
- **Behavior**: Force extraction + immediate preview with ROI overlay + cache update
- **Integration**: New frame becomes cached reference for subsequent edits
- **Simplified UX**: Single option instead of two confusing similar options

### User Experience Improvements

#### Before
- ❌ Random frame selected for each ROI modification
- ❌ No control over reference frame quality  
- ❌ Inconsistent editing experience

#### After  
- ✅ **Consistent frame**: Same reference frame for all ROI edits in session
- ✅ **User control**: "Tirer une nouvelle image" when current frame is poor
- ✅ **Immediate feedback**: New frame shown with ROI overlay
- ✅ **Efficient workflow**: No re-extraction for subsequent edits

### Validation
- ✅ Frame caching works (same frame reused across operations)
- ✅ Force new extraction works (different frame selected)  
- ✅ New frame becomes cached reference (subsequent calls use new frame)
- ✅ Menu integration works (new option appears and functions)
- ✅ Preview integration works (new frame displayed with ROIs)

## Phase 4: In-Memory ROI Configuration (2024-12-XX)

### Problem
- ROI modifications were auto-saved to `rois_config.json` during editing
- Users had no control over persistence of changes
- "Sauvegarder et lancer" vs "Lancer sans sauvegarder" options were meaningless
- Risk of corrupting base ROI configuration file

### Solution
- **In-memory modifications only**: `rois_config.json` remains immutable during script execution
- **User choice persistence**: "Sauvegarder" vs "Sans sauvegarder" now have real meaning
- **Session-based changes**: Modifications exist only for current script execution

### Changes Made

#### ROI Manager Modifications
```python
# src/roi_manager.py
def edit_roi_on_image(self, image, roi_name) -> bool:
    if updated_roi:
        self.set_roi(roi_name, updated_roi)
        # Removed: self.save() - no auto-save to file
        return True

def reload_from_file(self) -> None:
    """Discard in-memory changes, reload from file"""
    self.load()  # Overwrites self._config with file content
```

#### Interactive Export Logic
```python
# interactive_export.py
if roi_choice == "save_and_launch":
    # Use modified ROIs in memory for export
    pass
elif roi_choice == "launch_no_save":
    # Discard changes, use original ROIs from file
    menu.roi_manager.reload_from_file()
```

### User Experience

#### Before
- ❌ ROI changes auto-saved to `rois_config.json`
- ❌ No way to discard unwanted changes
- ❌ "Sauvegarder" option was confusing (already saved)
- ❌ Risk of corrupting base configuration

#### After
- ✅ **Safe experimentation**: Modify ROIs without affecting base config
- ✅ **Real choice**: "Sauvegarder" = use changes, "Sans sauvegarder" = ignore changes  
- ✅ **Immutable base config**: `rois_config.json` never modified by script
- ✅ **Session isolation**: Each script run starts with clean ROI state

### Technical Implementation

#### Configuration Flow
```
rois_config.json (immutable)
    ↓ load()
RoiManager._config (working copy)
    ↓ visual modifications
RoiManager._config (modified)
    ↓ user choice
Export uses: modified OR original (via reload_from_file())
```

#### File System Impact
- **Before**: `rois_config.json` modified during script execution
- **After**: `rois_config.json` read-only, never written by script

### Validation
- ✅ ROI modifications kept in memory only
- ✅ File remains unchanged after modifications
- ✅ `reload_from_file()` discards changes correctly
- ✅ Export can use either modified or original ROIs
- ✅ Session isolation maintained

## Future Improvements
- Consider adding ROI validation in visual editor
- Add keyboard shortcuts (R for reset, etc.) in ROI editor
- Support for batch ROI editing workflows
- Integration with video source metadata for better frame selection
- Add frame quality scoring to auto-select better reference frames
- Add "Export current ROI config" option to save modifications permanently