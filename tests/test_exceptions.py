# tests/test_exceptions.py
# V5.4: Unit tests for centralized exception handling
"""Tests for utils/exceptions.py module."""

import pytest
from utils.exceptions import (
    ErrorCode,
    AppException,
    ReconciliationError,
    DataLoadError,
    ValidationError,
    ConfigurationError,
    ReportGenerationError,
    ComparisonError,
    FileNotFoundError,
    FileReadError,
    MissingColumnError,
    EmptyDataError,
    InvalidContainerError,
    InvalidDateError
)


class TestErrorCode:
    """Tests for ErrorCode enum."""
    
    def test_error_codes_exist(self):
        """Verify all error codes are defined."""
        # Data errors
        assert ErrorCode.ERR_DAT_001.value == "ERR_DAT_001"
        assert ErrorCode.ERR_DAT_002.value == "ERR_DAT_002"
        
        # Validation errors
        assert ErrorCode.ERR_VAL_001.value == "ERR_VAL_001"
        assert ErrorCode.ERR_VAL_003.value == "ERR_VAL_003"
        
        # Config errors
        assert ErrorCode.ERR_CFG_001.value == "ERR_CFG_001"
        
        # Report errors
        assert ErrorCode.ERR_RPT_001.value == "ERR_RPT_001"
        
        # Comparison errors
        assert ErrorCode.ERR_CMP_001.value == "ERR_CMP_001"


class TestAppException:
    """Tests for AppException base class."""
    
    def test_basic_exception(self):
        """Test basic exception creation."""
        exc = AppException(
            code=ErrorCode.ERR_DAT_001,
            message="Test error message"
        )
        assert exc.code == ErrorCode.ERR_DAT_001
        assert exc.message == "Test error message"
        assert exc.user_message == "Test error message"
        assert exc.details == {}
    
    def test_exception_with_details(self):
        """Test exception with details."""
        exc = AppException(
            code=ErrorCode.ERR_DAT_002,
            message="Cannot read file",
            details={"file": "test.xlsx", "reason": "corrupted"}
        )
        assert exc.details["file"] == "test.xlsx"
        assert exc.details["reason"] == "corrupted"
    
    def test_exception_with_user_message(self):
        """Test exception with custom user message."""
        exc = AppException(
            code=ErrorCode.ERR_VAL_001,
            message="Technical error details",
            user_message="Vui lòng kiểm tra lại file"
        )
        assert exc.message == "Technical error details"
        assert exc.user_message == "Vui lòng kiểm tra lại file"
    
    def test_exception_str(self):
        """Test exception string representation."""
        exc = AppException(
            code=ErrorCode.ERR_DAT_001,
            message="File not found",
            details={"path": "/test/file.xlsx"}
        )
        str_repr = str(exc)
        assert "[ERR_DAT_001]" in str_repr
        assert "File not found" in str_repr
        assert "path=/test/file.xlsx" in str_repr
    
    def test_exception_to_dict(self):
        """Test exception to dictionary conversion."""
        exc = AppException(
            code=ErrorCode.ERR_VAL_005,
            message="Validation failed",
            details={"field": "container_id"},
            user_message="Dữ liệu không hợp lệ"
        )
        d = exc.to_dict()
        assert d["error_code"] == "ERR_VAL_005"
        assert d["message"] == "Validation failed"
        assert d["user_message"] == "Dữ liệu không hợp lệ"
        assert d["details"]["field"] == "container_id"


class TestReconciliationError:
    """Tests for ReconciliationError."""
    
    def test_basic_reconciliation_error(self):
        """Test basic reconciliation error."""
        exc = ReconciliationError("Reconciliation failed")
        assert exc.message == "Reconciliation failed"
        assert exc.code == ErrorCode.ERR_VAL_005  # Default code
    
    def test_reconciliation_error_with_details(self):
        """Test reconciliation error with details."""
        exc = ReconciliationError(
            "Missing data",
            details={"date": "12.01.2026"}
        )
        assert exc.details["date"] == "12.01.2026"


