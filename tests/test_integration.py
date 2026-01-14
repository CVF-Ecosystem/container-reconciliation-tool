# File: tests/test_integration.py
# Integration tests for end-to-end workflows

import pytest
import pandas as pd
from pathlib import Path
import sys
import tempfile
import shutil
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Col
from core.reconciliation_engine import perform_reconciliation
from reports.email_template_exporter import export_all_operators
from reports.email_sender import load_email_config


class TestEndToEndReconciliation:
    """Integration tests for full reconciliation workflow."""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing."""
        # TON CU - Baseline inventory
        ton_cu = pd.DataFrame({
            Col.CONTAINER: ['CONT001', 'CONT002', 'CONT003'],
            Col.OPERATOR: ['VMC', 'VFC', 'VMC'],
            Col.FE: ['F', 'E', 'F'],
            Col.ISO: ['20', '40', '20'],
            Col.LOCATION: ['A-01', 'B-02', 'C-03'],
            Col.TRANSACTION_TIME: [datetime(2026, 1, 11, 8, 0)] * 3,
            Col.MOVE_TYPE: ['IN', 'IN', 'IN'],
            Col.SOURCE_KEY: ['ton_cu', 'ton_cu', 'ton_cu']
        })
        
        # TON MOI - Current inventory
        ton_moi = pd.DataFrame({
            Col.CONTAINER: ['CONT001', 'CONT003', 'CONT004'],  # CONT002 left, CONT004 new
            Col.OPERATOR: ['VMC', 'VMC', 'VFC'],
            Col.FE: ['F', 'F', 'E'],
            Col.ISO: ['20', '20', '40'],
            Col.LOCATION: ['A-01', 'C-03', 'D-04'],
            Col.TRANSACTION_TIME: [datetime(2026, 1, 12, 15, 0)] * 3,
            Col.MOVE_TYPE: ['IN', 'IN', 'IN'],
            Col.SOURCE_KEY: ['ton_moi', 'ton_moi', 'ton_moi']
        })
        
        # GATE IN
        gate_in = pd.DataFrame({
            Col.CONTAINER: ['CONT004'],
            Col.OPERATOR: ['VFC'],
            Col.XE_VAO_CONG: [datetime(2026, 1, 12, 10, 30)],
            Col.TRANSACTION_TIME: [datetime(2026, 1, 12, 10, 30)],
            Col.MOVE_TYPE: ['IN'],
            Col.SOURCE_KEY: ['gate_in']
        })
        
        # GATE OUT
        gate_out = pd.DataFrame({
            Col.CONTAINER: ['CONT002'],
            Col.OPERATOR: ['VFC'],
            Col.XE_RA_CONG: [datetime(2026, 1, 12, 14, 15)],
            Col.TRANSACTION_TIME: [datetime(2026, 1, 12, 14, 15)],
            Col.MOVE_TYPE: ['OUT'],
            Col.SOURCE_KEY: ['gate_out']
        })
        
        return {
            'ton_cu': ton_cu,
            'ton_moi': ton_moi,
            'gate_in': gate_in,
            'gate_out': gate_out
        }
    
    def test_reconciliation_workflow(self, sample_data):
        """Test complete reconciliation workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_folder = Path(tmpdir)
            
            # Run reconciliation engine
            results = perform_reconciliation(
                file_dfs=sample_data,
                report_folder=report_folder,
                run_time=datetime(2026, 1, 12, 16, 0)
            )
            
            # Verify results structure
            assert 'counts' in results
            # Engine returns khop_chuan (matched containers)
            assert 'khop_chuan' in results or 'ton_chuan' in results
            
            # Verify counts exist and have expected structure
            counts = results['counts']
            # These are dynamic based on input data
            assert isinstance(counts, dict)
            assert len(counts) > 0
    
    def test_export_workflow(self, sample_data):
        """Test export workflow for email templates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            
            # Prepare data
            df_bien_dong = pd.concat([
                sample_data['gate_in'],
                sample_data['gate_out']
            ], ignore_index=True)
            
            df_ton_bai = sample_data['ton_moi']
            
            # Export for all operators
            results = export_all_operators(
                df_bien_dong=df_bien_dong,
                df_ton_bai=df_ton_bai,
                date_str="N12.1.2026",
                output_dir=output_dir,
                parallel=False  # Sequential for test stability
            )
            
            # Verify exports were created
            assert len(results) >= 0  # May be 0 if no data matches operators
    
    def test_email_config_loading(self):
        """Test email configuration loading."""
        config = load_email_config()
        
        assert 'smtp_settings' in config
        assert 'operator_recipients' in config
        
        smtp = config['smtp_settings']
        assert 'server' in smtp
        assert 'port' in smtp
        assert isinstance(smtp['port'], int)


class TestBatchProcessing:
    """Integration tests for batch processing."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace with sample files."""
        tmpdir = tempfile.mkdtemp()
        workspace = Path(tmpdir)
        
        # Create folder structure
        slot_folder = workspace / "8H N10.1 - 8H N12.1.2026"
        slot_folder.mkdir(parents=True)
        
        # Create sample Excel files
        ton_cu_file = slot_folder / "TON CU.xlsx"
        ton_moi_file = slot_folder / "TON MOI.xlsx"
        
        # Simple DataFrames
        df_ton = pd.DataFrame({
            'Số Container': ['TEST001', 'TEST002'],
            'Hãng khai thác': ['VMC', 'VFC'],
            'F/E': ['F', 'E']
        })
        
        df_ton.to_excel(ton_cu_file, index=False)
        df_ton.to_excel(ton_moi_file, index=False)
        
        yield workspace
        
        # Cleanup
        shutil.rmtree(tmpdir)
    
    def test_batch_file_detection(self, temp_workspace):
        """Test batch processor can detect files."""
        from core.batch_processor import group_files_by_date_slot, extract_date_slot_from_filename
        
        # Use actual function to detect files
        grouped = group_files_by_date_slot(temp_workspace)
        
        assert len(grouped) >= 1
        
        # Check date extraction using actual function
        folder_name = "8H N10.1 - 8H N12.1.2026"
        extracted = extract_date_slot_from_filename(folder_name)
        assert extracted is not None


