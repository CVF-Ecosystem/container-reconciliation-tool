# tests/test_profiler.py
# V5.4: Unit tests for performance profiling utilities
"""Tests for utils/profiler.py module."""

import pytest
import time
from pathlib import Path
import tempfile
import json
from utils.profiler import (
    profile,
    timed,
    PerformanceProfiler,
    ProfileResult,
    Timer,
    benchmark,
    get_profiling_results,
    clear_profiling_results,
    get_profiling_summary,
    export_profiling_report,
    DEFAULT_SLOW_THRESHOLD_MS,
    DEFAULT_MEMORY_THRESHOLD_MB
)


class TestProfileResult:
    """Tests for ProfileResult dataclass."""
    
    def test_create_result(self):
        """Test creating a profile result."""
        from datetime import datetime
        
        result = ProfileResult(
            name="test_operation",
            start_time=datetime.now(),
            elapsed_ms=100.5
        )
        
        assert result.name == "test_operation"
        assert result.elapsed_ms == 100.5
        assert result.success is True
    
    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        from datetime import datetime
        
        result = ProfileResult(
            name="test_op",
            start_time=datetime.now(),
            end_time=datetime.now(),
            elapsed_ms=50.0,
            memory_start_mb=10.0,
            memory_end_mb=15.0,
            memory_peak_mb=20.0
        )
        
        data = result.to_dict()
        
        assert data['name'] == 'test_op'
        assert data['elapsed_ms'] == 50.0
        assert data['memory_delta_mb'] == 5.0
        assert 'elapsed_seconds' in data
    
    def test_is_slow(self):
        """Test slow operation detection."""
        from datetime import datetime
        
        fast_result = ProfileResult(
            name="fast",
            start_time=datetime.now(),
            elapsed_ms=100
        )
        slow_result = ProfileResult(
            name="slow",
            start_time=datetime.now(),
            elapsed_ms=2000
        )
        
        assert fast_result.is_slow is False
        assert slow_result.is_slow is True
    
    def test_is_memory_heavy(self):
        """Test memory-heavy operation detection."""
        from datetime import datetime
        
        light_result = ProfileResult(
            name="light",
            start_time=datetime.now(),
            memory_peak_mb=50
        )
        heavy_result = ProfileResult(
            name="heavy",
            start_time=datetime.now(),
            memory_peak_mb=200
        )
        
        assert light_result.is_memory_heavy is False
        assert heavy_result.is_memory_heavy is True


class TestPerformanceProfiler:
    """Tests for PerformanceProfiler class."""
    
    def setup_method(self):
        """Clear results before each test."""
        clear_profiling_results()
    
    def test_basic_profiling(self):
        """Test basic profiling with context manager."""
        with PerformanceProfiler("test_operation", track_memory=False) as p:
            time.sleep(0.05)  # 50ms
        
        assert p.elapsed_ms >= 45  # Allow some tolerance
        assert p.elapsed >= 0.045
        assert p.result is not None
        assert p.result.success is True
    
    def test_profiling_with_memory(self):
        """Test profiling with memory tracking."""
        with PerformanceProfiler("memory_test", track_memory=True) as p:
            # Allocate some memory
            data = [0] * 10000
            _ = data  # Use variable
        
        assert p.result.memory_peak_mb >= 0
    
    def test_profiling_failure(self):
        """Test profiling when operation fails."""
        try:
            with PerformanceProfiler("failing_op", track_memory=False) as p:
                raise ValueError("Test error")
        except ValueError:
            pass
        
        assert p.result.success is False
        assert p.result.error == "Test error"
    
    def test_profiling_stores_results(self):
        """Test that results are stored globally."""
        clear_profiling_results()
        
        with PerformanceProfiler("op1", track_memory=False):
            pass
        with PerformanceProfiler("op2", track_memory=False):
            pass
        
        results = get_profiling_results()
        assert len(results) >= 2
    
    def test_profiling_with_metadata(self):
        """Test profiling with custom metadata."""
        with PerformanceProfiler(
            "metadata_test",
            track_memory=False,
            metadata={"rows": 1000, "file": "test.xlsx"}
        ) as p:
            pass
        
        assert p.result.metadata["rows"] == 1000
        assert p.result.metadata["file"] == "test.xlsx"


class TestProfileDecorator:
    """Tests for @profile decorator."""
    
    def setup_method(self):
        """Clear results before each test."""
        clear_profiling_results()
    
    def test_simple_decorator(self):
        """Test simple @profile usage."""
        @profile
        def simple_function():
            time.sleep(0.02)
            return "done"
        
        result = simple_function()
        
        assert result == "done"
        results = get_profiling_results()
        assert any(r.name == "simple_function" for r in results)
    
    def test_decorator_with_args(self):
        """Test @profile with custom arguments."""
        @profile(name="custom_name", track_memory=False)
        def another_function():
            return 42
        
        result = another_function()
        
        assert result == 42
        results = get_profiling_results()
        assert any(r.name == "custom_name" for r in results)
    
    def test_decorator_preserves_function_info(self):
        """Test that decorator preserves function metadata."""
        @profile
        def documented_function():
            """This is the docstring."""
            pass
        
        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is the docstring."
    
    def test_decorator_with_arguments(self):
        """Test decorated function with arguments."""
        @profile
        def add_numbers(a, b):
            return a + b
        
        result = add_numbers(5, 3)
        assert result == 8


