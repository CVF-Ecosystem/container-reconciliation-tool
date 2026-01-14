# File: time_slot_filter.py (V5.1.4)
# Filter biến động theo time slot yêu cầu của từng hãng tàu
"""
Logic:
- VMC/SVM: Chia theo ca (15h hôm trước - 8h = sáng, 8h - 15h = chiều)
- VOC/SVC, VFC/SVF và các hãng khác: Nguyên ngày (8h - 8h)

Cách sử dụng:
1. Load config từ HANG_TAU_TIME_CONFIG
2. Filter DataFrame theo operator và time range
"""

import pandas as pd
import json
import logging
from pathlib import Path
from datetime import datetime, time, timedelta
from typing import Dict, Any, Optional, Tuple

# Load config
def load_time_config() -> Dict[str, Any]:
    """Load HANG_TAU_TIME_CONFIG từ config_mappings.json"""
    config_path = Path(__file__).parent.parent / "config_mappings.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("HANG_TAU_TIME_CONFIG", {})
    except Exception as e:
        logging.error(f"Không thể load time config: {e}")
        return {}

HANG_TAU_TIME_CONFIG = load_time_config()


def get_operator_time_config(operator_code: str) -> Dict[str, Any]:
    """
    Lấy config thời gian cho một operator code.
    Trả về DEFAULT nếu không có config riêng.
    """
    return HANG_TAU_TIME_CONFIG.get(operator_code, HANG_TAU_TIME_CONFIG.get("DEFAULT", {
        "mode": "full_day",
        "time_range": {"from": "08:00", "to": "08:00", "cross_day": True}
    }))


def parse_time(time_str: str) -> time:
    """Parse string 'HH:MM' thành datetime.time"""
    h, m = map(int, time_str.split(':'))
    return time(h, m)


def get_time_range_for_date(
    operator_code: str, 
    target_date: datetime, 
    shift: str = "full"
) -> Tuple[datetime, datetime]:
    """
    Tính time range cho một operator vào một ngày cụ thể.
    
    Args:
        operator_code: Mã hãng tàu (VMC, VOC, VFC,...)
        target_date: Ngày cần lấy biến động
        shift: "morning" (ca sáng), "afternoon" (ca chiều), "full" (cả ngày)
    
    Returns:
        Tuple (start_datetime, end_datetime)
    """
    config = get_operator_time_config(operator_code)
    mode = config.get("mode", "full_day")
    
    if mode == "split" and shift != "full":
        # VMC mode: chia ca
        if shift == "morning":
            # Ca sáng: 15h hôm trước - 8h hôm nay
            slot = config.get("ca_sang", {})
            from_time = parse_time(slot.get("from", "15:00"))
            to_time = parse_time(slot.get("to", "08:00"))
            
            # Start = 15h ngày hôm trước
            start_dt = datetime.combine(target_date - timedelta(days=1), from_time)
            # End = 8h ngày target
            end_dt = datetime.combine(target_date, to_time)
            
        else:  # afternoon
            # Ca chiều: 8h - 15h cùng ngày
            slot = config.get("ca_chieu", {})
            from_time = parse_time(slot.get("from", "08:00"))
            to_time = parse_time(slot.get("to", "15:00"))
            
            start_dt = datetime.combine(target_date, from_time)
            end_dt = datetime.combine(target_date, to_time)
    else:
        # Full day mode (VOSCO, VFC, default)
        time_range = config.get("time_range", {"from": "08:00", "to": "08:00"})
        from_time = parse_time(time_range.get("from", "08:00"))
        to_time = parse_time(time_range.get("to", "08:00"))
        cross_day = time_range.get("cross_day", True)
        
        if cross_day:
            # 8h hôm trước - 8h hôm nay
            start_dt = datetime.combine(target_date - timedelta(days=1), from_time)
            end_dt = datetime.combine(target_date, to_time)
        else:
            start_dt = datetime.combine(target_date, from_time)
            end_dt = datetime.combine(target_date, to_time)
    
    return start_dt, end_dt


def filter_by_time_slot(
    df: pd.DataFrame,
    operator_code: str,
    target_date: datetime,
    shift: str = "full",
    time_col: str = None
) -> pd.DataFrame:
    """
    Filter DataFrame theo time slot của hãng tàu.
    
    Args:
        df: DataFrame cần filter
        operator_code: Mã hãng tàu
        target_date: Ngày target
        shift: "morning", "afternoon", "full"
        time_col: Tên cột chứa timestamp (tự detect nếu None)
    
    Returns:
        DataFrame đã filter
    """
    if df.empty:
        return df
    
    # Detect time column
    if time_col is None:
        time_cols = ['ThoiDiemGiaoDich', 'Xe vào cổng', 'Xe ra cổng', 
                     'Container vào bãi', 'Container ra bãi', 
                     'Ngày nhập bãi', 'Ngày ra bãi']
        for col in time_cols:
            if col in df.columns:
                time_col = col
                break
    
    if time_col is None or time_col not in df.columns:
        logging.warning(f"Không tìm thấy cột thời gian để filter cho {operator_code}")
        return df
    
    # Get time range
    start_dt, end_dt = get_time_range_for_date(operator_code, target_date, shift)
    
    # Convert column to datetime
    df = df.copy()
    df['_filter_time'] = pd.to_datetime(df[time_col], errors='coerce')
    
    # Filter
    mask = (df['_filter_time'] >= start_dt) & (df['_filter_time'] < end_dt)
    result = df[mask].drop(columns=['_filter_time'])
    
    logging.debug(f"Filter {operator_code} ({shift}): {len(df)} → {len(result)} records")
    
    return result


def get_shifts_for_operator(operator_code: str) -> list:
    """
    Trả về danh sách các shift cần xử lý cho operator.
    
    Returns:
        ['full'] cho mode full_day
        ['morning', 'afternoon'] cho mode split
    """
    config = get_operator_time_config(operator_code)
    mode = config.get("mode", "full_day")
    
    if mode == "split":
        return ["morning", "afternoon"]
    return ["full"]


def get_shift_display_name(shift: str, lang: str = "vi") -> str:
    """Lấy tên hiển thị cho shift"""
    names = {
        "vi": {"morning": "Ca sáng (15h-8h)", "afternoon": "Ca chiều (8h-15h)", "full": "Cả ngày (8h-8h)"},
        "en": {"morning": "Morning (15h-8h)", "afternoon": "Afternoon (8h-15h)", "full": "Full day (8h-8h)"}
    }
    return names.get(lang, names["vi"]).get(shift, shift)


def get_all_operator_configs() -> Dict[str, Dict]:
    """
    Trả về tất cả config của các hãng để hiển thị trong GUI.
    """
    result = {}
    for code, config in HANG_TAU_TIME_CONFIG.items():
        if code.startswith("_"):  # Skip comments
            continue
        result[code] = {
            "mode": config.get("mode", "full_day"),
            "description": config.get("description", ""),
            "shifts": get_shifts_for_operator(code)
        }
    return result
