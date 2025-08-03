#!/usr/bin/env python3
"""
Street Fighter 6 Character Name Cleaner

Script to clean and standardize character names in JSON result files using OCR text recognition.
Processes character1 and character2 fields to identify and replace with canonical SF6 character names.

Usage:
    python clean-character-names.py match_results.json
    python clean-character-names.py match_results.json --output cleaned_results.json
    python clean-character-names.py match_results.json --threshold 0.7 --backup
"""

import json
import argparse
import sys
import os
from datetime import datetime

from character_name_finder import CharacterNameFinder


def load_json_file(file_path):
    """Load JSON data from file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: File '{file_path}' not found.")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in '{file_path}': {e}")
        return None
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return None

def save_json_file(data, file_path):
    """Save JSON data to file."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Error saving file: {e}")
        return False


def create_backup(file_path):
    """Create a backup of the original file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{file_path}.backup_{timestamp}"
    
    try:
        import shutil
        shutil.copy2(file_path, backup_path)
        print(f"📁 Backup created: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"⚠️  Warning: Could not create backup: {e}")
        return None


def clean_character_names(data, finder, verbose=False):
    """
    Clean character names in JSON data.
    
    Args:
        data: JSON data (list of match results)
        finder: CharacterNameFinder instance
        verbose: Whether to show detailed processing info
        
    Returns:
        tuple: (cleaned_data, stats_dict)
    """
    if not isinstance(data, list):
        print("❌ Error: JSON data should be a list of match results")
        return None, None
    
    stats = {
        'total_entries': len(data),
        'character1_cleaned': 0,
        'character2_cleaned': 0,
        'character1_unchanged': 0,
        'character2_unchanged': 0,
        'character1_failed': 0,
        'character2_failed': 0
    }
    
    cleaned_data = []
    
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            print(f"⚠️  Warning: Entry {i} is not a dictionary, skipping")
            cleaned_data.append(entry)
            continue
        
        # Make a copy of the entry
        cleaned_entry = entry.copy()
        
        # Process character1
        if 'character1' in entry:
            original_char1 = entry['character1']
            if original_char1 and original_char1.strip():
                cleaned_char1 = finder.find_character(original_char1)
                if cleaned_char1:
                    if cleaned_char1 != original_char1:
                        cleaned_entry['character1'] = cleaned_char1
                        stats['character1_cleaned'] += 1
                        if verbose:
                            print(f"🔧 Entry {i+1}: '{original_char1}' → '{cleaned_char1}'")
                    else:
                        stats['character1_unchanged'] += 1
                else:
                    stats['character1_failed'] += 1
                    if verbose:
                        print(f"❓ Entry {i+1}: Could not identify character1 '{original_char1}'")
        
        # Process character2
        if 'character2' in entry:
            original_char2 = entry['character2']
            if original_char2 and original_char2.strip():
                cleaned_char2 = finder.find_character(original_char2)
                if cleaned_char2:
                    if cleaned_char2 != original_char2:
                        cleaned_entry['character2'] = cleaned_char2
                        stats['character2_cleaned'] += 1
                        if verbose:
                            print(f"🔧 Entry {i+1}: '{original_char2}' → '{cleaned_char2}'")
                    else:
                        stats['character2_unchanged'] += 1
                else:
                    stats['character2_failed'] += 1
                    if verbose:
                        print(f"❓ Entry {i+1}: Could not identify character2 '{original_char2}'")
        
        cleaned_data.append(cleaned_entry)
    
    return cleaned_data, stats


def print_stats(stats):
    """Print cleaning statistics."""
    print("\n📊 Cleaning Statistics:")
    print("=" * 40)
    print(f"Total entries processed: {stats['total_entries']}")
    print(f"Character1 - Cleaned: {stats['character1_cleaned']}")
    print(f"Character1 - Unchanged: {stats['character1_unchanged']}")
    print(f"Character1 - Failed: {stats['character1_failed']}")
    print(f"Character2 - Cleaned: {stats['character2_cleaned']}")
    print(f"Character2 - Unchanged: {stats['character2_unchanged']}")
    print(f"Character2 - Failed: {stats['character2_failed']}")
    
    total_cleaned = stats['character1_cleaned'] + stats['character2_cleaned']
    total_processed = (stats['character1_cleaned'] + stats['character1_unchanged'] + 
                      stats['character2_cleaned'] + stats['character2_unchanged'])
    
    if total_processed > 0:
        success_rate = (total_cleaned / total_processed) * 100
        print(f"Improvement rate: {total_cleaned}/{total_processed} ({success_rate:.1f}%)")


def main():
    parser = argparse.ArgumentParser(
        description='Clean and standardize character names in SF6 match result JSON files'
    )
    
    parser.add_argument(
        'input_file',
        help='Input JSON file to process'
    )
    
    parser.add_argument(
        '--output', '-o',
        help='Output file path (default: overwrites input file)'
    )
    
    parser.add_argument(
        '--threshold', '-t',
        type=float,
        default=0.6,
        help='Similarity threshold for fuzzy matching (0.0-1.0, default: 0.6)'
    )
    
    parser.add_argument(
        '--backup', '-b',
        action='store_true',
        help='Create backup of original file before processing'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed processing information'
    )
    
    parser.add_argument(
        '--dry-run', '-d',
        action='store_true',
        help='Show what would be changed without actually modifying files'
    )
    
    args = parser.parse_args()
    
    # Validate input file
    if not os.path.exists(args.input_file):
        print(f"❌ Error: Input file '{args.input_file}' does not exist.")
        sys.exit(1)
    
    # Validate threshold
    if not (0.0 <= args.threshold <= 1.0):
        print("❌ Error: Threshold must be between 0.0 and 1.0")
        sys.exit(1)
    
    print(f"🎮 Processing SF6 character names in: {args.input_file}")
    print(f"🎯 Using similarity threshold: {args.threshold}")
    
    # Load JSON data
    data = load_json_file(args.input_file)
    if data is None:
        sys.exit(1)
    
    # Initialize character finder
    finder = CharacterNameFinder(similarity_threshold=args.threshold)
    
    # Clean character names
    print(f"🔍 Processing {len(data) if isinstance(data, list) else 1} entries...")
    cleaned_data, stats = clean_character_names(data, finder, args.verbose or args.dry_run)
    
    if cleaned_data is None:
        sys.exit(1)
    
    # Print statistics
    print_stats(stats)
    
    # Save results (unless dry run)
    if args.dry_run:
        print("\n🔬 Dry run completed - no files were modified")
    else:
        # Determine output file
        output_file = args.output or args.input_file
        
        # Create backup if requested and not using different output file
        if args.backup and output_file == args.input_file:
            create_backup(args.input_file)
        
        # Save cleaned data
        if save_json_file(cleaned_data, output_file):
            print(f"✅ Cleaned data saved to: {output_file}")
        else:
            sys.exit(1)
    
    # Summary
    total_improvements = stats['character1_cleaned'] + stats['character2_cleaned']
    if total_improvements > 0:
        print(f"🎉 Successfully improved {total_improvements} character name(s)!")
    else:
        print("ℹ️  No character names needed cleaning.")


if __name__ == "__main__":
    main()