# File: core/batch_processor.py
"""
Batch Processor Module - Xử lý nhiều ngày dữ liệu liên tục.

Logic chính:
- TON MOI ngày N = TON CU ngày N+1
- Tự động nhận diện ngày từ tên file
- Xử lý tuần tự theo thứ tự thời gian
"""

import re
import os
import logging
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Callable, Any
from collections import defaultdict
import pandas as pd

import config
from config import Col


# ============================================================================
# DateSlot - Đại diện cho một ngày + time slot (8H/15H/None)
# ============================================================================

class DateSlot:
    """
    Đại diện cho một ngày VÀ time slot (nếu có).
    
    Hỗ trợ:
    - Full-day: DateSlot(date(2026,1,8), None) → "08/01/2026"
    - Half-day: DateSlot(date(2026,1,8), "8H") → "08/01/2026 (8H)"
    
    Thứ tự sắp xếp: date tăng dần, rồi slot (8H < 15H < None)
    """
    
    # Thứ tự slot để sắp xếp (8H trước, 15H sau, None cuối)
    SLOT_ORDER = {"8H": 0, "15H": 1, None: 2}
    
    def __init__(self, date_value: date, slot: Optional[str] = None):
        self.date_value = date_value
        self.slot = slot
    
    def __lt__(self, other: 'DateSlot') -> bool:
        """Sắp xếp theo date, rồi theo slot."""
        return self._sort_key() < other._sort_key()
    
    def __le__(self, other: 'DateSlot') -> bool:
        return self._sort_key() <= other._sort_key()
    
    def __gt__(self, other: 'DateSlot') -> bool:
        return self._sort_key() > other._sort_key()
    
    def __ge__(self, other: 'DateSlot') -> bool:
        return self._sort_key() >= other._sort_key()
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DateSlot):
            return False
        return self.date_value == other.date_value and self.slot == other.slot
    
    def __hash__(self) -> int:
        return hash((self.date_value, self.slot))
    
    def _sort_key(self) -> Tuple[date, int]:
        """Key để sắp xếp."""
        return (self.date_value, self.SLOT_ORDER.get(self.slot, 2))
    
    def __str__(self) -> str:
        if self.slot:
            return f"{self.date_value.strftime('%d/%m/%Y')} ({self.slot})"
        return self.date_value.strftime('%d/%m/%Y')
    
    def __repr__(self) -> str:
        return f"DateSlot({self.date_value}, {self.slot!r})"
    
    def display_label(self) -> str:
        """Label hiển thị trong UI (viết tắt hơn)."""
        if self.slot:
            return f"{self.date_value.strftime('%d/%m/%Y')} ({self.slot})"
        return self.date_value.strftime('%d/%m/%Y')
    
    def to_db_key(self) -> Tuple[str, Optional[str]]:
        """Trả về tuple (date_str, slot) để lưu vào database."""
        return (self.date_value.strftime('%Y-%m-%d'), self.slot)


# ============================================================================

# Date patterns để nhận diện ngày từ tên file
DATE_PATTERNS = [
    # N7.1.2026 hoặc N07.01.2026
    (r"N(\d{1,2})\.(\d{1,2})\.(\d{4})", "dmy"),
    # 7-1-2026 hoặc 07-01-2026
    (r"(\d{1,2})-(\d{1,2})-(\d{4})", "dmy"),
    # 7_1_2026 hoặc 07_01_2026
    (r"(\d{1,2})_(\d{1,2})_(\d{4})", "dmy"),
    # 2026-01-07 (ISO format)
    (r"(\d{4})-(\d{2})-(\d{2})", "ymd"),
    # 20260107 (compact)
    (r"(\d{4})(\d{2})(\d{2})", "ymd"),
]


def extract_date_from_filename(filename: str) -> Optional[date]:
    """
    Trích xuất ngày từ tên file.
    
    Args:
        filename: Tên file (vd: "TON MOI N7.1.2026.xlsx")
    
    Returns:
        date object nếu tìm thấy, None nếu không
    
    Examples:
        >>> extract_date_from_filename("TON MOI N7.1.2026.xlsx")
        date(2026, 1, 7)
        >>> extract_date_from_filename("GATE IN OUT 8H-15H N8.1.2026.xlsx")
        date(2026, 1, 8)
    """
    for pattern, format_type in DATE_PATTERNS:
        match = re.search(pattern, filename)
        if match:
            groups = match.groups()
            try:
                if format_type == "dmy":
                    day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                else:  # ymd
                    year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                return date(year, month, day)
            except ValueError:
                continue
    return None


def extract_date_slot_from_filename(filename: str) -> Optional[DateSlot]:
    """
    Trích xuất ngày VÀ time slot từ tên file/folder.
    
    Hỗ trợ các format linh hoạt:
    - "2 - BDTB DEN 8H N7.1 - 15H N7.1" → DateSlot(2026-01-07, "15H")
    - "3 - BDTB 15H N7.1 -  8H N8.1" → DateSlot(2026-01-08, "8H")
    - "FILE TONG 8H N5.1 - 8H N7.1" → DateSlot(2026-01-07, None) (full-day)
    - "N8.1.2026" → DateSlot(2026-01-08, None)
    
    Logic: Tìm tất cả patterns "数H" và "N数.数" riêng biệt, sau đó ghép lại.
    
    Returns:
        DateSlot với date và slot (8H/15H/None)
    """
    current_year = date.today().year
    
    # === Step 1: Tìm tất cả hour patterns (8H, 15H, etc.) ===
    hour_pattern = r'(\d{1,2})H'
    hours = re.findall(hour_pattern, filename, re.IGNORECASE)
    
    # === Step 2: Tìm tất cả date patterns ===
    # Pattern có năm: N7.1.2026
    full_date_pattern = r'N(\d{1,2})\.(\d{1,2})\.(\d{4})'
    full_dates = re.findall(full_date_pattern, filename)
    
    # Pattern không năm: N7.1 (không theo sau bởi .số)
    short_date_pattern = r'N(\d{1,2})\.(\d{1,2})(?!\.\d)'
    short_dates = re.findall(short_date_pattern, filename)
    
    # === Step 3: Xử lý các trường hợp ===
    
    # Trường hợp 1: Có format đầy đủ với năm (N8.1.2026)
    if full_dates:
        day, month, year = map(int, full_dates[-1])  # Lấy cái cuối cùng
        try:
            return DateSlot(date(year, month, day), None)
        except ValueError:
            pass
    
    # Trường hợp 2: Có ít nhất 2 hours và 2 dates → Range format
    if len(hours) >= 2 and len(short_dates) >= 2:
        hour1, hour2 = int(hours[0]), int(hours[-1])  # Lấy đầu và cuối
        date1 = (int(short_dates[0][0]), int(short_dates[0][1]))  # (day, month)
        date2 = (int(short_dates[-1][0]), int(short_dates[-1][1]))  # (day, month)
        
        # Kiểm tra full-day (cùng giờ nhưng khác ngày)
        is_full_day = (hour1 == hour2 and (date1[0] != date2[0] or date1[1] != date2[1]))
        
        try:
            end_date = date(current_year, date2[1], date2[0])
            if is_full_day:
                return DateSlot(end_date, None)  # Full day
            else:
                slot = f"{hour2}H"
                return DateSlot(end_date, slot)
        except ValueError:
            pass
    
    # Trường hợp 3: Chỉ có 1 hour và dates → Full-day (giờ là thời điểm xuất file, không phải slot)
    # VD: "TON MOI 8H N12.1.2026" → 8H là thời điểm export, không phải slot
    if len(hours) >= 1 and len(short_dates) >= 1:
        last_date = short_dates[-1]
        try:
            end_date = date(current_year, int(last_date[1]), int(last_date[0]))
            return DateSlot(end_date, None)  # Full-day, không có slot
        except ValueError:
            pass
    
    # Trường hợp 4: Chỉ có dates không có hours
    if short_dates:
        last_date = short_dates[-1]
        try:
            return DateSlot(date(current_year, int(last_date[1]), int(last_date[0])), None)
        except ValueError:
            pass
    
    # === Fallback: Các pattern cũ có năm ===
    old_date = extract_date_from_filename(filename)
    if old_date:
        return DateSlot(old_date, None)
    
    return None


