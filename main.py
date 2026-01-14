# File: main.py
import os
from datetime import datetime
import logging
from pathlib import Path
import sys
from tkinter import messagebox
import pandas as pd
import config
from data.data_loader import load_all_data
from data.data_validator import validate_dataframes_structure, validate_dataframes_quality
from core.reconciliation_engine import perform_reconciliation
from core.advanced_checker import perform_simple_reconciliation
from core.inventory_checker import compare_inventories
from reports.operator_analyzer import analyze_by_operator
from reports.report_generator import create_reports
from core.delta_checker import perform_delta_analysis
from core_logic import run_full_reconciliation_process
from config import Col, REQUIRED_COLUMNS_PER_FILE, DATA_VALIDATION_RULES

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
RUN_TIME = datetime.now()
REPORT_FOLDER = config.OUTPUT_DIR / f"Report_{TIMESTAMP}"
LOG_FILE = config.LOG_DIR / f"log_{TIMESTAMP}.txt"

def setup_initial_directories():
    """Kiểm tra và tạo các thư mục cần thiết khi chương trình khởi động."""
    logging.info("Kiểm tra cấu trúc thư mục dự án...")
    required_dirs = [
        config.INPUT_DIR,
        config.OUTPUT_DIR,
        config.LOG_DIR,
        Path("BI_Dashboard")
    ]
    for dir_path in required_dirs:
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logging.error(f"Không thể tạo thư mục '{dir_path}': {e}")
            if getattr(sys, 'frozen', False):
                messagebox.showerror("Lỗi Khởi Tạo", f"Không thể tạo thư mục cần thiết:\n{dir_path}\n\nVui lòng kiểm tra quyền ghi.")
            return False
    return True
def main():
    """Chạy chương trình ở chế độ dòng lệnh (backend)."""
    logging.info("Bắt đầu chạy quy trình xử lý backend...")
    try:
        # <<< SỬA LỖI: Hàm này trả về đối tượng Path, không phải dictionary >>>
        # Chạy toàn bộ logic và nhận về đường dẫn thư mục báo cáo
        report_folder = run_full_reconciliation_process(config.INPUT_DIR, config.OUTPUT_DIR)
        
        logging.info(f"HOÀN TẤT! Đã xử lý và lưu kết quả thành công. Báo cáo tại: {report_folder}")
    except (ValueError, RuntimeError) as e:
        logging.error(f"Chương trình đã dừng do lỗi: {e}")
    except Exception as e:
        logging.error("Đã xảy ra lỗi không mong muốn!", exc_info=True)

if __name__ == "__main__":
    log_folder = Path("logs")
    log_folder.mkdir(exist_ok=True)
    log_file = log_folder / "app_log.txt"

    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Format
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Handler 1: File (OVERWRITE mode - only keep latest run)
    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # Handler 2: Console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Clear existing handlers to avoid duplicates if called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()


    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    if not setup_initial_directories():
        sys.exit(1)

    main()