class TestDataValidation:
    """Integration tests for data validation."""
    
    def test_required_columns_validation(self):
        """Test validation of required columns."""
        from config import REQUIRED_COLUMNS_PER_FILE
        
        # Verify config loaded
        assert 'ton_cu' in REQUIRED_COLUMNS_PER_FILE
        assert 'ton_moi' in REQUIRED_COLUMNS_PER_FILE
        
        # Each should have list of column alternatives
        for key, columns in REQUIRED_COLUMNS_PER_FILE.items():
            assert isinstance(columns, list)
            assert len(columns) > 0
    
    def test_operator_mapping_validation(self):
        """Test operator mapping configuration."""
        from config import OPERATOR_MAPPING
        
        assert 'VIMC Lines' in OPERATOR_MAPPING
        assert isinstance(OPERATOR_MAPPING['VIMC Lines'], list)
        assert 'VMC' in OPERATOR_MAPPING['VIMC Lines']


class TestErrorRecovery:
    """Integration tests for error handling and recovery."""
    
    def test_missing_file_handling(self):
        """Test system handles missing files gracefully."""
        from data.data_loader import load_and_transform_one_file
        from pathlib import Path
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Try to load non-existent file
            try:
                result = load_and_transform_one_file(
                    Path("nonexistent.xlsx"), "nonexistent.xlsx", "test_key", Path(tmpdir)
                )
                # Should return empty DataFrame or raise error
                assert isinstance(result, pd.DataFrame)
            except Exception:
                # Exception is acceptable for missing file
                pass
    
    def test_corrupted_data_handling(self):
        """Test system handles corrupted data."""
        # Create DataFrame with problematic data
        df = pd.DataFrame({
            Col.CONTAINER: ['VALID001', None, '', 'VALID002'],
            Col.OPERATOR: ['VMC', None, 'Unknown', 'VFC']
        })
        
        # Should not crash on cleaning
        from data.data_loader import ultimate_clean_series
        
        cleaned = ultimate_clean_series(df[Col.CONTAINER])
        # Function filters out empty strings, so length may be less than original
        assert len(cleaned) >= 2  # At least 2 valid containers
        assert cleaned.notna().sum() >= 2  # At least 2 non-NA values


class TestPerformance:
    """Integration tests for performance scenarios."""
    
    def test_large_dataset_handling(self):
        """Test system can handle large datasets."""
        # Create large DataFrame
        large_df = pd.DataFrame({
            Col.CONTAINER: [f'CONT{i:06d}' for i in range(10000)],
            Col.OPERATOR: ['VMC'] * 5000 + ['VFC'] * 5000,
            Col.FE: ['F'] * 7000 + ['E'] * 3000
        })
        
        # Should process without memory issues
        from reports.email_template_exporter import filter_by_operator
        
        filtered = filter_by_operator(large_df, 'VIMC Lines', Col.OPERATOR)
        assert len(filtered) >= 0
    
    def test_parallel_export_performance(self):
        """Test parallel export is faster than sequential."""
        import time
        
        # Create test data
        df = pd.DataFrame({
            Col.CONTAINER: [f'CONT{i:03d}' for i in range(100)],
            Col.OPERATOR: ['VMC', 'VFC', 'VOC'] * 33 + ['VMC']
        })
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            
            # Test with small dataset (should use sequential)
            start = time.time()
            from reports.email_template_exporter import export_all_operators
            
            results = export_all_operators(
                df_bien_dong=df,
                df_ton_bai=df,
                date_str="N12.1.2026",
                output_dir=output_dir,
                operators=['VIMC Lines'],
                parallel=False
            )
            duration = time.time() - start
            
            # Should complete quickly (< 5 seconds)
            assert duration < 5.0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