def group_files_by_date(input_dir: Path) -> Dict[date, Dict[str, str]]:
    """
    Nhóm các file trong thư mục input theo ngày.
    Hỗ trợ cả files trực tiếp trong input_dir và files trong subfolder (vd: N8.1.2026/)
    
    Với subfolder: Files không cần có ngày trong tên, ngày lấy từ tên folder
    Ví dụ: N8.1.2026/TON CU.xlsx → ngày 8/1/2026
    
    Args:
        input_dir: Đường dẫn thư mục chứa files
    
    Returns:
        Dictionary với key là date, value là dict {file_type: filename hoặc subfolder/filename}
        Ví dụ: {
            date(2026, 1, 7): {
                'ton_cu': 'TON CU N7.1.2026.xlsx',  # file trực tiếp
                'ton_moi': 'N7.1.2026/TON MOI.xlsx',  # file trong subfolder
                ...
            },
            date(2026, 1, 8): {...}
        }
    """
    grouped: Dict[date, Dict[str, str]] = defaultdict(dict)
    skipped_files: List[str] = []  # Files bị bỏ qua vì không có ngày
    unrecognized_files: List[str] = []  # Files không nhận dạng được loại
    
    try:
        all_items = os.listdir(input_dir)
    except FileNotFoundError:
        logging.error(f"Thư mục không tồn tại: {input_dir}")
        return {}
    
    # Hàm xử lý file
    def process_file(filename: str, relative_path: str = "", folder_date: Optional[date] = None):
        """
        Xử lý một file và thêm vào grouped dict.
        
        Args:
            filename: Tên file
            relative_path: Đường dẫn tương đối (tên subfolder)
            folder_date: Ngày từ tên folder (nếu có)
        """
        if not filename.endswith(('.xlsx', '.xls', '.csv')):
            return
        
        full_path = os.path.join(relative_path, filename) if relative_path else filename
        
        # Ưu tiên: 1) Ngày từ tên file, 2) Ngày từ tên folder
        file_date = extract_date_from_filename(filename)
        if file_date is None:
            if folder_date:
                # Dùng ngày từ tên folder
                file_date = folder_date
                logging.debug(f"Dùng ngày từ folder cho file: {filename} -> {file_date}")
            else:
                # CẢNH BÁO: Không có ngày từ cả file lẫn folder
                skipped_files.append(full_path)
                logging.warning(f"⚠️ BỎ QUA: Không thể xác định ngày cho file '{full_path}' - Hãy thêm ngày vào tên file (VD: TON CU N8.1.2026.xlsx) hoặc đặt trong subfolder có ngày (VD: N8.1.2026/)")
                return
        
        # Xác định loại file dựa trên FILE_PATTERNS
        file_type = identify_file_type(filename)
        if file_type:
            if file_type in grouped[file_date]:
                logging.warning(f"Trùng lặp file type '{file_type}' cho ngày {file_date}: {filename}")
            else:
                grouped[file_date][file_type] = full_path
                logging.info(f"Grouped: {file_date} -> {file_type}: {full_path}")
        else:
            # File có ngày nhưng không nhận dạng được loại
            unrecognized_files.append(f"{full_path} (ngày: {file_date})")
            logging.warning(f"⚠️ KHÔNG NHẬN DẠNG: File '{full_path}' có ngày {file_date} nhưng không khớp loại file nào (TON CU, TON MOI, GATE...)")
    
    # Quét files trực tiếp trong input_dir
    for item in all_items:
        item_path = input_dir / item
        
        if item_path.is_file():
            # File trực tiếp trong input_dir - phải có ngày trong tên file
            process_file(item)
        
        elif item_path.is_dir():
            # Subfolder - kiểm tra xem có phải folder ngày không (vd: N8.1.2026)
            folder_date = extract_date_from_filename(item)
            if folder_date:
                logging.info(f"Phát hiện subfolder ngày: {item} -> {folder_date}")
            
            # Quét files trong subfolder
            try:
                for subfile in os.listdir(item_path):
                    if (item_path / subfile).is_file():
                        # Truyền folder_date để dùng nếu file không có ngày trong tên
                        process_file(subfile, item, folder_date)
            except Exception as e:
                logging.warning(f"Không thể quét subfolder {item}: {e}")
    
    # Tổng kết cảnh báo
    if skipped_files:
        logging.warning(f"═══ TỔNG KẾT: {len(skipped_files)} file bị bỏ qua vì KHÔNG CÓ NGÀY ═══")
        for f in skipped_files:
            logging.warning(f"  - {f}")
        logging.warning("💡 Gợi ý: Thêm ngày vào tên file (VD: N8.1.2026) hoặc đặt trong subfolder có ngày")
    
    if unrecognized_files:
        logging.warning(f"═══ TỔNG KẾT: {len(unrecognized_files)} file KHÔNG NHẬN DẠNG được loại ═══")
        for f in unrecognized_files:
            logging.warning(f"  - {f}")
        logging.warning("💡 Gợi ý: Tên file cần chứa từ khóa như: TON CU, TON MOI, GATE IN OUT, SHIFTING...")
    
    return dict(grouped)


