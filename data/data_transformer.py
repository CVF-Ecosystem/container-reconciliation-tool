# File: data_transformer.py
import pandas as pd
import logging
import re
from unidecode import unidecode
from config import Col, TIME_PRIORITY_COLS, BUSINESS_RULES

def normalize_vietnamese_text(series: pd.Series) -> pd.Series:
    """Chuẩn hóa text: bỏ dấu, chuyển sang in hoa, loại bỏ khoảng trắng thừa."""
    if series.empty or pd.api.types.is_numeric_dtype(series):
        return series
    return series.astype(str).apply(unidecode).str.upper().str.strip()

def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hóa tên cột: loại bỏ khoảng trắng thừa, chuyển thành chuỗi."""
    df.columns = [re.sub(r'\s+', ' ', str(col)).strip() for col in df.columns]
    return df

def standardize_datetime_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Chuyển đổi các cột thời gian, luôn ưu tiên định dạng dd/mm/yyyy."""
    for col in TIME_PRIORITY_COLS:
        if col in df.columns:
            s = df[col].astype(str)
            df[col] = pd.to_datetime(s, dayfirst=True, errors='coerce')
    return df

def assign_transaction_time(df: pd.DataFrame) -> pd.DataFrame:
    """Xác định ThoiDiemGiaoDich chính dựa trên các cột ưu tiên."""
    df[Col.TRANSACTION_TIME] = pd.NaT
    for col in TIME_PRIORITY_COLS:
        if col in df.columns:
            df[Col.TRANSACTION_TIME] = df[Col.TRANSACTION_TIME].fillna(df[col])
    df[Col.TRANSACTION_TIME] = df[Col.TRANSACTION_TIME].fillna(pd.to_datetime('1970-01-01'))
    return df

def apply_business_rules(df: pd.DataFrame) -> pd.DataFrame:
    """Áp dụng các quy tắc nghiệp vụ để xác định LoaiGiaoDich (MOVE_TYPE)."""
    df[Col.MOVE_TYPE] = 'UNKNOWN'
    for rule in BUSINESS_RULES:
        conditions, action = rule['conditions'], rule['action']
        mask = (df[Col.MOVE_TYPE] == 'UNKNOWN')
        for col, values in conditions.items():
            if col in df.columns:
                mask &= df[col].astype(str).str.upper().isin([v.upper() for v in values])
        df.loc[mask, Col.MOVE_TYPE] = action['move_type']
    
    unknown_moves = df[df[Col.MOVE_TYPE] == 'UNKNOWN']
    if not unknown_moves.empty:
        logging.warning(f"Tìm thấy {len(unknown_moves)} giao dịch không thể phân loại bằng Rule Engine.")
    return df