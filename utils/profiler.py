# File: utils/profiler.py
# @2026 v1.0: Performance profiling utilities
"""
Performance Profiling Module for Container Inventory Reconciliation Tool.

Provides utilities for:
- Function execution timing
- Memory usage tracking
- Bottleneck identification
- Performance reports generation

Example:
    from utils.profiler import profile, PerformanceProfiler
    
    @profile
    def slow_function():
        # Do something
        pass
    
    # Or use context manager
    with PerformanceProfiler("data_loading") as p:
        load_data()
    print(f"Took {p.elapsed:.2f}s")
"""

import time
import logging
import functools
import tracemalloc
from typing import Callable, Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import threading
import json


# ============ CONSTANTS ============

DEFAULT_SLOW_THRESHOLD_MS = 1000  # 1 second
DEFAULT_MEMORY_THRESHOLD_MB = 100  # 100 MB


# ============ DATA CLASSES ============

@dataclass
class ProfileResult:
    """
    Result of a single profiling operation.
    
    Attributes:
        name: Name/identifier of the profiled operation
        start_time: When the operation started
        end_time: When the operation ended
        elapsed_ms: Duration in milliseconds
        memory_start_mb: Memory usage at start (MB)
        memory_end_mb: Memory usage at end (MB)
        memory_peak_mb: Peak memory during operation (MB)
        success: Whether operation completed successfully
        error: Error message if failed
        metadata: Additional context information
    """
    name: str
    start_time: datetime
    end_time: datetime = None
    elapsed_ms: float = 0.0
    memory_start_mb: float = 0.0
    memory_end_mb: float = 0.0
    memory_peak_mb: float = 0.0
    success: bool = True
    error: str = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'elapsed_ms': round(self.elapsed_ms, 2),
            'elapsed_seconds': round(self.elapsed_ms / 1000, 3),
            'memory_start_mb': round(self.memory_start_mb, 2),
            'memory_end_mb': round(self.memory_end_mb, 2),
            'memory_peak_mb': round(self.memory_peak_mb, 2),
            'memory_delta_mb': round(self.memory_end_mb - self.memory_start_mb, 2),
            'success': self.success,
            'error': self.error,
            'metadata': self.metadata
        }
    
    @property
    def is_slow(self) -> bool:
        """Check if operation exceeded slow threshold."""
        return self.elapsed_ms > DEFAULT_SLOW_THRESHOLD_MS
    
    @property
    def is_memory_heavy(self) -> bool:
        """Check if operation used too much memory."""
        return self.memory_peak_mb > DEFAULT_MEMORY_THRESHOLD_MB


# ============ PROFILER CLASS ============

