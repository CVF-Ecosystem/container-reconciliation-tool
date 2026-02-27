# File: utils/retry_utils.py
# @2026 v1.0: Retry mechanism for file operations and network calls
"""
Retry utilities for handling transient failures.

Features:
- Configurable retry count and delays
- Exponential backoff
- Specific exception handling
- Logging of retry attempts
"""

import logging
import time
from functools import wraps
from typing import Callable, Type, Tuple, Optional, Any
from pathlib import Path


# ============ CONSTANTS ============

DEFAULT_MAX_RETRIES = 3
DEFAULT_DELAY_SECONDS = 1.0
DEFAULT_BACKOFF_FACTOR = 2.0
DEFAULT_MAX_DELAY_SECONDS = 30.0


# ============ RETRY DECORATOR ============

def retry(
    max_retries: int = DEFAULT_MAX_RETRIES,
    delay: float = DEFAULT_DELAY_SECONDS,
    backoff: float = DEFAULT_BACKOFF_FACTOR,
    max_delay: float = DEFAULT_MAX_DELAY_SECONDS,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Callable[[Exception, int], None] = None,
    reraise: bool = True
):
    """
    Decorator for automatic retry with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        max_delay: Maximum delay between retries
        exceptions: Tuple of exception types to catch and retry
        on_retry: Optional callback function(exception, attempt_number)
        reraise: Whether to reraise the exception after all retries fail
        
    Example:
        @retry(max_retries=3, delay=1, exceptions=(IOError, PermissionError))
        def read_excel_file(path):
            return pd.read_excel(path)
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        # Log retry attempt
                        logging.warning(
                            f"[Retry] {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        
                        # Call retry callback if provided
                        if on_retry:
                            on_retry(e, attempt + 1)
                        
                        # Wait before retry
                        time.sleep(current_delay)
                        
                        # Increase delay with backoff (capped at max_delay)
                        current_delay = min(current_delay * backoff, max_delay)
                    else:
                        # All retries exhausted
                        logging.error(
                            f"[Retry] {func.__name__} failed after {max_retries + 1} attempts. "
                            f"Last error: {e}"
                        )
            
            if reraise and last_exception:
                raise last_exception
            
            return None
        
        return wrapper
    return decorator


# ============ FILE OPERATION HELPERS ============

@retry(
    max_retries=3,
    delay=0.5,
    exceptions=(IOError, PermissionError, OSError)
)
def safe_read_file(file_path: Path, mode: str = 'r', encoding: str = 'utf-8') -> str:
    """
    Safely read a file with automatic retry.
    
    Args:
        file_path: Path to file
        mode: File open mode
        encoding: File encoding
        
    Returns:
        File contents as string
    """
    with open(file_path, mode, encoding=encoding) as f:
        return f.read()


@retry(
    max_retries=3,
    delay=0.5,
    exceptions=(IOError, PermissionError, OSError)
)
def safe_write_file(
    file_path: Path, 
    content: str, 
    mode: str = 'w', 
    encoding: str = 'utf-8'
) -> bool:
    """
    Safely write to a file with automatic retry.
    
    Args:
        file_path: Path to file
        content: Content to write
        mode: File open mode
        encoding: File encoding
        
    Returns:
        True if successful
    """
    # Ensure parent directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(file_path, mode, encoding=encoding) as f:
        f.write(content)
    return True


@retry(
    max_retries=3,
    delay=1.0,
    backoff=2.0,
    exceptions=(IOError, PermissionError, OSError)
)
def safe_read_excel(file_path: Path, **kwargs):
    """
    Safely read an Excel file with automatic retry.
    
    Handles cases where file is temporarily locked by another process.
    
    Args:
        file_path: Path to Excel file
        **kwargs: Additional arguments for pd.read_excel
        
    Returns:
        pandas DataFrame
    """
    import pandas as pd
    return pd.read_excel(file_path, **kwargs)


@retry(
    max_retries=3,
    delay=1.0,
    backoff=2.0,
    exceptions=(IOError, PermissionError, OSError)
)
def safe_write_excel(df, file_path: Path, **kwargs) -> bool:
    """
    Safely write a DataFrame to Excel with automatic retry.
    
    Args:
        df: pandas DataFrame to write
        file_path: Output path
        **kwargs: Additional arguments for df.to_excel
        
    Returns:
        True if successful
    """
    import pandas as pd
    
    # Ensure parent directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    df.to_excel(file_path, **kwargs)
    return True


@retry(
    max_retries=5,
    delay=0.5,
    backoff=1.5,
    exceptions=(PermissionError, OSError)
)
def safe_delete_file(file_path: Path) -> bool:
    """
    Safely delete a file with retry.
    
    Args:
        file_path: Path to file to delete
        
    Returns:
        True if deleted or didn't exist
    """
    if file_path.exists():
        file_path.unlink()
    return True


@retry(
    max_retries=3,
    delay=0.5,
    exceptions=(PermissionError, OSError)
)
def safe_rename_file(src: Path, dst: Path) -> bool:
    """
    Safely rename/move a file with retry.
    
    Args:
        src: Source path
        dst: Destination path
        
    Returns:
        True if successful
    """
    # Ensure parent directory exists
    dst.parent.mkdir(parents=True, exist_ok=True)
    
    src.rename(dst)
    return True


# ============ CONTEXT MANAGER ============

class RetryContext:
    """
    Context manager for retry operations.
    
    Example:
        with RetryContext(max_retries=3) as ctx:
            while ctx.should_retry():
                try:
                    result = risky_operation()
                    break
                except Exception as e:
                    ctx.record_failure(e)
    """
    
    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        delay: float = DEFAULT_DELAY_SECONDS,
        backoff: float = DEFAULT_BACKOFF_FACTOR,
        max_delay: float = DEFAULT_MAX_DELAY_SECONDS
    ):
        self.max_retries = max_retries
        self.delay = delay
        self.backoff = backoff
        self.max_delay = max_delay
        self.attempt = 0
        self.current_delay = delay
        self.last_exception: Optional[Exception] = None
        self.exceptions: list = []
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def should_retry(self) -> bool:
        """Check if another retry attempt should be made."""
        return self.attempt <= self.max_retries
    
    def record_failure(self, exception: Exception) -> None:
        """
        Record a failure and prepare for retry.
        
        Args:
            exception: The exception that occurred
        """
        self.last_exception = exception
        self.exceptions.append(exception)
        self.attempt += 1
        
        if self.attempt <= self.max_retries:
            logging.warning(
                f"[RetryContext] Attempt {self.attempt}/{self.max_retries + 1} failed: {exception}. "
                f"Waiting {self.current_delay:.1f}s..."
            )
            time.sleep(self.current_delay)
            self.current_delay = min(self.current_delay * self.backoff, self.max_delay)
    
    def raise_if_failed(self) -> None:
        """Raise the last exception if all retries failed."""
        if self.last_exception and self.attempt > self.max_retries:
            raise self.last_exception


# ============ UTILITY FUNCTIONS ============

def wait_for_file(
    file_path: Path,
    timeout_seconds: float = 30.0,
    check_interval: float = 0.5
) -> bool:
    """
    Wait for a file to become available (exist and be readable).
    
    Useful when waiting for another process to finish writing.
    
    Args:
        file_path: Path to file
        timeout_seconds: Maximum time to wait
        check_interval: Time between checks
        
    Returns:
        True if file became available, False if timeout
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout_seconds:
        if file_path.exists():
            try:
                # Try to open the file to check if it's locked
                with open(file_path, 'rb') as f:
                    f.read(1)
                return True
            except (IOError, PermissionError):
                pass
        
        time.sleep(check_interval)
    
    return False


def wait_for_file_stable(
    file_path: Path,
    stability_seconds: float = 2.0,
    timeout_seconds: float = 60.0,
    check_interval: float = 0.5
) -> bool:
    """
    Wait for a file to stop changing (stable size).
    
    Useful when another process is writing to the file.
    
    Args:
        file_path: Path to file
        stability_seconds: Time the file must remain unchanged
        timeout_seconds: Maximum time to wait
        check_interval: Time between checks
        
    Returns:
        True if file became stable, False if timeout
    """
    start_time = time.time()
    last_size = -1
    stable_since = None
    
    while time.time() - start_time < timeout_seconds:
        if not file_path.exists():
            stable_since = None
            time.sleep(check_interval)
            continue
        
        current_size = file_path.stat().st_size
        
        if current_size == last_size:
            if stable_since is None:
                stable_since = time.time()
            elif time.time() - stable_since >= stability_seconds:
                return True
        else:
            stable_since = None
            last_size = current_size
        
        time.sleep(check_interval)
    
    return False