def group_files_by_date_slot(input_dir: Path) -> Dict[DateSlot, Dict[str, str]]:
    """
    Nhóm các file trong thư mục input theo DateSlot (ngày + time slot).
    
    Đây là phiên bản mới hỗ trợ time slots (8H, 15H).
    Mỗi subfolder được nhận dạng thành một DateSlot riêng.
    
    Args:
        input_dir: Đường dẫn thư mục chứa files
    
    Returns:
        Dictionary với key là DateSlot, value là dict {file_type: filename}
        Ví dụ: {
            DateSlot(date(2026,1,7), '15H'): {'ton_cu': '...', 'ton_moi': '...'},
            DateSlot(date(2026,1,8), '8H'): {'ton_cu': '...', 'ton_moi': '...'},
            DateSlot(date(2026,1,8), '15H'): {'ton_cu': '...', 'ton_moi': '...'},
        }
    """
    grouped: Dict[DateSlot, Dict[str, str]] = defaultdict(dict)
    skipped_files: List[str] = []
    unrecognized_files: List[str] = []
    
    try:
        all_items = os.listdir(input_dir)
    except FileNotFoundError:
        logging.error(f"Thư mục không tồn tại: {input_dir}")
        return {}
    
    def process_file(filename: str, relative_path: str = "", folder_slot: Optional[DateSlot] = None):
        """Xử lý một file và thêm vào grouped dict."""
        if not filename.endswith(('.xlsx', '.xls', '.csv')):
            return
        
        full_path = os.path.join(relative_path, filename) if relative_path else filename
        
        # V5.2: ƯU TIÊN folder_slot nếu có (tất cả files trong folder được group chung)
        # Chỉ dùng file's DateSlot nếu không có folder_slot
        if folder_slot:
            file_slot = folder_slot
            logging.debug(f"Dùng DateSlot từ folder cho file: {filename} -> {file_slot}")
        else:
            file_slot = extract_date_slot_from_filename(filename)
            if file_slot is None:
                skipped_files.append(full_path)
                logging.warning(f"⚠️ BỎ QUA: Không thể xác định ngày cho file '{full_path}'")
                return
        
        # Xác định loại file
        file_type = identify_file_type(filename)
        if file_type:
            # V5.2.1: Chọn file có time range lớn nhất
            if file_type in grouped[file_slot]:
                existing = grouped[file_slot][file_type]
                existing_name = existing.split('\\')[-1] if '\\' in existing else existing
                new_name = filename
                
                # V5.7: Kiểm tra conflict RESTOW + SHIFTING (cùng là shifting_combined)
                if file_type == 'shifting_combined':
                    existing_upper = existing_name.upper()
                    new_upper = new_name.upper()
                    is_existing_restow = 'RESTOW' in existing_upper and 'SHIFTING' not in existing_upper
                    is_new_restow = 'RESTOW' in new_upper and 'SHIFTING' not in new_upper
                    is_existing_shifting = 'SHIFTING' in existing_upper
                    is_new_shifting = 'SHIFTING' in new_upper
                    
                    # Nếu một file là RESTOW và một file là SHIFTING -> cảnh báo conflict
                    if (is_existing_restow and is_new_shifting) or (is_existing_shifting and is_new_restow):
                        logging.warning(f"⚠️ CONFLICT: Slot {file_slot} có CẢ file RESTOW và SHIFTING!")
                        logging.warning(f"   📄 {existing_name}")
                        logging.warning(f"   📄 {new_name}")
                        logging.warning(f"   💡 RESTOW và SHIFTING là 2 tên gọi cho cùng loại dữ liệu (Shifting Tàu)")
                        logging.warning(f"   → Chỉ cần GIỮ 1 trong 2 file. Hệ thống sẽ dùng file có range lớn hơn.")
                        
                        # Ghi nhận conflict warning
                        if 'conflict_warnings' not in grouped[file_slot]:
                            grouped[file_slot]['conflict_warnings'] = []
                        grouped[file_slot]['conflict_warnings'].append({
                            'type': 'restow_shifting_conflict',
                            'file1': existing,
                            'file2': full_path,
                            'message': 'Có cả RESTOW và SHIFTING - chỉ cần 1 file'
                        })
                
                # Hàm helper: tính time range (số ngày) từ tên file
                def get_time_range_days(fname):
                    """Parse time range từ tên file và trả về số ngày"""
                    import re
                    # Pattern: 8H N10.1 - 8H N12.1 hoặc N10.1 - N12.1
                    range_pattern = r'N?(\d{1,2})\.(\d{1,2})(?:\.\d{4})?\s*-\s*\d*H?\s*N?(\d{1,2})\.(\d{1,2})'
                    match = re.search(range_pattern, fname)
                    if match:
                        start_day, start_month = int(match.group(1)), int(match.group(2))
                        end_day, end_month = int(match.group(3)), int(match.group(4))
                        # Tính số ngày
                        from datetime import date, datetime
                        year = datetime.now().year  # V5.2.1: Fix undefined current_year
                        try:
                            start = date(year, start_month, start_day)
                            end = date(year, end_month, end_day)
                            return (end - start).days
                        except:
                            return 0
                    return 0
                
                existing_range = get_time_range_days(existing_name)
                new_range = get_time_range_days(new_name)
                
                # Chọn file có range dài hơn
                should_replace = new_range > existing_range
                
                # Ghi nhận cảnh báo trùng lặp
                if 'duplicate_warnings' not in grouped[file_slot]:
                    grouped[file_slot]['duplicate_warnings'] = []
                
                if should_replace:
                    # File mới có range lớn hơn -> thay thế
                    grouped[file_slot][file_type] = full_path
                    grouped[file_slot]['duplicate_warnings'].append({
                        'type': file_type,
                        'existing': full_path,  # File mới được dùng
                        'duplicate': existing    # File cũ bị bỏ
                    })
                    logging.warning(f"⚠️ TRÙNG LẶP '{file_type}' - THAY THẾ bằng file có range dài hơn:")
                    logging.warning(f"   ✅ Dùng: {new_name} (range: {new_range} ngày)")
                    logging.warning(f"   ❌ Bỏ: {existing_name} (range: {existing_range} ngày)")
                else:
                    # File cũ có range >= -> giữ nguyên
                    grouped[file_slot]['duplicate_warnings'].append({
                        'type': file_type,
                        'existing': existing,
                        'duplicate': full_path
                    })
                    logging.warning(f"⚠️ TRÙNG LẶP '{file_type}' - GIỮ file có range dài hơn:")
                    logging.warning(f"   ✅ Dùng: {existing_name} (range: {existing_range} ngày)")
                    logging.warning(f"   ❌ Bỏ: {new_name} (range: {new_range} ngày)")
            else:
                grouped[file_slot][file_type] = full_path
                logging.info(f"Grouped: {file_slot} -> {file_type}: {full_path}")
        else:
            unrecognized_files.append(f"{full_path} (slot: {file_slot})")
            logging.warning(f"⚠️ KHÔNG NHẬN DẠNG: File '{full_path}' có {file_slot} nhưng không khớp loại file nào")
    
    # Quét files trực tiếp trong input_dir
    for item in all_items:
        item_path = input_dir / item
        
        if item_path.is_file():
            process_file(item)
        
        elif item_path.is_dir():
            # Subfolder - extract DateSlot từ tên folder
            folder_slot = extract_date_slot_from_filename(item)
            if folder_slot:
                logging.info(f"Phát hiện subfolder: {item} -> {folder_slot}")
            
            # Quét files trong subfolder
            try:
                for subfile in os.listdir(item_path):
                    if (item_path / subfile).is_file():
                        process_file(subfile, item, folder_slot)
            except Exception as e:
                logging.warning(f"Không thể quét subfolder {item}: {e}")
    
    # Tổng kết cảnh báo
    if skipped_files:
        logging.warning(f"═══ TỔNG KẾT: {len(skipped_files)} file bị bỏ qua vì KHÔNG CÓ NGÀY ═══")
        for f in skipped_files:
            logging.warning(f"  - {f}")
        logging.warning("💡 Gợi ý: Đặt tên folder theo format: 8H N7.1 - 15H N7.1 hoặc N8.1.2026")
    
    if unrecognized_files:
        logging.warning(f"═══ TỔNG KẾT: {len(unrecognized_files)} file KHÔNG NHẬN DẠNG được loại ═══")
        for f in unrecognized_files:
            logging.warning(f"  - {f}")
    
    return dict(grouped)


def identify_file_type(filename: str) -> Optional[str]:
    """
    Xác định loại file dựa trên tên file và FILE_PATTERNS trong config.
    
    V5.7: Cải thiện thứ tự match để tránh xung đột
    - Ưu tiên pattern cụ thể trước (nhap_shifting, xuat_shifting) rồi mới đến chung (shifting_combined)
    - RESTOW.xlsx -> shifting_combined, nhưng N-RESTOW -> nhap_shifting, X-RESTOW -> xuat_shifting
    
    Args:
        filename: Tên file
    
    Returns:
        Loại file (vd: 'ton_cu', 'ton_moi', 'gate_combined', ...)
    """
    filename_upper = filename.upper()
    
    # V5.7: Định nghĩa thứ tự ưu tiên match
    # QUAN TRỌNG: Pattern DÀI HƠN phải được check TRƯỚC pattern ngắn
    # Ví dụ: "GATE IN OUT" phải check trước "GATE IN"
    # Ví dụ: "NHAP XUAT" phải check trước "NHAP"
    priority_order = [
        # 1. File combined có pattern dài (NHAP XUAT, GATE IN OUT)
        "nhapxuat_combined",  # NHAP XUAT - pattern dài, check trước nhap_tau
        "gate_combined",      # GATE IN OUT, GATE.XLS - check trước gate_in/gate_out
        # 2. File riêng lẻ GATE (GATE IN, GATE OUT)
        "gate_in",        # GATE IN
        "gate_out",       # GATE OUT
        # 3. File shifting cụ thể (trước shifting_combined)
        "nhap_shifting",  # N-RESTOW, SHIFTING DISCHARGE, NHAP SHIFTING
        "xuat_shifting",  # X-RESTOW, SHIFTING LOADING, XUAT SHIFTING
        # 4. File shifting chung
        "shifting_combined",  # SHIFTING hoặc RESTOW.xlsx
        # 5. File riêng lẻ khác
        "nhap_tau",
        "xuat_tau",
        "ton_cu",
        "ton_moi",
    ]
    
    for file_type in priority_order:
        patterns = config.FILE_PATTERNS.get(file_type, [])
        for pattern in patterns:
            if pattern.upper() in filename_upper:
                return file_type
    
    # Fallback: check các file_type khác không trong priority_order
    for file_type, patterns in config.FILE_PATTERNS.items():
        if file_type not in priority_order:
            for pattern in patterns:
                if pattern.upper() in filename_upper:
                    return file_type
    
    return None


def get_available_dates(input_dir: Path) -> List[date]:
    """
    Lấy danh sách các ngày có dữ liệu, sắp xếp theo thứ tự.
    
    Args:
        input_dir: Đường dẫn thư mục input
    
    Returns:
        List các date objects, đã sắp xếp từ cũ đến mới
    """
    grouped = group_files_by_date(input_dir)
    dates = sorted(grouped.keys())
    return dates


def validate_date_chain(grouped_files: Dict[date, Dict[str, str]], dates: List[date]) -> List[str]:
    """
    Kiểm tra tính hợp lệ của chuỗi ngày.
    
    Args:
        grouped_files: Files đã nhóm theo ngày
        dates: Danh sách ngày cần xử lý
    
    Returns:
        List các cảnh báo/lỗi (nếu có)
    """
    warnings = []
    
    for i, current_date in enumerate(dates):
        files = grouped_files.get(current_date, {})
        
        # Kiểm tra file TON MOI bắt buộc
        if 'ton_moi' not in files:
            warnings.append(f"Ngày {current_date}: Thiếu file TON MOI (bắt buộc)")
        
        # Ngày đầu tiên cần có TON CU
        if i == 0 and 'ton_cu' not in files:
            warnings.append(f"Ngày {current_date}: Ngày đầu tiên cần có file TON CU")
        
        # Các ngày sau sẽ dùng TON MOI của ngày trước làm TON CU
        # Nên không cần file TON CU riêng
    
    return warnings


