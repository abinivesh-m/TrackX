"""
test_plate_normalization_artifacts.py

Tests for Indian license plate normalization with country marker artifact removal.
Ensures that OCR artifacts like "IND", "ND", "IND-", "-ND" are properly removed
while preserving legitimate plate characters.
"""
import sys
import os
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from recognition.plate_normalizer import normalize_indian_plate


class TestPlateNormalizationArtifacts(unittest.TestCase):
    """Test cases for country marker artifact removal in Indian plate normalization."""
    
    def test_ind_prefix_removal(self):
        """Test that IND prefix is removed from plates."""
        normalized, matched = normalize_indian_plate("INDTN09CQ1234")
        self.assertEqual(normalized, "TN09CQ1234")
        self.assertTrue(matched)
    
    def test_ind_suffix_removal(self):
        """Test that IND suffix is removed from plates."""
        normalized, matched = normalize_indian_plate("TN09CQ1234IND")
        self.assertEqual(normalized, "TN09CQ1234")
        self.assertTrue(matched)
    
    def test_nd_prefix_removal(self):
        """Test that ND prefix (partial artifact) is removed from plates."""
        normalized, matched = normalize_indian_plate("NDTN09CQ1234")
        self.assertEqual(normalized, "TN09CQ1234")
        self.assertTrue(matched)
    
    def test_nd_suffix_removal(self):
        """Test that ND suffix (partial artifact) is removed from plates."""
        normalized, matched = normalize_indian_plate("TN09CQ1234ND")
        self.assertEqual(normalized, "TN09CQ1234")
        self.assertTrue(matched)
    
    def test_ind_dash_prefix_removal(self):
        """Test that IND- prefix with dash is removed from plates."""
        normalized, matched = normalize_indian_plate("IND-TN09CQ1234")
        self.assertEqual(normalized, "TN09CQ1234")
        self.assertTrue(matched)
    
    def test_ind_dash_suffix_removal(self):
        """Test that -IND suffix with dash is removed from plates."""
        normalized, matched = normalize_indian_plate("TN09CQ1234-IND")
        self.assertEqual(normalized, "TN09CQ1234")
        self.assertTrue(matched)
    
    def test_nd_dash_suffix_removal(self):
        """Test that -ND suffix with dash is removed from plates."""
        normalized, matched = normalize_indian_plate("TN09CQ1234-ND")
        self.assertEqual(normalized, "TN09CQ1234")
        self.assertTrue(matched)
    
    def test_nd_dash_prefix_removal(self):
        """Test that -ND prefix with dash is removed from plates."""
        normalized, matched = normalize_indian_plate("-NDTN09CQ1234")
        self.assertEqual(normalized, "TN09CQ1234")
        self.assertTrue(matched)
    
    def test_no_artifact_preservation(self):
        """Test that plates without artifacts are preserved unchanged."""
        normalized, matched = normalize_indian_plate("TN09CQ1234")
        self.assertEqual(normalized, "TN09CQ1234")
        self.assertTrue(matched)
    
    def test_different_state_codes(self):
        """Test that artifact removal works with different state codes."""
        # Karnataka
        normalized, matched = normalize_indian_plate("INDKA01AB1234")
        self.assertEqual(normalized, "KA01AB1234")
        self.assertTrue(matched)
        
        # Maharashtra
        normalized, matched = normalize_indian_plate("MH02CD5678IND")
        self.assertEqual(normalized, "MH02CD5678")
        self.assertTrue(matched)
    
    def test_legitimate_characters_preserved(self):
        """Test that legitimate I, N, D characters in plates are preserved."""
        # Plates with legitimate I, N, D in registration number
        normalized, matched = normalize_indian_plate("TN09DI1234")  # 'D' and 'I' in series
        self.assertIn("D", normalized)
        self.assertIn("I", normalized)
        
        normalized, matched = normalize_indian_plate("TN09DN1234")  # 'D' and 'N' in series
        self.assertIn("D", normalized)
        self.assertIn("N", normalized)
    
    def test_short_text_no_removal(self):
        """Test that artifacts are not removed from short texts (< 9 chars)."""
        normalized, matched = normalize_indian_plate("IND123")
        # Should not remove IND because remaining text is too short
        self.assertIn("IND", normalized)
    
    def test_empty_text_handling(self):
        """Test that empty text is handled gracefully."""
        normalized, matched = normalize_indian_plate("")
        self.assertEqual(normalized, "")
        self.assertFalse(matched)
    
    def test_multiple_artifacts_single_removal(self):
        """Test that only one artifact is removed even if multiple are present."""
        normalized, matched = normalize_indian_plate("INDTN09CQ1234IND")
        # Should remove only one artifact (prefix in this case)
        # Result should be TN09CQ1234IND (prefix removed, suffix remains)
        self.assertEqual(normalized, "TN09CQ1234IND")
        # Should contain the plate number
        self.assertIn("TN09CQ1234", normalized)


if __name__ == "__main__":
    unittest.main()
