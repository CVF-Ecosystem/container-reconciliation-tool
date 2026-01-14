# tests/test_retry_utils.py
# V5.4: Unit tests for retry mechanism
"""Tests for utils/retry_utils.py module."""

import pytest
import time
from pathlib import Path
import tempfile
from utils.retry_utils import (
    retry,
    RetryContext,
    safe_read_file,
    safe_write_file,
    safe_delete_file,
    safe_rename_file,
    wait_for_file,
    DEFAULT_MAX_RETRIES,
    DEFAULT_DELAY_SECONDS
)


class TestRetryDecorator:
    """Tests for @retry decorator."""
    
    def test_successful_execution(self):
        """Test function that succeeds on first try."""
        call_count = 0
        
        @retry(max_retries=3)
        def always_succeeds():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = always_succeeds()
        
        assert result == "success"
        assert call_count == 1
    
    def test_retry_on_failure(self):
        """Test function that fails then succeeds."""
        call_count = 0
        
        @retry(max_retries=3, delay=0.01)
        def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"
        
        result = fails_twice()
        
        assert result == "success"
        assert call_count == 3
    
    def test_max_retries_exceeded(self):
        """Test function that always fails."""
        call_count = 0
        
        @retry(max_retries=2, delay=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")
        
        with pytest.raises(ValueError):
            always_fails()
        
        assert call_count == 3  # Initial + 2 retries
    
    def test_specific_exception_types(self):
        """Test retry only for specific exception types."""
        call_count = 0
        
        @retry(max_retries=3, delay=0.01, exceptions=(IOError,))
        def raises_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retried")
        
        with pytest.raises(ValueError):
            raises_value_error()
        
        # Should only be called once since ValueError is not in exceptions
        assert call_count == 1
    
    def test_multiple_exception_types(self):
        """Test retry for multiple exception types."""
        call_count = 0
        
        @retry(max_retries=2, delay=0.01, exceptions=(IOError, PermissionError))
        def raises_io_error():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise IOError("Temp error")
            return "success"
        
        result = raises_io_error()
        assert result == "success"
        assert call_count == 3
    
    def test_on_retry_callback(self):
        """Test on_retry callback is called."""
        call_count = 0
        callback_calls = []
        
        def on_retry_callback(exc, attempt):
            callback_calls.append((str(exc), attempt))
        
        @retry(max_retries=2, delay=0.01, on_retry=on_retry_callback)
        def fails_then_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"Attempt {call_count}")
            return "success"
        
        result = fails_then_succeeds()
        
        assert result == "success"
        assert len(callback_calls) == 2
        assert callback_calls[0][1] == 1
        assert callback_calls[1][1] == 2
    
    def test_no_reraise_option(self):
        """Test reraise=False option."""
        @retry(max_retries=1, delay=0.01, reraise=False)
        def always_fails():
            raise ValueError("Error")
        
        result = always_fails()
        assert result is None  # Returns None instead of raising
    
    def test_exponential_backoff(self):
        """Test that delay increases with backoff."""
        start_times = []
        
        @retry(max_retries=2, delay=0.05, backoff=2.0)
        def track_timing():
            start_times.append(time.time())
            if len(start_times) < 3:
                raise ValueError("Fail")
            return "success"
        
        track_timing()
        
        # Check delays increased
        delay1 = start_times[1] - start_times[0]
        delay2 = start_times[2] - start_times[1]
        
        # Second delay should be roughly double the first
        assert delay2 > delay1 * 1.5  # Allow some tolerance


