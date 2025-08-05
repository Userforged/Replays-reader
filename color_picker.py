#!/usr/bin/env python3
import os
# Force OpenCV to use non-Qt backend to disable auto-panning
os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
os.environ['OPENCV_UI_BACKEND'] = 'GTK'

import cv2 as cv
import numpy as np
import sys
import argparse

class ColorPicker:
    def __init__(self, image_path):
        self.image = cv.imread(image_path)
        if self.image is None:
            print(f"❌ Cannot load image: {image_path}")
            sys.exit(1)
        
        self.image_copy = self.image.copy()
        self.drawing = False
        self.start_point = None
        self.end_point = None
        self.rect_selected = False
        self.rectangle_mode = False
        
    def mouse_callback(self, event, x, y, flags, param):        
        # Left click for rectangle drawing when in rectangle mode
        if event == cv.EVENT_LBUTTONDOWN and self.rectangle_mode:
            if not self.drawing:
                self.drawing = True
                self.start_point = (x, y)
                self.rect_selected = False
                print("🖱️  Drawing rectangle... Press R again to validate")
            
        elif event == cv.EVENT_MOUSEMOVE and self.drawing and self.rectangle_mode:
            self.image_copy = self.image.copy()
            cv.rectangle(self.image_copy, self.start_point, (x, y), (0, 255, 0), 1)
            self.draw_live_bounds(self.start_point, (x, y))
            
        elif event == cv.EVENT_LBUTTONUP and self.drawing and self.rectangle_mode:
            self.end_point = (x, y)
        
        # When not in rectangle mode, left click is free for OpenCV pan
            
    def run(self):
        cv.namedWindow('Color Picker - Select Rectangle', cv.WINDOW_NORMAL)
        # Set window size to 50% of image
        height, width = self.image.shape[:2]
        cv.resizeWindow('Color Picker - Select Rectangle', width//2, height//2)
        cv.setMouseCallback('Color Picker - Select Rectangle', self.mouse_callback)
        
        print("🔘 Press R to start rectangle mode")
        print("🖱️  Then LEFT CLICK + drag to draw rectangle")
        print("🔘 Press R again to validate rectangle")
        print("📋 Press ENTER or SPACE to analyze selected area")
        print("🔍 LEFT CLICK + drag to pan (auto-enabled when zoomed)")
        print("🔍 Zoom with mouse wheel")
        print("❌ Press ESC to exit")
        
        while True:
            cv.imshow('Color Picker - Select Rectangle', self.image_copy)
            key = cv.waitKey(1) & 0xFF
            
            if key == 27:  # ESC
                break
            elif key == 13 and self.rect_selected:  # ENTER
                print("ENTER detected, analyzing...")
                self.analyze_selection()
            elif key == 10 and self.rect_selected:  # Alternative ENTER code
                print("ENTER (alternative) detected, analyzing...")
                self.analyze_selection()
            elif key == ord('r'):  # R
                self.handle_r_key()
            elif key == ord(' ') and self.rect_selected:  # SPACE as alternative
                print("SPACE detected, analyzing...")
                self.analyze_selection()
                
        cv.destroyAllWindows()
        
    def draw_live_bounds(self, start_point, end_point):
        # Ensure correct rectangle coordinates
        x1, y1 = start_point
        x2, y2 = end_point
        x_min, x_max = min(x1, x2), max(x1, x2)
        y_min, y_max = min(y1, y2), max(y1, y2)
        
        # Extract selected region
        roi = self.image[y_min:y_max, x_min:x_max]
        
        if roi.size == 0:
            return
            
        # Calculate bounds
        b_min, g_min, r_min = np.min(roi, axis=(0, 1))
        b_max, g_max, r_max = np.max(roi, axis=(0, 1))
        
        lower_bound = (int(b_min), int(g_min), int(r_min))
        upper_bound = (int(b_max), int(g_max), int(r_max))
        
        # Display bounds as text
        text1 = f"Lower: {lower_bound}"
        text2 = f"Upper: {upper_bound}"
        
        # Position text above or below rectangle
        text_x = x_min
        img_height = self.image_copy.shape[0]
        
        # Try to place above rectangle, if not enough space, place below
        if y_min > 50:  # Enough space above
            text_y1 = y_min - 35
            text_y2 = y_min - 15
        else:  # Place below rectangle
            text_y1 = y_max + 20
            text_y2 = y_max + 40
        
        # Ensure text doesn't go out of image bounds
        text_y1 = max(20, min(text_y1, img_height - 30))
        text_y2 = max(40, min(text_y2, img_height - 10))
        
        # Calculate text width for background
        text_size1 = cv.getTextSize(text1, cv.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
        text_size2 = cv.getTextSize(text2, cv.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
        
        # Add text background
        cv.rectangle(self.image_copy, (text_x - 2, text_y1 - 15), (text_x + text_size1[0] + 4, text_y1 + 5), (0, 0, 0), -1)
        cv.rectangle(self.image_copy, (text_x - 2, text_y2 - 15), (text_x + text_size2[0] + 4, text_y2 + 5), (0, 0, 0), -1)
        
        # Add text
        cv.putText(self.image_copy, text1, (text_x, text_y1), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        cv.putText(self.image_copy, text2, (text_x, text_y2), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    def handle_r_key(self):
        if not self.rectangle_mode:
            # Start rectangle mode
            self.rectangle_mode = True
            self.rect_selected = False
            print("🔘 Rectangle mode ON - Click and drag to draw rectangle")
        elif self.drawing:
            # Validate current rectangle
            self.drawing = False
            self.rect_selected = True
            self.image_copy = self.image.copy()
            cv.rectangle(self.image_copy, self.start_point, self.end_point, (0, 255, 0), 1)
            self.draw_live_bounds(self.start_point, self.end_point)
            print("✅ Rectangle validated - Press ENTER to analyze")
        else:
            # Reset and exit rectangle mode
            self.rectangle_mode = False
            self.rect_selected = False
            self.drawing = False
            self.start_point = None
            self.end_point = None
            self.image_copy = self.image.copy()
            print("🔘 Rectangle mode OFF")

    def analyze_selection(self):
        if not self.rect_selected or not self.start_point or not self.end_point:
            print("⚠️  No valid selection")
            return
            
        # Ensure correct rectangle coordinates
        x1, y1 = self.start_point
        x2, y2 = self.end_point
        x_min, x_max = min(x1, x2), max(x1, x2)
        y_min, y_max = min(y1, y2), max(y1, y2)
        
        # Extract selected region
        roi = self.image[y_min:y_max, x_min:x_max]
        
        if roi.size == 0:
            print("⚠️  Selected area is too small")
            return
            
        print(f"\n🔍 Analyzing rectangle: ({x_min},{y_min}) to ({x_max},{y_max})")
        print(f"📐 Size: {x_max-x_min}x{y_max-y_min} pixels")
        
        # Calculate min and max values for each channel
        b_min, g_min, r_min = np.min(roi, axis=(0, 1))
        b_max, g_max, r_max = np.max(roi, axis=(0, 1))
        
        # Calculate mean values
        b_mean, g_mean, r_mean = np.mean(roi, axis=(0, 1)).astype(int)
        
        lower_bound = (int(b_min), int(g_min), int(r_min))
        upper_bound = (int(b_max), int(g_max), int(r_max))
        mean_color = (int(b_mean), int(g_mean), int(r_mean))
        
        print(f"🎨 Color range found:")
        print(f"   Lower bound (BGR): {lower_bound}")
        print(f"   Upper bound (BGR): {upper_bound}")
        print(f"   Mean color (BGR):  {mean_color}")
        
        # Convert to HEX for display
        def bgr_to_hex(bgr):
            return f"{bgr[2]:02x}{bgr[1]:02x}{bgr[0]:02x}"
            
        print(f"   Lower bound (HEX): #{bgr_to_hex(lower_bound)}")
        print(f"   Upper bound (HEX): #{bgr_to_hex(upper_bound)}")
        print(f"   Mean color (HEX):  #{bgr_to_hex(mean_color)}")
        
        # Test the mask
        mask = cv.inRange(self.image, lower_bound, upper_bound)
        result = cv.bitwise_and(self.image, self.image, mask=mask)
        
        pixels_matched = np.sum(mask > 0)
        total_pixels = mask.shape[0] * mask.shape[1]
        percentage = (pixels_matched / total_pixels) * 100
        
        print(f"✨ Mask test: {pixels_matched}/{total_pixels} pixels matched ({percentage:.1f}%)")
        
        # Show result at 50% size
        cv.namedWindow('Mask Result', cv.WINDOW_NORMAL)
        result_height, result_width = result.shape[:2]
        cv.resizeWindow('Mask Result', result_width//2, result_height//2)
        cv.imshow('Mask Result', result)
        
        print(f"👁️  Result displayed - press any key to continue")

def main():
    parser = argparse.ArgumentParser(description='Interactive color picker tool')
    parser.add_argument('image', help='Path to input image')
    args = parser.parse_args()
    
    picker = ColorPicker(args.image)
    picker.run()

if __name__ == "__main__":
    main()