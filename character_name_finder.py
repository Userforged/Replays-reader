"""
Street Fighter 6 Character Name Finder

A utility class for identifying Street Fighter 6 character names from OCR text.
Provides fuzzy matching capabilities to handle OCR errors.
"""

from difflib import get_close_matches

class CharacterNameFinder:
    """Finds and validates Street Fighter 6 character names from text input."""
    
    SF6_CHARACTERS = [
        "RYU",
        "CHUN-LI",
        "LUKE",
        "JAMIE",
        "MANON",
        "KIMBERLY",
        "MARISA",
        "LILY",
        "JP",
        "JURI",
        "DEE JAY",
        "CAMMY",
        "KEN",
        "BLANKA",
        "GUILE",
        "HONDA",
        "ZANGIEF",
        "DHALSIM",
        "RASHID",
        "A.K.I.",
        "ED",
        "AKUMA",
        "TERRY",
        "MAI",
        "ELENA",
        "BISON",
        "SAGAT"
    ]
    
    def __init__(self, similarity_threshold=0.5):
        """
        Initialize the character name finder.
        
        Args:
            similarity_threshold (float): Minimum similarity for fuzzy matching (0.0-1.0)
        """
        self.similarity_threshold = similarity_threshold
    
    def find_character(self, text):
        """
        Find Street Fighter 6 character name from input text.
        
        Args:
            text (str): Text to search for character names
            
        Returns:
            str: Character name if found, empty string otherwise
        """
        if not text or not isinstance(text, str):
            return ""
        
        # Clean and normalize the input text
        cleaned_text = text.upper().strip()
        
        if not cleaned_text:
            return ""
        
        # Try exact match first
        exact_match = self._find_exact_match(cleaned_text)
        if exact_match:
            return exact_match
        
        # Try fuzzy matching for OCR errors
        fuzzy_match = self._find_fuzzy_match(cleaned_text)
        if fuzzy_match:
            return fuzzy_match
        
        return ""
    
    def _find_exact_match(self, text):
        """Find exact character name matches."""
        # Check direct matches in character list
        if text in self.SF6_CHARACTERS:
            return text
        
        # Check if text contains a character name
        for char_name in self.SF6_CHARACTERS:
            if char_name in text:
                return char_name
        
        return None
    
    def _find_fuzzy_match(self, text):
        """Find character names using fuzzy matching for OCR errors."""
        # Try fuzzy matching against all character names
        matches = get_close_matches(
            text, 
            self.SF6_CHARACTERS, 
            n=1, 
            cutoff=self.similarity_threshold
        )
        
        if matches:
            return matches[0]
        
        # Try fuzzy matching with individual words (in case of extra text)
        words = text.split()
        for word in words:
            if len(word) >= 3:  # Skip very short words
                matches = get_close_matches(
                    word, 
                    self.SF6_CHARACTERS, 
                    n=1, 
                    cutoff=self.similarity_threshold
                )
                if matches:
                    return matches[0]
        
        return None
    
    def get_all_characters(self):
        """Get list of all available character names."""
        return self.SF6_CHARACTERS.copy()
    
    def is_valid_character(self, name):
        """Check if a name is a valid SF6 character."""
        if not name:
            return False
        
        name = name.upper().strip()
        return name in self.SF6_CHARACTERS
