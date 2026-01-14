"""
Unit Tests for data_loader module.
Tests data loading, cleaning, and transformation functions.
"""
import unittest
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from data.data_loader import ultimate_clean_series


class TestUltimateCleanSeries(unittest.TestCase):
    """Test the container ID cleaning function."""
    
    def test_removes_special_characters(self):
        """Verify special characters are removed from container IDs."""
        s = pd.Series(['TEST-123', 'ABC.456', 'XYZ 789'])
        result = ultimate_clean_series(s)
        
        self.assertEqual(result.iloc[0], 'TEST123')
        self.assertEqual(result.iloc[1], 'ABC456')
        self.assertEqual(result.iloc[2], 'XYZ789')
    
    def test_converts_to_uppercase(self):
        """Verify all container IDs are uppercased."""
        s = pd.Series(['test123', 'AbC456'])
        result = ultimate_clean_series(s)
        
        self.assertEqual(result.iloc[0], 'TEST123')
        self.assertEqual(result.iloc[1], 'ABC456')
    
    def test_removes_trailing_decimal(self):
        """Verify .0 suffix is removed (common Excel issue)."""
        s = pd.Series(['123456.0', '789012.0'])
        result = ultimate_clean_series(s)
        
        self.assertEqual(result.iloc[0], '123456')
        self.assertEqual(result.iloc[1], '789012')
    
    def test_handles_empty_strings(self):
        """Verify empty strings become NA."""
        s = pd.Series(['', '   ', 'VALID123'])
        result = ultimate_clean_series(s)
        
        self.assertTrue(pd.isna(result.iloc[0]))
        self.assertTrue(pd.isna(result.iloc[1]))
        self.assertEqual(result.iloc[2], 'VALID123')
    
    def test_handles_nan_values(self):
        """Verify NaN values are handled gracefully."""
        s = pd.Series([None, float('nan'), 'VALID123'])
        result = ultimate_clean_series(s)
        
        # NaN values should be dropped, only VALID123 remains
        self.assertEqual(len(result.dropna()), 1)
        self.assertEqual(result.dropna().iloc[0], 'VALID123')
    
    def test_raises_error_for_non_series(self):
        """Verify TypeError is raised for non-Series input."""
        with self.assertRaises(TypeError):
            ultimate_clean_series(['not', 'a', 'series'])
        
        with self.assertRaises(TypeError):
            ultimate_clean_series('just a string')


class TestDataLoaderIntegration(unittest.TestCase):
    """Integration tests for the data loading pipeline."""
    
    def test_sample_container_format(self):
        """Test with realistic container ID formats."""
        # Standard ISO container format: XXXX1234567
        s = pd.Series([
            'MSCU1234567',    # Standard format
            'MSCU 123 4567',  # With spaces
            'mscu1234567.0',  # Lowercase with decimal
            'MSCU-1234567',   # With dash
        ])
        
        result = ultimate_clean_series(s)
        
        # All should become standardized
        self.assertEqual(result.iloc[0], 'MSCU1234567')
        self.assertEqual(result.iloc[1], 'MSCU1234567')
        self.assertEqual(result.iloc[2], 'MSCU1234567')
        self.assertEqual(result.iloc[3], 'MSCU1234567')


if __name__ == '__main__':
    unittest.main(verbosity=2)
