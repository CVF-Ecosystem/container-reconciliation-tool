import unittest
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import config
from core.reconciliation_engine import correct_future_dates
import pandas as pd
from datetime import datetime

class TestConfig(unittest.TestCase):
    def test_config_loading(self):
        """Test config loading from JSON"""
        self.assertTrue(hasattr(config, 'REQUIRED_COLUMNS_PER_FILE'))
        self.assertTrue(hasattr(config, 'OPERATOR_MAPPING'))
        self.assertIn('ton_cu', config.REQUIRED_COLUMNS_PER_FILE)
        
    def test_business_rules_existence(self):
        """Test that business rules constant exists"""
        self.assertTrue(hasattr(config, 'BUSINESS_RULES'))
        self.assertIsInstance(config.BUSINESS_RULES, list)

class TestReconciliation(unittest.TestCase):
    def test_future_dates_warning_only(self):
        """Test that correct_future_dates DOES NOT modify data, only reports"""
        run_time = datetime(2023, 1, 1)
        future_date = datetime(2023, 1, 2)
        
        df = pd.DataFrame({
            config.Col.TRANSACTION_TIME: [future_date],
            'Value': [1]
        })
        
        df_result, df_report = correct_future_dates(df, run_time)
        
        # Check original is unmodified
        self.assertEqual(df_result.iloc[0][config.Col.TRANSACTION_TIME], future_date)
        
        # Check report contains warning
        self.assertFalse(df_report.empty)
        self.assertIn('GhiChu_SuaLoi', df_report.columns)

if __name__ == '__main__':
    unittest.main()
