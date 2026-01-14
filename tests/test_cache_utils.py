# tests/test_cache_utils.py
# V5.4: Unit tests for caching module
"""Tests for utils/cache_utils.py module."""

import pytest
import time
from datetime import datetime
from pathlib import Path
from utils.cache_utils import (
    CacheManager,
    get_cache,
    cached,
    calculate_file_hash,
    get_input_files_hashes,
    is_cache_valid,
    save_cache_metadata,
    load_cache_metadata
)


class TestCacheManager:
    """Tests for CacheManager class."""
    
    def setup_method(self):
        """Reset cache before each test."""
        # Get fresh cache and clear it
        self.cache = CacheManager()
        self.cache.clear()
    
    def test_basic_set_get(self):
        """Test basic set and get operations."""
        self.cache.set("key1", "value1")
        assert self.cache.get("key1") == "value1"
    
    def test_get_nonexistent_key(self):
        """Test getting a key that doesn't exist."""
        assert self.cache.get("nonexistent") is None
    
    def test_set_with_complex_value(self):
        """Test storing complex values."""
        complex_value = {
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
            "number": 42
        }
        self.cache.set("complex", complex_value)
        result = self.cache.get("complex")
        
        assert result["list"] == [1, 2, 3]
        assert result["dict"]["nested"] == "value"
        assert result["number"] == 42
    
    def test_delete_key(self):
        """Test deleting a key."""
        self.cache.set("to_delete", "value")
        assert self.cache.get("to_delete") == "value"
        
        result = self.cache.delete("to_delete")
        assert result is True
        assert self.cache.get("to_delete") is None
    
    def test_delete_nonexistent_key(self):
        """Test deleting a key that doesn't exist."""
        result = self.cache.delete("nonexistent")
        assert result is False
    
    def test_clear_cache(self):
        """Test clearing all cache entries."""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        
        self.cache.clear()
        
        assert self.cache.get("key1") is None
        assert self.cache.get("key2") is None
    
    def test_get_keys(self):
        """Test getting all cache keys."""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        
        keys = self.cache.get_keys()
        assert "key1" in keys
        assert "key2" in keys
    
    def test_invalidate_by_pattern(self):
        """Test invalidating keys by pattern."""
        self.cache.set("user:1:name", "John")
        self.cache.set("user:1:age", 30)
        self.cache.set("user:2:name", "Jane")
        self.cache.set("other:key", "value")
        
        count = self.cache.invalidate_by_pattern("user:1")
        
        assert count == 2
        assert self.cache.get("user:1:name") is None
        assert self.cache.get("user:1:age") is None
        assert self.cache.get("user:2:name") == "Jane"
        assert self.cache.get("other:key") == "value"
    
    def test_invalidate_by_tag(self):
        """Test invalidating keys by tag."""
        self.cache.set("key1", "value1", tags=["group_a"])
        self.cache.set("key2", "value2", tags=["group_a", "group_b"])
        self.cache.set("key3", "value3", tags=["group_b"])
        
        count = self.cache.invalidate_by_tag("group_a")
        
        assert count == 2
        assert self.cache.get("key1") is None
        assert self.cache.get("key2") is None
        assert self.cache.get("key3") == "value3"
    
    def test_cache_statistics(self):
        """Test cache statistics."""
        self.cache.clear()
        
        self.cache.set("key1", "value1")
        self.cache.get("key1")  # Hit
        self.cache.get("key1")  # Hit
        self.cache.get("nonexistent")  # Miss
        
        stats = self.cache.get_stats()
        
        assert stats["size"] == 1
        assert stats["hits"] >= 2
        assert stats["misses"] >= 1
    
    def test_singleton_pattern(self):
        """Test that CacheManager is singleton."""
        cache1 = CacheManager()
        cache2 = CacheManager()
        
        cache1.set("singleton_test", "value")
        assert cache2.get("singleton_test") == "value"


class TestCacheManagerTTL:
    """Tests for TTL (Time-To-Live) functionality."""
    
    def setup_method(self):
        """Reset cache before each test."""
        self.cache = CacheManager()
        self.cache.clear()
    
    def test_ttl_not_expired(self):
        """Test value before TTL expires."""
        self.cache.set("ttl_key", "value", ttl_minutes=1)
        
        # Should still be available
        assert self.cache.get("ttl_key") == "value"
    
    def test_no_expiration(self):
        """Test value with no TTL (ttl_minutes=0)."""
        self.cache.set("no_expire", "value", ttl_minutes=0)
        
        # Should be available indefinitely
        assert self.cache.get("no_expire") == "value"


