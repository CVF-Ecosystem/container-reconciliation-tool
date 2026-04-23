# File: config.py — @2026 v1.0
"""Application configuration: paths, column definitions, business rules, email settings."""
import os
import sys
import configparser
from pathlib import Path

# --- APP INFO ---
APP_VERSION = "1.0"
APP_YEAR = "2026"
APP_COPYRIGHT = "@2026"

# --- PATHS ---
# Detect if running as EXE or Python script
def get_app_dir():
    """Get the directory where the EXE/script is located."""
    if getattr(sys, 'frozen', False):
        # Running as compiled EXE (PyInstaller)
        return Path(sys.executable).resolve().parent
    else:
        # Running as Python script
        return Path(__file__).resolve().parent

BASE_DIR = get_app_dir()
INPUT_DIR = BASE_DIR / "data_input"
OUTPUT_DIR = BASE_DIR / "data_output"
LOG_DIR = BASE_DIR / "logs"

# --- AUTO-CREATE DIRECTORIES ---
def ensure_directories():
    """Create required directories if they don't exist."""
    for folder in [INPUT_DIR, OUTPUT_DIR, LOG_DIR]:
        folder.mkdir(parents=True, exist_ok=True)

# Auto-create on import
ensure_directories()
# --- COLUMN DEFINITIONS ---
class Col:
    CONTAINER = 'Số Container'
    SOURCE_FILE = 'SourceFile'
    SOURCE_KEY = 'SourceKey'
    TRANSACTION_TIME = 'ThoiDiemGiaoDich'
    MOVE_TYPE = 'LoaiGiaoDich'
    PHUONG_AN = 'Phương án'
    VAO_RA = 'Vào/Ra'
    FE = 'F/E'
    OPERATOR = 'Hãng khai thác'
    ISO = 'Kích cỡ ISO'
    LOCATION = 'Vị trí trên bãi'
    JOB_ORDER = 'Số lệnh'
    XE_VAO_CONG = 'Xe vào cổng'
    CONT_VAO_BAI = 'Container vào bãi'
    CONT_RA_BAI = 'Container ra bãi'
    XE_RA_CONG = 'Xe ra cổng'
    NGAY_NHAP_BAI = 'Ngày nhập bãi'
    NGAY_RA_BAI = 'Ngày ra bãi'
    LOAI_CONT = 'Loại cont'  # SOC/COC

import json
import logging

# --- LOAD EXTERNAL CONFIG ---
MAPPING_CONFIG_FILE = BASE_DIR / "config_mappings.json"

