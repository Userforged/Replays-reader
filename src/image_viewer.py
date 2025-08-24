"""
ImageViewer - Class for OpenCV-based image display and ROI visualization.

Handles all visual display responsibilities that were previously mixed in RoiManager:
- OpenCV window management
- Rectangle/overlay rendering  
- Mouse event handling for ROI editing
- Visual feedback and annotations

This class is used internally by RoiManager via composition pattern.
"""

import cv2 as cv
import numpy as np
from typing import Dict, List, Any, Optional, Tuple


class ImageViewer:
    """
    Handles OpenCV-based image display and ROI visualization.
    
    This class encapsulates all visual display logic that was previously
    scattered between RoiManager and the ROIs_placer notebook.
    """
    
    def __init__(self):
        """Initialize the ImageViewer."""
        pass
    
    def display_rois_on_image(
        self, 
        image: np.ndarray, 
        rois: List[Dict[str, Any]], 
        show_labels: bool = True
    ) -> np.ndarray:
        """
        Draw ROIs on an image for preview.
        
        Args:
            image: OpenCV image (numpy array)
            rois: List of ROI configurations
            show_labels: Whether to display ROI labels
            
        Returns:
            Image with ROIs drawn on it
        """
        if image is None:
            raise ValueError("Image cannot be None")
        
        preview_img = image.copy()
        height, width = image.shape[:2]
        
        for roi in rois:
            self._draw_roi_on_image(preview_img, roi, width, height, show_labels)
        
        return preview_img
    
    def _draw_roi_on_image(
        self, 
        image: np.ndarray, 
        roi: Dict[str, Any], 
        width: int, 
        height: int, 
        show_labels: bool
    ) -> None:
        """
        Draw a single ROI on the image.
        
        Args:
            image: Image to draw on (modified in place)
            roi: ROI configuration
            width: Image width
            height: Image height  
            show_labels: Whether to show labels
        """
        boundaries = roi["boundaries"]
        color = tuple(boundaries.get("color", [0, 255, 0]))  # Default green
        label = roi.get("label", roi["name"].upper())
        
        # Calculate pixel coordinates
        left = int(boundaries["left"] * width)
        top = int(boundaries["top"] * height)  
        right = int(boundaries["right"] * width)
        bottom = int(boundaries["bottom"] * height)
        
        # Draw rectangle
        cv.rectangle(image, (left, top), (right, bottom), color, 2)
        
        if show_labels:
            self._draw_roi_label(image, label, left, top, color)
    
    def _draw_roi_label(
        self, 
        image: np.ndarray, 
        label: str, 
        x: int, 
        y: int, 
        color: Tuple[int, int, int]
    ) -> None:
        """
        Draw a label for a ROI.
        
        Args:
            image: Image to draw on
            label: Text label
            x, y: Position coordinates
            color: Text color
        """
        font = cv.FONT_HERSHEY_SIMPLEX
        scale = 0.6
        thickness = 2
        
        # Calculate text size
        (text_width, text_height), _ = cv.getTextSize(label, font, scale, thickness)
        text_x = x
        text_y = max(y - 10, text_height + 5)
        
        # Draw black background for text
        cv.rectangle(
            image,
            (text_x - 2, text_y - text_height - 2),
            (text_x + text_width + 2, text_y + 2),
            (0, 0, 0),
            -1
        )
        
        # Draw white text
        cv.putText(
            image, 
            label, 
            (text_x, text_y), 
            font, 
            scale, 
            (255, 255, 255), 
            thickness
        )
    
    def display_frame_with_rois(
        self, 
        frame: np.ndarray, 
        window_title: str,
        max_width: int = 1200,
        max_height: int = 800
    ) -> None:
        """
        Display a frame with ROIs in an OpenCV window.
        
        Args:
            frame: Frame to display
            window_title: Window title
            max_width: Maximum window width
            max_height: Maximum window height
        """
        try:
            # Resize frame if too large
            height, width = frame.shape[:2]
            
            if height > max_height or width > max_width:
                scale = min(max_height / height, max_width / width)
                new_width = int(width * scale)
                new_height = int(height * scale)
                frame = cv.resize(frame, (new_width, new_height))
            
            # Display frame
            cv.imshow(window_title, frame)
            
            print(f"🪟 Window '{window_title}' opened - Press any key to close...")
            
            # Wait for key press
            cv.waitKey(0)
            cv.destroyAllWindows()
            
            print("✅ Window closed.")
            
        except Exception as e:
            print(f"❌ Display error: {str(e)}")
            # Fallback: save frame to file
            try:
                output_path = "output/frame_display_fallback.jpg"
                cv.imwrite(output_path, frame)
                print(f"💾 Frame saved to {output_path}")
            except Exception as save_error:
                print(f"❌ Save error: {str(save_error)}")
    
    def interactive_roi_editor(
        self, 
        image: np.ndarray, 
        roi_config: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Launch interactive ROI editor using OpenCV.
        
        Extracted from ROIs_placer notebook's ROISelector class.
        
        Args:
            image: Reference image for editing
            roi_config: ROI configuration to edit
            
        Returns:
            Updated ROI configuration if modified, None if cancelled
        """
        if image is None:
            raise ValueError("Image cannot be None")
        if roi_config is None:
            raise ValueError("ROI config cannot be None")
            
        editor = ROIEditor(image, roi_config)
        return editor.run()
    
    def close_all_windows(self) -> None:
        """Close all OpenCV windows."""
        cv.destroyAllWindows()


class ROIEditor:
    """
    Interactive ROI editor extracted from ROIs_placer notebook.
    
    Provides drag & drop and resize functionality for ROI boundaries.
    """
    
    def __init__(self, image: np.ndarray, roi_config: Dict[str, Any]):
        """
        Initialize the ROI editor.
        
        Args:
            image: Reference image
            roi_config: ROI configuration to edit
        """
        self.image = image.copy()
        if self.image is None:
            raise ValueError("Cannot load image")
        
        self.roi_config = roi_config.copy()
        self.roi_name = roi_config["name"]
        self.image_copy = self.image.copy()
        self.img_height, self.img_width = self.image.shape[:2]
        
        # Load boundaries from config
        boundaries = roi_config["boundaries"]
        self.left = int(boundaries["left"] * self.img_width)
        self.top = int(boundaries["top"] * self.img_height)
        self.right = int(boundaries["right"] * self.img_width) 
        self.bottom = int(boundaries["bottom"] * self.img_height)
        
        # Color from config (BGR format)
        color = boundaries.get("color", [0, 255, 0])
        self.color = tuple(color) if isinstance(color, list) else color
        
        # State variables
        self.dragging = False
        self.resize_mode = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.roi_selected = False
        
        print(f"🎯 Editing ROI '{self.roi_name}':")
        print(f"   Position: ({self.left}, {self.top}) -> ({self.right}, {self.bottom})")
        print(f"   Size: {self.right - self.left}x{self.bottom - self.top}px")
        print(f"   Color: {self.color}")
    
    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse events for ROI editing."""
        if event == cv.EVENT_LBUTTONDOWN:
            # Check if clicking inside ROI (move) or on edges (resize)
            if self.left <= x <= self.right and self.top <= y <= self.bottom:
                # If clicking near edges (resize mode)
                if abs(x - self.right) < 10 and abs(y - self.bottom) < 10:
                    self.resize_mode = True
                    print(f"🔧 Resize mode for {self.roi_name}...")
                else:
                    # Move mode
                    self.dragging = True
                    self.drag_offset_x = x - self.left
                    self.drag_offset_y = y - self.top
                    print(f"🖱️ Move mode for {self.roi_name}...")
        
        elif event == cv.EVENT_MOUSEMOVE:
            if self.dragging:
                # Move ROI
                new_left = x - self.drag_offset_x
                new_top = y - self.drag_offset_y
                roi_width = self.right - self.left
                roi_height = self.bottom - self.top
                
                # Constrain to image boundaries
                new_left = max(0, min(new_left, self.img_width - roi_width))
                new_top = max(0, min(new_top, self.img_height - roi_height))
                
                self.left = new_left
                self.top = new_top
                self.right = self.left + roi_width
                self.bottom = self.top + roi_height
                
                self.update_display()
                
            elif self.resize_mode:
                # Resize ROI
                self.right = max(self.left + 20, min(x, self.img_width))
                self.bottom = max(self.top + 20, min(y, self.img_height))
                
                self.update_display()
        
        elif event == cv.EVENT_LBUTTONUP:
            if self.dragging or self.resize_mode:
                self.dragging = False
                self.resize_mode = False
                self.roi_selected = True
                print(f"✅ ROI {self.roi_name} updated")
    
    def update_display(self):
        """Update the display with current ROI."""
        self.image_copy = self.image.copy()
        
        thickness = 3 if self.roi_selected else 2
        
        # Main rectangle
        cv.rectangle(
            self.image_copy, 
            (self.left, self.top), 
            (self.right, self.bottom), 
            self.color, 
            thickness
        )
        
        # Resize handle (bottom-right corner)
        cv.circle(self.image_copy, (self.right, self.bottom), 8, self.color, -1)
        
        # Info text
        roi_width = self.right - self.left
        roi_height = self.bottom - self.top
        label = self.roi_config.get("label", self.roi_name.upper())
        info_text = f"{label}: {roi_width}x{roi_height}px"
        
        # Black background for text
        text_size = cv.getTextSize(info_text, cv.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
        text_pos = (self.left, self.top - 10)
        cv.rectangle(
            self.image_copy,
            (text_pos[0] - 2, text_pos[1] - text_size[1] - 5),
            (text_pos[0] + text_size[0] + 2, text_pos[1] + 5),
            (0, 0, 0),
            -1
        )
        
        cv.putText(
            self.image_copy,
            info_text,
            text_pos,
            cv.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )
    
    def run(self) -> Optional[Dict[str, Any]]:
        """
        Run the interactive ROI editor.
        
        Returns:
            Updated ROI config if saved, None if cancelled
        """
        window_name = f'ROI {self.roi_config.get("label", self.roi_name)} Editor'
        cv.namedWindow(window_name, cv.WINDOW_NORMAL)
        
        # Resize window for better viewing
        height, width = self.image.shape[:2]
        cv.resizeWindow(window_name, int(width * 0.7), int(height * 0.7))
        cv.setMouseCallback(window_name, self.mouse_callback)
        
        print(f"🎯 ROI Editor: {self.roi_config.get('label', self.roi_name)}")
        print("🖱️ Click and drag to move")
        print("🔧 Click bottom-right circle to resize")
        print("⏎ ENTER to save • ESC to cancel")
        
        self.update_display()
        
        while True:
            cv.imshow(window_name, self.image_copy)
            key = cv.waitKey(1) & 0xFF
            
            if key == 27:  # ESC
                print(f"❌ {self.roi_config.get('label', self.roi_name)} editing cancelled")
                cv.destroyAllWindows()
                return None
            elif key in [13, 10, 32]:  # ENTER or SPACE
                print(f"✅ {self.roi_config.get('label', self.roi_name)} ROI saved")
                self.roi_selected = True
                self.save_selection()
                cv.destroyAllWindows()
                return self.roi_config
        
        cv.destroyAllWindows()
        return None
    
    def save_selection(self):
        """Save the ROI selection in percentage format."""
        # Update boundaries in config
        self.roi_config["boundaries"]["left"] = self.left / self.img_width
        self.roi_config["boundaries"]["top"] = self.top / self.img_height
        self.roi_config["boundaries"]["right"] = self.right / self.img_width
        self.roi_config["boundaries"]["bottom"] = self.bottom / self.img_height
        
        width_px = self.right - self.left
        height_px = self.bottom - self.top
        label = self.roi_config.get("label", self.roi_name)
        print(f"💾 {label} ROI: {width_px}x{height_px}px")
        print(f"   Boundaries: {self.roi_config['boundaries']}")