# File: utils/data_validator.py
"""
Data Validator Module - Kiểm tra tính hợp lệ của dữ liệu đầu vào.

V5.0 - Phase 1: Stability
"""

import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import pandas as pd

try:
    import config
    from config import Col
except ImportError:
    Col = None


@dataclass
class ValidationResult:
    """Kết quả validation."""
    file_type: str
    filename: str
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    row_count: int = 0


# Required columns for each file type
REQUIRED_COLUMNS = {
    'ton_cu': [Col.CONTAINER if Col else 'Số Container'],
    'ton_moi': [Col.CONTAINER if Col else 'Số Container'],
    'gate_combined': [Col.CONTAINER if Col else 'Số Container', Col.VAO_RA if Col else 'Vào/Ra'],
    'nhapxuat_combined': [Col.CONTAINER if Col else 'Số Container'],
}


def validate_excel_file(filepath: Path) -> Tuple[bool, str]:
    """
    Kiểm tra file Excel có thể đọc được.
    
    Returns:
        Tuple (is_valid, error_message)
    """
    try:
        if not filepath.exists():
            return False, f"File not found: {filepath}"
        
        if filepath.stat().st_size == 0:
            return False, "File is empty (0 bytes)"
        
        # Try to read first few rows
        df = pd.read_excel(filepath, nrows=5)
        
        if df.empty:
            return False, "File contains no data"
        
        return True, "OK"
    
    except Exception as e:
        return False, f"Cannot read Excel file: {e}"


def validate_required_columns(df: pd.DataFrame, file_type: str) -> Tuple[bool, List[str]]:
    """
    Kiểm tra các cột bắt buộc có tồn tại.
    
    Returns:
        Tuple (is_valid, list of missing columns)
    """
    required = REQUIRED_COLUMNS.get(file_type, [])
    if not required:
        return True, []
    
    missing = []
    for col in required:
        if col and col not in df.columns:
            missing.append(col)
    
    return len(missing) == 0, missing


def validate_container_format(df: pd.DataFrame, container_col: str = None) -> Tuple[int, int]:
    """
    Kiểm tra format số container.
    
    Container ID format: 4 letters + 7 digits (e.g., MSCU1234567)
    
    Returns:
        Tuple (valid_count, invalid_count)
    """
    import re
    
    if container_col is None:
        container_col = Col.CONTAINER if Col else 'Số Container'
    
    if container_col not in df.columns:
        return 0, 0
    
    pattern = re.compile(r'^[A-Z]{4}\d{7}$')
    
    valid_count = 0
    invalid_count = 0
    
    for val in df[container_col].dropna():
        val_str = str(val).strip().upper()
        if pattern.match(val_str):
            valid_count += 1
        else:
            invalid_count += 1
    
    return valid_count, invalid_count


def validate_file(filepath: Path, file_type: str) -> ValidationResult:
    """
    Validate một file đầu vào.
    
    Args:
        filepath: Đường dẫn file
        file_type: Loại file (ton_cu, ton_moi, gate_combined, etc.)
    
    Returns:
        ValidationResult
    """
    errors = []
    warnings = []
    row_count = 0
    
    # Check file can be read
    is_readable, msg = validate_excel_file(filepath)
    if not is_readable:
        return ValidationResult(
            file_type=file_type,
            filename=filepath.name,
            is_valid=False,
            errors=[msg],
            warnings=[],
            row_count=0
        )
    
    try:
        df = pd.read_excel(filepath)
        row_count = len(df)
        
        # Check required columns
        cols_valid, missing = validate_required_columns(df, file_type)
        if not cols_valid:
            errors.append(f"Missing columns: {', '.join(missing)}")
        
        # Check container format
        valid_ct, invalid_ct = validate_container_format(df)
        if invalid_ct > 0:
            warnings.append(f"{invalid_ct} containers with invalid format")
        
        # Check for duplicates
        container_col = Col.CONTAINER if Col else 'Số Container'
        if container_col in df.columns:
            dup_count = df[container_col].duplicated().sum()
            if dup_count > 0:
                warnings.append(f"{dup_count} duplicate containers")
        
        # Check empty file
        if row_count == 0:
            errors.append("File contains no data rows")
        elif row_count < 10:
            warnings.append(f"File has only {row_count} rows")
        
    except Exception as e:
        errors.append(f"Validation error: {e}")
    
    return ValidationResult(
        file_type=file_type,
        filename=filepath.name,
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        row_count=row_count
    )


def validate_all_files(files_dict: Dict[str, str], input_dir: Path) -> List[ValidationResult]:
    """
    Validate tất cả files trong dict.
    
    Args:
        files_dict: Dictionary {file_type: filename}
        input_dir: Thư mục chứa files
    
    Returns:
        List of ValidationResult
    """
    results = []
    
    for file_type, filename in files_dict.items():
        filepath = input_dir / filename
        result = validate_file(filepath, file_type)
        results.append(result)
        
        # Log result
        if result.is_valid:
            logging.info(f"[Validate] ✅ {filename}: {result.row_count} rows")
        else:
            logging.warning(f"[Validate] ❌ {filename}: {', '.join(result.errors)}")
        
        for warning in result.warnings:
            logging.warning(f"[Validate] ⚠️ {filename}: {warning}")
    
    return results


def format_validation_report(results: List[ValidationResult]) -> str:
    """Format validation results as string."""
    lines = ["=" * 50, "DATA VALIDATION REPORT", "=" * 50]
    
    for result in results:
        status = "✅" if result.is_valid else "❌"
        lines.append(f"\n{status} {result.filename} ({result.file_type})")
        lines.append(f"   Rows: {result.row_count}")
        
        for err in result.errors:
            lines.append(f"   ❌ ERROR: {err}")
        
        for warn in result.warnings:
            lines.append(f"   ⚠️ WARNING: {warn}")
    
    lines.append("\n" + "=" * 50)
    
    valid_count = sum(1 for r in results if r.is_valid)
    total_count = len(results)
    lines.append(f"Result: {valid_count}/{total_count} files valid")
    
    return "\n".join(lines)