class TestDataLoadError:
    """Tests for DataLoadError and subclasses."""
    
    def test_data_load_error(self):
        """Test basic data load error."""
        exc = DataLoadError("Cannot load file")
        assert exc.code == ErrorCode.ERR_DAT_002
    
    def test_file_not_found_error(self):
        """Test file not found error."""
        exc = FileNotFoundError("/path/to/file.xlsx")
        assert exc.code == ErrorCode.ERR_DAT_001
        assert exc.file_path == "/path/to/file.xlsx"
        assert "File not found" in exc.message
    
    def test_file_read_error(self):
        """Test file read error."""
        exc = FileReadError("/path/to/file.xlsx", "corrupted")
        assert exc.code == ErrorCode.ERR_DAT_002
        assert "Cannot read file" in exc.message
        assert exc.details["reason"] == "corrupted"


class TestValidationError:
    """Tests for ValidationError and subclasses."""
    
    def test_validation_error(self):
        """Test basic validation error."""
        exc = ValidationError("Invalid data")
        assert exc.code == ErrorCode.ERR_VAL_005
    
    def test_missing_column_error(self):
        """Test missing column error."""
        exc = MissingColumnError("Số Container", "TON MOI.xlsx")
        assert exc.code == ErrorCode.ERR_VAL_001
        assert exc.column == "Số Container"
        assert exc.file == "TON MOI.xlsx"
        assert "Missing required column" in exc.message
    
    def test_empty_data_error(self):
        """Test empty data error."""
        exc = EmptyDataError("TON CU.xlsx")
        assert exc.code == ErrorCode.ERR_VAL_002
        assert exc.source == "TON CU.xlsx"
        assert "No data found" in exc.message
    
    def test_invalid_container_error(self):
        """Test invalid container error."""
        exc = InvalidContainerError("ABC123", "too short")
        assert exc.code == ErrorCode.ERR_VAL_003
        assert exc.container_id == "ABC123"
        assert "Invalid container format" in exc.message
    
    def test_invalid_date_error(self):
        """Test invalid date error."""
        exc = InvalidDateError("32.13.2026", "DD.MM.YYYY")
        assert exc.code == ErrorCode.ERR_VAL_004
        assert exc.date_value == "32.13.2026"
        assert "Invalid date format" in exc.message


class TestConfigurationError:
    """Tests for ConfigurationError."""
    
    def test_configuration_error(self):
        """Test configuration error."""
        exc = ConfigurationError("Invalid JSON")
        assert exc.code == ErrorCode.ERR_CFG_001


class TestReportGenerationError:
    """Tests for ReportGenerationError."""
    
    def test_report_generation_error(self):
        """Test report generation error."""
        exc = ReportGenerationError("Cannot create report")
        assert exc.code == ErrorCode.ERR_RPT_001


class TestComparisonError:
    """Tests for ComparisonError."""
    
    def test_comparison_error(self):
        """Test comparison error."""
        exc = ComparisonError("Files cannot be compared")
        assert exc.code == ErrorCode.ERR_CMP_001


class TestExceptionRaising:
    """Tests for raising and catching exceptions."""
    
    def test_raise_and_catch_app_exception(self):
        """Test raising and catching AppException."""
        with pytest.raises(AppException) as exc_info:
            raise AppException(
                code=ErrorCode.ERR_DAT_001,
                message="Test error"
            )
        assert exc_info.value.code == ErrorCode.ERR_DAT_001
    
    def test_catch_subclass_as_parent(self):
        """Test catching subclass as parent type."""
        with pytest.raises(ReconciliationError):
            raise ValidationError("Test")
        
        with pytest.raises(DataLoadError):
            raise FileNotFoundError("/test/path")
    
    def test_exception_inheritance(self):
        """Test exception inheritance chain."""
        exc = MissingColumnError("col", "file.xlsx")
        assert isinstance(exc, MissingColumnError)
        assert isinstance(exc, ValidationError)
        assert isinstance(exc, ReconciliationError)
        assert isinstance(exc, AppException)
        assert isinstance(exc, Exception)