class TestCacheDecorator:
    """Tests for @cached decorator."""
    
    def setup_method(self):
        """Reset cache before each test."""
        get_cache().clear()
        self.call_count = 0
    
    def test_cached_function_basic(self):
        """Test basic cached function."""
        @cached(ttl_minutes=10, key_prefix="test")
        def expensive_function(x):
            self.call_count += 1
            return x * 2
        
        # First call - should execute function
        result1 = expensive_function(5)
        assert result1 == 10
        assert self.call_count == 1
        
        # Second call - should use cache
        result2 = expensive_function(5)
        assert result2 == 10
        assert self.call_count == 1  # Still 1, used cache
    
    def test_cached_function_different_args(self):
        """Test cached function with different arguments."""
        @cached(key_prefix="test2")
        def add(a, b):
            self.call_count += 1
            return a + b
        
        result1 = add(1, 2)
        result2 = add(1, 2)  # Same args - cached
        result3 = add(3, 4)  # Different args - not cached
        
        assert result1 == 3
        assert result2 == 3
        assert result3 == 7
        assert self.call_count == 2  # Only 2 calls (1,2 was cached)
    
    def test_cached_function_with_kwargs(self):
        """Test cached function with keyword arguments."""
        @cached(key_prefix="test3")
        def greet(name, greeting="Hello"):
            self.call_count += 1
            return f"{greeting}, {name}!"
        
        result1 = greet("Alice", greeting="Hi")
        result2 = greet("Alice", greeting="Hi")  # Cached
        result3 = greet("Alice", greeting="Hey")  # Different kwarg
        
        assert result1 == "Hi, Alice!"
        assert result2 == "Hi, Alice!"
        assert result3 == "Hey, Alice!"
        assert self.call_count == 2


class TestFileHashFunctions:
    """Tests for file hash functions."""
    
    def test_calculate_file_hash(self):
        """Test file hash calculation."""
        import tempfile
        
        # Create temp file with known content
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("test content")
            temp_path = Path(f.name)
        
        try:
            hash1 = calculate_file_hash(temp_path)
            hash2 = calculate_file_hash(temp_path)
            
            # Same file should produce same hash
            assert hash1 == hash2
            assert len(hash1) == 32  # MD5 hex length
        finally:
            temp_path.unlink()
    
    def test_calculate_file_hash_nonexistent(self):
        """Test hash calculation for non-existent file."""
        result = calculate_file_hash(Path("/nonexistent/file.txt"))
        assert result == ""
    
    def test_get_input_files_hashes(self):
        """Test getting hashes for directory."""
        import tempfile
        
        # Create temp directory with Excel files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Create test files
            (tmpdir_path / "test1.xlsx").write_bytes(b"content1")
            (tmpdir_path / "test2.xlsx").write_bytes(b"content2")
            (tmpdir_path / "other.txt").write_bytes(b"ignored")
            
            hashes = get_input_files_hashes(tmpdir_path)
            
            assert "test1.xlsx" in hashes
            assert "test2.xlsx" in hashes
            assert "other.txt" not in hashes  # Only .xlsx files
    
    def test_get_input_files_hashes_nonexistent_dir(self):
        """Test hashes for non-existent directory."""
        result = get_input_files_hashes(Path("/nonexistent/dir"))
        assert result == {}


class TestCacheMetadata:
    """Tests for cache metadata persistence."""
    
    def test_save_and_load_metadata(self):
        """Test saving and loading cache metadata."""
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            hashes = {"file1.xlsx": "abc123", "file2.xlsx": "def456"}
            save_cache_metadata(tmpdir_path, hashes)
            
            loaded = load_cache_metadata(tmpdir_path)
            
            assert loaded is not None
            assert loaded["hashes"] == hashes
            assert "timestamp" in loaded
    
    def test_load_metadata_nonexistent(self):
        """Test loading metadata when file doesn't exist."""
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = load_cache_metadata(Path(tmpdir))
            assert result is None


class TestCacheValidity:
    """Tests for cache validity checking."""
    
    def test_cache_valid_no_changes(self):
        """Test cache validity when files haven't changed."""
        import tempfile
        
        with tempfile.TemporaryDirectory() as input_dir:
            with tempfile.TemporaryDirectory() as output_dir:
                input_path = Path(input_dir)
                output_path = Path(output_dir)
                
                # Create test file
                (input_path / "test.xlsx").write_bytes(b"content")
                
                # Save initial metadata
                hashes = get_input_files_hashes(input_path)
                save_cache_metadata(output_path, hashes)
                
                # Check validity - should be valid
                assert is_cache_valid(input_path, output_path) is True
    
    def test_cache_invalid_file_changed(self):
        """Test cache validity when file has changed."""
        import tempfile
        
        with tempfile.TemporaryDirectory() as input_dir:
            with tempfile.TemporaryDirectory() as output_dir:
                input_path = Path(input_dir)
                output_path = Path(output_dir)
                
                # Create test file
                test_file = input_path / "test.xlsx"
                test_file.write_bytes(b"original content")
                
                # Save initial metadata
                hashes = get_input_files_hashes(input_path)
                save_cache_metadata(output_path, hashes)
                
                # Modify file
                test_file.write_bytes(b"modified content")
                
                # Check validity - should be invalid
                assert is_cache_valid(input_path, output_path) is False
    
    def test_cache_invalid_new_file(self):
        """Test cache validity when new file added."""
        import tempfile
        
        with tempfile.TemporaryDirectory() as input_dir:
            with tempfile.TemporaryDirectory() as output_dir:
                input_path = Path(input_dir)
                output_path = Path(output_dir)
                
                # Create initial file
                (input_path / "test1.xlsx").write_bytes(b"content1")
                
                # Save metadata
                hashes = get_input_files_hashes(input_path)
                save_cache_metadata(output_path, hashes)
                
                # Add new file
                (input_path / "test2.xlsx").write_bytes(b"content2")
                
                # Check validity - should be invalid
                assert is_cache_valid(input_path, output_path) is False