def load_mapping_config():
    default_required = {
        "ton_cu": [[Col.CONTAINER], [Col.OPERATOR]],
        "ton_moi": [[Col.CONTAINER], [Col.OPERATOR]]
    }
    default_operators = {
        "VIMC Lines": ["VMC"],
        "Vinafco": ["VFC"],
        "Vosco": ["VOC", "VOSCO"],
    }
    
    if not MAPPING_CONFIG_FILE.exists():
        logging.warning(f"Config file not found: {MAPPING_CONFIG_FILE}. Using defaults.")
        return default_required, default_operators
        
    try:
        with open(MAPPING_CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("REQUIRED_COLUMNS_PER_FILE", default_required), data.get("OPERATOR_MAPPING", default_operators)
    except Exception as e:
        logging.error(f"Error loading config mapping: {e}")
        return default_required, default_operators

REQUIRED_COLUMNS_PER_FILE, OPERATOR_MAPPING = load_mapping_config()

# --- VALIDATION 2: CHẤT LƯỢNG CHUYÊN SÂU (Nghiêm ngặt) ---
DATA_VALIDATION_RULES = {
    'all': {
        'required_columns': [Col.CONTAINER],
        'check_nulls': {
            Col.CONTAINER: 0.9, # Cảnh báo nếu cột CONTAINER trống hơn 90%
        }
    },
}

# --- FILE IDENTIFICATION ---
# Lưu ý: Pattern được check theo thứ tự trong identify_file_type()
FILE_PATTERNS = {
    # File chung (sẽ được tách bởi data loader)
    "nhapxuat_combined": ["NHAPXUAT", "NHAP XUAT", "NHẬP XUẤT"],  # File chứa cả nhập và xuất tàu
    "gate_combined": ["GATE IN OUT", "GATE VAO RA", "GATE.XLS"],
    "shifting_combined": ["SHIFTING", "RESTOW.XLS"],   # SHIFTING.xlsx hoặc RESTOW.xlsx
    # File riêng lẻ
    "ton_cu": ["TON CU", "TON CŨ", "BASELINE"],
    "nhap_tau": ["NHAP TAU", "NHẬP TÀU", "DISCHARGE"],  # Xóa "NHAP" để tránh match NHAPXUAT
    "nhap_shifting": ["NHAP SHIFTING", "N-RESTOW", "SHIFTING DISCHARGE", "SHIFTING NHẬP"],
    "gate_out": ["GATE OUT", "CONG RA", "CỔNG RA"],
    "gate_in": ["GATE IN", "CONG VAO", "CỔNG VÀO"],  # Xóa "VAO" để tránh xung đột
    "xuat_tau": ["XUAT TAU", "XUẤT TÀU", "LOADING"],  # Xóa "XUAT" để tránh match NHAPXUAT
    "xuat_shifting": ["XUAT SHIFTING", "X-RESTOW", "SHIFTING LOADING", "SHIFTING XUẤT"],
    "ton_moi": ["TON MOI", "TỒN MỚI", "CURRENT"],
}
REQUIRED_FILES = ["ton_moi"]

# --- RECONCILIATION LOGIC ---
TIME_PRIORITY_COLS = [
    Col.NGAY_RA_BAI, Col.XE_RA_CONG, Col.CONT_RA_BAI,
    Col.XE_VAO_CONG, Col.CONT_VAO_BAI, Col.NGAY_NHAP_BAI
]

# Dành cho Logic Chính (Rule Engine)
# Business rules được tách ra file riêng config_business_rules.py để dễ bảo trì
from config_business_rules import BUSINESS_RULES  # noqa: F401 (re-export)

# Dành cho Logic Đơn giản (Checker)
INBOUND_KEYS = ["ton_cu", "gate_in", "nhap_tau", "nhap_shifting"]
OUTBOUND_KEYS = ["gate_out", "xuat_tau", "xuat_shifting"]

# --- SHIFTING NỘI BÃI CONFIGURATION (V4.3) ---
SHIFTING_RULES = {
    "enabled": True,                    # Bật/tắt xử lý shifting nội bãi
    "same_yard_cancel": True,           # Nếu X-RESTOW + N-RESTOW trong thời gian ngắn = Cancel
    "time_threshold_minutes": 60,       # Thời gian tối đa giữa 2 giao dịch để coi là 1 lần shifting
    "shifting_source_keys": ["nhap_shifting", "xuat_shifting"]  # Các source key của shifting
}

COMPARE_COLS_FOR_MISMATCH = [   
    # Col.JOB_ORDER,  # TODO: Bật lại sau khi test data nhiều ngày
    Col.FE, Col.ISO, Col.LOCATION
]

# --- DATE FILTERING ---
START_DATE = None
END_DATE = None

# --- CONSTANTS ---
# Fallback date dùng khi không tìm thấy ngày giao dịch hợp lệ trong dữ liệu.
# Dùng epoch (1970-01-01) để dễ nhận biết và lọc ra khi cần.
DEFAULT_FALLBACK_DATE = "1970-01-01"

# Hệ số TEU mặc định khi không có thông tin kích thước container.
# 1 TEU = 20ft, 2 TEU = 40ft/45ft. Hệ số 1.5 là ước tính trung bình.
DEFAULT_TEU_FACTOR = 1.5
# --- CONSTANTS FOR DICTIONARY KEYS ---
class ResultKeys:
    KHOP = "khop"
    THIEU = "thieu"
    THUA = "thua"

class ReportKeys:
    SUMMARY = "summary"
    DETAILS_ROI_BAI = "details_roi_bai"
    DETAILS_MOI_VAO = "details_moi_vao"
    DETAILS_VAN_TON = "details_van_ton"

class MainResultKeys:
    TON_CHUAN = "ton_chuan"
    KHOP_SAI_INFO = "khop_sai_info"

# --- EMAIL NOTIFICATION CONFIGURATION ---
# Ưu tiên đọc từ Environment Variables (an toàn hơn INI file)
# INI file chỉ dùng làm fallback cho các setting không nhạy cảm (smtp_server, port, v.v.)
ini_path = BASE_DIR / "gui_settings.ini"
email_config = {}
if ini_path.exists():
    try:
        parser = configparser.ConfigParser()
        parser.read(ini_path)
        if "Email" in parser:
            email_config = parser["Email"]
    except Exception as e:
        logging.debug(f"Could not read email config from INI: {e}")

# Password: ưu tiên env var, KHÔNG đọc từ INI file để tránh lưu plaintext
_email_password_from_ini = email_config.get("sender_password", "")
_email_password = os.getenv("APP_EMAIL_PASSWORD") or _email_password_from_ini
if _email_password_from_ini and not os.getenv("APP_EMAIL_PASSWORD"):
    logging.warning(
        "[SECURITY] Email password found in gui_settings.ini (plaintext). "
        "Please migrate to APP_EMAIL_PASSWORD environment variable instead."
    )

EMAIL_SETTINGS = {
    "enabled": email_config.get("enabled", "False") == "True",
    "smtp_server": email_config.get("smtp_server", "smtp.gmail.com"),
    "smtp_port": int(email_config.get("smtp_port", "587")),
    "sender_email": os.getenv("APP_EMAIL_USER") or email_config.get("sender_email", "your_email@gmail.com"),
    "sender_password": _email_password or "your_app_password",
    "recipients": email_config.get("recipients", "recipient1@example.com").split(",") if "recipients" in email_config else ["recipient1@example.com"],
    "subject_prefix": "[BÁO CÁO ĐỐI SOÁT TỰ ĐỘNG]"
}
# --- POWER BI CONFIGURATION ---
# Đường dẫn đến file báo cáo Power BI (.pbix) trong thư mục dự án
# Chương trình sẽ tự động tạo thư mục 'BI_Dashboard' nếu chưa có.
POWER_BI_REPORT_PATH = "BI_Dashboard/Dashboard.pbix"