class PerformanceProfiler:
    """
    Context manager for profiling code blocks.
    
    Tracks execution time and memory usage for a named operation.
    Can be used as context manager or decorator.
    
    Example:
        # As context manager
        with PerformanceProfiler("load_excel") as p:
            df = pd.read_excel("data.xlsx")
        print(f"Loaded in {p.elapsed_ms:.0f}ms")
        
        # As decorator
        @PerformanceProfiler.as_decorator("process_data")
        def process():
            pass
    
    Attributes:
        name: Identifier for this profiling session
        track_memory: Whether to track memory usage
        log_result: Whether to log the result automatically
        slow_threshold_ms: Threshold for slow operation warning
    """
    
    def __init__(
        self,
        name: str,
        track_memory: bool = True,
        log_result: bool = True,
        slow_threshold_ms: float = DEFAULT_SLOW_THRESHOLD_MS,
        metadata: Dict[str, Any] = None
    ):
        """
        Initialize profiler.
        
        Args:
            name: Name for this profiling operation
            track_memory: Whether to track memory (adds overhead)
            log_result: Whether to log result after completion
            slow_threshold_ms: Threshold for slow operation warning
            metadata: Additional context to include in result
        """
        self.name = name
        self.track_memory = track_memory
        self.log_result = log_result
        self.slow_threshold_ms = slow_threshold_ms
        self.metadata = metadata or {}
        
        self._start_time: float = 0
        self._start_datetime: datetime = None
        self._memory_start: int = 0
        self._result: ProfileResult = None
    
    def __enter__(self) -> 'PerformanceProfiler':
        """Start profiling when entering context."""
        self._start_datetime = datetime.now()
        self._start_time = time.perf_counter()
        
        if self.track_memory:
            tracemalloc.start()
            self._memory_start = tracemalloc.get_traced_memory()[0]
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Stop profiling when exiting context."""
        end_time = time.perf_counter()
        end_datetime = datetime.now()
        elapsed_ms = (end_time - self._start_time) * 1000
        
        # Get memory stats
        memory_end = 0
        memory_peak = 0
        if self.track_memory:
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            memory_end = current
            memory_peak = peak
        
        # Create result
        self._result = ProfileResult(
            name=self.name,
            start_time=self._start_datetime,
            end_time=end_datetime,
            elapsed_ms=elapsed_ms,
            memory_start_mb=self._memory_start / (1024 * 1024),
            memory_end_mb=memory_end / (1024 * 1024),
            memory_peak_mb=memory_peak / (1024 * 1024),
            success=exc_type is None,
            error=str(exc_val) if exc_val else None,
            metadata=self.metadata
        )
        
        # Log result
        if self.log_result:
            self._log_result()
        
        # Store in global results
        _profiler_results.append(self._result)
        
        return False  # Don't suppress exceptions
    
    def _log_result(self) -> None:
        """Log the profiling result."""
        r = self._result
        
        if r.is_slow:
            logging.warning(
                f"[Profile] SLOW: {r.name} took {r.elapsed_ms:.0f}ms "
                f"(threshold: {self.slow_threshold_ms}ms)"
            )
        else:
            logging.debug(
                f"[Profile] {r.name}: {r.elapsed_ms:.1f}ms"
            )
        
        if self.track_memory and r.is_memory_heavy:
            logging.warning(
                f"[Profile] HIGH MEMORY: {r.name} used {r.memory_peak_mb:.1f}MB peak"
            )
    
    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return self._result.elapsed_ms if self._result else 0
    
    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        return self.elapsed_ms / 1000
    
    @property
    def result(self) -> ProfileResult:
        """Get the profiling result."""
        return self._result
    
    @classmethod
    def as_decorator(
        cls,
        name: str = None,
        track_memory: bool = True,
        slow_threshold_ms: float = DEFAULT_SLOW_THRESHOLD_MS
    ):
        """
        Use profiler as a decorator.
        
        Args:
            name: Operation name (defaults to function name)
            track_memory: Whether to track memory
            slow_threshold_ms: Slow operation threshold
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                op_name = name or func.__name__
                with cls(op_name, track_memory, slow_threshold_ms=slow_threshold_ms):
                    return func(*args, **kwargs)
            return wrapper
        return decorator


# ============ SIMPLE DECORATOR ============

def profile(
    func: Callable = None,
    *,
    name: str = None,
    track_memory: bool = False,
    slow_threshold_ms: float = DEFAULT_SLOW_THRESHOLD_MS
):
    """
    Simple decorator for profiling functions.
    
    Can be used with or without arguments:
        
        @profile
        def my_function():
            pass
            
        @profile(name="custom_name", track_memory=True)
        def another_function():
            pass
    
    Args:
        func: Function to profile (when used without arguments)
        name: Custom name for the operation
        track_memory: Whether to track memory usage
        slow_threshold_ms: Threshold for slow operation warning
        
    Returns:
        Decorated function or decorator
    """
    def decorator(fn: Callable):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            op_name = name or fn.__name__
            with PerformanceProfiler(
                op_name,
                track_memory=track_memory,
                slow_threshold_ms=slow_threshold_ms
            ):
                return fn(*args, **kwargs)
        return wrapper
    
    if func is not None:
        return decorator(func)
    return decorator


