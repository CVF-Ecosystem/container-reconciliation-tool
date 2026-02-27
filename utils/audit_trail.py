# File: utils/audit_trail.py
# @2026 v1.0: Audit trail module for tracking all important operations
"""
Audit Trail System for Container Inventory Reconciliation Tool.

Features:
- Track all user actions and system operations
- Store audit logs in SQLite database
- Query audit history
- Generate audit reports
- Support for compliance requirements
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
from contextlib import contextmanager
import threading


# ============ ENUMS ============

class AuditAction(Enum):
    """Types of auditable actions."""
    # User actions
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    
    # Data operations
    DATA_LOAD = "DATA_LOAD"
    DATA_EXPORT = "DATA_EXPORT"
    DATA_DELETE = "DATA_DELETE"
    
    # Reconciliation
    RECON_START = "RECON_START"
    RECON_COMPLETE = "RECON_COMPLETE"
    RECON_ERROR = "RECON_ERROR"
    
    # Report operations
    REPORT_GENERATE = "REPORT_GENERATE"
    REPORT_EXPORT = "REPORT_EXPORT"
    REPORT_EMAIL = "REPORT_EMAIL"
    
    # Comparison
    COMPARE_START = "COMPARE_START"
    COMPARE_COMPLETE = "COMPARE_COMPLETE"
    
    # Settings
    SETTINGS_CHANGE = "SETTINGS_CHANGE"
    LANGUAGE_CHANGE = "LANGUAGE_CHANGE"
    THEME_CHANGE = "THEME_CHANGE"
    
    # System
    APP_START = "APP_START"
    APP_CLOSE = "APP_CLOSE"
    ERROR = "ERROR"
    WARNING = "WARNING"


class AuditSeverity(Enum):
    """Severity levels for audit events."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ============ DATA CLASSES ============

@dataclass
class AuditEntry:
    """Represents a single audit log entry."""
    id: Optional[int] = None
    timestamp: str = None
    action: str = None
    severity: str = "INFO"
    user_id: str = "system"
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    description: str = ""
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    metadata: Optional[str] = None
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


# ============ AUDIT LOGGER ============

