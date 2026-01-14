# File: tests/test_duplicate_checker.py
# Unit tests for duplicate_checker module
# Version: V4.3

import pytest
import pandas as pd
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Col
from core.duplicate_checker import (
    check_duplicate_containers,
    check_duplicates_with_position_change,
    check_duplicates_with_time_difference,
    check_th3_missing_transaction_line,
    check_th4_gateout_but_still_in_inventory,
    run_all_duplicate_checks,
    generate_duplicate_summary
)


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def sample_df_with_duplicates():
    """DataFrame with duplicate containers."""
    return pd.DataFrame({
        Col.CONTAINER: ['CONT001', 'CONT001', 'CONT002', 'CONT003', 'CONT003'],
        Col.OPERATOR: ['MSC', 'MSC', 'OOCL', 'CMA', 'CMA'],
        Col.LOCATION: ['A-01-01', 'A-01-02', 'B-02-01', 'C-03-01', 'C-03-01']
    })


@pytest.fixture
def sample_df_no_duplicates():
    """DataFrame without any duplicates."""
    return pd.DataFrame({
        Col.CONTAINER: ['CONT001', 'CONT002', 'CONT003'],
        Col.OPERATOR: ['MSC', 'OOCL', 'CMA']
    })


@pytest.fixture
def empty_df():
    """Empty DataFrame."""
    return pd.DataFrame()


@pytest.fixture
def sample_df_with_time():
    """DataFrame with time differences."""
    return pd.DataFrame({
        Col.CONTAINER: ['CONT001', 'CONT001', 'CONT002'],
        Col.TRANSACTION_TIME: pd.to_datetime([
            '2024-12-24 08:00:00',
            '2024-12-24 10:30:00',  # 2.5 hours difference
            '2024-12-24 09:00:00'
        ]),
        Col.OPERATOR: ['MSC', 'MSC', 'OOCL']
    })


@pytest.fixture
def sample_file_dfs():
    """Sample file_dfs dictionary for integration tests."""
    return {
        'gate_in': pd.DataFrame({
            Col.CONTAINER: ['CONT001', 'CONT002', 'CONT003'],
            Col.XE_VAO_CONG: pd.to_datetime(['2024-12-24 08:00', None, '2024-12-24 09:00']),
            Col.CONT_VAO_BAI: pd.to_datetime(['2024-12-24 08:30', '2024-12-24 08:45', None])
        }),
        'gate_out': pd.DataFrame({
            Col.CONTAINER: ['CONT001', 'CONT004'],  # CONT004 has no gate_in
            Col.CONT_RA_BAI: pd.to_datetime(['2024-12-24 15:00', '2024-12-24 16:00']),
            Col.XE_RA_CONG: pd.to_datetime(['2024-12-24 15:30', '2024-12-24 16:30'])
        }),
        'ton_moi': pd.DataFrame({
            Col.CONTAINER: ['CONT001', 'CONT002', 'CONT003'],  # CONT001 should not be here
            Col.OPERATOR: ['MSC', 'OOCL', 'CMA']
        })
    }


# ============================================================================
# TEST: check_duplicate_containers
# ============================================================================

class TestCheckDuplicateContainers:
    """Tests for check_duplicate_containers function."""
    
    def test_finds_duplicates(self, sample_df_with_duplicates):
        """Should correctly identify duplicate containers."""
        result = check_duplicate_containers(sample_df_with_duplicates, "TEST")
        
        assert not result.empty
        assert 'CONT001' in result[Col.CONTAINER].values
        assert 'CONT003' in result[Col.CONTAINER].values
        assert 'SoLanXuatHien' in result.columns
        assert 'LoaiBatThuong' in result.columns
    
    def test_no_duplicates(self, sample_df_no_duplicates):
        """Should return empty DataFrame when no duplicates exist."""
        result = check_duplicate_containers(sample_df_no_duplicates, "TEST")
        
        assert result.empty
    
    def test_empty_dataframe(self, empty_df):
        """Should handle empty DataFrame gracefully."""
        result = check_duplicate_containers(empty_df, "TEST")
        
        assert result.empty
    
    def test_missing_container_column(self):
        """Should handle DataFrame without container column."""
        df = pd.DataFrame({'OtherColumn': [1, 2, 3]})
        result = check_duplicate_containers(df, "TEST")
        
        assert result.empty


# ============================================================================
# TEST: check_duplicates_with_position_change
# ============================================================================