def compare_ton_moi_with_next_ton_cu(
    input_dir: Path,
    grouped_files: Dict[date, Dict[str, str]], 
    dates: List[date]
) -> List[Dict]:
    """
    So sánh TON MOI ngày N với TON CU ngày N+1 (nếu cả 2 đều có file).
    
    Logic: TON MOI ngày N phải = TON CU ngày N+1
    
    Args:
        input_dir: Đường dẫn thư mục input
        grouped_files: Files đã nhóm theo ngày
        dates: Danh sách ngày cần xử lý (đã sắp xếp)
    
    Returns:
        List kết quả so sánh cho từng cặp ngày liên tiếp
    """
    import pandas as pd
    from config import Col
    
    results = []
    
    for i in range(len(dates) - 1):
        day_n = dates[i]
        day_n1 = dates[i + 1]
        
        files_n = grouped_files.get(day_n, {})
        files_n1 = grouped_files.get(day_n1, {})
        
        # Chỉ so sánh nếu cả 2 file đều tồn tại
        if 'ton_moi' not in files_n or 'ton_cu' not in files_n1:
            results.append({
                'day_n': day_n,
                'day_n1': day_n1,
                'status': 'skipped',
                'reason': 'Thiếu file để so sánh'
            })
            continue
        
        # Load 2 files
        try:
            ton_moi_file = input_dir / files_n['ton_moi']
            ton_cu_file = input_dir / files_n1['ton_cu']
            
            df_ton_moi = pd.read_excel(ton_moi_file)
            df_ton_cu = pd.read_excel(ton_cu_file)
            
            # Normalize column names to find container column
            container_col = None
            for col in df_ton_moi.columns:
                if 'container' in col.lower() or col == Col.CONTAINER:
                    container_col = col
                    break
            
            if not container_col:
                container_col = df_ton_moi.columns[0]  # Fallback to first column
            
            # Get container sets
            set_ton_moi = set(df_ton_moi[container_col].dropna().astype(str).str.strip().str.upper())
            
            # Try to find matching column in ton_cu
            ton_cu_col = None
            for col in df_ton_cu.columns:
                if 'container' in col.lower() or col == Col.CONTAINER:
                    ton_cu_col = col
                    break
            if not ton_cu_col:
                ton_cu_col = df_ton_cu.columns[0]
            
            set_ton_cu = set(df_ton_cu[ton_cu_col].dropna().astype(str).str.strip().str.upper())
            
            # Compare
            common = set_ton_moi & set_ton_cu
            only_in_moi = set_ton_moi - set_ton_cu  # Có trong TON MOI N nhưng không có trong TON CU N+1
            only_in_cu = set_ton_cu - set_ton_moi   # Có trong TON CU N+1 nhưng không có trong TON MOI N
            
            match_rate = len(common) / max(len(set_ton_moi), 1) * 100
            
            if match_rate >= 99:
                status = 'match'
            elif match_rate >= 95:
                status = 'mostly_match'
            else:
                status = 'mismatch'
            
            results.append({
                'day_n': day_n,
                'day_n1': day_n1,
                'status': status,
                'ton_moi_count': len(set_ton_moi),
                'ton_cu_count': len(set_ton_cu),
                'common_count': len(common),
                'only_in_moi': len(only_in_moi),
                'only_in_cu': len(only_in_cu),
                'match_rate': match_rate,
                'message': f"TON MOI {day_n.strftime('%d/%m')}: {len(set_ton_moi)} | "
                          f"TON CU {day_n1.strftime('%d/%m')}: {len(set_ton_cu)} | "
                          f"Khớp: {match_rate:.1f}%"
            })
            
        except Exception as e:
            results.append({
                'day_n': day_n,
                'day_n1': day_n1,
                'status': 'error',
                'error': str(e)
            })
    
    return results


def format_chain_validation_message(comparison_results: List[Dict]) -> str:
    """Tạo message tóm tắt kết quả so sánh chain."""
    if not comparison_results:
        return "Không có cặp ngày liên tiếp để so sánh."
    
    lines = ["=== KIỂM TRA TÍNH LIÊN TỤC (TON MOI ngày N = TON CU ngày N+1) ===\n"]
    
    has_issue = False
    for r in comparison_results:
        day_n = r['day_n'].strftime('%d/%m/%Y')
        day_n1 = r['day_n1'].strftime('%d/%m/%Y')
        
        if r['status'] == 'match':
            lines.append(f"✅ {day_n} → {day_n1}: KHỚP ({r['match_rate']:.1f}%)")
        elif r['status'] == 'mostly_match':
            lines.append(f"⚠️ {day_n} → {day_n1}: Gần khớp ({r['match_rate']:.1f}%)")
            lines.append(f"   Chênh lệch: +{r['only_in_cu']} / -{r['only_in_moi']} containers")
            has_issue = True
        elif r['status'] == 'mismatch':
            lines.append(f"❌ {day_n} → {day_n1}: KHÔNG KHỚP ({r['match_rate']:.1f}%)")
            lines.append(f"   TON MOI {day_n}: {r['ton_moi_count']} container")
            lines.append(f"   TON CU {day_n1}: {r['ton_cu_count']} container")
            lines.append(f"   Chênh lệch: +{r['only_in_cu']} / -{r['only_in_moi']}")
            has_issue = True
        elif r['status'] == 'skipped':
            lines.append(f"⏭️ {day_n} → {day_n1}: Bỏ qua ({r.get('reason', '')})")
        else:
            lines.append(f"❓ {day_n} → {day_n1}: Lỗi - {r.get('error', 'Unknown')}")
            has_issue = True
    
    if has_issue:
        lines.append("\n⚠️ LƯU Ý: Có sự khác biệt giữa các file.")
        lines.append("Bạn có thể:")
        lines.append("  1. Tiếp tục - hệ thống sẽ dùng TON MOI ngày trước làm TON CU")
        lines.append("  2. Hủy - kiểm tra lại dữ liệu đầu vào")
    else:
        lines.append("\n✅ Dữ liệu liên tục, hợp lệ!")
    
    return "\n".join(lines)


# ============================================================================
# V5.5: SLOT-BASED CHAIN VALIDATION (Kiểm tra liên tục theo slots)
# ============================================================================

def get_expected_previous_slot(current_slot: DateSlot) -> DateSlot:
    """
    Xác định slot trước đó theo logic nghiệp vụ.
    
    Logic:
    - Nếu slot hiện tại là 8H → slot trước là 15H ngày hôm trước
    - Nếu slot hiện tại là 15H → slot trước là 8H cùng ngày
    - Nếu slot hiện tại là None (full-day) → slot trước là full-day ngày hôm trước
    
    Args:
        current_slot: DateSlot hiện tại
    
    Returns:
        DateSlot mong đợi của slot trước đó
    """
    from datetime import timedelta
    
    if current_slot.slot == '8H':
        # 8H hôm nay <- 15H hôm qua
        prev_date = current_slot.date_value - timedelta(days=1)
        return DateSlot(prev_date, '15H')
    elif current_slot.slot == '15H':
        # 15H hôm nay <- 8H cùng ngày
        return DateSlot(current_slot.date_value, '8H')
    else:
        # Full-day <- Full-day ngày trước
        prev_date = current_slot.date_value - timedelta(days=1)
        return DateSlot(prev_date, None)


