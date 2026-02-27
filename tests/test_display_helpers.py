# File: tests/test_display_helpers.py
# @2026 v1.0: Unit tests for utils/display_helpers.py
"""Tests for display helper functions extracted from app.py."""

import pytest
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Col, DEFAULT_TEU_FACTOR
from utils.display_helpers import (
    prepare_df_for_display,
    add_stt_column,
    format_operator_table,
    calculate_teus,
    add_teus_to_summary,
    add_teus_columns_to_operator_table,
)


class TestPreparedfForDisplay:
    """Tests for prepare_df_for_display."""
    
    def test_converts_object_columns_to_string(self):
        """Object columns should be converted to string."""
        df = pd.DataFrame({
            'Name': ['Alice', None, 'Bob'],
            'Count': [1, 2, 3]
        })
        result = prepare_df_for_display(df)
        assert result['Name'].dtype == object  # string type
        assert 'nan' not in result['Name'].values
    
    def test_none_returns_empty_dataframe(self):
        """None input should return empty DataFrame."""
        result = prepare_df_for_display(None)
        assert result.empty
    
    def test_empty_df_returns_empty(self):
        """Empty DataFrame should return empty DataFrame."""
        result = prepare_df_for_display(pd.DataFrame())
        assert result.empty
    
    def test_does_not_modify_numeric_columns(self):
        """Numeric columns should not be converted."""
        df = pd.DataFrame({'Count': [1, 2, 3]})
        result = prepare_df_for_display(df)
        assert result['Count'].dtype in ['int64', 'int32']


class TestAddSttColumn:
    """Tests for add_stt_column."""
    
    def test_adds_stt_column_at_start(self):
        """STT column should be added at position 0."""
        df = pd.DataFrame({'Name': ['A', 'B', 'C']})
        result = add_stt_column(df)
        assert result.columns[0] == 'STT'
        assert list(result['STT']) == [1, 2, 3]
    
    def test_uses_translator_for_column_name(self):
        """Should use translator function for column name."""
        df = pd.DataFrame({'Name': ['A']})
        t = lambda key: 'Số TT' if key == 'col_stt' else key
        result = add_stt_column(df, t)
        assert 'Số TT' in result.columns
    
    def test_none_returns_none(self):
        """None input should return None."""
        result = add_stt_column(None)
        assert result is None
    
    def test_empty_df_returns_empty(self):
        """Empty DataFrame should be returned as-is."""
        df = pd.DataFrame()
        result = add_stt_column(df)
        assert result.empty


class TestFormatOperatorTable:
    """Tests for format_operator_table."""
    
    def test_resets_index_and_adds_stt(self):
        """Should reset index and add STT column."""
        df = pd.DataFrame(
            {'Tồn Mới': [10, 20]},
            index=['VMC', 'VFC']
        )
        df.index.name = 'Hãng khai thác'
        result = format_operator_table(df)
        assert 'STT' in result.columns
        assert result.columns[0] == 'STT'
    
    def test_none_returns_none(self):
        """None input should return None."""
        result = format_operator_table(None)
        assert result is None
    
    def test_empty_df_returns_empty(self):
        """Empty DataFrame should be returned as-is."""
        df = pd.DataFrame()
        result = format_operator_table(df)
        assert result.empty


class TestCalculateTeus:
    """Tests for calculate_teus."""
    
    def test_20ft_container_is_1_teu(self):
        """20ft container should count as 1 TEU."""
        df = pd.DataFrame({Col.ISO: ['20', '20GP', '20DC']})
        result = calculate_teus(df, Col.ISO)
        assert result == 3
    
    def test_40ft_container_is_2_teus(self):
        """40ft container should count as 2 TEUs."""
        df = pd.DataFrame({Col.ISO: ['40', '40HC', '40GP']})
        result = calculate_teus(df, Col.ISO)
        assert result == 6
    
    def test_mixed_sizes(self):
        """Mixed sizes should be calculated correctly."""
        df = pd.DataFrame({Col.ISO: ['20', '40HC', '20GP']})
        result = calculate_teus(df, Col.ISO)
        assert result == 4  # 1 + 2 + 1
    
    def test_no_size_column_uses_default_factor(self):
        """Without size column, should use DEFAULT_TEU_FACTOR."""
        df = pd.DataFrame({'Name': ['A', 'B']})
        result = calculate_teus(df, 'NonExistentCol')
        assert result == int(2 * DEFAULT_TEU_FACTOR)
    
    def test_none_returns_zero(self):
        """None input should return 0."""
        assert calculate_teus(None) == 0
    
    def test_empty_df_returns_zero(self):
        """Empty DataFrame should return 0."""
        assert calculate_teus(pd.DataFrame()) == 0


class TestAddTeusToSummary:
    """Tests for add_teus_to_summary."""
    
    def test_adds_teus_column(self):
        """Should add TEUs column based on count column."""
        df = pd.DataFrame({'Count': [10, 20]})
        result = add_teus_to_summary(df, 'Count')
        assert 'TEUs' in result.columns
        assert result['TEUs'].iloc[0] == int(10 * DEFAULT_TEU_FACTOR)
    
    def test_none_returns_none(self):
        """None input should return None."""
        result = add_teus_to_summary(None, 'Count')
        assert result is None
    
    def test_missing_count_col_no_change(self):
        """Missing count column should not add TEUs."""
        df = pd.DataFrame({'Other': [1, 2]})
        result = add_teus_to_summary(df, 'Count')
        assert 'TEUs' not in result.columns


class TestAddTeusColumnsToOperatorTable:
    """Tests for add_teus_columns_to_operator_table."""
    
    def test_adds_teus_columns_with_fallback(self):
        """Should add TEUs columns using DEFAULT_TEU_FACTOR when no raw data."""
        df = pd.DataFrame(
            {'Tồn Mới': [10, 20], 'Tồn Cũ': [8, 15]},
            index=['VMC', 'VFC']
        )
        result = add_teus_columns_to_operator_table(df, None)
        assert 'TEUs Mới' in result.columns
        assert 'TEUs Cũ' in result.columns
    
    def test_none_returns_none(self):
        """None input should return None."""
        result = add_teus_columns_to_operator_table(None, None)
        assert result is None
    
    def test_empty_df_returns_empty(self):
        """Empty DataFrame should be returned as-is."""
        df = pd.DataFrame()
        result = add_teus_columns_to_operator_table(df, None)
        assert result.empty
    
    def test_teus_columns_ordered_after_conts(self):
        """TEUs columns should appear after corresponding Conts columns."""
        df = pd.DataFrame(
            {'Tồn Cũ': [8], 'Tồn Mới': [10]},
            index=['VMC']
        )
        result = add_teus_columns_to_operator_table(df, None)
        cols = list(result.columns)
        # TEUs Cũ should come after Tồn Cũ
        if 'Tồn Cũ' in cols and 'TEUs Cũ' in cols:
            assert cols.index('TEUs Cũ') > cols.index('Tồn Cũ')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
