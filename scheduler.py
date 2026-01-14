"""
Scheduled Jobs utility for automated reconciliation.
Supports Windows Task Scheduler and in-process scheduling.
"""
import logging
import subprocess
import sys
from pathlib import Path
from datetime import datetime, time
from typing import Optional


def create_windows_task(
    task_name: str = "ContainerReconciliation",
    python_path: Optional[str] = None,
    script_path: Optional[str] = None,
    run_time: time = time(8, 0),  # Default: 8:00 AM
    working_dir: Optional[str] = None
) -> bool:
    """
    Create a Windows Task Scheduler task for daily reconciliation.
    
    Args:
        task_name: Name of the scheduled task.
        python_path: Path to python.exe. Defaults to current interpreter.
        script_path: Path to main.py. Defaults to current directory.
        run_time: Time of day to run (default 8:00 AM).
        working_dir: Working directory for the task.
    
    Returns:
        True if task was created successfully, False otherwise.
    
    Requires:
        Administrator privileges on Windows.
    """
    if python_path is None:
        python_path = sys.executable
    
    if script_path is None:
        script_path = str(Path(__file__).parent / "main.py")
    
    if working_dir is None:
        working_dir = str(Path(__file__).parent)
    
    time_str = run_time.strftime("%H:%M")
    
    # Build schtasks command
    cmd = [
        "schtasks", "/create",
        "/tn", task_name,
        "/tr", f'"{python_path}" "{script_path}"',
        "/sc", "DAILY",
        "/st", time_str,
        "/f"  # Force overwrite if exists
    ]
    
    try:
        logging.info(f"Creating scheduled task '{task_name}' for {time_str}...")
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        
        if result.returncode == 0:
            logging.info(f"Task '{task_name}' created successfully.")
            return True
        else:
            logging.error(f"Failed to create task: {result.stderr}")
            return False
            
    except Exception as e:
        logging.error(f"Error creating scheduled task: {e}")
        return False


def delete_windows_task(task_name: str = "ContainerReconciliation") -> bool:
    """
    Delete a Windows Task Scheduler task.
    
    Args:
        task_name: Name of the task to delete.
    
    Returns:
        True if deleted successfully.
    """
    cmd = ["schtasks", "/delete", "/tn", task_name, "/f"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            logging.info(f"Task '{task_name}' deleted.")
            return True
        else:
            logging.warning(f"Could not delete task: {result.stderr}")
            return False
    except Exception as e:
        logging.error(f"Error deleting task: {e}")
        return False


def check_task_exists(task_name: str = "ContainerReconciliation") -> bool:
    """
    Check if a scheduled task exists.
    
    Args:
        task_name: Name of the task to check.
    
    Returns:
        True if task exists.
    """
    cmd = ["schtasks", "/query", "/tn", task_name]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        return result.returncode == 0
    except Exception:
        return False


def get_task_info(task_name: str = "ContainerReconciliation") -> Optional[str]:
    """
    Get information about a scheduled task.
    
    Args:
        task_name: Name of the task.
    
    Returns:
        Task info string or None if not found.
    """
    cmd = ["schtasks", "/query", "/tn", task_name, "/fo", "LIST"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            return result.stdout
        return None
    except Exception:
        return None


# Example usage and CLI
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage scheduled reconciliation tasks")
    parser.add_argument("action", choices=["create", "delete", "check", "info"])
    parser.add_argument("--time", default="08:00", help="Run time in HH:MM format")
    parser.add_argument("--name", default="ContainerReconciliation", help="Task name")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    if args.action == "create":
        hour, minute = map(int, args.time.split(":"))
        create_windows_task(task_name=args.name, run_time=time(hour, minute))
    elif args.action == "delete":
        delete_windows_task(task_name=args.name)
    elif args.action == "check":
        exists = check_task_exists(task_name=args.name)
        logging.info(f"Task '{args.name}' exists: {exists}")
    elif args.action == "info":
        info = get_task_info(task_name=args.name)
        logging.info(info or "Task not found.")