def is_slot_continuous(slot1: DateSlot, slot2: DateSlot) -> Tuple[bool, str]:
    """
    Kiểm tra 2 slots có liên tục không (slot2 phải ngay sau slot1).
    
    Logic nghiệp vụ:
    - 8H ngày N → 15H ngày N: Liên tục (cùng ngày)
    - 15H ngày N → 8H ngày N+1: Liên tục (qua đêm)
    - 15H ngày Thứ 6 → 8H ngày Thứ 2: Liên tục (qua cuối tuần)
    - 15H ngày N → 15H ngày N+1: KHÔNG liên tục (thiếu 8H ngày N+1)
    
    Args:
        slot1: Slot trước
        slot2: Slot sau
    
    Returns:
        Tuple[bool, str]: (is_continuous, gap_description)
    """
    from datetime import timedelta
    
    # Tính expected_next của slot1
    if slot1.slot == '8H':
        # 8H -> 15H cùng ngày
        expected_next = DateSlot(slot1.date_value, '15H')
    elif slot1.slot == '15H':
        # 15H -> 8H ngày hôm sau
        next_date = slot1.date_value + timedelta(days=1)
        expected_next = DateSlot(next_date, '8H')
    else:
        # Full-day -> Full-day ngày sau
        next_date = slot1.date_value + timedelta(days=1)
        expected_next = DateSlot(next_date, None)
    
    if slot2 == expected_next:
        return True, ""
    
    # Kiểm tra có phải qua cuối tuần / ngày lễ không
    # Nếu slot2.date > expected_next.date, có thể là qua weekend
    if slot2.date_value > slot1.date_value:
        # Tính số ngày giữa slot1 và slot2
        total_days_gap = (slot2.date_value - slot1.date_value).days
        
        # Kiểm tra pattern: 15H Thứ 6 → 8H Thứ 2 (qua T7, CN)
        if slot1.slot == '15H' and slot2.slot == '8H':
            # Tính ngày trong tuần (0=Monday, 4=Friday, 5=Saturday, 6=Sunday)
            slot1_weekday = slot1.date_value.weekday()  # Thứ 6 (Friday) = 4
            slot2_weekday = slot2.date_value.weekday()  # Thứ 2 (Monday) = 0
            
            # Pattern 1: Thứ 6 → Thứ 2 (gap = 3 ngày: T6 → T7 → CN → T2)
            if slot1_weekday == 4 and slot2_weekday == 0 and total_days_gap == 3:
                return True, "Qua cuối tuần (T7, CN)"
            
            # Pattern 2: Normal case - liên tiếp qua đêm (gap = 1 ngày)
            if total_days_gap == 1:
                return True, ""
        
        # Kiểm tra full-day qua cuối tuần
        if slot1.slot is None and slot2.slot is None:
            slot1_weekday = slot1.date_value.weekday()
            slot2_weekday = slot2.date_value.weekday()
            
            # Thứ 6 → Thứ 2 (gap = 3 ngày)
            if slot1_weekday == 4 and slot2_weekday == 0 and total_days_gap == 3:
                return True, "Qua cuối tuần (T7, CN)"
        
        # Gap thật sự - tính số slots thiếu
        if slot1.slot == '15H' and slot2.slot == '8H':
            # Số ngày thiếu = total_days_gap - 1 (trừ ngày tiếp theo hợp lệ)
            missing_days = total_days_gap - 1
            return False, f"Thiếu {missing_days} ngày dữ liệu"
        elif slot1.slot == '8H' and slot2.slot == '15H':
            if slot1.date_value == slot2.date_value:
                return True, ""  # Cùng ngày
            else:
                missing = total_days_gap * 2 - 1  # Số slots thiếu
                return False, f"Thiếu {missing} slots dữ liệu"
        elif slot1.slot == '8H' and slot2.slot == '8H':
            missing = total_days_gap * 2 - 1  # Thiếu 15H hôm trước + các slots khác
            return False, f"Thiếu {missing} slots dữ liệu"
        elif slot1.slot == '15H' and slot2.slot == '15H':
            missing = total_days_gap * 2 - 1  # Thiếu 8H hôm sau + các slots khác
            return False, f"Thiếu {missing} slots dữ liệu"
        else:
            return False, f"Thiếu {total_days_gap - 1} ngày dữ liệu"
    
    # slot2 không đúng expected_next
    if slot2.slot != expected_next.slot:
        return False, f"Thiếu slot {expected_next.display_label()}"
    
    return False, f"Không liên tục: mong đợi {expected_next.display_label()}"


def detect_slot_gaps(slots: List[DateSlot]) -> List[Dict]:
    """
    Phát hiện các GAP (khoảng trống) trong chuỗi slots.
    
    Args:
        slots: Danh sách slots đã sắp xếp theo thời gian
    
    Returns:
        List các gaps được phát hiện
    """
    if len(slots) < 2:
        return []
    
    gaps = []
    
    for i in range(len(slots) - 1):
        slot1 = slots[i]
        slot2 = slots[i + 1]
        
        is_continuous, gap_desc = is_slot_continuous(slot1, slot2)
        
        if not is_continuous:
            gaps.append({
                'slot_before': slot1,
                'slot_after': slot2,
                'gap_description': gap_desc,
                'expected_slot': get_expected_previous_slot(slot2) if slot2 != slot1 else None,
                'is_weekend_gap': 'cuối tuần' in gap_desc.lower() if gap_desc else False
            })
    
    return gaps


def check_slots_already_in_database(
    slots: List[DateSlot], 
    output_dir: Path
) -> List[Dict]:
    """
    Kiểm tra xem các slots đã có dữ liệu trong database chưa.
    
    Args:
        slots: Danh sách slots cần kiểm tra
        output_dir: Thư mục output (chứa database)
    
    Returns:
        List các slots đã tồn tại trong database
    """
    from utils.history_db import HistoryDatabase
    
    duplicates = []
    
    try:
        history_db = HistoryDatabase(output_dir)
        
        for slot in slots:
            df = history_db.get_snapshot_for_date_slot(slot.date_value, slot.slot)
            
            if not df.empty:
                duplicates.append({
                    'slot': slot,
                    'existing_count': len(df),
                    'message': f"Slot {slot.display_label()} đã có {len(df)} container trong database"
                })
    except Exception as e:
        logging.warning(f"Không thể kiểm tra database: {e}")
    
    return duplicates


def compare_slots_chain(
    input_dir: Path,
    grouped_files_slot: Dict[DateSlot, Dict[str, str]], 
    slots: List[DateSlot]
) -> List[Dict]:
    """
    So sánh TON MOI của slot N với TON CU của slot N+1 (nếu cả 2 đều có file).
    
    Logic: TON MOI slot N phải = TON CU slot N+1
    Ví dụ: TON MOI của 09.01 15H phải khớp với TON CU của 10.01 8H
    
    Args:
        input_dir: Đường dẫn thư mục input
        grouped_files_slot: Files đã nhóm theo DateSlot
        slots: Danh sách DateSlot cần xử lý (đã sắp xếp)
    
    Returns:
        List kết quả so sánh cho từng cặp slot liên tiếp
    """
    import pandas as pd
    from config import Col
    
    results = []
    
    for i in range(len(slots) - 1):
        slot_n = slots[i]
        slot_n1 = slots[i + 1]
        
        files_n = grouped_files_slot.get(slot_n, {})
        files_n1 = grouped_files_slot.get(slot_n1, {})
        
        # Chỉ so sánh nếu slot N có TON MOI và slot N+1 có TON CU
        if 'ton_moi' not in files_n:
            results.append({
                'slot_n': slot_n,
                'slot_n1': slot_n1,
                'status': 'skipped',
                'reason': f'Thiếu TON MOI trong {slot_n.display_label()}'
            })
            continue
        
        if 'ton_cu' not in files_n1:
            # V5.5: CẢNH BÁO QUAN TRỌNG - Thiếu TON CU trong slot sau
            results.append({
                'slot_n': slot_n,
                'slot_n1': slot_n1,
                'status': 'missing_ton_cu',
                'reason': f'⚠️ THIẾU FILE TON CU trong {slot_n1.display_label()}',
                'suggestion': f'Hệ thống sẽ dùng TON MOI của {slot_n.display_label()} làm TON CU'
            })
            continue
        
        # Load 2 files và so sánh
        try:
            ton_moi_file = input_dir / files_n['ton_moi']
            ton_cu_file = input_dir / files_n1['ton_cu']
            
            df_ton_moi = pd.read_excel(ton_moi_file)
            df_ton_cu = pd.read_excel(ton_cu_file)
            
            # Tìm cột container
            container_col = None
            for col in df_ton_moi.columns:
                if 'container' in col.lower() or col == Col.CONTAINER:
                    container_col = col
                    break
            if not container_col:
                container_col = df_ton_moi.columns[0]
            
            # Lấy set containers
            set_ton_moi = set(df_ton_moi[container_col].dropna().astype(str).str.strip().str.upper())
            
            # Tìm cột trong TON CU
            ton_cu_col = None
            for col in df_ton_cu.columns:
                if 'container' in col.lower() or col == Col.CONTAINER:
                    ton_cu_col = col
                    break
            if not ton_cu_col:
                ton_cu_col = df_ton_cu.columns[0]
            
            set_ton_cu = set(df_ton_cu[ton_cu_col].dropna().astype(str).str.strip().str.upper())
            
            # So sánh
            common = set_ton_moi & set_ton_cu
            only_in_moi = set_ton_moi - set_ton_cu  # Có trong TON MOI N nhưng không có trong TON CU N+1
            only_in_cu = set_ton_cu - set_ton_moi   # Có trong TON CU N+1 nhưng không có trong TON MOI N
            
            match_rate = len(common) / max(len(set_ton_moi), 1) * 100
            
            if match_rate >= 99:
                status = 'match'
            elif match_rate >= 95:
                status = 'mostly_match'
            else:
                status = 'mismatch'
            
            results.append({
                'slot_n': slot_n,
                'slot_n1': slot_n1,
                'status': status,
                'ton_moi_count': len(set_ton_moi),
                'ton_cu_count': len(set_ton_cu),
                'common_count': len(common),
                'only_in_moi': len(only_in_moi),
                'only_in_cu': len(only_in_cu),
                'match_rate': match_rate,
                'message': f"TON MOI {slot_n.display_label()}: {len(set_ton_moi)} | "
                          f"TON CU {slot_n1.display_label()}: {len(set_ton_cu)} | "
                          f"Khớp: {match_rate:.1f}%"
            })
            
        except Exception as e:
            results.append({
                'slot_n': slot_n,
                'slot_n1': slot_n1,
                'status': 'error',
                'error': str(e)
            })
    
    return results


