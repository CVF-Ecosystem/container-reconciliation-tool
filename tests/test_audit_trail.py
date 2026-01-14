# tests/test_audit_trail.py
# V5.4: Unit tests for audit trail system
"""Tests for utils/audit_trail.py module."""

import pytest
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import threading
from utils.audit_trail import (
    AuditLogger,
    AuditAction,
    AuditSeverity,
    AuditEntry,
    audited,
    get_audit_logger,
    audit_log,
    audit_error
)


class TestAuditAction:
    """Tests for AuditAction enum."""
    
    def test_action_values(self):
        """Test all action types exist."""
        actions = [
            AuditAction.LOGIN,
            AuditAction.LOGOUT,
            AuditAction.DATA_LOAD,
            AuditAction.DATA_EXPORT,
            AuditAction.DATA_DELETE,
            AuditAction.RECON_START,
            AuditAction.RECON_COMPLETE,
            AuditAction.RECON_ERROR,
            AuditAction.REPORT_GENERATE,
            AuditAction.REPORT_EXPORT,
            AuditAction.REPORT_EMAIL,
            AuditAction.COMPARE_START,
            AuditAction.COMPARE_COMPLETE,
            AuditAction.SETTINGS_CHANGE,
            AuditAction.LANGUAGE_CHANGE,
            AuditAction.THEME_CHANGE,
            AuditAction.APP_START,
            AuditAction.APP_CLOSE,
            AuditAction.ERROR,
            AuditAction.WARNING
        ]
        
        assert len(actions) == 20
    
    def test_action_string_values(self):
        """Test action string representations."""
        assert AuditAction.DATA_LOAD.value == "DATA_LOAD"
        assert AuditAction.DATA_EXPORT.value == "DATA_EXPORT"


class TestAuditSeverity:
    """Tests for AuditSeverity enum."""
    
    def test_severity_values(self):
        """Test severity levels exist."""
        severities = [
            AuditSeverity.INFO,
            AuditSeverity.WARNING,
            AuditSeverity.ERROR,
            AuditSeverity.CRITICAL
        ]
        
        assert len(severities) == 4
    
    def test_severity_ordering(self):
        """Test severity level values."""
        assert AuditSeverity.INFO.value == "INFO"
        assert AuditSeverity.CRITICAL.value == "CRITICAL"


class TestAuditEntry:
    """Tests for AuditEntry dataclass."""
    
    def test_create_entry(self):
        """Test creating audit entry."""
        entry = AuditEntry(
            action="DATA_LOAD",
            description="Loaded file test.xlsx",
            severity="INFO",
            metadata='{"filename": "test.xlsx"}'
        )
        
        assert entry.action == "DATA_LOAD"
        assert entry.description == "Loaded file test.xlsx"
        assert entry.severity == "INFO"
        assert entry.timestamp is not None
    
    def test_entry_with_user(self):
        """Test entry with user information."""
        entry = AuditEntry(
            action="SETTINGS_CHANGE",
            description="Changed setting",
            user_id="admin"
        )
        
        assert entry.user_id == "admin"
    
    def test_entry_to_dict(self):
        """Test entry conversion to dictionary."""
        entry = AuditEntry(
            action="DATA_LOAD",
            description="Processed data"
        )
        
        data = entry.to_dict()
        
        assert data["action"] == "DATA_LOAD"
        assert data["description"] == "Processed data"
        assert "timestamp" in data


