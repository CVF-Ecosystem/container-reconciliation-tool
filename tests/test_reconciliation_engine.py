"""
Unit Tests for reconciliation_engine module.
Tests the core reconciliation logic and date handling functions.
"""
import unittest
import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import config
from config import Col


class TestFutureDatesWarning(unittest.TestCase):
    """Test that future dates are reported but NOT auto-corrected."""
    
    def setUp(self):
        from core.reconciliation_engine import correct_future_dates
        self.correct_future_dates = correct_future_dates
        self.run_time = datetime(2023, 6, 15, 10, 0, 0)
    
    def test_no_modification_of_future_dates(self):
        """Verify that original data is NOT modified when future dates are found."""
        future_date = datetime(2023, 6, 20)  # 5 days in the future
        
        df_input = pd.DataFrame({
            Col.TRANSACTION_TIME: [future_date],
            'Container': ['TEST001']
        })
        
        df_result, df_report = self.correct_future_dates(df_input, self.run_time)
        
        # Original data should be unchanged
        self.assertEqual(df_result.iloc[0][Col.TRANSACTION_TIME], future_date)
        
        # Report should contain the problematic row
        self.assertEqual(len(df_report), 1)
        self.assertIn('GhiChu_SuaLoi', df_report.columns)
    
    def test_empty_report_for_valid_dates(self):
        """Verify no report generated for valid (past) dates."""
        past_date = datetime(2023, 6, 10)  # 5 days in the past
        
        df_input = pd.DataFrame({
            Col.TRANSACTION_TIME: [past_date],
            'Container': ['TEST001']
        })
        
        df_result, df_report = self.correct_future_dates(df_input, self.run_time)
        
        self.assertTrue(df_report.empty)


class TestMismatchDetection(unittest.TestCase):
    """Test the mismatch detection logic."""
    
    def setUp(self):
        from core.reconciliation_engine import _find_mismatched_rows
        self._find_mismatched_rows = _find_mismatched_rows
    
    def test_operator_column_not_in_compare_cols(self):
        """V4.7.1+: Col.OPERATOR không còn trong COMPARE_COLS_FOR_MISMATCH.
        
        Operator mismatch không được detect nữa vì file giao dịch không có cột Hãng.
        Test này verify rằng operator khác nhau KHÔNG bị coi là mismatch.
        """
        df = pd.DataFrame({
            f'{Col.OPERATOR}_lythuyet': ['VMC'],
            f'{Col.OPERATOR}_thucte': ['VFC'],
            f'{Col.FE}_lythuyet': ['F'],
            f'{Col.FE}_thucte': ['F'],
            f'{Col.ISO}_lythuyet': ['20'],
            f'{Col.ISO}_thucte': ['20'],
            f'{Col.LOCATION}_lythuyet': ['A-01'],
            f'{Col.LOCATION}_thucte': ['A-01'],
        })
        
        result = self._find_mismatched_rows(df)
        # Operator khác nhau nhưng FE/ISO/LOCATION giống nhau → KHÔNG phải mismatch
        self.assertFalse(result.iloc[0])
    
    def test_no_mismatch_when_all_compare_cols_identical(self):
        """Verify no mismatch when FE, ISO, LOCATION all match (V4.7.1+)."""
        df = pd.DataFrame({
            f'{Col.OPERATOR}_lythuyet': ['VMC'],
            f'{Col.OPERATOR}_thucte': ['VFC'],  # Operator khác nhau nhưng không check
            f'{Col.FE}_lythuyet': ['F'],
            f'{Col.FE}_thucte': ['F'],
            f'{Col.ISO}_lythuyet': ['40HC'],
            f'{Col.ISO}_thucte': ['40HC'],
            f'{Col.LOCATION}_lythuyet': ['A-01-01'],
            f'{Col.LOCATION}_thucte': ['A-01-01'],
        })
        
        result = self._find_mismatched_rows(df)
        self.assertFalse(result.iloc[0])  # No mismatch in checked columns
    
    def test_detects_fe_mismatch(self):
        """V4.7.1: Test with current comparison columns (FE, ISO, LOCATION)."""
        df = pd.DataFrame({
            f'{Col.FE}_lythuyet': ['F'],
            f'{Col.FE}_thucte': ['E'],
            f'{Col.ISO}_lythuyet': ['40HC'],
            f'{Col.ISO}_thucte': ['40HC'],
            f'{Col.LOCATION}_lythuyet': ['A-01-01'],
            f'{Col.LOCATION}_thucte': ['A-01-01'],
        })
        
        result = self._find_mismatched_rows(df)
        self.assertTrue(result.iloc[0])  # F/E mismatch should be detected
    
    def test_no_mismatch_current_cols(self):
        """V4.7.1: Verify no mismatch when FE, ISO, LOCATION all match."""
        df = pd.DataFrame({
            f'{Col.FE}_lythuyet': ['F'],
            f'{Col.FE}_thucte': ['F'],
            f'{Col.ISO}_lythuyet': ['40HC'],
            f'{Col.ISO}_thucte': ['40HC'],
            f'{Col.LOCATION}_lythuyet': ['A-01-01'],
            f'{Col.LOCATION}_thucte': ['A-01-01'],
        })
        
        result = self._find_mismatched_rows(df)
        self.assertFalse(result.iloc[0])  # No mismatch


