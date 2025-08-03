#!/usr/bin/env python3
"""
Street Fighter 6 Character Name Finder Test

Test script for the CharacterNameFinder class to validate character name recognition
from OCR text with various edge cases and common OCR errors.

Usage:
    python test-character-finder.py
"""

import sys
import os

# Add parent directory to path to import CharacterNameFinder
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from character_name_finder import CharacterNameFinder

def test_character_finder():
    """Test the CharacterNameFinder with various OCR scenarios."""
    
    finder = CharacterNameFinder()
    
    # Test cases: (input_text, expected_output, description)
    test_cases = [
        # Perfect matches
        ("RYU", "RYU", "Perfect match"),
        ("CHUN-LI", "CHUN-LI", "Perfect match with hyphen"),
        ("A.K.I.", "A.K.I.", "Perfect match with dots"),
        ("DEE JAY", "DEE JAY", "Perfect match with space"),
        
        # Text with noise/context
        ("Player 1: RYU", "RYU", "Text with context"),
        ("CAMMY wins!", "CAMMY", "Text with exclamation"),
        ("  LUKE  ", "LUKE", "Text with spaces"),
        ("Victory: JURI", "JURI", "Text with prefix"),
        
        # Common OCR errors (character confusion)
        ("RYL", "RYU", "U→L confusion"),
        ("CAMM1", "CAMMY", "Y→1 confusion"),
        ("BLANKA", "BLANKA", "Should work perfectly"),
        ("8LANKA", "BLANKA", "B→8 confusion"),
        ("KEN", "KEN", "Should work perfectly"),
        ("XEN", "KEN", "K→X confusion"),
        ("CHUN-L1", "CHUN-LI", "I→1 confusion"),
        ("CHUN-LI", "CHUN-LI", "Should work perfectly"),
        ("DHALS1M", "DHALSIM", "I→1 confusion"),
        ("ZANG1EF", "ZANGIEF", "I→1 confusion"),
        
        # Punctuation/special character errors
        ("RYU.", "RYU", "Extra period"),
        ("CAMMY!", "CAMMY", "Extra exclamation"),
        ("LUKE?", "LUKE", "Extra question mark"),
        ("A.K.I", "A.K.I.", "Missing final dot"),
        ("AKI", "A.K.I.", "Missing dots entirely"),
        ("DEE-JAY", "DEE JAY", "Space→hyphen confusion"),
        ("DEEJAY", "DEE JAY", "Missing space"),
        
        # Case variations (should all work since we normalize)
        ("ryu", "RYU", "Lowercase"),
        ("Cammy", "CAMMY", "Mixed case"),
        ("chun-li", "CHUN-LI", "Lowercase with hyphen"),
        
        # Edge cases that should fail
        ("MARIO", "", "Non-SF6 character"),
        ("RY", "", "Too short/ambiguous"),
        ("ZZZZ", "", "Random text"),
        ("123", "", "Numbers only"),
        ("", "", "Empty string"),
        
        # Multiple character names (should return first found)
        ("RYU vs CAMMY", "RYU", "Multiple characters - first found"),
        ("CAMMY defeats LUKE", "CAMMY", "Multiple characters - first found"),
    ]
    
    print("🎮 Testing Street Fighter 6 Character Name Finder")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for input_text, expected, description in test_cases:
        result = finder.find_character(input_text)
        
        if result == expected:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1
        
        print(f"{status} | Input: '{input_text}' → Expected: '{expected}' | Got: '{result}' | {description}")
    
    print("=" * 60)
    print(f"📊 Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed!")
    else:
        print(f"⚠️  {failed} test(s) failed. Consider adjusting similarity threshold or adding more test cases.")
    
    return failed == 0


def test_similarity_thresholds():
    """Test different similarity thresholds to find optimal settings."""
    
    print("\n🔧 Testing different similarity thresholds")
    print("=" * 60)
    
    # Test cases that require fuzzy matching
    fuzzy_test_cases = [
        ("RYL", "RYU"),
        ("CAMM1", "CAMMY"),
        ("8LANKA", "BLANKA"),
        ("XEN", "KEN"),
        ("CHUN-L1", "CHUN-LI"),
    ]
    
    thresholds = [0.4, 0.5, 0.6, 0.7, 0.8]
    
    for threshold in thresholds:
        finder = CharacterNameFinder(similarity_threshold=threshold)
        print(f"\n📊 Threshold: {threshold}")
        
        for input_text, expected in fuzzy_test_cases:
            result = finder.find_character(input_text)
            status = "✅" if result == expected else "❌"
            print(f"  {status} '{input_text}' → '{result}' (expected: '{expected}')")


def interactive_test():
    """Interactive mode to test custom inputs."""
    
    print("\n🎯 Interactive Testing Mode")
    print("Enter text to test character recognition (or 'quit' to exit)")
    print("=" * 60)
    
    finder = CharacterNameFinder()
    
    while True:
        try:
            input_text = input("\n🎮 Enter text: ").strip()
            
            if input_text.lower() in ['quit', 'exit', 'q']:
                break
            
            if not input_text:
                continue
            
            result = finder.find_character(input_text)
            
            if result:
                print(f"✅ Found character: '{result}'")
            else:
                print("❌ No character found")
                
        except KeyboardInterrupt:
            break
    
    print("\n👋 Goodbye!")


if __name__ == "__main__":
    print("🚀 Starting Character Name Finder Tests\n")
    
    # Run main test suite
    success = test_character_finder()
    
    # Test different thresholds
    test_similarity_thresholds()
    
    # Interactive mode
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_test()
    else:
        print("\n💡 Tip: Run with --interactive flag for interactive testing mode")
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)