class TestRetryContext:
    """Tests for RetryContext manager."""
    
    def test_successful_with_context(self):
        """Test successful operation with context manager."""
        with RetryContext(max_retries=3) as ctx:
            while ctx.should_retry():
                try:
                    result = "success"
                    break
                except Exception as e:
                    ctx.record_failure(e)
        
        assert result == "success"
        assert ctx.attempt == 0
    
    def test_retry_with_context(self):
        """Test retry with context manager."""
        attempts = 0
        
        with RetryContext(max_retries=3, delay=0.01) as ctx:
            while ctx.should_retry():
                try:
                    attempts += 1
                    if attempts < 3:
                        raise ValueError("Temp error")
                    result = "success"
                    break
                except ValueError as e:
                    ctx.record_failure(e)
        
        assert result == "success"
        assert attempts == 3
    
    def test_all_retries_failed(self):
        """Test when all retries fail."""
        with RetryContext(max_retries=2, delay=0.01) as ctx:
            while ctx.should_retry():
                try:
                    raise ValueError("Always fails")
                except ValueError as e:
                    ctx.record_failure(e)
        
        assert ctx.attempt > ctx.max_retries
        assert ctx.last_exception is not None
        
        with pytest.raises(ValueError):
            ctx.raise_if_failed()
    
    def test_context_exceptions_list(self):
        """Test that all exceptions are recorded."""
        with RetryContext(max_retries=2, delay=0.01) as ctx:
            while ctx.should_retry():
                try:
                    raise ValueError(f"Error {ctx.attempt}")
                except ValueError as e:
                    ctx.record_failure(e)
        
        assert len(ctx.exceptions) == 3  # Initial + 2 retries


class TestSafeFileOperations:
    """Tests for safe file operation functions."""
    
    def test_safe_write_and_read_file(self):
        """Test safe write and read operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            
            # Write
            result = safe_write_file(file_path, "Hello, World!")
            assert result is True
            assert file_path.exists()
            
            # Read
            content = safe_read_file(file_path)
            assert content == "Hello, World!"
    
    def test_safe_write_creates_directory(self):
        """Test that safe_write creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "nested" / "dir" / "test.txt"
            
            result = safe_write_file(file_path, "content")
            
            assert result is True
            assert file_path.exists()
    
    def test_safe_delete_file(self):
        """Test safe file deletion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "to_delete.txt"
            file_path.write_text("delete me")
            
            result = safe_delete_file(file_path)
            
            assert result is True
            assert not file_path.exists()
    
    def test_safe_delete_nonexistent(self):
        """Test deleting non-existent file."""
        result = safe_delete_file(Path("/nonexistent/file.txt"))
        assert result is True  # Should succeed silently
    
    def test_safe_rename_file(self):
        """Test safe file rename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_path = Path(tmpdir) / "original.txt"
            dst_path = Path(tmpdir) / "renamed.txt"
            
            src_path.write_text("content")
            
            result = safe_rename_file(src_path, dst_path)
            
            assert result is True
            assert not src_path.exists()
            assert dst_path.exists()
            assert dst_path.read_text() == "content"
    
    def test_safe_rename_creates_directory(self):
        """Test that safe_rename creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_path = Path(tmpdir) / "original.txt"
            dst_path = Path(tmpdir) / "nested" / "dir" / "renamed.txt"
            
            src_path.write_text("content")
            
            result = safe_rename_file(src_path, dst_path)
            
            assert result is True
            assert dst_path.exists()


class TestWaitForFile:
    """Tests for file waiting functions."""
    
    def test_wait_for_existing_file(self):
        """Test waiting for a file that already exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "exists.txt"
            file_path.write_text("content")
            
            result = wait_for_file(file_path, timeout_seconds=1)
            
            assert result is True
    
    def test_wait_for_nonexistent_file_timeout(self):
        """Test timeout when file doesn't exist."""
        result = wait_for_file(
            Path("/nonexistent/file.txt"),
            timeout_seconds=0.1,
            check_interval=0.05
        )
        
        assert result is False


class TestDefaultValues:
    """Tests for default configuration values."""
    
    def test_default_max_retries(self):
        """Test default max retries value."""
        assert DEFAULT_MAX_RETRIES == 3
    
    def test_default_delay(self):
        """Test default delay value."""
        assert DEFAULT_DELAY_SECONDS == 1.0