class AuditLogger:
    """
    Thread-safe audit logger with SQLite backend.
    
    Usage:
        audit = AuditLogger(db_path="logs/audit.db")
        audit.log(
            action=AuditAction.RECON_START,
            description="Started reconciliation for N12.01.2026",
            entity_type="reconciliation",
            entity_id="N12.01.2026"
        )
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, db_path: Union[str, Path] = None):
        """Singleton pattern for global audit logger."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path: Union[str, Path] = None):
        if self._initialized:
            return
        
        if db_path is None:
            db_path = Path("logs/audit.db")
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._user_id = "default_user"
        
        self._init_database()
        self._initialized = True
        
        # Log app start
        self.log(
            action=AuditAction.APP_START,
            description="Application started",
            severity=AuditSeverity.INFO
        )
    
    def _init_database(self) -> None:
        """Initialize SQLite database with audit table."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    severity TEXT DEFAULT 'INFO',
                    user_id TEXT DEFAULT 'system',
                    entity_type TEXT,
                    entity_id TEXT,
                    description TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    metadata TEXT,
                    ip_address TEXT,
                    session_id TEXT
                )
            """)
            
            # Create indexes for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp 
                ON audit_log(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_action 
                ON audit_log(action)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_entity 
                ON audit_log(entity_type, entity_id)
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get thread-safe database connection."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def set_user(self, user_id: str) -> None:
        """Set the current user ID for audit entries."""
        self._user_id = user_id
    
    def log(
        self,
        action: Union[AuditAction, str],
        description: str = "",
        severity: Union[AuditSeverity, str] = AuditSeverity.INFO,
        entity_type: str = None,
        entity_id: str = None,
        old_value: Any = None,
        new_value: Any = None,
        metadata: Dict[str, Any] = None
    ) -> Optional[int]:
        """
        Log an audit entry.
        
        Args:
            action: Type of action being logged
            description: Human-readable description
            severity: Severity level
            entity_type: Type of entity affected (e.g., 'container', 'report')
            entity_id: ID of affected entity
            old_value: Previous value (for changes)
            new_value: New value (for changes)
            metadata: Additional metadata as dictionary
            
        Returns:
            ID of created audit entry, or None on error
        """
        try:
            # Convert enums to strings
            action_str = action.value if isinstance(action, AuditAction) else str(action)
            severity_str = severity.value if isinstance(severity, AuditSeverity) else str(severity)
            
            # Serialize values to JSON
            old_json = json.dumps(old_value) if old_value is not None else None
            new_json = json.dumps(new_value) if new_value is not None else None
            meta_json = json.dumps(metadata) if metadata else None
            
            entry = AuditEntry(
                timestamp=datetime.now().isoformat(),
                action=action_str,
                severity=severity_str,
                user_id=self._user_id,
                entity_type=entity_type,
                entity_id=entity_id,
                description=description,
                old_value=old_json,
                new_value=new_json,
                metadata=meta_json,
                session_id=self._session_id
            )
            
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO audit_log (
                        timestamp, action, severity, user_id, entity_type, 
                        entity_id, description, old_value, new_value, 
                        metadata, ip_address, session_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.timestamp, entry.action, entry.severity, entry.user_id,
                    entry.entity_type, entry.entity_id, entry.description,
                    entry.old_value, entry.new_value, entry.metadata,
                    entry.ip_address, entry.session_id
                ))
                conn.commit()
                
                logging.debug(f"[Audit] {action_str}: {description}")
                return cursor.lastrowid
                
        except Exception as e:
            logging.error(f"[Audit] Failed to log entry: {e}")
            return None
    
    def log_error(self, error: Exception, context: str = "") -> Optional[int]:
        """Log an error with full details."""
        return self.log(
            action=AuditAction.ERROR,
            description=f"{context}: {str(error)}" if context else str(error),
            severity=AuditSeverity.ERROR,
            metadata={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context
            }
        )
    
    def query(
        self,
        action: Union[AuditAction, str] = None,
        entity_type: str = None,
        entity_id: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        severity: Union[AuditSeverity, str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditEntry]:
        """
        Query audit log entries.
        
        Args:
            action: Filter by action type
            entity_type: Filter by entity type
            entity_id: Filter by entity ID
            start_date: Filter entries after this date
            end_date: Filter entries before this date
            severity: Filter by severity
            limit: Maximum entries to return
            offset: Number of entries to skip
            
        Returns:
            List of AuditEntry objects
        """
        conditions = []
        params = []
        
        if action:
            action_str = action.value if isinstance(action, AuditAction) else action
            conditions.append("action = ?")
            params.append(action_str)
        
        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type)
        
        if entity_id:
            conditions.append("entity_id = ?")
            params.append(entity_id)
        
        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date.isoformat())
        
        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date.isoformat())
        
        if severity:
            severity_str = severity.value if isinstance(severity, AuditSeverity) else severity
            conditions.append("severity = ?")
            params.append(severity_str)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
            SELECT * FROM audit_log 
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        
        entries = []
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            for row in rows:
                entries.append(AuditEntry(
                    id=row['id'],
                    timestamp=row['timestamp'],
                    action=row['action'],
                    severity=row['severity'],
                    user_id=row['user_id'],
                    entity_type=row['entity_type'],
                    entity_id=row['entity_id'],
                    description=row['description'],
                    old_value=row['old_value'],
                    new_value=row['new_value'],
                    metadata=row['metadata'],
                    ip_address=row['ip_address'],
                    session_id=row['session_id']
                ))
        
        return entries
    
    def get_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get audit statistics for the specified period.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with statistics
        """
        start_date = datetime.now() - timedelta(days=days)
        
        stats = {
            'period_days': days,
            'start_date': start_date.isoformat(),
            'end_date': datetime.now().isoformat(),
            'total_entries': 0,
            'by_action': {},
            'by_severity': {},
            'errors_count': 0,
            'reconciliations_count': 0,
            'reports_count': 0
        }
        
        with self._get_connection() as conn:
            # Total entries
            row = conn.execute("""
                SELECT COUNT(*) as cnt FROM audit_log 
                WHERE timestamp >= ?
            """, (start_date.isoformat(),)).fetchone()
            stats['total_entries'] = row['cnt']
            
            # By action
            rows = conn.execute("""
                SELECT action, COUNT(*) as cnt FROM audit_log 
                WHERE timestamp >= ?
                GROUP BY action
            """, (start_date.isoformat(),)).fetchall()
            stats['by_action'] = {row['action']: row['cnt'] for row in rows}
            
            # By severity
            rows = conn.execute("""
                SELECT severity, COUNT(*) as cnt FROM audit_log 
                WHERE timestamp >= ?
                GROUP BY severity
            """, (start_date.isoformat(),)).fetchall()
            stats['by_severity'] = {row['severity']: row['cnt'] for row in rows}
            
            # Specific counts
            stats['errors_count'] = stats['by_severity'].get('ERROR', 0) + stats['by_severity'].get('CRITICAL', 0)
            stats['reconciliations_count'] = stats['by_action'].get('RECON_COMPLETE', 0)
            stats['reports_count'] = stats['by_action'].get('REPORT_GENERATE', 0)
        
        return stats
    
    def cleanup(self, days_to_keep: int = 90) -> int:
        """
        Remove old audit entries.
        
        Args:
            days_to_keep: Number of days of history to keep
            
        Returns:
            Number of entries deleted
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                DELETE FROM audit_log WHERE timestamp < ?
            """, (cutoff_date.isoformat(),))
            conn.commit()
            deleted = cursor.rowcount
            
        if deleted > 0:
            self.log(
                action=AuditAction.DATA_DELETE,
                description=f"Cleaned up {deleted} audit entries older than {days_to_keep} days",
                severity=AuditSeverity.INFO
            )
        
        return deleted
    
    def export_to_excel(self, output_path: Path, days: int = 30) -> bool:
        """
        Export audit log to Excel file.
        
        Args:
            output_path: Path for output Excel file
            days: Number of days to export
            
        Returns:
            True if successful
        """
        try:
            import pandas as pd
            
            start_date = datetime.now() - timedelta(days=days)
            entries = self.query(start_date=start_date, limit=10000)
            
            if not entries:
                logging.warning("No audit entries to export")
                return False
            
            data = [e.to_dict() for e in entries]
            df = pd.DataFrame(data)
            
            df.to_excel(output_path, index=False, sheet_name='Audit Log')
            
            self.log(
                action=AuditAction.REPORT_EXPORT,
                description=f"Exported audit log to {output_path}",
                entity_type="audit_report",
                entity_id=str(output_path)
            )
            
            return True
            
        except Exception as e:
            logging.error(f"Failed to export audit log: {e}")
            return False


# ============ GLOBAL FUNCTIONS ============

_audit_logger: Optional[AuditLogger] = None


def get_audit_logger(db_path: Union[str, Path] = None) -> AuditLogger:
    """Get or create the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(db_path)
    return _audit_logger


