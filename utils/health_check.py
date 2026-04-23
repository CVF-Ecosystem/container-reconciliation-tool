# File: utils/health_check.py
"""
Health Check Module - Kiểm tra sức khỏe hệ thống khi khởi động.

V5.0 - Phase 1: Stability
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class HealthCheckResult:
    """Kết quả kiểm tra sức khỏe."""
    name: str
    passed: bool
    message: str
    critical: bool = True  # If critical and failed, app should not start


def check_directory_exists(path: Path, create_if_missing: bool = True) -> HealthCheckResult:
    """Kiểm tra thư mục tồn tại."""
    if path.exists():
        return HealthCheckResult(
            name=f"Directory: {path.name}",
            passed=True,
            message=f"OK - {path}"
        )
    
    if create_if_missing:
        try:
            path.mkdir(parents=True, exist_ok=True)
            return HealthCheckResult(
                name=f"Directory: {path.name}",
                passed=True,
                message=f"Created - {path}"
            )
        except Exception as e:
            return HealthCheckResult(
                name=f"Directory: {path.name}",
                passed=False,
                message=f"Cannot create: {e}"
            )
    
    return HealthCheckResult(
        name=f"Directory: {path.name}",
        passed=False,
        message=f"Not found: {path}"
    )


def check_disk_space(path: Path, min_mb: int = 100) -> HealthCheckResult:
    """Kiểm tra dung lượng ổ đĩa."""
    try:
        import shutil
        total, used, free = shutil.disk_usage(path)
        free_mb = free // (1024 * 1024)
        free_gb = free_mb / 1024
        
        if free_mb >= min_mb:
            return HealthCheckResult(
                name="Disk Space",
                passed=True,
                message=f"OK - {free_gb:.1f} GB free",
                critical=False
            )
        else:
            return HealthCheckResult(
                name="Disk Space",
                passed=False,
                message=f"LOW - Only {free_mb} MB free (need {min_mb} MB)",
                critical=True
            )
    except Exception as e:
        return HealthCheckResult(
            name="Disk Space",
            passed=False,
            message=f"Cannot check: {e}",
            critical=False
        )


def check_database_connection(db_path: Path) -> HealthCheckResult:
    """Kiểm tra kết nối database."""
    try:
        import sqlite3
        
        if not db_path.exists():
            return HealthCheckResult(
                name="Database",
                passed=True,
                message="Will be created on first run",
                critical=False
            )
        
        # Try to connect and query
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
        tables = cursor.fetchall()
        conn.close()
        
        return HealthCheckResult(
            name="Database",
            passed=True,
            message=f"OK - Connected ({len(tables)} tables)"
        )
    except Exception as e:
        return HealthCheckResult(
            name="Database",
            passed=False,
            message=f"Connection failed: {e}"
        )


def check_required_modules() -> HealthCheckResult:
    """Kiểm tra các module Python cần thiết."""
    required = ['pandas', 'openpyxl', 'ttkbootstrap', 'streamlit']
    missing = []
    
    for module in required:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    
    if not missing:
        return HealthCheckResult(
            name="Python Modules",
            passed=True,
            message="All required modules installed"
        )
    else:
        return HealthCheckResult(
            name="Python Modules",
            passed=False,
            message=f"Missing: {', '.join(missing)}"
        )


def check_file_permissions(path: Path) -> HealthCheckResult:
    """Kiểm tra quyền đọc/ghi."""
    try:
        # Test write permission
        test_file = path / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
        
        return HealthCheckResult(
            name="Write Permission",
            passed=True,
            message=f"OK - Can write to {path.name}"
        )
    except Exception as e:
        return HealthCheckResult(
            name="Write Permission",
            passed=False,
            message=f"Cannot write to {path}: {e}"
        )


def run_all_health_checks(input_dir: Path, output_dir: Path) -> Tuple[bool, List[HealthCheckResult]]:
    """
    Chạy tất cả health checks.
    
    Args:
        input_dir: Thư mục input
        output_dir: Thư mục output
    
    Returns:
        Tuple (all_passed, list of results)
    """
    results = []
    
    # Check directories
    results.append(check_directory_exists(input_dir))
    results.append(check_directory_exists(output_dir))
    
    # Check disk space
    results.append(check_disk_space(output_dir, min_mb=100))
    
    # Check database
    db_path = output_dir / "container_history.db"
    results.append(check_database_connection(db_path))
    
    # Check write permissions
    results.append(check_file_permissions(output_dir))
    
    # Check required modules
    results.append(check_required_modules())
    
    # Determine overall status
    critical_failures = [r for r in results if not r.passed and r.critical]
    all_passed = len(critical_failures) == 0
    
    return all_passed, results


def run_health_checks(input_dir: Path | None = None, output_dir: Path | None = None) -> Dict[str, bool]:
    """
    Run the canonical health check contract used by API, Docker, and tests.

    Returns a flat mapping so callers can decide how to expose status without
    relying on localized display names from HealthCheckResult.
    """
    if input_dir is None or output_dir is None:
        try:
            import config
            input_dir = input_dir or config.INPUT_DIR
            output_dir = output_dir or config.OUTPUT_DIR
        except Exception as exc:
            logging.error(f"[Health] Cannot load config: {exc}")
            return {
                "api": True,
                "config": False,
                "input_dir": False,
                "output_dir": False,
                "disk_space": False,
                "database": False,
                "write_permission": False,
                "python_modules": False,
            }

    checks: Dict[str, bool] = {"api": True, "config": True}
    try:
        all_passed, results = run_all_health_checks(Path(input_dir), Path(output_dir))
    except Exception as exc:
        logging.error(f"[Health] Health checks failed unexpectedly: {exc}", exc_info=True)
        return {
            "api": True,
            "config": True,
            "input_dir": False,
            "output_dir": False,
            "disk_space": False,
            "database": False,
            "write_permission": False,
            "python_modules": False,
        }

    name_map = {
        "Directory: data_input": "input_dir",
        "Directory: data_output": "output_dir",
        f"Directory: {Path(input_dir).name}": "input_dir",
        f"Directory: {Path(output_dir).name}": "output_dir",
        "Disk Space": "disk_space",
        "Database": "database",
        "Write Permission": "write_permission",
        "Python Modules": "python_modules",
    }
    for result in results:
        key = name_map.get(result.name, result.name.lower().replace(" ", "_").replace(":", ""))
        checks[key] = result.passed

    checks["critical"] = all_passed
    return checks


def run_health_check() -> None:
    """CLI/Docker entry point. Exits non-zero when any critical check fails."""
    checks = run_health_checks()
    raise SystemExit(0 if checks.get("critical", all(checks.values())) else 1)


def format_health_report(results: List[HealthCheckResult]) -> str:
    """Format health check results as string."""
    lines = ["=" * 50, "HEALTH CHECK REPORT", "=" * 50]
    
    for result in results:
        status = "✅" if result.passed else "❌"
        lines.append(f"{status} {result.name}: {result.message}")
    
    lines.append("=" * 50)
    
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    lines.append(f"Result: {passed}/{total} checks passed")
    
    return "\n".join(lines)


def log_health_results(results: List[HealthCheckResult]):
    """Log health check results."""
    for result in results:
        if result.passed:
            logging.info(f"[Health] ✅ {result.name}: {result.message}")
        else:
            level = logging.ERROR if result.critical else logging.WARNING
            logging.log(level, f"[Health] ❌ {result.name}: {result.message}")
