# File: exceptions.py — @2026 v1.0
# Custom exception classes for Container Inventory Reconciliation Tool V5.4
# Provides specific error handling with error codes and translation support

"""
Hierarchy:
    AppException (Base - with error codes)
    └── ReconciliationError
        ├── DataLoadError
        │   ├── FileNotFoundError
        │   └── FileReadError
        ├── ValidationError
        │   ├── MissingColumnError
        │   └── EmptyDataError
        ├── ConfigurationError
        ├── ReportGenerationError
        └── ComparisonError

Error Code Format: ERR_XXX_NNN
    XXX = Category (DAT=Data, VAL=Validation, CFG=Config, RPT=Report, CMP=Compare)
    NNN = Number
"""

from enum import Enum
from typing import Optional, Dict, Any


class ErrorCode(Enum):
    """Centralized error codes for the application."""
    # Data errors (DAT)
    ERR_DAT_001 = "ERR_DAT_001"  # File not found
    ERR_DAT_002 = "ERR_DAT_002"  # Cannot read file
    ERR_DAT_003 = "ERR_DAT_003"  # Invalid file format
    ERR_DAT_004 = "ERR_DAT_004"  # File corrupted
    ERR_DAT_005 = "ERR_DAT_005"  # Permission denied
    
    # Validation errors (VAL)
    ERR_VAL_001 = "ERR_VAL_001"  # Missing required column
    ERR_VAL_002 = "ERR_VAL_002"  # Empty data
    ERR_VAL_003 = "ERR_VAL_003"  # Invalid container format
    ERR_VAL_004 = "ERR_VAL_004"  # Invalid date format
    ERR_VAL_005 = "ERR_VAL_005"  # Business rule violation
    
    # Configuration errors (CFG)
    ERR_CFG_001 = "ERR_CFG_001"  # Config file not found
    ERR_CFG_002 = "ERR_CFG_002"  # Invalid JSON format
    ERR_CFG_003 = "ERR_CFG_003"  # Missing required setting
    
    # Report errors (RPT)
    ERR_RPT_001 = "ERR_RPT_001"  # Cannot create report
    ERR_RPT_002 = "ERR_RPT_002"  # Disk full
    ERR_RPT_003 = "ERR_RPT_003"  # Invalid output path
    
    # Comparison errors (CMP)
    ERR_CMP_001 = "ERR_CMP_001"  # Cannot load comparison file
    ERR_CMP_002 = "ERR_CMP_002"  # No container column found
    ERR_CMP_003 = "ERR_CMP_003"  # Comparison failed


class AppException(Exception):
    """
    Base exception class with error code support.
    
    Attributes:
        code: ErrorCode enum value
        message: Human-readable error description
        details: Optional dictionary with additional context
        user_message: Optional user-friendly message (for UI display)
    """
    def __init__(
        self, 
        code: ErrorCode,
        message: str, 
        details: Dict[str, Any] = None,
        user_message: str = None
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        self.user_message = user_message or message
        super().__init__(self.message)
    
    def __str__(self) -> str:
        base = f"[{self.code.value}] {self.message}"
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{base} [{detail_str}]"
        return base
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error_code": self.code.value,
            "message": self.message,
            "user_message": self.user_message,
            "details": self.details
        }


class ReconciliationError(AppException):
    """
    Base exception class for all reconciliation-related errors.
    
    Attributes:
        message: Human-readable error description
        details: Optional dictionary with additional context
    """
    def __init__(self, message: str, details: dict = None, code: ErrorCode = None):
        super().__init__(
            code=code or ErrorCode.ERR_VAL_005,
            message=message,
            details=details
        )


class DataLoadError(ReconciliationError):
    """
    Raised when data loading from Excel files fails.
    
    Common causes:
        - File not found
        - Invalid file format
        - Permission denied
        - Corrupted file
    
    Example:
        >>> raise DataLoadError("Cannot read file", {"file": "TON MOI.xlsx", "reason": "corrupted"})
    """
    def __init__(self, message: str, details: dict = None, code: ErrorCode = None):
        super().__init__(message, details, code or ErrorCode.ERR_DAT_002)