def audit_log(
    action: Union[AuditAction, str],
    description: str = "",
    **kwargs
) -> Optional[int]:
    """Convenience function for logging audit entries."""
    return get_audit_logger().log(action, description, **kwargs)


def audit_error(error: Exception, context: str = "") -> Optional[int]:
    """Convenience function for logging errors."""
    return get_audit_logger().log_error(error, context)


# ============ DECORATORS ============

def audited(
    action: AuditAction,
    entity_type: str = None,
    get_entity_id: callable = None,
    log_args: bool = False
):
    """
    Decorator to automatically audit function calls.
    
    Args:
        action: Action type to log
        entity_type: Type of entity being affected
        get_entity_id: Function to extract entity ID from args
        log_args: Whether to log function arguments
        
    Example:
        @audited(AuditAction.REPORT_GENERATE, entity_type='report')
        def generate_report(date: str, operator: str):
            ...
    """
    def decorator(func):
        from functools import wraps
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            audit = get_audit_logger()
            
            # Determine entity_id if extractor provided
            eid = None
            if get_entity_id:
                try:
                    eid = get_entity_id(*args, **kwargs)
                except:
                    pass
            
            # Build metadata
            meta = {}
            if log_args:
                meta['args'] = str(args)
                meta['kwargs'] = str(kwargs)
            
            # Log start
            audit.log(
                action=action,
                description=f"Started: {func.__name__}",
                entity_type=entity_type,
                entity_id=eid,
                metadata=meta if meta else None
            )
            
            try:
                result = func(*args, **kwargs)
                
                # Log success
                audit.log(
                    action=action,
                    description=f"Completed: {func.__name__}",
                    entity_type=entity_type,
                    entity_id=eid,
                    severity=AuditSeverity.INFO
                )
                
                return result
                
            except Exception as e:
                # Log error
                audit.log(
                    action=AuditAction.ERROR,
                    description=f"Failed: {func.__name__} - {str(e)}",
                    entity_type=entity_type,
                    entity_id=eid,
                    severity=AuditSeverity.ERROR,
                    metadata={'error': str(e), 'function': func.__name__}
                )
                raise
        
        return wrapper
    return decorator
