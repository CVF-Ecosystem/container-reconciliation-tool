# File: utils/file_watcher.py
"""
File Watcher Module - Auto-detect new files in input folder.

V5.0 - Phase 4: Automation
"""

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Set
import os


class FileWatcher:
    """Watch folder for new files and trigger callback."""
    
    def __init__(
        self,
        watch_dir: Path,
        callback: Optional[Callable[[Set[str]], None]] = None,
        check_interval: int = 30,
        file_extensions: tuple = ('.xlsx', '.xls', '.csv')
    ):
        """
        Initialize file watcher.
        
        Args:
            watch_dir: Directory to watch
            callback: Function to call when new files detected
            check_interval: Seconds between checks
            file_extensions: File extensions to watch
        """
        self.watch_dir = Path(watch_dir)
        self.callback = callback
        self.check_interval = check_interval
        self.file_extensions = file_extensions
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self._known_files: Set[str] = set()
        self._initialized = False
    
    def _get_current_files(self) -> Set[str]:
        """Get set of current file names in watch directory."""
        if not self.watch_dir.exists():
            return set()
        
        files = set()
        for f in self.watch_dir.iterdir():
            if f.is_file() and f.suffix.lower() in self.file_extensions:
                files.add(f.name)
        return files
    
    def start(self):
        """Start watching in background thread."""
        if self.running:
            logging.info("[Watcher] Already running")
            return
        
        # Initialize known files on start
        self._known_files = self._get_current_files()
        self._initialized = True
        
        self.running = True
        self.thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.thread.start()
        logging.info(f"[Watcher] Started watching {self.watch_dir} ({len(self._known_files)} files)")
    
    def stop(self):
        """Stop watching."""
        self.running = False
        logging.info("[Watcher] Stopped")
    
    def _watch_loop(self):
        """Main watch loop."""
        while self.running:
            try:
                current_files = self._get_current_files()
                new_files = current_files - self._known_files
                
                if new_files:
                    logging.info(f"[Watcher] Detected {len(new_files)} new file(s): {', '.join(list(new_files)[:3])}...")
                    
                    # Wait a bit to ensure file is fully written
                    time.sleep(2)
                    
                    if self.callback:
                        try:
                            self.callback(new_files)
                        except Exception as e:
                            logging.error(f"[Watcher] Callback failed: {e}")
                    
                    # Update known files
                    self._known_files = current_files
                
                # Also check for removed files
                removed_files = self._known_files - current_files
                if removed_files:
                    self._known_files = current_files
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                logging.error(f"[Watcher] Error: {e}")
                time.sleep(self.check_interval)
    
    def get_status(self) -> dict:
        """Get current watcher status."""
        return {
            'running': self.running,
            'watch_dir': str(self.watch_dir),
            'file_count': len(self._known_files),
            'check_interval': self.check_interval
        }


def create_file_watcher(
    watch_dir: Path,
    on_new_files: Optional[Callable] = None,
    auto_start: bool = True
) -> FileWatcher:
    """
    Convenience function to create and optionally start a file watcher.
    
    Args:
        watch_dir: Directory to watch
        on_new_files: Callback when new files detected
        auto_start: Whether to start immediately
    
    Returns:
        FileWatcher instance
    """
    watcher = FileWatcher(watch_dir, on_new_files)
    if auto_start:
        watcher.start()
    return watcher