def format_slot_chain_validation_message(comparison_results: List[Dict]) -> str:
    """
    V5.5: Tạo message tóm tắt kết quả so sánh chain cho DateSlots.
    
    Args:
        comparison_results: Kết quả từ compare_slots_chain()
    
    Returns:
        Message string để hiển thị cho user
    """
    if not comparison_results:
        return "Không có cặp slot liên tiếp để so sánh."
    
    lines = ["=== KIỂM TRA TÍNH LIÊN TỤC (TON MOI slot N = TON CU slot N+1) ===\n"]
    lines.append("📋 Logic: Tồn MỚI của ca trước phải khớp với Tồn CŨ của ca sau.\n")
    lines.append("Ví dụ: TON MOI 09.01 (15H) → TON CU 10.01 (8H)\n")
    
    has_issue = False
    missing_ton_cu_count = 0
    mismatch_count = 0
    
    for r in comparison_results:
        slot_n = r['slot_n'].display_label()
        slot_n1 = r['slot_n1'].display_label()
        
        if r['status'] == 'match':
            lines.append(f"✅ {slot_n} → {slot_n1}: KHỚP ({r['match_rate']:.1f}%)")
        elif r['status'] == 'mostly_match':
            lines.append(f"⚠️ {slot_n} → {slot_n1}: Gần khớp ({r['match_rate']:.1f}%)")
            lines.append(f"   Chênh lệch: +{r['only_in_cu']} / -{r['only_in_moi']} containers")
            has_issue = True
        elif r['status'] == 'mismatch':
            lines.append(f"❌ {slot_n} → {slot_n1}: KHÔNG KHỚP ({r['match_rate']:.1f}%)")
            lines.append(f"   TON MOI {slot_n}: {r['ton_moi_count']} container")
            lines.append(f"   TON CU {slot_n1}: {r['ton_cu_count']} container")
            lines.append(f"   Chênh lệch: +{r['only_in_cu']} / -{r['only_in_moi']}")
            has_issue = True
            mismatch_count += 1
        elif r['status'] == 'missing_ton_cu':
            lines.append(f"⚠️ {slot_n} → {slot_n1}: THIẾU TON CU")
            lines.append(f"   {r.get('suggestion', '')}")
            has_issue = True
            missing_ton_cu_count += 1
        elif r['status'] == 'skipped':
            lines.append(f"⏭️ {slot_n} → {slot_n1}: Bỏ qua ({r.get('reason', '')})")
        else:
            lines.append(f"❓ {slot_n} → {slot_n1}: Lỗi - {r.get('error', 'Unknown')}")
            has_issue = True
    
    lines.append("")  # Blank line
    
    if missing_ton_cu_count > 0:
        lines.append(f"⚠️ CẢNH BÁO: {missing_ton_cu_count} slot THIẾU FILE TON CU!")
        lines.append("   → Hệ thống sẽ tự động dùng TON MOI của slot trước làm TON CU.")
        lines.append("   → Đảm bảo TON MOI của slot trước là chính xác!\n")
    
    if mismatch_count > 0:
        lines.append(f"❌ CẢNH BÁO: {mismatch_count} cặp slot KHÔNG KHỚP!")
        lines.append("   → Có thể bạn đang dùng file TON CU không đúng.")
        lines.append("   → Kiểm tra lại file TON CU hoặc bỏ file để hệ thống tự dùng TON MOI slot trước.\n")
    
    if has_issue:
        lines.append("Bạn có thể:")
        lines.append("  ✅ Tiếp tục - hệ thống sẽ dùng TON MOI slot trước làm TON CU")
        lines.append("  ❌ Hủy - kiểm tra lại dữ liệu đầu vào")
    else:
        lines.append("✅ Dữ liệu liên tục, hợp lệ!")
    
    return "\n".join(lines)