class TestTimedDecorator:
    """Tests for @timed decorator."""
    
    def test_timed_function(self):
        """Test @timed decorator."""
        @timed
        def quick_function():
            return "quick"
        
        result = quick_function()
        assert result == "quick"
    
    def test_timed_preserves_return(self):
        """Test that @timed preserves return value."""
        @timed
        def return_dict():
            return {"key": "value"}
        
        result = return_dict()
        assert result["key"] == "value"


class TestTimer:
    """Tests for Timer class."""
    
    def test_basic_timer(self):
        """Test basic timer functionality."""
        timer = Timer()
        timer.start()
        time.sleep(0.05)
        timer.stop()
        
        assert timer.elapsed_ms >= 45
        assert timer.elapsed >= 0.045
    
    def test_timer_chain(self):
        """Test timer method chaining."""
        timer = Timer().start()
        time.sleep(0.02)
        timer.stop()
        
        assert timer.elapsed_ms >= 15
    
    def test_timer_laps(self):
        """Test timer lap functionality."""
        timer = Timer()
        timer.start()
        
        time.sleep(0.02)
        timer.lap("first")
        
        time.sleep(0.02)
        timer.lap("second")
        
        timer.stop()
        
        laps = timer.laps
        assert len(laps) == 2
        assert laps[0]['name'] == 'first'
        assert laps[1]['name'] == 'second'
        assert laps[1]['elapsed_ms'] > laps[0]['elapsed_ms']
    
    def test_timer_running_elapsed(self):
        """Test elapsed time while timer is running."""
        timer = Timer().start()
        time.sleep(0.02)
        
        # Get elapsed while still running
        elapsed = timer.elapsed_ms
        assert elapsed >= 15


class TestBenchmark:
    """Tests for benchmark function."""
    
    def test_basic_benchmark(self):
        """Test basic benchmark functionality."""
        def simple_operation():
            time.sleep(0.01)
        
        result = benchmark(simple_operation, iterations=3, warmup=1)
        
        assert result['iterations'] == 3
        assert result['avg_ms'] >= 8
        assert result['min_ms'] <= result['avg_ms']
        assert result['max_ms'] >= result['avg_ms']
        assert 'std_ms' in result
    
    def test_benchmark_with_name(self):
        """Test benchmark with custom name."""
        result = benchmark(
            lambda: None,
            iterations=5,
            warmup=0,
            name="custom_bench"
        )
        
        assert result['name'] == 'custom_bench'


class TestProfilingResults:
    """Tests for global profiling results management."""
    
    def setup_method(self):
        """Clear results before each test."""
        clear_profiling_results()
    
    def test_get_results(self):
        """Test getting profiling results."""
        with PerformanceProfiler("test1", track_memory=False):
            pass
        
        results = get_profiling_results()
        assert len(results) >= 1
    
    def test_clear_results(self):
        """Test clearing profiling results."""
        with PerformanceProfiler("test", track_memory=False):
            pass
        
        clear_profiling_results()
        results = get_profiling_results()
        
        assert len(results) == 0
    
    def test_get_summary_empty(self):
        """Test summary with no results."""
        clear_profiling_results()
        summary = get_profiling_summary()
        
        assert summary['total_operations'] == 0
        assert summary['total_time_ms'] == 0
    
    def test_get_summary(self):
        """Test getting profiling summary."""
        # Create some results
        for i in range(3):
            with PerformanceProfiler(f"op_{i % 2}", track_memory=False):
                time.sleep(0.01)
        
        summary = get_profiling_summary()
        
        assert summary['total_operations'] == 3
        assert summary['total_time_ms'] > 0
        assert 'by_operation' in summary
        assert len(summary['slowest_operations']) <= 5


class TestExportReport:
    """Tests for exporting profiling reports."""
    
    def setup_method(self):
        """Clear results before each test."""
        clear_profiling_results()
    
    def test_export_report(self):
        """Test exporting profiling report to JSON."""
        # Create some results
        with PerformanceProfiler("test_export", track_memory=False):
            time.sleep(0.01)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "profile_report.json"
            
            result = export_profiling_report(output_path)
            
            assert result is True
            assert output_path.exists()
            
            # Verify content
            with open(output_path) as f:
                data = json.load(f)
            
            assert 'generated_at' in data
            assert 'summary' in data
            assert 'results' in data
    
    def test_export_creates_directory(self):
        """Test that export creates parent directory."""
        with PerformanceProfiler("test", track_memory=False):
            pass
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "dir" / "report.json"
            
            result = export_profiling_report(output_path)
            
            assert result is True
            assert output_path.exists()


class TestDefaultValues:
    """Tests for default configuration values."""
    
    def test_default_slow_threshold(self):
        """Test default slow threshold value."""
        assert DEFAULT_SLOW_THRESHOLD_MS == 1000
    
    def test_default_memory_threshold(self):
        """Test default memory threshold value."""
        assert DEFAULT_MEMORY_THRESHOLD_MB == 100