def timed(func: Callable) -> Callable:
    """
    Simple timing decorator without memory tracking.
    
    Lightweight alternative to @profile for quick measurements.
    
    Example:
        @timed
        def quick_operation():
            pass
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            logging.debug(f"[Timed] {func.__name__}: {elapsed:.1f}ms")
    return wrapper


# ============ GLOBAL RESULTS STORAGE ============

_profiler_results: List[ProfileResult] = []
_profiler_lock = threading.Lock()


def get_profiling_results() -> List[ProfileResult]:
    """
    Get all profiling results collected so far.
    
    Returns:
        List of ProfileResult objects
    """
    with _profiler_lock:
        return list(_profiler_results)


def clear_profiling_results() -> None:
    """Clear all stored profiling results."""
    with _profiler_lock:
        _profiler_results.clear()


def get_profiling_summary() -> Dict[str, Any]:
    """
    Get summary statistics of all profiling results.
    
    Returns:
        Dictionary with summary statistics including:
        - total_operations: Total number of profiled operations
        - total_time_ms: Total time across all operations
        - slowest_operations: Top 5 slowest operations
        - memory_heavy_operations: Operations using most memory
        - by_operation: Statistics grouped by operation name
    """
    results = get_profiling_results()
    
    if not results:
        return {
            'total_operations': 0,
            'total_time_ms': 0,
            'slowest_operations': [],
            'memory_heavy_operations': [],
            'by_operation': {}
        }
    
    # Group by operation name
    by_operation: Dict[str, List[ProfileResult]] = {}
    for r in results:
        if r.name not in by_operation:
            by_operation[r.name] = []
        by_operation[r.name].append(r)
    
    # Calculate statistics per operation
    operation_stats = {}
    for name, op_results in by_operation.items():
        times = [r.elapsed_ms for r in op_results]
        operation_stats[name] = {
            'count': len(op_results),
            'total_ms': sum(times),
            'avg_ms': sum(times) / len(times),
            'min_ms': min(times),
            'max_ms': max(times),
            'success_rate': sum(1 for r in op_results if r.success) / len(op_results)
        }
    
    # Find slowest operations
    slowest = sorted(results, key=lambda r: r.elapsed_ms, reverse=True)[:5]
    
    # Find memory-heavy operations
    memory_heavy = sorted(
        [r for r in results if r.memory_peak_mb > 0],
        key=lambda r: r.memory_peak_mb,
        reverse=True
    )[:5]
    
    return {
        'total_operations': len(results),
        'total_time_ms': sum(r.elapsed_ms for r in results),
        'slowest_operations': [r.to_dict() for r in slowest],
        'memory_heavy_operations': [r.to_dict() for r in memory_heavy],
        'by_operation': operation_stats
    }


def export_profiling_report(output_path: Path) -> bool:
    """
    Export profiling results to JSON file.
    
    Args:
        output_path: Path for output JSON file
        
    Returns:
        True if successful
    """
    try:
        results = get_profiling_results()
        summary = get_profiling_summary()
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': summary,
            'results': [r.to_dict() for r in results]
        }
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logging.info(f"[Profile] Exported report to {output_path}")
        return True
        
    except Exception as e:
        logging.error(f"[Profile] Failed to export report: {e}")
        return False


# ============ BENCHMARK UTILITIES ============

def benchmark(
    func: Callable,
    iterations: int = 10,
    warmup: int = 2,
    name: str = None
) -> Dict[str, float]:
    """
    Benchmark a function by running it multiple times.
    
    Args:
        func: Function to benchmark (should take no arguments)
        iterations: Number of timed iterations
        warmup: Number of warmup iterations (not counted)
        name: Name for the benchmark
        
    Returns:
        Dictionary with timing statistics:
        - iterations: Number of iterations run
        - total_ms: Total time
        - avg_ms: Average time per iteration
        - min_ms: Minimum time
        - max_ms: Maximum time
        - std_ms: Standard deviation
    """
    import statistics
    
    op_name = name or getattr(func, '__name__', 'benchmark')
    
    # Warmup
    for _ in range(warmup):
        func()
    
    # Timed runs
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
    
    result = {
        'name': op_name,
        'iterations': iterations,
        'total_ms': sum(times),
        'avg_ms': statistics.mean(times),
        'min_ms': min(times),
        'max_ms': max(times),
        'std_ms': statistics.stdev(times) if len(times) > 1 else 0
    }
    
    logging.info(
        f"[Benchmark] {op_name}: {result['avg_ms']:.1f}ms avg "
        f"(min={result['min_ms']:.1f}, max={result['max_ms']:.1f}, n={iterations})"
    )
    
    return result


class Timer:
    """
    Simple timer for manual timing.
    
    Example:
        timer = Timer()
        timer.start()
        # Do work
        timer.stop()
        print(f"Took {timer.elapsed_ms}ms")
        
        # Or
        timer.start()
        # Do step 1
        timer.lap("step1")
        # Do step 2
        timer.lap("step2")
        timer.stop()
        print(timer.laps)
    """
    
    def __init__(self):
        """Initialize timer."""
        self._start: float = 0
        self._end: float = 0
        self._laps: List[Dict[str, Any]] = []
        self._running: bool = False
    
    def start(self) -> 'Timer':
        """Start the timer."""
        self._start = time.perf_counter()
        self._running = True
        self._laps = []
        return self
    
    def stop(self) -> 'Timer':
        """Stop the timer."""
        self._end = time.perf_counter()
        self._running = False
        return self
    
    def lap(self, name: str = None) -> float:
        """
        Record a lap time.
        
        Args:
            name: Optional name for this lap
            
        Returns:
            Elapsed time since start in milliseconds
        """
        current = time.perf_counter()
        elapsed = (current - self._start) * 1000
        self._laps.append({
            'name': name or f"lap_{len(self._laps) + 1}",
            'elapsed_ms': elapsed,
            'timestamp': datetime.now().isoformat()
        })
        return elapsed
    
    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        if self._running:
            return (time.perf_counter() - self._start) * 1000
        return (self._end - self._start) * 1000
    
    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        return self.elapsed_ms / 1000
    
    @property
    def laps(self) -> List[Dict[str, Any]]:
        """Get all recorded laps."""
        return list(self._laps)