class TestSuspiciousDates(unittest.TestCase):
    """Test suspicious date detection (dd/mm swap detection)."""
    
    def setUp(self):
        from core.reconciliation_engine import find_suspicious_dates
        self.find_suspicious_dates = find_suspicious_dates
    
    def test_detects_swapped_date(self):
        """Verify detection of dates where day/month may be swapped.
        
        Logic: A date is suspicious if:
        - date.month == run_time.day
        - date.day == run_time.month
        - date.date != run_time.date
        
        Example: If run_time is Dec 6 (month=12, day=6), a suspicious date would be
        Jun 12 (month=6, day=12) - looks like dd/mm was swapped to mm/dd.
        """
        run_time = datetime(2023, 12, 6)  # Dec 6, 2023 (month=12, day=6)
        
        # Suspicious: month=6 (== run_time.day), day=12 (== run_time.month)
        suspicious_date = datetime(2023, 6, 12)  # Jun 12, 2023
        
        df = pd.DataFrame({
            Col.TRANSACTION_TIME: [suspicious_date],
            'Container': ['TEST001']
        })
        
        result = self.find_suspicious_dates(df, run_time)
        
        # Note: The function checks within a 60-day window.
        # Jun 12 is ~177 days before Dec 6, so it falls OUTSIDE the 60-day window.
        # Therefore, it should NOT be flagged. This is the expected behavior.
        self.assertEqual(len(result), 0)
    
    def test_within_window_suspicious_date(self):
        """Test with a date that IS within the 60-day window."""
        run_time = datetime(2023, 7, 6)  # Jul 6, 2023 (month=7, day=6)
        
        # A date within 60 days that has swapped day/month characteristics
        # We need: date.month == 6 (run_time.day) and date.day == 7 (run_time.month)
        suspicious_date = datetime(2023, 6, 7)  # Jun 7, 2023 (within 60 days of Jul 6)
        
        df = pd.DataFrame({
            Col.TRANSACTION_TIME: [suspicious_date],
            'Container': ['TEST001']
        })
        
        result = self.find_suspicious_dates(df, run_time)
        
        # Jun 7 is ~29 days before Jul 6, so it IS within the 60-day window
        # And it matches the swap pattern (month=6==day, day=7==month)
        self.assertEqual(len(result), 1)


class TestIdentifyPendingShifting(unittest.TestCase):
    """Test the Smart Shifting logic (V4.4)."""
    
    def setUp(self):
        from core.reconciliation_engine import identify_pending_shifting
        self.identify_pending_shifting = identify_pending_shifting
    
    def test_identifies_pending_restow(self):
        """Verify detection of containers with N-Shifting but no X-Shifting."""
        # Container that was shifted IN but not shifted OUT
        df_all_moves = pd.DataFrame({
            Col.CONTAINER: ['CONT001', 'CONT002', 'CONT002'],
            Col.SOURCE_KEY: ['nhap_shifting', 'nhap_shifting', 'xuat_shifting'],
            Col.TRANSACTION_TIME: pd.to_datetime([
                '2024-12-24 08:00',
                '2024-12-24 09:00',
                '2024-12-24 10:00'  # CONT002 completed shifting
            ])
        })
        
        df_ton_moi = pd.DataFrame({
            Col.CONTAINER: ['CONT001', 'CONT003'],  # CONT001 still in yard
        })
        
        result = self.identify_pending_shifting(df_all_moves, df_ton_moi)
        
        # CONT001 should be flagged as pending shifting
        self.assertEqual(len(result), 1)
        self.assertIn('CONT001', result[Col.CONTAINER].values)
    
    def test_no_pending_when_completed(self):
        """Verify no flag when shifting is completed (X-Shifting done)."""
        df_all_moves = pd.DataFrame({
            Col.CONTAINER: ['CONT001', 'CONT001'],
            Col.SOURCE_KEY: ['nhap_shifting', 'xuat_shifting'],
            Col.TRANSACTION_TIME: pd.to_datetime([
                '2024-12-24 08:00',
                '2024-12-24 09:00'  # Completed
            ])
        })
        
        df_ton_moi = pd.DataFrame({
            Col.CONTAINER: ['CONT001'],
        })
        
        result = self.identify_pending_shifting(df_all_moves, df_ton_moi)
        
        # Last status is xuat_shifting, so no pending
        self.assertEqual(len(result), 0)
    
    def test_empty_dataframes(self):
        """Verify handling of empty DataFrames."""
        result = self.identify_pending_shifting(pd.DataFrame(), pd.DataFrame())
        self.assertTrue(result.empty)


class TestGenerateMismatchNotes(unittest.TestCase):
    """Test mismatch note generation."""
    
    def setUp(self):
        from core.reconciliation_engine import generate_mismatch_notes
        self.generate_mismatch_notes = generate_mismatch_notes
    
    def test_generates_detailed_notes(self):
        """V4.7.1: Test with current columns (FE, ISO, LOCATION)."""
        row = pd.Series({
            f'{Col.FE}_lythuyet': 'F',
            f'{Col.FE}_thucte': 'E',
            f'{Col.ISO}_lythuyet': '40HC',
            f'{Col.ISO}_thucte': '40HC',
            f'{Col.LOCATION}_lythuyet': 'A-01-01',
            f'{Col.LOCATION}_thucte': 'B-02-03',
        })
        
        notes = self.generate_mismatch_notes(row)
        
        self.assertIn('Sai', notes)
        # Should detect F/E and LOCATION mismatch
        self.assertIn("F", notes)
        self.assertIn("E", notes)
    
    def test_empty_notes_when_matching(self):
        """V4.7.1: Verify empty string when FE, ISO, LOCATION all match."""
        row = pd.Series({
            f'{Col.FE}_lythuyet': 'F',
            f'{Col.FE}_thucte': 'F',
            f'{Col.ISO}_lythuyet': '40HC',
            f'{Col.ISO}_thucte': '40HC',
            f'{Col.LOCATION}_lythuyet': 'A-01-01',
            f'{Col.LOCATION}_thucte': 'A-01-01',
        })
        
        notes = self.generate_mismatch_notes(row)
        
        self.assertEqual(notes, '')


if __name__ == '__main__':
    unittest.main(verbosity=2)
