import os
import sys
import configparser
from pathlib import Path

# --- APP INFO ---
APP_VERSION = "5.7"
APP_YEAR = "2026"

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
    default_operators = {}
    
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
# V4.5.3: Sửa thứ tự và pattern để tránh xung đột
# V5.7: Thêm pattern cụ thể hơn để tránh match nhầm
# Lưu ý: Pattern được check theo thứ tự trong identify_file_type()
FILE_PATTERNS = {
    # File chung (sẽ được tách bởi data loader)
    "nhapxuat_combined": ["NHAPXUAT", "NHAP XUAT", "NHẬP XUẤT"],  # File chứa cả nhập và xuất tàu
    "gate_combined": ["GATE IN OUT", "GATE VAO RA", "GATE.XLS"],  # V5.7: Pattern cụ thể hơn để tránh match GATE IN/OUT riêng lẻ
    # V5.7: RESTOW là tên khác của SHIFTING (Tàu-Bãi-Tàu)
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
# Cập nhật V4.5.2: Mở rộng thuật ngữ - hỗ trợ cả tiếng Anh và tiếng Việt
BUSINESS_RULES = [
    # Theo Source Key - Ưu tiên cao nhất
    {'conditions': {Col.SOURCE_KEY: ['xuat_tau', 'xuat_shifting', 'gate_out']}, 'action': {'move_type': 'OUT'}},
    {'conditions': {Col.SOURCE_KEY: ['nhap_tau', 'nhap_shifting', 'gate_in', 'ton_cu']}, 'action': {'move_type': 'IN'}},
    
    # ===== PHƯƠNG ÁN XUẤT (RA khỏi bãi) =====
    # Lấy Nguyên - nhiều cách viết
    {'conditions': {Col.PHUONG_AN: ['LAY NGUYEN', 'Lấy Nguyên', 'LẤY NGUYÊN', 'lay nguyen', 'PICK UP', 'Pick Up', 'Pick up']}, 'action': {'move_type': 'OUT'}},
    # Cấp Rỗng - nhiều cách viết  
    {'conditions': {Col.PHUONG_AN: ['CAP RONG', 'Cấp rỗng', 'CẤP RỖNG', 'cap rong', 'EMPTY RELEASE', 'Empty Release']}, 'action': {'move_type': 'OUT'}},
    # Lưu Rỗng (xuất)
    {'conditions': {Col.PHUONG_AN: ['LUU RONG', 'Lưu rỗng', 'LƯU RỖNG', 'luu rong'], Col.VAO_RA: ['RA', 'Ra', 'OUT', 'Out']}, 'action': {'move_type': 'OUT'}},
    # Xuất tàu
    {'conditions': {Col.PHUONG_AN: ['XUAT TAU', 'Xuất tàu', 'XUẤT TÀU', 'xuat tau', 'LOADING', 'Loading', 'SHIP OUT', 'Ship Out']}, 'action': {'move_type': 'OUT'}},
    # Chuyển tàu (xuất)
    {'conditions': {Col.PHUONG_AN: ['CHUYEN TAU', 'Chuyển tàu', 'CHUYỂN TÀU', 'chuyen tau', 'TRANSHIPMENT', 'Transhipment'], Col.VAO_RA: ['RA', 'Ra', 'OUT', 'Out']}, 'action': {'move_type': 'OUT'}},
    # Shifting Loading (Bãi → Tàu)
    {'conditions': {Col.PHUONG_AN: ['SHIFTING LOADING', 'Shifting Loading', 'shifting loading', 'SHIFTING XUẤT', 'Shifting xuất', 'X-RESTOW', 'RESTOW OUT', 'Shifting xuất (Bãi→Tàu)']}, 'action': {'move_type': 'OUT'}},
    
    # ===== PHƯƠNG ÁN NHẬP (VÀO bãi) =====
    # Hạ Bãi - nhiều cách viết
    {'conditions': {Col.PHUONG_AN: ['HA BAI', 'Hạ bãi', 'HẠ BÃI', 'ha bai', 'DROP OFF', 'Drop Off', 'Drop off', 'DROP']}, 'action': {'move_type': 'IN'}},
    # Trả Rỗng - nhiều cách viết
    {'conditions': {Col.PHUONG_AN: ['TRA RONG', 'Trả rỗng', 'TRẢ RỖNG', 'tra rong', 'EMPTY RETURN', 'Empty Return', 'MTY RETURN']}, 'action': {'move_type': 'IN'}},
    # Lưu Rỗng (nhập)
    {'conditions': {Col.PHUONG_AN: ['LUU RONG', 'Lưu rỗng', 'LƯU RỖNG', 'luu rong'], Col.VAO_RA: ['VAO', 'VÀO', 'Vào', 'IN', 'In']}, 'action': {'move_type': 'IN'}},
    # Nhập tàu
    {'conditions': {Col.PHUONG_AN: ['NHAP TAU', 'Nhập tàu', 'NHẬP TÀU', 'nhap tau', 'DISCHARGE', 'Discharge', 'SHIP IN', 'Ship In']}, 'action': {'move_type': 'IN'}},
    # Chuyển tàu (nhập)
    {'conditions': {Col.PHUONG_AN: ['CHUYEN TAU', 'Chuyển tàu', 'CHUYỂN TÀU', 'chuyen tau', 'TRANSHIPMENT', 'Transhipment'], Col.VAO_RA: ['VAO', 'VÀO', 'Vào', 'IN', 'In']}, 'action': {'move_type': 'IN'}},
    # Shifting Discharge (Tàu → Bãi)
    {'conditions': {Col.PHUONG_AN: ['SHIFTING DISCHARGE', 'Shifting Discharge', 'shifting discharge', 'SHIFTING NHẬP', 'Shifting nhập', 'N-RESTOW', 'RESTOW IN', 'Shifting nhập (Tàu→Bãi)']}, 'action': {'move_type': 'IN'}},
    
    # ===== ĐÓNG HÀNG / RÚT HÀNG (phụ thuộc Vào/Ra) =====
    {'conditions': {Col.PHUONG_AN: ['DONG HANG', 'RUT HANG', 'ĐÓNG HÀNG', 'RÚT HÀNG', 'ĐÓNG HÀNG XE - CONT', 'ĐÓNG HÀNG GHE - CONT', 'STUFFING', 'Stuffing', 'UNSTUFFING', 'Unstuffing'], Col.VAO_RA: ['RA', 'Ra', 'OUT', 'Out']}, 'action': {'move_type': 'OUT'}},
    {'conditions': {Col.PHUONG_AN: ['DONG HANG', 'RUT HANG', 'ĐÓNG HÀNG', 'RÚT HÀNG', 'ĐÓNG HÀNG XE - CONT', 'ĐÓNG HÀNG GHE - CONT', 'STUFFING', 'Stuffing', 'UNSTUFFING', 'Unstuffing'], Col.VAO_RA: ['VAO', 'VÀO', 'Vào', 'IN', 'In']}, 'action': {'move_type': 'IN'}},
    
    # ===== RÚT HÀNG TỪ XE / GHE (phụ thuộc Vào/Ra) =====
    {'conditions': {Col.PHUONG_AN: ['RÚT HÀNG TỪ XE - CONT', 'RÚT HÀNG TỪ GHE - CONT', 'RUT HANG TU XE', 'RUT HANG TU GHE'], Col.VAO_RA: ['RA', 'Ra', 'OUT', 'Out']}, 'action': {'move_type': 'OUT'}},
    {'conditions': {Col.PHUONG_AN: ['RÚT HÀNG TỪ XE - CONT', 'RÚT HÀNG TỪ GHE - CONT', 'RUT HANG TU XE', 'RUT HANG TU GHE'], Col.VAO_RA: ['VAO', 'VÀO', 'Vào', 'IN', 'In']}, 'action': {'move_type': 'IN'}},
    
    # ===== ĐÓNG HÀNG SANG CONTAINER (CFS) =====
    {'conditions': {Col.PHUONG_AN: ['Đóng hàng sang container sử dụng xe nâng', 'DONG HANG SANG CONT', 'CFS STUFFING'], Col.VAO_RA: ['RA', 'Ra', 'OUT', 'Out']}, 'action': {'move_type': 'OUT'}},
    {'conditions': {Col.PHUONG_AN: ['Đóng hàng sang container sử dụng xe nâng', 'DONG HANG SANG CONT', 'CFS STUFFING'], Col.VAO_RA: ['VAO', 'VÀO', 'Vào', 'IN', 'In']}, 'action': {'move_type': 'IN'}},
]

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
    # V4.7.1: Bỏ Col.OPERATOR vì file giao dịch không có cột Hãng, gây sai thông tin giả
    # V4.7.2: Tạm vô hiệu hóa Col.JOB_ORDER - khách đăng ký trước nhưng chưa đến lấy = bình thường
    # Col.JOB_ORDER,  # TODO: Bật lại sau khi test data nhiều ngày
    Col.FE, Col.ISO, Col.LOCATION
]

