# tests/conftest.py
# Configure pytest path and shared fixtures for all tests

import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime

import pytest
import pandas as pd

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config import Col


# ============ SHARED FIXTURES ============

@pytest.fixture
def sample_ton_cu():
    """Baseline inventory (TON CU) DataFrame for testing."""
    return pd.DataFrame({
        Col.CONTAINER: ['CONT001', 'CONT002', 'CONT003'],
        Col.OPERATOR: ['VMC', 'VFC', 'VMC'],
        Col.FE: ['F', 'E', 'F'],
        Col.ISO: ['20', '40HC', '20'],
        Col.LOCATION: ['A-01-01', 'B-02-03', 'C-03-05'],
        Col.TRANSACTION_TIME: [datetime(2026, 1, 11, 8, 0)] * 3,
        Col.MOVE_TYPE: ['IN', 'IN', 'IN'],
        Col.SOURCE_KEY: ['ton_cu', 'ton_cu', 'ton_cu'],
        Col.SOURCE_FILE: ['TON_CU.xlsx'] * 3,
    })


@pytest.fixture
def sample_ton_moi():
    """Current inventory (TON MOI) DataFrame for testing.
    
    CONT002 đã rời bãi, CONT004 mới vào.
    """
    return pd.DataFrame({
        Col.CONTAINER: ['CONT001', 'CONT003', 'CONT004'],
        Col.OPERATOR: ['VMC', 'VMC', 'VFC'],
        Col.FE: ['F', 'F', 'E'],
        Col.ISO: ['20', '20', '40HC'],
        Col.LOCATION: ['A-01-01', 'C-03-05', 'D-04-02'],
        Col.TRANSACTION_TIME: [datetime(2026, 1, 12, 15, 0)] * 3,
        Col.MOVE_TYPE: ['IN', 'IN', 'IN'],
        Col.SOURCE_KEY: ['ton_moi', 'ton_moi', 'ton_moi'],
        Col.SOURCE_FILE: ['TON_MOI.xlsx'] * 3,
    })


@pytest.fixture
def sample_gate_in():
    """Gate IN transactions DataFrame for testing."""
    return pd.DataFrame({
        Col.CONTAINER: ['CONT004'],
        Col.OPERATOR: ['VFC'],
        Col.FE: ['E'],
        Col.ISO: ['40HC'],
        Col.TRANSACTION_TIME: [datetime(2026, 1, 12, 10, 30)],
        Col.MOVE_TYPE: ['IN'],
        Col.SOURCE_KEY: ['gate_in'],
        Col.SOURCE_FILE: ['GATE_IN.xlsx'],
        Col.PHUONG_AN: ['Trả rỗng'],
    })


@pytest.fixture
def sample_gate_out():
    """Gate OUT transactions DataFrame for testing."""
    return pd.DataFrame({
        Col.CONTAINER: ['CONT002'],
        Col.OPERATOR: ['VFC'],
        Col.FE: ['E'],
        Col.ISO: ['40HC'],
        Col.TRANSACTION_TIME: [datetime(2026, 1, 12, 14, 15)],
        Col.MOVE_TYPE: ['OUT'],
        Col.SOURCE_KEY: ['gate_out'],
        Col.SOURCE_FILE: ['GATE_OUT.xlsx'],
        Col.PHUONG_AN: ['Lấy nguyên'],
    })


@pytest.fixture
def sample_file_dfs(sample_ton_cu, sample_ton_moi, sample_gate_in, sample_gate_out):
    """Complete file_dfs dictionary for reconciliation testing."""
    return {
        'ton_cu': sample_ton_cu,
        'ton_moi': sample_ton_moi,
        'gate_in': sample_gate_in,
        'gate_out': sample_gate_out,
    }


@pytest.fixture
def temp_output_dir():
    """Temporary directory for output files in tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_input_dir():
    """Temporary directory for input files in tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def run_time():
    """Standard run time for tests."""
    return datetime(2026, 1, 12, 15, 0, 0)


@pytest.fixture
def empty_dataframe():
    """Empty DataFrame for edge case testing."""
    return pd.DataFrame()


@pytest.fixture
def sample_summary_df():
    """Sample summary DataFrame for testing."""
    return pd.DataFrame({
        'Hang muc': [
            'Ton cu (baseline)',
            'Ton moi (thoi diem kiem tra)',
            'Tong giao dich NHAP',
            'Tong giao dich XUAT',
            'Khop hoan toan',
        ],
        'So luong': [3, 3, 1, 1, 2]
    })