class BatchProcessor:
    """
    Xử lý batch nhiều ngày dữ liệu liên tục.
    
    Usage:
        processor = BatchProcessor(input_dir, output_dir)
        dates = processor.get_available_dates()
        results = processor.run_batch(dates)
    """
    
    def __init__(
        self, 
        input_dir: Path, 
        output_dir: Path,
        update_status: Optional[Callable[[str], None]] = None,
        update_progress: Optional[Callable[[int], None]] = None
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.update_status = update_status or (lambda x: logging.info(x))
        self.update_progress = update_progress or (lambda x: None)
        
        # V5.1: Sử dụng DateSlot thay vì date
        self.grouped_files_slot: Dict[DateSlot, Dict[str, str]] = {}
        # Backward compatibility - giữ lại grouped_files cho API cũ
        self.grouped_files: Dict[date, Dict[str, str]] = {}
        self.results: List[Dict] = []
        self._previous_ton_moi: Optional[pd.DataFrame] = None
    
    def scan_files(self) -> Dict[DateSlot, Dict[str, str]]:
        """Quét và nhóm files theo DateSlot (ngày + time slot)."""
        self.update_status("Đang quét và nhóm files theo ngày/slot...")
        self.grouped_files_slot = group_files_by_date_slot(self.input_dir)
        # Backward compatibility: tạo grouped_files từ grouped_files_slot
        self.grouped_files = {}
        for slot, files in self.grouped_files_slot.items():
            if slot.date_value not in self.grouped_files:
                self.grouped_files[slot.date_value] = {}
            self.grouped_files[slot.date_value].update(files)
        return self.grouped_files_slot
    
    def get_available_slots(self) -> List[DateSlot]:
        """Lấy danh sách DateSlot có dữ liệu (API mới)."""
        if not self.grouped_files_slot:
            self.scan_files()
        return sorted(self.grouped_files_slot.keys())
    
    def get_available_dates(self) -> List[date]:
        """Lấy danh sách ngày có dữ liệu (backward compatibility)."""
        if not self.grouped_files_slot:
            self.scan_files()
        return sorted(set(slot.date_value for slot in self.grouped_files_slot.keys()))
    
    def get_date_summary(self) -> str:
        """Tạo tóm tắt các DateSlots và files tìm thấy."""
        if not self.grouped_files_slot:
            self.scan_files()
        
        lines = []
        for slot in sorted(self.grouped_files_slot.keys()):
            files = self.grouped_files_slot[slot]
            lines.append(f"\n📅 {slot.display_label()}:")
            for ftype, fname in files.items():
                lines.append(f"   • {ftype}: {fname}")
        
        return "\n".join(lines) if lines else "Không tìm thấy dữ liệu theo ngày."
    
    def validate(self, dates: Optional[List[date]] = None) -> List[str]:
        """Kiểm tra tính hợp lệ trước khi chạy."""
        if not self.grouped_files:
            self.scan_files()
        
        dates = dates or self.get_available_dates()
        return validate_date_chain(self.grouped_files, dates)
    
    def validate_slots(self, slots: Optional[List[DateSlot]] = None) -> Dict[str, Any]:
        """
        V5.5: Kiểm tra tính hợp lệ và liên tục của các DateSlots trước khi chạy.
        
        Kiểm tra:
        1. Mỗi slot có file TON MOI (bắt buộc)
        2. Slot đầu tiên cần có TON CU (hoặc sẽ dùng từ database)
        3. Phát hiện GAP (thiếu slots) trong chuỗi thời gian
        4. Phát hiện TRÙNG LẶP với data đã lưu trong database
        5. So sánh TON MOI slot N với TON CU slot N+1 (nếu có cả 2 file)
        
        Args:
            slots: Danh sách DateSlot cần xử lý (None = tất cả)
        
        Returns:
            Dict với các keys:
                - 'warnings': List[str] - Cảnh báo/lỗi cơ bản
                - 'chain_results': List[Dict] - Kết quả so sánh chain chi tiết
                - 'gaps': List[Dict] - Các khoảng trống được phát hiện
                - 'duplicates': List[Dict] - Các slots đã có trong database
                - 'has_critical_issues': bool - True nếu có vấn đề nghiêm trọng
        """
        if not self.grouped_files_slot:
            self.scan_files()
        
        slots = slots or self.get_available_slots()
        
        warnings = []
        has_critical_issues = False
        
        for i, slot in enumerate(slots):
            files = self.grouped_files_slot.get(slot, {})
            
            # Kiểm tra file TON MOI bắt buộc
            if 'ton_moi' not in files:
                warnings.append(f"❌ {slot.display_label()}: Thiếu file TON MOI (bắt buộc)")
                has_critical_issues = True
            
            # Slot đầu tiên cần có TON CU (hoặc sẽ dùng từ database)
            if i == 0 and 'ton_cu' not in files:
                warnings.append(f"⚠️ {slot.display_label()}: Slot đầu tiên không có file TON CU - sẽ thử tải từ database")
        
        # Phát hiện GAP trong chuỗi slots
        gaps = []
        if len(slots) > 1:
            gaps = detect_slot_gaps(slots)
            for gap in gaps:
                if not gap.get('is_weekend_gap', False):
                    warnings.append(
                        f"⚠️ THIẾU DỮ LIỆU: {gap['slot_before'].display_label()} → {gap['slot_after'].display_label()}: "
                        f"{gap['gap_description']}"
                    )
        
        # Kiểm tra TRÙNG LẶP với database
        duplicates = check_slots_already_in_database(slots, self.output_dir)
        if duplicates:
            for dup in duplicates:
                warnings.append(
                    f"⚠️ TRÙNG LẶP: {dup['slot'].display_label()} đã có {dup['existing_count']} container trong database"
                )
        
        # So sánh chain nếu có nhiều hơn 1 slot
        chain_results = []
        if len(slots) > 1:
            chain_results = compare_slots_chain(self.input_dir, self.grouped_files_slot, slots)
        
        return {
            'warnings': warnings,
            'chain_results': chain_results,
            'gaps': gaps,
            'duplicates': duplicates,
            'has_critical_issues': has_critical_issues
        }

    def run_batch(
        self, 
        dates: Optional[List[date]] = None,
        confirm_callback: Optional[Callable[[str], bool]] = None
    ) -> List[Dict]:
        """
        Chạy đối soát cho nhiều ngày liên tục.
        
        Args:
            dates: Danh sách ngày cần xử lý (None = tất cả)
            confirm_callback: Callback hỏi user khi có vấn đề
        
        Returns:
            List kết quả cho từng ngày
        """
        from core_logic import run_full_reconciliation_process
        from data.data_loader import load_all_data
        
        if not self.grouped_files:
            self.scan_files()
        
        dates = dates or self.get_available_dates()
        if not dates:
            self.update_status("❌ Không tìm thấy ngày nào để xử lý!")
            return []
        
        # Validate
        warnings = self.validate(dates)
        if warnings:
            msg = "Các cảnh báo:\n" + "\n".join(warnings)
            self.update_status(f"⚠️ {msg}")
            if confirm_callback and not confirm_callback(msg + "\n\nBạn có muốn tiếp tục?"):
                return []
        
        total_days = len(dates)
        self.results = []
        self._previous_ton_moi = None
        
        for idx, current_date in enumerate(dates):
            progress_base = int((idx / total_days) * 100)
            self.update_progress(progress_base)
            
            self.update_status(f"📅 [{idx+1}/{total_days}] Đang xử lý ngày {current_date.strftime('%d/%m/%Y')}...")
            
            try:
                result = self._process_single_day(current_date, idx == 0)
                self.results.append(result)
                
                # Lưu TON MOI để làm TON CU cho ngày tiếp theo
                if result.get('success') and result.get('ton_moi_df') is not None:
                    self._previous_ton_moi = result['ton_moi_df']
                    self.update_status(f"✅ Ngày {current_date.strftime('%d/%m/%Y')}: Hoàn tất ({len(self._previous_ton_moi)} containers)")
                else:
                    self.update_status(f"⚠️ Ngày {current_date.strftime('%d/%m/%Y')}: Có lỗi")
                    
            except Exception as e:
                logging.error(f"Lỗi xử lý ngày {current_date}: {e}")
                self.results.append({
                    'date': current_date,
                    'success': False,
                    'error': str(e)
                })
        
        self.update_progress(100)
        self.update_status(f"🎉 Hoàn tất xử lý {total_days} ngày!")
        
        return self.results
    
    def run_batch_slots(
        self, 
        slots: Optional[List[DateSlot]] = None,
        confirm_callback: Optional[Callable[[str], bool]] = None
    ) -> List[Dict]:
        """
        Chạy đối soát cho nhiều DateSlots liên tục (API mới).
        
        Args:
            slots: Danh sách DateSlot cần xử lý (None = tất cả)
            confirm_callback: Callback hỏi user khi có vấn đề
        
        Returns:
            List kết quả cho từng slot
        """
        from core_logic import run_full_reconciliation_process
        from data.data_loader import load_all_data
        
        if not self.grouped_files_slot:
            self.scan_files()
        
        slots = slots or self.get_available_slots()
        if not slots:
            self.update_status("❌ Không tìm thấy slot nào để xử lý!")
            return []
        
        total_slots = len(slots)
        self.results = []
        self._previous_ton_moi = None
        
        for idx, current_slot in enumerate(slots):
            progress_base = int((idx / total_slots) * 100)
            self.update_progress(progress_base)
            
            self.update_status(f"📅 [{idx+1}/{total_slots}] Đang xử lý {current_slot.display_label()}...")
            
            try:
                result = self._process_single_slot(current_slot, idx == 0)
                self.results.append(result)
                
                # Lưu TON MOI để làm TON CU cho slot tiếp theo
                if result.get('success') and result.get('ton_moi_df') is not None:
                    self._previous_ton_moi = result['ton_moi_df']
                    self.update_status(f"✅ {current_slot.display_label()}: Hoàn tất ({len(self._previous_ton_moi)} containers)")
                else:
                    self.update_status(f"⚠️ {current_slot.display_label()}: Có lỗi")
                    
            except Exception as e:
                logging.error(f"Lỗi xử lý slot {current_slot}: {e}")
                self.results.append({
                    'slot': current_slot,
                    'date': current_slot.date_value,
                    'success': False,
                    'error': str(e)
                })
        
        self.update_progress(100)
        self.update_status(f"🎉 Hoàn tất xử lý {total_slots} slots!")
        
        return self.results

    
    def _process_single_day(self, target_date: date, is_first_day: bool) -> Dict:
        """
        Xử lý một ngày duy nhất.
        
        Args:
            target_date: Ngày cần xử lý
            is_first_day: True nếu là ngày đầu tiên trong chuỗi
        
        Returns:
            Dictionary kết quả
        """
        from data.data_loader import load_all_data
        from core.reconciliation_engine import perform_reconciliation
        from core.advanced_checker import perform_simple_reconciliation
        from core.inventory_checker import compare_inventories
        from reports.operator_analyzer import analyze_by_operator
        from reports.report_generator import create_reports
        from utils.history_db import HistoryDatabase
        from core_logic import create_summary_dataframe, save_results
        
        files_for_date = self.grouped_files.get(target_date, {})
        date_label = target_date.strftime('%d/%m/%Y')
        
        if 'ton_moi' not in files_for_date:
            return {
                'date': target_date,
                'success': False,
                'error': 'Thiếu file TON MOI'
            }
        
        # V5.0: Detailed progress messages
        self.update_status(f"📁 {date_label}: Tạo thư mục báo cáo...")
        
        # Tạo thư mục output cho ngày này - V5.1.5: Format ngắn gọn
        time_part = datetime.now().strftime("%Hh%M")
        date_part = target_date.strftime("N%d.%m.%Y")
        report_folder = self.output_dir / f"Report_{date_part}_{time_part}"
        report_folder.mkdir(parents=True, exist_ok=True)
        
        run_time = datetime.combine(target_date, datetime.min.time())
        
        # V5.0: Step 1 - Load data
        self.update_status(f"📂 {date_label}: Đang tải {len(files_for_date)} files...")
        file_dfs = load_all_data(files_for_date, self.input_dir, report_folder)
        
        # Xử lý TON CU: dùng của ngày trước nếu có
        if not is_first_day and self._previous_ton_moi is not None:
            # TON CU = TON MOI của ngày trước
            file_dfs['ton_cu'] = self._previous_ton_moi.copy()
            self.update_status(f"🔗 {date_label}: Dùng TON MOI ngày trước làm TON CU ({len(self._previous_ton_moi)} conts)")
        elif 'ton_cu' not in file_dfs or file_dfs.get('ton_cu', pd.DataFrame()).empty:
            # Thử tải từ database
            try:
                history_db = HistoryDatabase(self.output_dir)
                ton_cu_from_db = history_db.get_yesterday_as_ton_cu()
                if not ton_cu_from_db.empty:
                    file_dfs['ton_cu'] = ton_cu_from_db
                    self.update_status(f"💾 {date_label}: Tải TON CU từ database ({len(ton_cu_from_db)} conts)")
            except Exception as e:
                logging.warning(f"Không thể tải TON CU từ database: {e}")
        
        # V5.0: Step 2 - Run reconciliation
        self.update_status(f"⚙️ {date_label}: Đang chạy đối soát...")
        main_results = perform_reconciliation(file_dfs, report_folder, run_time)
        
        self.update_status(f"🔍 {date_label}: Kiểm tra SourceKey...")
        simple_results = perform_simple_reconciliation(file_dfs)
        
        self.update_status(f"📊 {date_label}: Phân tích biến động...")
        inventory_change_results = compare_inventories(file_dfs)
        operator_analysis_result = analyze_by_operator(file_dfs)
        
        # V5.0: Step 3 - Create summary
        self.update_status(f"📋 {date_label}: Tạo báo cáo tổng hợp...")
        summary_df = create_summary_dataframe(main_results, simple_results, inventory_change_results)
        
        # Chạy Delta Analysis (so sánh với lần chạy trước)
        try:
            from core.delta_checker import perform_delta_analysis
            delta_analysis_result = perform_delta_analysis(
                summary_df.set_index('Hang muc'), 
                self.output_dir, 
                report_folder.name
            )
        except Exception as e:
            logging.warning(f"Could not perform delta analysis: {e}")
            delta_analysis_result = {}
        
        # Gộp kết quả
        final_results = {
            "main_results": main_results,
            "simple_results": simple_results,
            "inventory_change_results": inventory_change_results,
            "operator_analysis_result": operator_analysis_result,
            "delta_analysis_result": delta_analysis_result,
            "summary_df": summary_df,
            "quality_warnings": [],
            "report_folder": report_folder,
            "run_timestamp": run_time
        }
        
        # V5.0: Step 4 - Create reports
        self.update_status(f"📝 {date_label}: Tạo file báo cáo Excel...")
        create_reports(final_results)
        save_results(final_results, self.output_dir)
        
        # V5.0: Step 5 - Save to history
        self.update_status(f"💾 {date_label}: Lưu vào database...")
        try:
            history_db = HistoryDatabase(self.output_dir)
            history_db.save_run(final_results)
            
            df_ton_moi = file_dfs.get('ton_moi', pd.DataFrame())
            if not df_ton_moi.empty:
                history_db.save_daily_snapshot(df_ton_moi, run_time)
        except Exception as e:
            logging.warning(f"Không thể lưu vào history: {e}")
        
        return {
            'date': target_date,
            'success': True,
            'report_folder': report_folder,
            'summary_df': summary_df,
            'ton_moi_df': file_dfs.get('ton_moi'),
            'ton_cu_count': len(file_dfs.get('ton_cu', pd.DataFrame())),
            'ton_moi_count': len(file_dfs.get('ton_moi', pd.DataFrame()))
        }
    
    def _process_single_slot(self, target_slot: DateSlot, is_first_slot: bool) -> Dict:
        """
        Xử lý một DateSlot duy nhất (API mới hỗ trợ time slots).
        
        Args:
            target_slot: DateSlot cần xử lý
            is_first_slot: True nếu là slot đầu tiên trong chuỗi
        
        Returns:
            Dictionary kết quả
        """
        from data.data_loader import load_all_data
        from core.reconciliation_engine import perform_reconciliation
        from core.advanced_checker import perform_simple_reconciliation
        from core.inventory_checker import compare_inventories
        from reports.operator_analyzer import analyze_by_operator
        from reports.report_generator import create_reports
        from utils.history_db import HistoryDatabase
        from core_logic import create_summary_dataframe, save_results
        
        files_for_slot = self.grouped_files_slot.get(target_slot, {})
        slot_label = target_slot.display_label()
        
        if 'ton_moi' not in files_for_slot:
            return {
                'slot': target_slot,
                'date': target_slot.date_value,
                'success': False,
                'error': 'Thiếu file TON MOI'
            }
        
        self.update_status(f"📁 {slot_label}: Tạo thư mục báo cáo...")
        
        # Tạo thư mục output cho slot này
        time_part = datetime.now().strftime("%Hh%M")
        date_part = target_slot.date_value.strftime("N%d.%m.%Y")
        slot_suffix = f"_{target_slot.slot}" if target_slot.slot else ""
        report_folder = self.output_dir / f"Report_{date_part}{slot_suffix}_{time_part}"
        report_folder.mkdir(parents=True, exist_ok=True)
        
        run_time = datetime.combine(target_slot.date_value, datetime.min.time())
        
        # Load data
        # V5.2.1: Đếm số files thực (không tính duplicate_warnings)
        actual_file_count = len([k for k in files_for_slot.keys() if k != 'duplicate_warnings'])
        self.update_status(f"📂 {slot_label}: Đang tải {actual_file_count} files...")
        file_dfs = load_all_data(files_for_slot, self.input_dir, report_folder)
        
        # Xử lý TON CU: dùng TON MOI của slot trước nếu có
        if not is_first_slot and self._previous_ton_moi is not None:
            file_dfs['ton_cu'] = self._previous_ton_moi.copy()
            self.update_status(f"🔗 {slot_label}: Dùng TON MOI slot trước làm TON CU ({len(self._previous_ton_moi)} conts)")
        elif 'ton_cu' not in file_dfs or file_dfs.get('ton_cu', pd.DataFrame()).empty:
            try:
                history_db = HistoryDatabase(self.output_dir)
                ton_cu_from_db = history_db.get_previous_slot_as_ton_cu(target_slot.date_value, target_slot.slot)
                if not ton_cu_from_db.empty:
                    file_dfs['ton_cu'] = ton_cu_from_db
                    self.update_status(f"💾 {slot_label}: Tải TON CU từ database ({len(ton_cu_from_db)} conts)")
            except Exception as e:
                logging.warning(f"Không thể tải TON CU từ database: {e}")
        
        # Run reconciliation
        self.update_status(f"⚙️ {slot_label}: Đang chạy đối soát...")
        main_results = perform_reconciliation(file_dfs, report_folder, run_time)
        
        self.update_status(f"🔍 {slot_label}: Kiểm tra SourceKey...")
        simple_results = perform_simple_reconciliation(file_dfs)
        
        self.update_status(f"📊 {slot_label}: Phân tích biến động...")
        inventory_change_results = compare_inventories(file_dfs)
        operator_analysis_result = analyze_by_operator(file_dfs)
        
        # Create summary
        self.update_status(f"📋 {slot_label}: Tạo báo cáo tổng hợp...")
        summary_df = create_summary_dataframe(main_results, simple_results, inventory_change_results)
        
        # Delta Analysis
        try:
            from core.delta_checker import perform_delta_analysis
            delta_analysis_result = perform_delta_analysis(
                summary_df.set_index('Hang muc'), 
                self.output_dir, 
                report_folder.name
            )
        except Exception as e:
            logging.warning(f"Could not perform delta analysis: {e}")
            delta_analysis_result = {}
        
        final_results = {
            "main_results": main_results,
            "simple_results": simple_results,
            "inventory_change_results": inventory_change_results,
            "operator_analysis_result": operator_analysis_result,
            "delta_analysis_result": delta_analysis_result,
            "summary_df": summary_df,
            "quality_warnings": [],
            "report_folder": report_folder,
            "run_timestamp": run_time,
            "time_slot": target_slot.slot  # V5.1: Thêm time_slot
        }
        
        # Create reports
        self.update_status(f"📝 {slot_label}: Tạo file báo cáo Excel...")
        create_reports(final_results)
        save_results(final_results, self.output_dir)
        
        # Save to history with time_slot
        self.update_status(f"💾 {slot_label}: Lưu vào database...")
        try:
            history_db = HistoryDatabase(self.output_dir)
            history_db.save_run(final_results)
            
            df_ton_moi = file_dfs.get('ton_moi', pd.DataFrame())
            if not df_ton_moi.empty:
                history_db.save_daily_snapshot_with_slot(df_ton_moi, run_time, target_slot.slot)
        except Exception as e:
            logging.warning(f"Không thể lưu vào history: {e}")
        
        return {
            'slot': target_slot,
            'date': target_slot.date_value,
            'success': True,
            'report_folder': report_folder,
            'summary_df': summary_df,
            'ton_moi_df': file_dfs.get('ton_moi'),
            'ton_cu_count': len(file_dfs.get('ton_cu', pd.DataFrame())),
            'ton_moi_count': len(file_dfs.get('ton_moi', pd.DataFrame()))
        }
    
    def get_batch_summary(self) -> pd.DataFrame:
        """Tạo bảng tóm tắt kết quả batch."""
        rows = []
        for r in self.results:
            # V5.1: Hỗ trợ cả date và slot
            if 'slot' in r and r.get('slot'):
                label = r['slot'].display_label()
            elif r.get('date'):
                label = r['date'].strftime('%d/%m/%Y')
            else:
                label = 'N/A'
            
            rows.append({
                'Ngày/Slot': label,
                'Trạng thái': '✅ Thành công' if r.get('success') else '❌ Lỗi',
                'TON CU': r.get('ton_cu_count', 0),
                'TON MOI': r.get('ton_moi_count', 0),
                'Ghi chú': r.get('error', '')
            })
        return pd.DataFrame(rows)
