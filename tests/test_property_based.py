# File: tests/test_property_based.py — @2026 v1.0
"""
Property-based tests using Hypothesis.

Tests that should hold for ANY valid input, not just specific examples.
Helps discover edge cases that manual tests might miss.

Requires: pip install hypothesis
"""

import pytest
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from hypothesis import given, settings, assume, HealthCheck
    from hypothesis import strategies as st
    from hypothesis.extra.pandas import column, data_frames, range_indexes
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not HYPOTHESIS_AVAILABLE,
    reason="Hypothesis not installed. Run: pip install hypothesis"
)

from config import Col, DEFAULT_TEU_FACTOR
from utils.display_helpers import calculate_teus, prepare_df_for_display, add_stt_column
from utils.validators import validate_container_id
from utils.exceptions import InvalidContainerError


# ============ CONTAINER ID VALIDATION ============

@given(st.text(min_size=0, max_size=20))
@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
def test_validate_container_id_never_crashes(container_id):
    """validate_container_id should never crash, only raise InvalidContainerError."""
    try:
        result = validate_container_id(container_id, strict=False)
        # If it succeeds, result should be uppercase string
        assert isinstance(result, str)
        assert result == result.upper()
    except InvalidContainerError:
        pass  # Expected for invalid IDs
    except Exception as e:
        pytest.fail(f"Unexpected exception for input '{container_id}': {type(e).__name__}: {e}")


@given(st.from_regex(r'[A-Z]{4}[0-9]{7}', fullmatch=True))
@settings(max_examples=100)
def test_valid_container_format_always_passes(container_id):
    """Container IDs matching ISO format should always pass non-strict validation."""
    result = validate_container_id(container_id, strict=False)
    assert result == container_id


# ============ CALCULATE TEUS ============

@given(st.lists(
    st.sampled_from(['20', '20GP', '20DC', '40', '40HC', '40GP', '45', '45HC', '22G1', '42G1']),
    min_size=0,
    max_size=100
))
@settings(max_examples=200)
def test_calculate_teus_always_non_negative(iso_sizes):
    """TEU calculation should always return non-negative integer."""
    df = pd.DataFrame({Col.ISO: iso_sizes})
    result = calculate_teus(df, Col.ISO)
    assert isinstance(result, int)
    assert result >= 0


@given(st.lists(
    st.sampled_from(['20', '20GP', '40HC']),
    min_size=1,
    max_size=50
))
@settings(max_examples=100)
def test_calculate_teus_monotonic(iso_sizes):
    """Adding more containers should never decrease TEU count."""
    df1 = pd.DataFrame({Col.ISO: iso_sizes})
    df2 = pd.DataFrame({Col.ISO: iso_sizes + ['20']})  # Add one 20ft
    
    teus1 = calculate_teus(df1, Col.ISO)
    teus2 = calculate_teus(df2, Col.ISO)
    
    assert teus2 >= teus1


@given(st.integers(min_value=0, max_value=1000))
@settings(max_examples=100)
def test_calculate_teus_empty_uses_factor(n_rows):
    """Without size column, TEUs = n_rows * DEFAULT_TEU_FACTOR."""
    df = pd.DataFrame({'Name': ['X'] * n_rows})
    result = calculate_teus(df, 'NonExistentCol')
    expected = int(n_rows * DEFAULT_TEU_FACTOR)
    assert result == expected


# ============ PREPARE DF FOR DISPLAY ============

@given(data_frames(
    columns=[
        column('text_col', dtype=str),
        column('int_col', dtype=int),
    ],
    index=range_indexes(min_size=0, max_size=50)
))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_prepare_df_for_display_never_crashes(df):
    """prepare_df_for_display should handle any DataFrame without crashing."""
    result = prepare_df_for_display(df)
    assert isinstance(result, pd.DataFrame)


@given(data_frames(
    columns=[column('col', dtype=str)],
    index=range_indexes(min_size=1, max_size=20)
))
@settings(max_examples=50)
def test_prepare_df_preserves_row_count(df):
    """prepare_df_for_display should not change row count."""
    result = prepare_df_for_display(df)
    assert len(result) == len(df)


# ============ ADD STT COLUMN ============

@given(st.integers(min_value=1, max_value=100))
@settings(max_examples=50)
def test_add_stt_column_sequential(n_rows):
    """STT column should always be sequential 1..n."""
    df = pd.DataFrame({'Name': ['X'] * n_rows})
    result = add_stt_column(df)
    assert list(result['STT']) == list(range(1, n_rows + 1))


# ============ RECONCILIATION PROPERTIES ============

@given(
    st.lists(st.text(min_size=11, max_size=11, alphabet=st.characters(whitelist_categories=('Lu', 'Nd'))), min_size=0, max_size=50),
    st.lists(st.text(min_size=11, max_size=11, alphabet=st.characters(whitelist_categories=('Lu', 'Nd'))), min_size=0, max_size=50),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_set_operations_consistency(set_a, set_b):
    """
    Test that set operations used in reconciliation are consistent.
    
    Property: |A ∩ B| + |A - B| = |A|
    """
    set_a = set(set_a)
    set_b = set(set_b)
    
    intersection = set_a.intersection(set_b)
    only_in_a = set_a.difference(set_b)
    
    # Fundamental set property
    assert len(intersection) + len(only_in_a) == len(set_a)
    
    # No overlap between intersection and difference
    assert intersection.isdisjoint(only_in_a)


# ============ CACHE UTILS PROPERTIES ============

@given(st.text(min_size=1, max_size=100))
@settings(max_examples=100)
def test_cache_get_set_roundtrip(key):
    """Cache set then get should return same value."""
    from utils.cache_utils import CacheManager
    
    cache = CacheManager()
    cache.clear()
    
    value = f"test_value_{key}"
    cache.set(key, value, ttl_minutes=0)  # No expiration
    
    result = cache.get(key)
    assert result == value


@given(st.integers(min_value=1, max_value=50))
@settings(max_examples=20)
def test_cache_max_size_respected(max_size):
    """Cache should not exceed max_size entries."""
    from utils.cache_utils import CacheManager
    
    # Create fresh cache with specific max_size
    cache = CacheManager.__new__(CacheManager)
    cache._cache = {}
    cache._default_ttl = __import__('datetime').timedelta(minutes=30)
    cache._max_size = max_size
    cache._hits = 0
    cache._misses = 0
    cache._lock = __import__('threading').Lock()
    cache._initialized = True
    
    # Add more items than max_size
    for i in range(max_size + 10):
        cache.set(f"key_{i}", f"value_{i}")
    
    assert len(cache._cache) <= max_size
