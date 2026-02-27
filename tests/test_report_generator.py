# File: tests/test_report_generator.py
"""
Unit tests for reports/report_generator.py.
Tests cover: _add_total_row, _create_phuong_an_breakdown, _create_summary_by_source,
             _create_inventory_change_summary, _write_sheet.
"""
import pytest
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Col
from reports.report_generator import (
    _add_total_row,
    _create_phuong_an_breakdown,
    _create_summary_by_source,
    _create_inventory_change_summary,
    _write_sheet,
)


class TestAddTotalRow:
    """Tests for _add_total_row function."""
    
    def test_adds_total_row_with_numeric_columns(self):
        """Should add TỔNG CỘNG row with sum of numeric columns."""
        df = pd.DataFrame({
            'Name': ['A', 'B', 'C'],
            'Count': [10, 20, 30],
            'Amount': [100.0, 200.0, 300.0]
        })
        
        result = _add_total_row(df)
        
        assert len(result) == 4  # 3 rows + 1 total
        assert result.iloc[-1]['Name'] == 'TỔNG CỘNG'
        assert result.iloc[-1]['Count'] == 60
        assert result.iloc[-1]['Amount'] == 600.0
    
    def test_empty_dataframe_returns_empty(self):
        """Empty DataFrame should be returned as-is."""
        df = pd.DataFrame()
        result = _add_total_row(df)
        assert result.empty
    
    def test_no_numeric_columns_returns_unchanged(self):
        """DataFrame with no numeric columns should be returned unchanged."""
        df = pd.DataFrame({
            'Name': ['A', 'B'],
            'Category': ['X', 'Y']
        })
        
        result = _add_total_row(df)
        assert len(result) == 2  # No total row added
    
    def test_total_row_has_empty_string_for_non_numeric(self):
        """Non-numeric columns (except first) should have empty string in total row."""
        df = pd.DataFrame({
            'Label': ['A', 'B'],
            'Count': [5, 10],
            'Note': ['x', 'y']
        })
        
        result = _add_total_row(df)
        total_row = result.iloc[-1]
        assert total_row['Note'] == ''


class TestCreatePhuongAnBreakdown:
    """Tests for _create_phuong_an_breakdown function."""
    
    def test_creates_breakdown_with_phuong_an(self):
        """Should create breakdown table when PHUONG_AN column exists."""
        raw_data = {
            'gate_in': pd.DataFrame({
                Col.CONTAINER: ['C001', 'C002', 'C003'],
                Col.PHUONG_AN: ['Hạ bãi', 'Hạ bãi', 'Trả rỗng']
            }),
            'gate_out': pd.DataFrame({
                Col.CONTAINER: ['C004'],
                Col.PHUONG_AN: ['Lấy nguyên']
            })
        }
        
        result = _create_phuong_an_breakdown(raw_data)
        
        assert not result.empty
        assert 'Nguồn' in result.columns
        assert 'Phương án' in result.columns
        assert 'Số lượng' in result.columns
    
    def test_empty_raw_data_returns_empty(self):
        """Empty raw_data should return empty DataFrame."""
        result = _create_phuong_an_breakdown({})
        assert result.empty
    
    def test_handles_missing_phuong_an_column(self):
        """Should handle DataFrames without PHUONG_AN column."""
        raw_data = {
            'ton_cu': pd.DataFrame({
                Col.CONTAINER: ['C001', 'C002']
                # No PHUONG_AN column
            })
        }
        
        result = _create_phuong_an_breakdown(raw_data)
        # Should still return a result with '(Tổng)' as phương án
        assert not result.empty
        assert '(Tổng)' in result['Phương án'].values


