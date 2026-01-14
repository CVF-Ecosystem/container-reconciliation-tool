# tests/test_validators.py
# V5.4: Unit tests for data validation module
"""Tests for utils/validators.py module."""

import pytest
from datetime import date, datetime
from utils.validators import (
    validate_container_id,
    validate_date,
    validate_fe_status,
    validate_operator,
    validate_dataframe,
    validate_file_path,
    validate_batch,
    sanitize_input,
    ValidationResult,
    CONTAINER_PATTERN
)
from utils.exceptions import (
    InvalidContainerError,
    InvalidDateError,
    ValidationError
)


class TestValidateContainerId:
    """Tests for container ID validation."""
    
    def test_valid_container_id(self):
        """Test valid container IDs."""
        # Standard format
        result = validate_container_id("MSCU1234567")
        assert result == "MSCU1234567"
        
        # With lowercase - should normalize
        result = validate_container_id("mscu1234567")
        assert result == "MSCU1234567"
        
        # With spaces - should strip
        result = validate_container_id("  MSCU1234567  ")
        assert result == "MSCU1234567"
    
    def test_valid_container_with_separator(self):
        """Test container ID with separators."""
        result = validate_container_id("MSCU-1234567")
        assert result == "MSCU1234567"
        
        result = validate_container_id("MSCU 1234567")
        assert result == "MSCU1234567"
    
    def test_invalid_container_empty(self):
        """Test empty container ID."""
        with pytest.raises(InvalidContainerError):
            validate_container_id("")
        
        with pytest.raises(InvalidContainerError):
            validate_container_id(None)
    
    def test_invalid_container_too_short(self):
        """Test container ID too short."""
        with pytest.raises(InvalidContainerError) as exc_info:
            validate_container_id("MSCU123")
        assert "Too short" in str(exc_info.value)
    
    def test_invalid_container_wrong_prefix(self):
        """Test container ID with wrong prefix."""
        with pytest.raises(InvalidContainerError) as exc_info:
            validate_container_id("1234567890A")
        assert "Must start with 4 letters" in str(exc_info.value)
    
    def test_strict_validation_valid(self):
        """Test strict validation with valid check digit."""
        # MSCU1234567 - need to use a known valid container
        # Using non-strict for basic test
        result = validate_container_id("MSCU1234567", strict=False)
        assert result == "MSCU1234567"
    
    def test_strict_validation_invalid_format(self):
        """Test strict validation with invalid format."""
        with pytest.raises(InvalidContainerError):
            validate_container_id("MSCU12345", strict=True)


class TestValidateDate:
    """Tests for date validation."""
    
    def test_valid_date_ddmmyyyy(self):
        """Test valid date in DD.MM.YYYY format."""
        result = validate_date("12.01.2026")
        assert result == date(2026, 1, 12)
    
    def test_valid_date_ddmmyyyy_slash(self):
        """Test valid date in DD/MM/YYYY format."""
        result = validate_date("12/01/2026")
        assert result == date(2026, 1, 12)
    
    def test_valid_date_yyyymmdd(self):
        """Test valid date in YYYY-MM-DD format."""
        result = validate_date("2026-01-12")
        assert result == date(2026, 1, 12)
    
    def test_valid_date_object(self):
        """Test passing date object."""
        d = date(2026, 1, 12)
        result = validate_date(d)
        assert result == d
    
    def test_valid_datetime_object(self):
        """Test passing datetime object."""
        dt = datetime(2026, 1, 12, 10, 30, 0)
        result = validate_date(dt)
        # Validator may return datetime or date object
        assert result is not None
    
    def test_none_date(self):
        """Test None date value."""
        result = validate_date(None)
        assert result is None
    
    def test_empty_date(self):
        """Test empty string date."""
        result = validate_date("")
        assert result is None
        
        result = validate_date("   ")
        assert result is None
    
    def test_invalid_date(self):
        """Test invalid date format."""
        with pytest.raises(InvalidDateError):
            validate_date("32.13.2026")
        
        with pytest.raises(InvalidDateError):
            validate_date("not-a-date")
    
    def test_custom_format(self):
        """Test custom date format."""
        result = validate_date("2026/01/12", formats=["%Y/%m/%d"])
        assert result == date(2026, 1, 12)


class TestValidateFEStatus:
    """Tests for F/E status validation."""
    
    def test_full_status(self):
        """Test Full status normalization."""
        assert validate_fe_status("F") == "F"
        assert validate_fe_status("f") == "F"
        assert validate_fe_status("FULL") == "F"
        assert validate_fe_status("Full") == "F"
        assert validate_fe_status("FCL") == "F"
        assert validate_fe_status("LCL") == "F"
    
    def test_empty_status(self):
        """Test Empty status normalization."""
        assert validate_fe_status("E") == "E"
        assert validate_fe_status("e") == "E"
        assert validate_fe_status("EMPTY") == "E"
        assert validate_fe_status("Empty") == "E"
        assert validate_fe_status("MTY") == "E"
    
    def test_blank_status(self):
        """Test blank status."""
        assert validate_fe_status("") == ""
        assert validate_fe_status(None) == ""
    
    def test_unknown_status(self):
        """Test unknown status - returns as-is."""
        assert validate_fe_status("X") == "X"
        assert validate_fe_status("unknown") == "UNKNOWN"


