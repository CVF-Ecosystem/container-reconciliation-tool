"""
Smart caching utility for reconciliation results.
V5.4: Enhanced with TTL, memory caching, and cache management.

Features:
- File hash-based cache invalidation
- Time-to-live (TTL) support
- In-memory caching with LRU
- Cache statistics and management
"""
import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any, Callable
from datetime import datetime, timedelta
from functools import wraps
from threading import Lock
import pickle


CACHE_METADATA_FILE = "cache_metadata.json"


# ============ IN-MEMORY CACHE ============

class CacheManager:
    """
    Thread-safe in-memory cache with TTL support.
    
    Features:
    - Time-to-live (TTL) for automatic expiration
    - LRU-like eviction when max size reached
    - Thread-safe operations
    - Cache statistics
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        """Singleton pattern for global cache."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, default_ttl_minutes: int = 30, max_size: int = 100):
        if self._initialized:
            return
        
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._default_ttl = timedelta(minutes=default_ttl_minutes)
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
        self._lock = Lock()
        self._initialized = True
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache if exists and not expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            entry = self._cache[key]
            
            # Check TTL
            if entry['expires_at'] and datetime.now() > entry['expires_at']:
                del self._cache[key]
                self._misses += 1
                return None
            
            # Update access time
            entry['last_accessed'] = datetime.now()
            entry['access_count'] += 1
            self._hits += 1
            
            return entry['value']
    
    def set(
        self, 
        key: str, 
        value: Any, 
        ttl_minutes: int = None,
        tags: list = None
    ) -> None:
        """
        Set value in cache with optional TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_minutes: Time-to-live in minutes (None = default, 0 = no expiration)
            tags: Optional tags for grouped invalidation
        """
        with self._lock:
            # Evict if at max size
            if len(self._cache) >= self._max_size and key not in self._cache:
                self._evict_lru()
            
            # Calculate expiration
            if ttl_minutes is None:
                expires_at = datetime.now() + self._default_ttl
            elif ttl_minutes == 0:
                expires_at = None  # Never expires
            else:
                expires_at = datetime.now() + timedelta(minutes=ttl_minutes)
            
            self._cache[key] = {
                'value': value,
                'created_at': datetime.now(),
                'last_accessed': datetime.now(),
                'expires_at': expires_at,
                'access_count': 0,
                'tags': tags or []
            }
    
    def delete(self, key: str) -> bool:
        """Delete a specific key from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def invalidate_by_tag(self, tag: str) -> int:
        """
        Invalidate all cache entries with a specific tag.
        
        Args:
            tag: Tag to match
            
        Returns:
            Number of entries invalidated
        """
        with self._lock:
            keys_to_delete = [
                k for k, v in self._cache.items() 
                if tag in v.get('tags', [])
            ]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)
    
    def invalidate_by_pattern(self, pattern: str) -> int:
        """
        Invalidate all cache entries matching a pattern.
        
        Args:
            pattern: Pattern to match in key names
            
        Returns:
            Number of entries invalidated
        """
        with self._lock:
            keys_to_delete = [k for k in self._cache if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
    
    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._cache:
            return
        
        # Find LRU entry
        lru_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k]['last_accessed']
        )
        del self._cache[lru_key]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'size': len(self._cache),
                'max_size': self._max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate_percent': round(hit_rate, 2),
                'default_ttl_minutes': self._default_ttl.total_seconds() / 60
            }
    
    def get_keys(self) -> list:
        """Get all cache keys."""
        with self._lock:
            return list(self._cache.keys())


# Global cache instance
_cache = CacheManager()


def get_cache() -> CacheManager:
    """Get the global cache manager instance."""
    return _cache


# ============ CACHE DECORATOR ============

def cached(ttl_minutes: int = None, key_prefix: str = '', tags: list = None):
    """
    Decorator for caching function results.
    
    Args:
        ttl_minutes: Cache TTL in minutes
        key_prefix: Prefix for cache key
        tags: Tags for grouped invalidation
        
    Example:
        @cached(ttl_minutes=10, key_prefix='operator')
        def get_operator_summary(date: str) -> pd.DataFrame:
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(a) for a in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(filter(None, key_parts))
            
            # Try to get from cache
            cache = get_cache()
            cached_value = cache.get(cache_key)
            
            if cached_value is not None:
                logging.debug(f"Cache hit: {cache_key}")
                return cached_value
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl_minutes=ttl_minutes, tags=tags)
            logging.debug(f"Cache miss, stored: {cache_key}")
            
            return result
        
        # Add cache control methods to wrapper
        wrapper.cache_invalidate = lambda: _cache.invalidate_by_pattern(f"{key_prefix}:{func.__name__}")
        
        return wrapper
    return decorator


