# File: utils/validators.py
# @2026 v1.0: Data validation layer using Pydantic for container data validation
"""
Validation module for container inventory reconciliation.
Provides:
- Container ID format validation (ISO 6346)
- Date/time validation
- Business rule validation
- DataFrame validation
"""

import re
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass
from enum import Enum

try:
    from pydantic import BaseModel, validator, Field, root_validator
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    logging.warning("Pydantic not installed. Using basic validation only.")

from utils.exceptions import (
    ValidationError, 
    InvalidContainerError, 
    InvalidDateError,
    ErrorCode
)


# ============ CONSTANTS ============

# ISO 6346 Container ID format: 4 letters (owner) + 6 digits + 1 check digit
CONTAINER_PATTERN = re.compile(r'^[A-Z]{4}\d{7}$')

# Valid F/E statuses
VALID_FE_STATUSES = {'F', 'E', 'FULL', 'EMPTY', 'MTY', 'FCL', 'LCL'}

# Valid container sizes
VALID_SIZES = {'20', '40', '45', '20\'', '40\'', '45\'', '20GP', '40GP', '40HC', '45HC'}

# Valid movement types
VALID_MOVE_TYPES = {
    'GATE_IN', 'GATE_OUT', 'GATE IN', 'GATE OUT',
    'DISCHARGE', 'LOADING', 'NHẬP', 'XUẤT',
    'SHIFT', 'SHIFTING', 'ĐẢO CHUYỂN',
    'CFS_IN', 'CFS_OUT', 'ĐÓNG HÀNG', 'RÚT HÀNG'
}


# ============ BASIC VALIDATORS ============

def validate_container_id(container_id: str, strict: bool = False) -> str:
    """
    Validate container ID format.
    
    Args:
        container_id: Container ID to validate
        strict: If True, require exact ISO 6346 format with check digit
        
    Returns:
        Normalized container ID (uppercase, stripped)
        
    Raises:
        InvalidContainerError: If format is invalid
    """
    if not container_id:
        raise InvalidContainerError("", "Container ID cannot be empty")
    
    # Normalize
    normalized = str(container_id).strip().upper()
    
    # Remove common separators
    normalized = normalized.replace('-', '').replace(' ', '')
    
    if strict:
        # Strict ISO 6346 validation with check digit
        if not CONTAINER_PATTERN.match(normalized):
            raise InvalidContainerError(
                container_id, 
                f"Must be 4 letters + 7 digits (got: {normalized})"
            )
        
        # Validate check digit
        if not _validate_check_digit(normalized):
            raise InvalidContainerError(
                container_id,
                "Invalid check digit"
            )
    else:
        # Basic validation - at least 10-11 characters, starts with letters
        if len(normalized) < 10:
            raise InvalidContainerError(
                container_id,
                f"Too short: {len(normalized)} characters (minimum 10)"
            )
        
        if not normalized[:4].isalpha():
            raise InvalidContainerError(
                container_id,
                "Must start with 4 letters"
            )
    
    return normalized


def _validate_check_digit(container_id: str) -> bool:
    """
    Validate ISO 6346 check digit.
    
    The check digit is calculated using the formula defined in ISO 6346.
    """
    if len(container_id) != 11:
        return False
    
    # Letter to number mapping (ISO 6346)
    letter_values = {
        'A': 10, 'B': 12, 'C': 13, 'D': 14, 'E': 15, 'F': 16, 'G': 17,
        'H': 18, 'I': 19, 'J': 20, 'K': 21, 'L': 23, 'M': 24, 'N': 25,
        'O': 26, 'P': 27, 'Q': 28, 'R': 29, 'S': 30, 'T': 31, 'U': 32,
        'V': 34, 'W': 35, 'X': 36, 'Y': 37, 'Z': 38
    }
    
    try:
        total = 0
        for i, char in enumerate(container_id[:10]):
            if char.isalpha():
                value = letter_values.get(char, 0)
            else:
                value = int(char)
            total += value * (2 ** i)
        
        check_digit = total % 11
        if check_digit == 10:
            check_digit = 0
        
        return check_digit == int(container_id[10])
    except (ValueError, KeyError):
        return False


