# File: utils/scheduler.py
"""
Task Scheduler Module - Run tasks at scheduled times.

V5.0 - Phase 4: Automation
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Optional
from pathlib import Path
import configparser


class TaskScheduler:
    """Simple task scheduler for daily runs."""
    
    def __init__(self, config_path: Path = Path("gui_settings.ini")):
        self.config_path = config_path
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.task_callback: Optional[Callable] = None
        self.check_interval = 60  # Check every 60 seconds
    
    def set_callback(self, callback: Callable):
        """Set the callback function to run at scheduled time."""
        self.task_callback = callback
    
    def is_enabled(self) -> bool:
        """Check if scheduling is enabled in config."""
        if not self.config_path.exists():
            return False
        
        config = configparser.ConfigParser()
        config.read(self.config_path)
        return config.getboolean('Schedule', 'enabled', fallback=False)
    
    def get_scheduled_time(self) -> Optional[str]:
        """Get scheduled run time from config."""
        if not self.config_path.exists():
            return None
        
        config = configparser.ConfigParser()
        config.read(self.config_path)
        return config.get('Schedule', 'run_time', fallback='08:00')
    
    def start(self):
        """Start the scheduler in a background thread."""
        if self.running:
            logging.info("[Scheduler] Already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logging.info("[Scheduler] Started")
    
    def stop(self):
        """Stop the scheduler."""
        self.running = False
        logging.info("[Scheduler] Stopped")
    
    def _run_loop(self):
        """Main scheduler loop."""
        last_run_date = None
        
        while self.running:
            try:
                # Check if scheduling is enabled
                if not self.is_enabled():
                    time.sleep(self.check_interval)
                    continue
                
                # Get scheduled time
                scheduled_time_str = self.get_scheduled_time()
                if not scheduled_time_str:
                    time.sleep(self.check_interval)
                    continue
                
                # Parse scheduled time
                try:
                    scheduled_hour, scheduled_minute = map(int, scheduled_time_str.split(':'))
                except:
                    logging.warning(f"[Scheduler] Invalid time format: {scheduled_time_str}")
                    time.sleep(self.check_interval)
                    continue
                
                # Check if it's time to run
                now = datetime.now()
                today = now.date()
                
                # Only run once per day
                if last_run_date == today:
                    time.sleep(self.check_interval)
                    continue
                
                # Check if current time matches scheduled time (within 1 minute)
                if now.hour == scheduled_hour and now.minute == scheduled_minute:
                    logging.info(f"[Scheduler] Running scheduled task at {now.strftime('%H:%M')}")
                    
                    if self.task_callback:
                        try:
                            self.task_callback()
                            last_run_date = today
                            logging.info("[Scheduler] Task completed successfully")
                        except Exception as e:
                            logging.error(f"[Scheduler] Task failed: {e}")
                    else:
                        logging.warning("[Scheduler] No callback set")
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                logging.error(f"[Scheduler] Error in loop: {e}")
                time.sleep(self.check_interval)
    
    def run_now(self):
        """Manually trigger the scheduled task."""
        if self.task_callback:
            logging.info("[Scheduler] Manual run triggered")
            try:
                self.task_callback()
                logging.info("[Scheduler] Manual run completed")
            except Exception as e:
                logging.error(f"[Scheduler] Manual run failed: {e}")
        else:
            logging.warning("[Scheduler] No callback set")


# Global scheduler instance
_scheduler: Optional[TaskScheduler] = None


def get_scheduler() -> TaskScheduler:
    """Get the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
    return _scheduler


def start_scheduler(callback: Callable):
    """Start the global scheduler with a callback."""
    scheduler = get_scheduler()
    scheduler.set_callback(callback)
    scheduler.start()


def stop_scheduler():
    """Stop the global scheduler."""
    scheduler = get_scheduler()
    scheduler.stop()
