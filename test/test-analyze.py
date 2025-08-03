#!/usr/bin/env python3
"""
Street Fighter 6 Image Analysis Test

This script provides functionality to:
- Analyze single images for OCR text detection
- Visualize detection regions on images
- Save annotated results for review

Usage:
    python test-analyze.py screenshot.png
    python test-analyze.py screenshot.png --dry
    python test-analyze.py screenshot.png --regions timer character1
"""

import argparse
import sys
import os
import cv2 as cv
from ..image_analyzer import ImageAnalyzer

def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description='Analyze a Street Fighter 6 image to detect timer and character information',
        epilog='Examples:\n'
               '  %(prog)s screenshot.png              # Analyze image with OCR\n'
               '  %(prog)s screenshot.png --dry        # Show regions without OCR\n',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        'image',
        type=str,
        help='Path to the image to analyze'
    )

    parser.add_argument(
        '--dry', '-D',
        action='store_true',
        help='Dry-run mode: only draw regions without OCR analysis'
    )

    parser.add_argument(
        '--regions', '-r',
        nargs='+',
        choices=['timer', 'character1', 'character2'],
        help='Specific regions to analyze (default: all regions)'
    )

    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default='output',
        help='Output directory for results (default: output)'
    )

    parser.add_argument(
        '--analyzed-dir', '-a',
        type=str,
        default='analyzed',
        help='Subdirectory for analyzed images (default: analyzed)'
    )

    args = parser.parse_args()

    # Verify input file exists
    if not os.path.exists(args.image):
        print(f"❌ Error: Image file '{args.image}' does not exist.", file=sys.stderr)
        sys.exit(1)

    analyzer = ImageAnalyzer(
        output_directory=args.output_dir,
        analyzed_frames_subdirectory=args.analyzed_dir
    )

    try:
        if args.dry:
            print("🔍 Dry-run mode enabled - Visualizing regions")
            regions = args.regions or None
            output_file = analyzer.visualize_regions(args.image, regions_to_show=regions)
            print(f"✓ Regions saved to: {output_file}")

        else:
            # Analyze image
            regions = args.regions or None
            results = analyzer.analyze_image(args.image, regions_to_analyze=regions)

            # Display results
            print("\n=== DETECTION RESULTS ===")
            has_detections = False
            for region_name, detected_text in results.items():
                if detected_text:
                    print(f"{region_name.upper()}: {detected_text}")
                    has_detections = True
                else:
                    print(f"{region_name.upper()}: ⚠ No text detected")

            # Create and save annotated image
            print("\n📸 Creating annotated image...")
            image = cv.imread(args.image)
            annotated = analyzer.annotate_frame_with_regions(
                image,
                list(results.keys()),
                show_text=True,
                detection_results=results
            )

            analyzer._ensure_output_directories()

            output_path = os.path.join(
                analyzer.output_directory,
                analyzer.analyzed_frames_subdirectory,
                'analyzed_' + os.path.basename(args.image)
            )
            cv.imwrite(output_path, annotated)
            print(f"✓ Annotated image saved: {output_path}")

            if has_detections:
                print("\n✓ Analysis completed successfully")
            else:
                print("\n⚠ Analysis completed but no text was detected")

    except ValueError as e:
        print(f"❌ Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error during analysis: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