def validate_date(date_value: Any, formats: List[str] = None) -> Optional[date]:
    """
    Validate and parse date from various formats.
    
    Args:
        date_value: Date value to validate (str, datetime, date)
        formats: List of expected formats to try
        
    Returns:
        Parsed date object or None if invalid
        
    Raises:
        InvalidDateError: If date cannot be parsed
    """
    if date_value is None or (isinstance(date_value, str) and not date_value.strip()):
        return None
    
    if isinstance(date_value, date):
        return date_value
    
    if isinstance(date_value, datetime):
        return date_value.date()
    
    # Default formats to try
    if formats is None:
        formats = [
            '%d.%m.%Y',      # 12.01.2026
            '%d/%m/%Y',      # 12/01/2026
            '%Y-%m-%d',      # 2026-01-12
            '%d-%m-%Y',      # 12-01-2026
            '%d.%m.%y',      # 12.01.26
            '%Y/%m/%d',      # 2026/01/12
        ]
    
    date_str = str(date_value).strip()
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    raise InvalidDateError(date_str, " or ".join(formats[:3]))


def validate_fe_status(status: str) -> str:
    """
    Validate and normalize F/E (Full/Empty) status.
    
    Returns:
        'F' or 'E'
    """
    if not status:
        return ''
    
    normalized = str(status).strip().upper()
    
    if normalized in {'F', 'FULL', 'FCL', 'LCL'}:
        return 'F'
    elif normalized in {'E', 'EMPTY', 'MTY'}:
        return 'E'
    else:
        return normalized  # Return as-is if unknown


def validate_operator(operator: str) -> str:
    """
    Validate and normalize operator (shipping line) code.
    
    Returns:
        Uppercase operator code
    """
    if not operator:
        return ''
    
    return str(operator).strip().upper()


# ============ PYDANTIC MODELS ============

if PYDANTIC_AVAILABLE:
    
    class ContainerRecord(BaseModel):
        """Pydantic model for container record validation."""
        
        container_id: str = Field(..., min_length=10, max_length=15)
        operator: Optional[str] = None
        fe_status: Optional[str] = None
        iso_size: Optional[str] = None
        location: Optional[str] = None
        entry_date: Optional[date] = None
        
        class Config:
            extra = 'allow'  # Allow additional fields
        
        @validator('container_id', pre=True)
        def validate_container(cls, v):
            return validate_container_id(v, strict=False)
        
        @validator('fe_status', pre=True)
        def validate_fe(cls, v):
            if v:
                return validate_fe_status(v)
            return v
        
        @validator('operator', pre=True)
        def validate_opr(cls, v):
            if v:
                return validate_operator(v)
            return v
        
        @validator('entry_date', pre=True)
        def validate_entry_date(cls, v):
            if v:
                return validate_date(v)
            return v
    
    
    class MovementRecord(BaseModel):
        """Pydantic model for container movement record validation."""
        
        container_id: str = Field(..., min_length=10)
        move_type: str
        timestamp: Optional[datetime] = None
        operator: Optional[str] = None
        vessel: Optional[str] = None
        location: Optional[str] = None
        fe_status: Optional[str] = None
        
        class Config:
            extra = 'allow'
        
        @validator('container_id', pre=True)
        def validate_container(cls, v):
            return validate_container_id(v, strict=False)
        
        @validator('move_type', pre=True)
        def validate_move_type(cls, v):
            if not v:
                raise ValueError("Move type cannot be empty")
            normalized = str(v).strip().upper()
            return normalized


# ============ DATAFRAME VALIDATORS ============

