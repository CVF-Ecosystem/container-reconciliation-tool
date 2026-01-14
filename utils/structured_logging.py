# File: utils/structured_logging.py
"""
Structured Logging Module - JSON format logging for easy parsing.

V5.0 - Phase 1: Stability
"""

import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for easy parsing and analysis."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'extra_data'):
            log_data["data"] = record.extra_data
        
        return json.dumps(log_data, ensure_ascii=False)


class PerformanceLogger:
    """Log performance metrics for analysis."""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time: Optional[datetime] = None
        self.metrics: Dict[str, Any] = {}
    
    def __enter__(self):
        self.start_time = datetime.now()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()
        self.metrics["duration_seconds"] = duration
        
        log_data = {
            "operation": self.operation_name,
            "duration_seconds": duration,
            "success": exc_type is None,
            **self.metrics
        }
        
        if exc_type:
            log_data["error"] = str(exc_val)
        
        logging.info(f"[PERF] {self.operation_name}: {duration:.2f}s", 
                    extra={"extra_data": log_data})
        
        return False  # Don't suppress exceptions
    
    def add_metric(self, key: str, value: Any):
        """Add a custom metric to the performance log."""
        self.metrics[key] = value


def setup_json_logging(log_dir: Path, log_name: str = "app_json.log"):
    """
    Setup JSON logging alongside regular text logging.
    
    Args:
        log_dir: Directory for log files
        log_name: Name of the JSON log file
    """
    log_dir.mkdir(exist_ok=True)
    json_log_path = log_dir / log_name
    
    # Create JSON file handler
    json_handler = logging.FileHandler(json_log_path, encoding='utf-8')
    json_handler.setFormatter(JSONFormatter())
    json_handler.setLevel(logging.INFO)
    
    # Add to root logger
    logging.getLogger().addHandler(json_handler)
    
    logging.info(f"[Logging] JSON logging enabled: {json_log_path}")
    
    return json_log_path


def log_event(event_type: str, data: Dict[str, Any], level: str = "INFO"):
    """
    Log a structured event.
    
    Args:
        event_type: Type of event (e.g., "batch_start", "file_loaded")
        data: Event data
        level: Log level
    """
    record = logging.LogRecord(
        name="app",
        level=getattr(logging, level.upper()),
        pathname="",
        lineno=0,
        msg=f"[{event_type}] {json.dumps(data, ensure_ascii=False)}",
        args=(),
        exc_info=None
    )
    record.extra_data = {"event_type": event_type, **data}
    logging.getLogger().handle(record)


def log_batch_start(dates: list, file_count: int):
    """Log batch processing start."""
    log_event("batch_start", {
        "dates": [str(d) for d in dates],
        "date_count": len(dates),
        "file_count": file_count
    })


def log_batch_complete(success_count: int, total_count: int, duration: float):
    """Log batch processing completion."""
    log_event("batch_complete", {
        "success_count": success_count,
        "total_count": total_count,
        "duration_seconds": duration,
        "success_rate": f"{success_count/total_count*100:.1f}%" if total_count > 0 else "N/A"
    })


def log_file_processed(filename: str, rows: int, duration: float, success: bool):
    """Log individual file processing."""
    log_event("file_processed", {
        "filename": filename,
        "row_count": rows,
        "duration_seconds": duration,
        "success": success
    }, level="INFO" if success else "WARNING")


def log_error(error_type: str, message: str, context: Optional[Dict] = None):
    """Log an error with context."""
    data = {
        "error_type": error_type,
        "message": message
    }
    if context:
        data["context"] = context
    log_event("error", data, level="ERROR")