class TestCreateSummaryBySource:
    """Tests for _create_summary_by_source function."""
    
    def test_creates_summary_with_all_sources(self):
        """Should create summary for all data sources."""
        raw_data = {
            'ton_cu': pd.DataFrame({Col.CONTAINER: ['C001', 'C002']}),
            'ton_moi': pd.DataFrame({Col.CONTAINER: ['C001', 'C003']}),
            'gate_in': pd.DataFrame({Col.CONTAINER: ['C003']}),
            'gate_out': pd.DataFrame({Col.CONTAINER: ['C002']}),
        }
        
        result = _create_summary_by_source(raw_data)
        
        assert not result.empty
        assert 'Nhóm' in result.columns
        assert 'Loại' in result.columns
        assert 'Số lượng' in result.columns
    
    def test_counts_are_correct(self):
        """Counts should match actual DataFrame lengths."""
        raw_data = {
            'ton_cu': pd.DataFrame({Col.CONTAINER: ['C001', 'C002', 'C003']}),
            'ton_moi': pd.DataFrame({Col.CONTAINER: ['C001']}),
        }
        
        result = _create_summary_by_source(raw_data)
        
        ton_cu_row = result[result['Loại'] == 'Tồn đầu kỳ (Baseline)']
        assert ton_cu_row.iloc[0]['Số lượng'] == 3
        
        ton_moi_row = result[result['Loại'] == 'Tồn hiện tại']
        assert ton_moi_row.iloc[0]['Số lượng'] == 1
    
    def test_empty_sources_show_zero(self):
        """Missing sources should show 0 count."""
        raw_data = {}  # No data
        
        result = _create_summary_by_source(raw_data)
        
        # All counts should be 0
        assert (result['Số lượng'] == 0).all()


class TestCreateInventoryChangeSummary:
    """Tests for _create_inventory_change_summary function."""
    
    def test_creates_summary_with_data(self):
        """Should create summary with moi_vao and da_roi data."""
        inventory_results = {
            'moi_vao_bai': pd.DataFrame({Col.CONTAINER: ['C001', 'C002']}),
            'da_roi_bai': pd.DataFrame({Col.CONTAINER: ['C003']}),
            'van_con_ton': pd.DataFrame({Col.CONTAINER: ['C004', 'C005', 'C006']}),
        }
        
        result = _create_inventory_change_summary(inventory_results)
        
        assert not result.empty
        assert 'Hạng mục' in result.columns
        assert 'Số lượng' in result.columns
    
    def test_counts_match_data(self):
        """Counts should match actual data."""
        inventory_results = {
            'moi_vao_bai': pd.DataFrame({Col.CONTAINER: ['C001', 'C002']}),
            'da_roi_bai': pd.DataFrame({Col.CONTAINER: ['C003']}),
            'van_con_ton': pd.DataFrame({Col.CONTAINER: ['C004']}),
        }
        
        result = _create_inventory_change_summary(inventory_results)
        
        moi_vao_row = result[result['Hạng mục'] == 'Container MỚI VÀO bãi']
        assert moi_vao_row.iloc[0]['Số lượng'] == 2
        
        da_roi_row = result[result['Hạng mục'] == 'Container ĐÃ RỜI bãi']
        assert da_roi_row.iloc[0]['Số lượng'] == 1


class TestWriteSheet:
    """Tests for _write_sheet function."""
    
    def test_write_sheet_with_valid_data(self):
        """Should write sheet without errors."""
        df = pd.DataFrame({
            'Name': ['A', 'B'],
            'Count': [1, 2]
        })
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            tmp_path = f.name
        
        try:
            with pd.ExcelWriter(tmp_path, engine='openpyxl') as writer:
                _write_sheet(writer, df, "Test_Sheet")
            
            # Verify file was written
            result = pd.read_excel(tmp_path, sheet_name='Test_Sheet')
            assert len(result) >= 2  # At least 2 data rows (may have total row)
        finally:
            import os
            os.unlink(tmp_path)
    
    def test_write_sheet_with_none_df(self):
        """Should handle None DataFrame gracefully."""
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            tmp_path = f.name
        
        try:
            with pd.ExcelWriter(tmp_path, engine='openpyxl') as writer:
                # Write a dummy sheet first so file is valid
                pd.DataFrame({'x': [1]}).to_excel(writer, sheet_name='Dummy')
                # This should not raise
                _write_sheet(writer, None, "Empty_Sheet")
        finally:
            import os
            os.unlink(tmp_path)
    
    def test_write_sheet_with_empty_df(self):
        """Should handle empty DataFrame gracefully."""
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            tmp_path = f.name
        
        try:
            with pd.ExcelWriter(tmp_path, engine='openpyxl') as writer:
                pd.DataFrame({'x': [1]}).to_excel(writer, sheet_name='Dummy')
                _write_sheet(writer, pd.DataFrame(), "Empty_Sheet")
        finally:
            import os
            os.unlink(tmp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