@dataclass
class ValidationResult:
    """Result of a validation operation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    valid_count: int
    invalid_count: int
    details: Dict[str, Any]


def validate_dataframe(
    df,
    required_columns: List[str] = None,
    container_column: str = None,
    validate_containers: bool = True,
    strict_container: bool = False
) -> ValidationResult:
    """
    Validate a pandas DataFrame.
    
    Args:
        df: DataFrame to validate
        required_columns: List of required column names
        container_column: Name of container ID column (for container validation)
        validate_containers: Whether to validate container IDs
        strict_container: Use strict ISO 6346 validation
        
    Returns:
        ValidationResult with validation outcome
    """
    import pandas as pd
    
    errors = []
    warnings = []
    details = {}
    
    # Check if empty
    if df is None or df.empty:
        return ValidationResult(
            is_valid=False,
            errors=["DataFrame is empty"],
            warnings=[],
            valid_count=0,
            invalid_count=0,
            details={}
        )
    
    # Check required columns
    if required_columns:
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            errors.append(f"Missing required columns: {missing}")
    
    # Validate containers if specified
    valid_count = len(df)
    invalid_count = 0
    invalid_containers = []
    
    if validate_containers and container_column and container_column in df.columns:
        for idx, container in df[container_column].items():
            try:
                if pd.notna(container):
                    validate_container_id(str(container), strict=strict_container)
            except InvalidContainerError as e:
                invalid_count += 1
                if len(invalid_containers) < 10:  # Limit examples
                    invalid_containers.append(str(container))
        
        valid_count = len(df) - invalid_count
        
        if invalid_containers:
            warnings.append(
                f"Found {invalid_count} invalid container IDs. "
                f"Examples: {invalid_containers[:5]}"
            )
        
        details['invalid_containers'] = invalid_containers
    
    # Check for null values in important columns
    if required_columns:
        null_counts = {}
        for col in required_columns:
            if col in df.columns:
                null_count = df[col].isna().sum()
                if null_count > 0:
                    null_counts[col] = null_count
        
        if null_counts:
            warnings.append(f"Null values found: {null_counts}")
            details['null_counts'] = null_counts
    
    is_valid = len(errors) == 0
    
    return ValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        valid_count=valid_count,
        invalid_count=invalid_count,
        details=details
    )


# ============ UTILITY FUNCTIONS ============

def sanitize_input(value: str, max_length: int = 255) -> str:
    """
    Sanitize user input to prevent injection attacks.
    
    Args:
        value: Input string to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
    """
    if not value:
        return ''
    
    # Convert to string and strip
    sanitized = str(value).strip()
    
    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    # Remove control characters
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', sanitized)
    
    return sanitized


def validate_file_path(path: str, must_exist: bool = True, allowed_extensions: List[str] = None) -> bool:
    """
    Validate a file path.
    
    Args:
        path: File path to validate
        must_exist: Whether file must exist
        allowed_extensions: List of allowed file extensions
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If path is invalid
    """
    from pathlib import Path as PathLib
    
    if not path:
        raise ValidationError("File path cannot be empty", code=ErrorCode.ERR_VAL_005)
    
    path_obj = PathLib(path)
    
    if must_exist and not path_obj.exists():
        raise ValidationError(
            f"File does not exist: {path}",
            {"path": path},
            ErrorCode.ERR_DAT_001
        )
    
    if allowed_extensions:
        ext = path_obj.suffix.lower()
        if ext not in [e.lower() for e in allowed_extensions]:
            raise ValidationError(
                f"Invalid file extension: {ext}. Allowed: {allowed_extensions}",
                {"path": path, "extension": ext, "allowed": allowed_extensions},
                ErrorCode.ERR_VAL_005
            )
    
    return True


# ============ BATCH VALIDATION ============

def validate_batch(
    records: List[Dict[str, Any]],
    container_key: str = 'container_id',
    stop_on_first_error: bool = False
) -> ValidationResult:
    """
    Validate a batch of records.
    
    Args:
        records: List of dictionaries to validate
        container_key: Key for container ID in each record
        stop_on_first_error: Stop validation on first error
        
    Returns:
        ValidationResult with aggregated results
    """
    errors = []
    warnings = []
    valid_count = 0
    invalid_count = 0
    invalid_records = []
    
    for i, record in enumerate(records):
        try:
            container_id = record.get(container_key)
            if container_id:
                validate_container_id(container_id, strict=False)
            valid_count += 1
        except InvalidContainerError as e:
            invalid_count += 1
            if len(invalid_records) < 20:
                invalid_records.append({
                    'index': i,
                    'container_id': record.get(container_key),
                    'error': str(e)
                })
            
            if stop_on_first_error:
                errors.append(f"Validation stopped at record {i}: {e}")
                break
    
    if invalid_records:
        errors.append(f"Found {invalid_count} invalid records")
    
    return ValidationResult(
        is_valid=invalid_count == 0,
        errors=errors,
        warnings=warnings,
        valid_count=valid_count,
        invalid_count=invalid_count,
        details={'invalid_records': invalid_records}
    )
