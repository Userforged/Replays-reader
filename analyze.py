#!/usr/bin/env python3
"""
Street Fighter 6 Screenshot Analyzer CLI

Command-line interface for analyzing Street Fighter 6 screenshots
to extract timer values, character names, and variations.
"""

import argparse
import sys
import os
import cv2 as cv
from image_analyzer import ImageAnalyzer

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
        choices=['timer', 'character1', 'character2', 'variation1', 'variation2'],
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

    # Create analyzer with custom directories if provided
    analyzer = ImageAnalyzer(
        output_directory=args.output_dir,
        analyzed_frames_subdirectory=args.analyzed_dir
    )

    try:
        if args.dry:
            # Dry-run mode: visualize regions only
            print("🔍 Dry-run mode enabled - Visualizing regions with color analysis")
            regions = args.regions or None
            output_file = analyzer.visualize_regions(args.image, regions_to_show=regions)
            print(f"✓ Regions saved to: {output_file}")

        else:
            # Normal mode: full analysis
            print("🎯 Detection with color context: C=Purple, M=Orange, D=Light Blue")

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

            # Ensure output directories exist
            analyzer._ensure_output_directories()

            # Save annotated image
            output_path = os.path.join(
                analyzer.output_directory,
                analyzer.analyzed_frames_subdirectory,
                'analyzed_' + os.path.basename(args.image)
            )
            cv.imwrite(output_path, annotated)
            print(f"✓ Annotated image saved: {output_path}")

            # Final status
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