class TestCheckDuplicatesWithPositionChange:
    """Tests for position change detection."""
    
    def test_detects_position_changes(self, sample_df_with_duplicates):
        """Should detect containers with different positions."""
        result = check_duplicates_with_position_change(sample_df_with_duplicates, "TEST")
        
        # CONT001 has different positions (A-01-01, A-01-02)
        assert not result.empty
        assert 'CONT001' in result[Col.CONTAINER].values
        assert 'CacViTriKhacNhau' in result.columns
    
    def test_same_position_duplicates(self):
        """Should not flag duplicates with same position."""
        df = pd.DataFrame({
            Col.CONTAINER: ['CONT001', 'CONT001'],
            Col.LOCATION: ['A-01-01', 'A-01-01']  # Same position
        })
        result = check_duplicates_with_position_change(df, "TEST")
        
        assert result.empty
    
    def test_empty_dataframe(self, empty_df):
        """Should handle empty DataFrame."""
        result = check_duplicates_with_position_change(empty_df, "TEST")
        assert result.empty


# ============================================================================
# TEST: check_duplicates_with_time_difference
# ============================================================================

class TestCheckDuplicatesWithTimeDifference:
    """Tests for time difference detection."""
    
    def test_detects_large_time_difference(self, sample_df_with_time):
        """Should detect duplicates with time difference > threshold."""
        result = check_duplicates_with_time_difference(
            sample_df_with_time, 
            time_threshold_minutes=60, 
            source_name="TEST"
        )
        
        # CONT001 has 2.5 hour difference
        assert not result.empty
        assert 'CONT001' in result[Col.CONTAINER].values
        assert 'KhoangThoiGian' in result.columns
    
    def test_small_time_difference(self):
        """Should not flag duplicates within threshold."""
        df = pd.DataFrame({
            Col.CONTAINER: ['CONT001', 'CONT001'],
            Col.TRANSACTION_TIME: pd.to_datetime([
                '2024-12-24 08:00:00',
                '2024-12-24 08:30:00'  # Only 30 min difference
            ])
        })
        result = check_duplicates_with_time_difference(df, 60, "TEST")
        
        assert result.empty


# ============================================================================
# TEST: B14 Checklist Functions
# ============================================================================

class TestTH3MissingTransactionLine:
    """Tests for TH3 - Missing transaction line detection."""
    
    def test_detects_gate_out_without_gate_in(self, sample_file_dfs):
        """Should detect containers with gate out but no gate in."""
        result = check_th3_missing_transaction_line(sample_file_dfs)
        
        assert not result.empty
        assert 'CONT004' in result[Col.CONTAINER].values
        assert 'LoaiBatThuong' in result.columns
    
    def test_empty_files(self):
        """Should handle empty file_dfs."""
        result = check_th3_missing_transaction_line({})
        assert result.empty


class TestTH4GateoutStillInInventory:
    """Tests for TH4 - Gate out but still in inventory."""
    
    def test_detects_still_in_inventory(self, sample_file_dfs):
        """Should detect containers that are gated out but still in ton_moi."""
        result = check_th4_gateout_but_still_in_inventory(sample_file_dfs)
        
        # CONT001 is gated out but still in ton_moi
        assert not result.empty
        assert 'CONT001' in result[Col.CONTAINER].values


# ============================================================================
# TEST: Integration Tests
# ============================================================================

class TestRunAllDuplicateChecks:
    """Integration tests for run_all_duplicate_checks."""
    
    def test_runs_all_checks(self, sample_file_dfs):
        """Should run all checks and return results dictionary."""
        results = run_all_duplicate_checks(sample_file_dfs)
        
        assert isinstance(results, dict)
        assert 'TH3_missing_gate_record' in results
        assert 'TH4_gateout_still_in_inventory' in results


class TestGenerateDuplicateSummary:
    """Tests for summary generation."""
    
    def test_generates_summary(self, sample_file_dfs):
        """Should generate summary DataFrame from check results."""
        check_results = run_all_duplicate_checks(sample_file_dfs)
        summary = generate_duplicate_summary(check_results)
        
        assert isinstance(summary, pd.DataFrame)
        assert 'MaKiemTra' in summary.columns
        assert 'SoContainerBatThuong' in summary.columns
    
    def test_empty_results(self):
        """Should handle empty results."""
        summary = generate_duplicate_summary({})
        
        assert not summary.empty
        assert summary['SoContainerBatThuong'].iloc[0] == 0


# ============================================================================
# RUNNING TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