# --- DATE FILTERING ---
START_DATE = None
END_DATE = None
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
# Load settings from gui_settings.ini (Legacy/User Config) or use Env Vars
ini_path = BASE_DIR / "gui_settings.ini"
email_config = {}
if ini_path.exists():
    try:
        parser = configparser.ConfigParser()
        parser.read(ini_path)
        if "Email" in parser:
            email_config = parser["Email"]
    except Exception:
        pass

EMAIL_SETTINGS = {
    "enabled": email_config.get("enabled", "False") == "True",
    "smtp_server": email_config.get("smtp_server", "smtp.gmail.com"),
    "smtp_port": int(email_config.get("smtp_port", "587")),
    "sender_email": email_config.get("sender_email") or os.getenv("APP_EMAIL_USER", "your_email@gmail.com"),
    "sender_password": email_config.get("sender_password") or os.getenv("APP_EMAIL_PASSWORD", "your_app_password"),
    "recipients": email_config.get("recipients", "recipient1@example.com").split(",") if "recipients" in email_config else ["recipient1@example.com"],
    "subject_prefix": "[BÁO CÁO ĐỐI SOÁT TỰ ĐỘNG]"
}
# --- POWER BI CONFIGURATION ---
# Đường dẫn đến file báo cáo Power BI (.pbix) trong thư mục dự án
# Chương trình sẽ tự động tạo thư mục 'BI_Dashboard' nếu chưa có.
POWER_BI_REPORT_PATH = "BI_Dashboard/Dashboard.pbix"