def calculate_file_hash(file_path: Path) -> str:
    """
    Calculate MD5 hash of a file for change detection.
    
    Args:
        file_path: Path to the file to hash.
    
    Returns:
        MD5 hex digest string.
    """
    hasher = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        logging.warning(f"Could not hash file {file_path}: {e}")
        return ""


def get_input_files_hashes(input_dir: Path) -> Dict[str, str]:
    """
    Get hashes of all Excel files in the input directory.
    
    Args:
        input_dir: Directory containing input Excel files.
    
    Returns:
        Dictionary mapping filename to its MD5 hash.
    """
    hashes = {}
    if not input_dir.exists():
        return hashes
    
    for file_path in input_dir.glob("*.xlsx"):
        hashes[file_path.name] = calculate_file_hash(file_path)
    
    return hashes


def load_cache_metadata(output_dir: Path) -> Optional[Dict]:
    """
    Load previously saved cache metadata.
    
    Args:
        output_dir: Directory where cache metadata is stored.
    
    Returns:
        Dictionary with 'hashes' and 'timestamp', or None if not found.
    """
    metadata_path = output_dir / CACHE_METADATA_FILE
    if not metadata_path.exists():
        return None
    
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.warning(f"Could not load cache metadata: {e}")
        return None


def save_cache_metadata(output_dir: Path, hashes: Dict[str, str]) -> None:
    """
    Save current file hashes as cache metadata.
    
    Args:
        output_dir: Directory where cache metadata should be stored.
        hashes: Dictionary of filename to hash mappings.
    """
    metadata_path = output_dir / CACHE_METADATA_FILE
    metadata = {
        "hashes": hashes,
        "timestamp": datetime.now().isoformat(),
        "version": "1.0"
    }
    
    try:
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        logging.info(f"Cache metadata saved to {metadata_path}")
    except Exception as e:
        logging.error(f"Could not save cache metadata: {e}")


def is_cache_valid(input_dir: Path, output_dir: Path) -> bool:
    """
    Check if cached results are still valid (input files haven't changed).
    
    Args:
        input_dir: Directory containing input Excel files.
        output_dir: Directory containing cached results.
    
    Returns:
        True if cache is valid and can be reused, False otherwise.
    """
    # Load previous metadata
    prev_metadata = load_cache_metadata(output_dir)
    if prev_metadata is None:
        logging.info("No cache metadata found. Full processing required.")
        return False
    
    # Calculate current hashes
    current_hashes = get_input_files_hashes(input_dir)
    prev_hashes = prev_metadata.get("hashes", {})
    
    # Compare
    if current_hashes != prev_hashes:
        # Find what changed
        changed_files = []
        for filename, current_hash in current_hashes.items():
            if filename not in prev_hashes:
                changed_files.append(f"{filename} (new)")
            elif prev_hashes[filename] != current_hash:
                changed_files.append(f"{filename} (modified)")
        
        for filename in prev_hashes:
            if filename not in current_hashes:
                changed_files.append(f"{filename} (deleted)")
        
        if changed_files:
            logging.info(f"Cache invalidated. Changed files: {', '.join(changed_files)}")
        return False
    
    logging.info(f"Cache is valid. Using cached results from {prev_metadata.get('timestamp', 'unknown')}.")
    return True