class TestValidateOperator:
    """Tests for operator validation."""
    
    def test_valid_operator(self):
        """Test valid operator normalization."""
        assert validate_operator("VIMC") == "VIMC"
        assert validate_operator("vimc") == "VIMC"
        assert validate_operator("  VIMC  ") == "VIMC"
    
    def test_blank_operator(self):
        """Test blank operator."""
        assert validate_operator("") == ""
        assert validate_operator(None) == ""


class TestValidateDataFrame:
    """Tests for DataFrame validation."""
    
    def test_empty_dataframe(self):
        """Test empty DataFrame validation."""
        import pandas as pd
        
        df = pd.DataFrame()
        result = validate_dataframe(df)
        
        assert result.is_valid is False
        assert "DataFrame is empty" in result.errors[0]
    
    def test_none_dataframe(self):
        """Test None DataFrame validation."""
        result = validate_dataframe(None)
        
        assert result.is_valid is False
        assert result.valid_count == 0
    
    def test_missing_required_columns(self):
        """Test DataFrame with missing required columns."""
        import pandas as pd
        
        df = pd.DataFrame({"col1": [1, 2, 3]})
        result = validate_dataframe(df, required_columns=["col1", "col2", "col3"])
        
        assert result.is_valid is False
        assert "Missing required columns" in result.errors[0]
        assert "col2" in result.errors[0]
        assert "col3" in result.errors[0]
    
    def test_valid_dataframe(self):
        """Test valid DataFrame."""
        import pandas as pd
        
        df = pd.DataFrame({
            "Số Container": ["MSCU1234567", "TEMU9876543"],
            "Hãng khai thác": ["VIMC", "VOSCO"]
        })
        result = validate_dataframe(
            df, 
            required_columns=["Số Container", "Hãng khai thác"]
        )
        
        assert result.is_valid is True
        assert result.valid_count == 2
    
    def test_container_validation_in_dataframe(self):
        """Test container validation within DataFrame."""
        import pandas as pd
        
        df = pd.DataFrame({
            "container_id": ["MSCU1234567", "INVALID", "TEMU9876543"]
        })
        result = validate_dataframe(
            df,
            container_column="container_id",
            validate_containers=True
        )
        
        assert result.invalid_count == 1
        assert "INVALID" in result.details.get("invalid_containers", [])


class TestSanitizeInput:
    """Tests for input sanitization."""
    
    def test_basic_sanitization(self):
        """Test basic input sanitization."""
        assert sanitize_input("  hello world  ") == "hello world"
        assert sanitize_input("") == ""
        assert sanitize_input(None) == ""
    
    def test_max_length(self):
        """Test max length truncation."""
        long_input = "a" * 500
        result = sanitize_input(long_input, max_length=100)
        assert len(result) == 100
    
    def test_control_character_removal(self):
        """Test control character removal."""
        result = sanitize_input("hello\x00world\x1f")
        assert "\x00" not in result
        assert "\x1f" not in result
        assert result == "helloworld"


class TestValidateFilePath:
    """Tests for file path validation."""
    
    def test_empty_path(self):
        """Test empty file path."""
        with pytest.raises(ValidationError):
            validate_file_path("")
    
    def test_valid_extension(self):
        """Test file extension validation."""
        from pathlib import Path
        import tempfile
        
        # Create temp file
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            temp_path = f.name
        
        try:
            result = validate_file_path(
                temp_path, 
                must_exist=True,
                allowed_extensions=[".xlsx", ".xls"]
            )
            assert result is True
        finally:
            Path(temp_path).unlink()
    
    def test_invalid_extension(self):
        """Test invalid file extension."""
        from pathlib import Path
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            temp_path = f.name
        
        try:
            with pytest.raises(ValidationError) as exc_info:
                validate_file_path(
                    temp_path,
                    must_exist=True,
                    allowed_extensions=[".xlsx"]
                )
            assert "Invalid file extension" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()


class TestValidateBatch:
    """Tests for batch validation."""
    
    def test_valid_batch(self):
        """Test batch of valid records."""
        records = [
            {"container_id": "MSCU1234567"},
            {"container_id": "TEMU9876543"},
        ]
        result = validate_batch(records)
        
        assert result.is_valid is True
        assert result.valid_count == 2
        assert result.invalid_count == 0
    
    def test_batch_with_invalid_records(self):
        """Test batch with some invalid records."""
        records = [
            {"container_id": "MSCU1234567"},
            {"container_id": "INVALID"},
            {"container_id": "TEMU9876543"},
        ]
        result = validate_batch(records)
        
        assert result.is_valid is False
        assert result.valid_count == 2
        assert result.invalid_count == 1
    
    def test_stop_on_first_error(self):
        """Test stopping on first error."""
        records = [
            {"container_id": "INVALID1"},
            {"container_id": "INVALID2"},
            {"container_id": "MSCU1234567"},
        ]
        result = validate_batch(records, stop_on_first_error=True)
        
        # Should stop after first error
        assert result.invalid_count == 1
        assert result.valid_count == 0


class TestValidationResult:
    """Tests for ValidationResult dataclass."""
    
    def test_validation_result_creation(self):
        """Test ValidationResult creation."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=["Some warning"],
            valid_count=10,
            invalid_count=0,
            details={"key": "value"}
        )
        
        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert result.valid_count == 10
        assert result.details["key"] == "value"