class ValidationError(ReconciliationError):
    """
    Raised when data validation fails.
    
    Common causes:
        - Missing required columns
        - Invalid data types
        - Empty required fields
        - Business rule violations
    
    Example:
        >>> raise ValidationError("Missing column", {"column": "Số Container", "file": "GATE IN.xlsx"})
    """
    def __init__(self, message: str, details: dict = None, code: ErrorCode = None):
        super().__init__(message, details, code or ErrorCode.ERR_VAL_005)


class ConfigurationError(ReconciliationError):
    """
    Raised when configuration is invalid or missing.
    
    Common causes:
        - Missing config file
        - Invalid JSON format
        - Missing required settings
    
    Example:
        >>> raise ConfigurationError("Invalid config", {"file": "config_mappings.json"})
    """
    def __init__(self, message: str, details: dict = None, code: ErrorCode = None):
        super().__init__(message, details, code or ErrorCode.ERR_CFG_001)


class ReportGenerationError(ReconciliationError):
    """
    Raised when report generation fails.
    
    Common causes:
        - Disk full
        - Permission denied
        - Invalid output path
    
    Example:
        >>> raise ReportGenerationError("Cannot write report", {"path": "/output/report.xlsx"})
    """
    def __init__(self, message: str, details: dict = None, code: ErrorCode = None):
        super().__init__(message, details, code or ErrorCode.ERR_RPT_001)


class ComparisonError(ReconciliationError):
    """
    Raised when file comparison fails.
    
    Example:
        >>> raise ComparisonError("Cannot compare files", {"reason": "no container column"})
    """
    def __init__(self, message: str, details: dict = None, code: ErrorCode = None):
        super().__init__(message, details, code or ErrorCode.ERR_CMP_001)


class FileNotFoundError(DataLoadError):
    """Raised when a required input file is not found."""
    def __init__(self, file_path: str):
        super().__init__(
            f"File not found: {file_path}",
            {"file": file_path},
            ErrorCode.ERR_DAT_001
        )
        self.file_path = file_path


class FileReadError(DataLoadError):
    """Raised when a file cannot be read."""
    def __init__(self, file_path: str, reason: str = None):
        super().__init__(
            f"Cannot read file: {file_path}",
            {"file": file_path, "reason": reason or "unknown"},
            ErrorCode.ERR_DAT_002
        )


class MissingColumnError(ValidationError):
    """Raised when a required column is missing from a DataFrame."""
    
    def __init__(self, column: str, file: str):
        super().__init__(
            f"Missing required column '{column}'",
            {"column": column, "file": file},
            ErrorCode.ERR_VAL_001
        )
        self.column = column
        self.file = file


class EmptyDataError(ValidationError):
    """Raised when required data is empty."""
    
    def __init__(self, source: str):
        super().__init__(
            f"No data found in '{source}'",
            {"source": source},
            ErrorCode.ERR_VAL_002
        )
        self.source = source


class InvalidContainerError(ValidationError):
    """Raised when container ID format is invalid."""
    
    def __init__(self, container_id: str, reason: str = None):
        super().__init__(
            f"Invalid container format: {container_id}",
            {"container_id": container_id, "reason": reason or "does not match ISO 6346"},
            ErrorCode.ERR_VAL_003
        )
        self.container_id = container_id


class InvalidDateError(ValidationError):
    """Raised when date format is invalid."""
    
    def __init__(self, date_value: str, expected_format: str = None):
        super().__init__(
            f"Invalid date format: {date_value}",
            {"date_value": date_value, "expected_format": expected_format or "DD.MM.YYYY"},
            ErrorCode.ERR_VAL_004
        )
        self.date_value = date_value