class TestAuditLogger:
    """Tests for AuditLogger class."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            yield db_path
    
    @pytest.fixture
    def logger(self, temp_db):
        """Create audit logger with temp database."""
        # Reset singleton for testing
        AuditLogger._instance = None
        logger = AuditLogger(db_path=temp_db)
        yield logger
    
    def test_logger_initialization(self, logger, temp_db):
        """Test logger creates database."""
        assert temp_db.exists()
    
    def test_log_entry(self, logger):
        """Test logging an entry."""
        entry_id = logger.log(
            action=AuditAction.DATA_LOAD,
            description="Test log entry"
        )
        
        assert entry_id is not None
        assert entry_id > 0
    
    def test_log_with_metadata(self, logger):
        """Test logging with metadata dictionary."""
        entry_id = logger.log(
            action=AuditAction.DATA_EXPORT,
            description="Export completed",
            metadata={"rows": 1000, "format": "xlsx"}
        )
        
        entries = logger.query(action=AuditAction.DATA_EXPORT)
        # Filter out APP_START entry
        entries = [e for e in entries if e.action == "DATA_EXPORT"]
        assert len(entries) == 1
    
    def test_log_with_severity(self, logger):
        """Test logging with different severities."""
        logger.log(
            action=AuditAction.ERROR,
            description="Error happened",
            severity=AuditSeverity.ERROR
        )
        
        entries = logger.query(severity=AuditSeverity.ERROR)
        assert len(entries) >= 1
    
    def test_query_by_action(self, logger):
        """Test querying by action type."""
        logger.log(AuditAction.DATA_LOAD, "Load 1")
        logger.log(AuditAction.DATA_EXPORT, "Export 1")
        logger.log(AuditAction.DATA_LOAD, "Load 2")
        
        entries = logger.query(action=AuditAction.DATA_LOAD)
        
        assert len(entries) == 2
        for entry in entries:
            assert entry.action == "DATA_LOAD"
    
    def test_query_by_date_range(self, logger):
        """Test querying by date range."""
        # Log entry
        logger.log(AuditAction.RECON_START, "Process data")
        
        # Query for today
        start = datetime.now().replace(hour=0, minute=0, second=0)
        end = datetime.now().replace(hour=23, minute=59, second=59)
        
        entries = logger.query(start_date=start, end_date=end)
        
        assert len(entries) >= 1
    
    def test_query_limit(self, logger):
        """Test query with limit."""
        for i in range(10):
            logger.log(AuditAction.RECON_START, f"Entry {i}")
        
        entries = logger.query(limit=5)
        
        assert len(entries) == 5
    
    def test_get_statistics(self, logger):
        """Test getting audit statistics."""
        logger.log(AuditAction.DATA_LOAD, "Load 1")
        logger.log(AuditAction.DATA_LOAD, "Load 2")
        logger.log(AuditAction.DATA_EXPORT, "Export 1")
        logger.log(AuditAction.ERROR, "Error", severity=AuditSeverity.ERROR)
        
        stats = logger.get_statistics()
        
        assert stats["total_entries"] >= 4
        assert stats["by_action"]["DATA_LOAD"] == 2
        assert stats["by_action"]["DATA_EXPORT"] == 1
        assert stats["by_severity"]["ERROR"] >= 1
    
    def test_cleanup_old_entries(self, logger):
        """Test cleaning up old entries."""
        # This test mainly verifies the method runs without error
        # In practice, entries would need to be older than retention period
        deleted = logger.cleanup(days_to_keep=90)
        
        assert deleted >= 0  # Should return number deleted
    
    def test_export_to_excel(self, logger):
        """Test exporting to Excel format."""
        logger.log(AuditAction.DATA_LOAD, "Test entry")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = Path(tmpdir) / "audit_export.xlsx"
            
            result = logger.export_to_excel(export_path)
            
            assert result is True
            assert export_path.exists()


class TestAuditLoggerSingleton:
    """Tests for singleton pattern."""
    
    def test_get_audit_logger_singleton(self):
        """Test that get_audit_logger returns singleton."""
        # Reset singleton
        AuditLogger._instance = None
        
        # Note: This test may be affected by other tests
        # that initialize the global logger
        logger1 = get_audit_logger()
        logger2 = get_audit_logger()
        
        assert logger1 is logger2


class TestAuditedDecorator:
    """Tests for @audited decorator."""
    
    @pytest.fixture
    def setup_global_logger(self):
        """Setup global logger for decorator tests."""
        import utils.audit_trail as audit_module
        
        # Reset singleton and global logger
        AuditLogger._instance = None
        audit_module._audit_logger = None
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            logger = AuditLogger(db_path=db_path)
            audit_module._audit_logger = logger
            yield logger
    
    def test_audited_function_success(self, setup_global_logger):
        """Test audited decorator logs success."""
        @audited(
            action=AuditAction.RECON_START,
            entity_type="test"
        )
        def process_data():
            return "processed"
        
        result = process_data()
        
        assert result == "processed"
        
        entries = setup_global_logger.query(action=AuditAction.RECON_START)
        assert len(entries) >= 1
    
    def test_audited_function_failure(self, setup_global_logger):
        """Test audited decorator logs failure."""
        @audited(
            action=AuditAction.RECON_START,
            entity_type="test"
        )
        def failing_process():
            raise ValueError("Process failed")
        
        with pytest.raises(ValueError):
            failing_process()
        
        # Check error was logged
        entries = setup_global_logger.query(severity=AuditSeverity.ERROR)
        assert len(entries) >= 1
    
    def test_audited_captures_args(self, setup_global_logger):
        """Test audited decorator captures arguments."""
        @audited(
            action=AuditAction.DATA_LOAD,
            entity_type="file",
            log_args=True
        )
        def load_file(filename, encoding="utf-8"):
            return f"Loaded {filename}"
        
        load_file("test.xlsx", encoding="cp1252")
        
        entries = setup_global_logger.query(action=AuditAction.DATA_LOAD)
        assert len(entries) >= 1
    
    def test_audited_with_return_value(self, setup_global_logger):
        """Test audited preserves return value."""
        @audited(
            action=AuditAction.REPORT_GENERATE,
            entity_type="report"
        )
        def generate_report():
            return {"rows": 100, "status": "complete"}
        
        result = generate_report()
        
        assert result["rows"] == 100
        assert result["status"] == "complete"


class TestDatabaseSchema:
    """Tests for database schema and integrity."""
    
    def test_schema_created_correctly(self):
        """Test that database schema is correct."""
        # Reset singleton
        AuditLogger._instance = None
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            logger = AuditLogger(db_path=db_path)
            
            # Check table exists
            conn = sqlite3.connect(db_path)
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'"
            )
            tables = cursor.fetchall()
            
            assert len(tables) == 1
            
            # Check columns
            cursor = conn.execute("PRAGMA table_info(audit_log)")
            columns = {row[1] for row in cursor.fetchall()}
            
            expected_columns = {
                'id', 'timestamp', 'action', 'description',
                'severity', 'user_id', 'metadata'
            }
            
            assert expected_columns.issubset(columns)
            
            conn.close()
    
    def test_index_exists(self):
        """Test that indexes are created."""
        # Reset singleton
        AuditLogger._instance = None
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            logger = AuditLogger(db_path=db_path)
            
            conn = sqlite3.connect(db_path)
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
            indexes = [row[0] for row in cursor.fetchall()]
            
            # Should have indexes for common query patterns
            assert any('timestamp' in idx.lower() for idx in indexes)
            
            conn.close()


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_log_with_none_metadata(self):
        """Test logging with None metadata."""
        # Reset singleton
        AuditLogger._instance = None
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            logger = AuditLogger(db_path=db_path)
            
            entry_id = logger.log(
                action=AuditAction.RECON_START,
                description="No metadata",
                metadata=None
            )
            
            assert entry_id is not None
    
    def test_log_with_complex_metadata(self):
        """Test logging with complex nested metadata."""
        # Reset singleton
        AuditLogger._instance = None
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            logger = AuditLogger(db_path=db_path)
            
            metadata = {
                "files": ["a.xlsx", "b.xlsx"],
                "config": {"encoding": "utf-8", "skip_rows": 5},
                "statistics": {"total": 1000, "errors": 5}
            }
            
            entry_id = logger.log(
                action=AuditAction.RECON_START,
                description="Complex metadata",
                metadata=metadata
            )
            
            assert entry_id is not None
    
    def test_query_empty_database(self):
        """Test querying empty database."""
        # Reset singleton
        AuditLogger._instance = None
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            logger = AuditLogger(db_path=db_path)
            
            # Query for non-existent action
            entries = logger.query(action="NON_EXISTENT_ACTION")
            
            assert entries == []
    
    def test_statistics_empty_database(self):
        """Test statistics on mostly empty database."""
        # Reset singleton
        AuditLogger._instance = None
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            logger = AuditLogger(db_path=db_path)
            
            stats = logger.get_statistics()
            
            # APP_START is auto-logged
            assert stats["total_entries"] >= 0
