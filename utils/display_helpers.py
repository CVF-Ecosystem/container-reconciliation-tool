# File: utils/display_helpers.py — @2026 v1.0
"""
Helper functions for display/UI logic extracted from app.py.
Tách business logic ra khỏi UI để dễ test và tái sử dụng.
"""
import pandas as pd
from typing import Optional
from config import DEFAULT_TEU_FACTOR, Col


def prepare_df_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """
    Chuẩn bị DataFrame để hiển thị an toàn trên Streamlit.
    Chuyển đổi tất cả các cột có kiểu dữ liệu hỗn hợp (object) sang chuỗi.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    df_display = df.copy()
    for col in df_display.columns:
        if df_display[col].dtype == 'object':
            df_display[col] = df_display[col].astype(str).replace('nan', '').replace('NaT', '')
    return df_display


def add_stt_column(df: pd.DataFrame, t=None) -> pd.DataFrame:
    """Thêm cột STT (Số thứ tự) vào đầu DataFrame."""
    if df is None or df.empty:
        return df
    df_copy = df.copy()
    col_name = t('col_stt') if t else 'STT'
    df_copy.insert(0, col_name, range(1, len(df_copy) + 1))
    return df_copy


def format_operator_table(df: pd.DataFrame, t=None, operator_col: str = None) -> pd.DataFrame:
    """
    Format bảng theo Hãng khai thác: thêm STT, đặt lại tên cột Hãng khai thác.
    Handles dataframes where operator is in index or in a column.
    """
    if df is None or df.empty:
        return df
    
    index_name = df.index.name
    df_copy = df.reset_index()
    
    first_col = df_copy.columns[0]
    operator_label = t('col_operator') if t else 'Hãng khai thác'
    
    if first_col in ['index', index_name] or first_col is None:
        df_copy = df_copy.rename(columns={first_col: operator_label})
    elif operator_col and operator_col in df_copy.columns:
        df_copy = df_copy.rename(columns={operator_col: operator_label})
    
    stt_label = t('col_stt') if t else 'STT'
    if stt_label not in df_copy.columns and 'STT' not in df_copy.columns:
        df_copy.insert(0, stt_label, range(1, len(df_copy) + 1))
    
    return df_copy


def calculate_teus(df: pd.DataFrame, size_col: str = None) -> int:
    """
    Tính tổng TEUs từ DataFrame dựa trên kích thước container.
    20ft = 1 TEU, 40ft/45ft = 2 TEUs.
    
    Dùng DEFAULT_TEU_FACTOR từ config khi không có thông tin kích thước.
    """
    if df is None or df.empty:
        return 0
    
    if size_col is None:
        size_col = Col.ISO if hasattr(Col, 'ISO') else None
    
    if size_col is None or size_col not in df.columns:
        # Fallback: dùng DEFAULT_TEU_FACTOR từ config
        return int(len(df) * DEFAULT_TEU_FACTOR)
    
    total_teus = 0
    for size in df[size_col]:
        size_str = str(size).strip().upper() if pd.notna(size) else ''
        if size_str.startswith('4') or size_str.startswith('45'):
            total_teus += 2  # 40ft hoặc 45ft = 2 TEUs
        else:
            total_teus += 1  # 20ft hoặc không rõ = 1 TEU
    
    return total_teus


def add_teus_to_summary(df: pd.DataFrame, count_col: str, size_data: pd.DataFrame = None) -> pd.DataFrame:
    """Thêm cột TEUs vào bảng tổng hợp dùng DEFAULT_TEU_FACTOR."""
    if df is None or df.empty:
        return df
    df_copy = df.copy()
    if count_col in df_copy.columns:
        df_copy['TEUs'] = (df_copy[count_col] * DEFAULT_TEU_FACTOR).astype(int)
    return df_copy


def add_teus_columns_to_operator_table(operator_df: pd.DataFrame, raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Thêm cột TEUs vào bảng operator summary.
    Tính TEUs cho mỗi hãng dựa trên dữ liệu raw.
    """
    if operator_df is None or operator_df.empty:
        return operator_df
    
    df_copy = operator_df.copy()
    operator_col = Col.OPERATOR if hasattr(Col, 'OPERATOR') else None
    
    if raw_df is not None and not raw_df.empty and operator_col and operator_col in raw_df.columns:
        teus_dict = {}
        for operator in df_copy.index:
            operator_data = raw_df[raw_df[operator_col] == operator]
            teus_dict[operator] = calculate_teus(operator_data)
        
        if 'Tồn Mới' in df_copy.columns:
            df_copy['TEUs Mới'] = df_copy.index.map(lambda x: teus_dict.get(x, 0))
        if 'Tồn Cũ' in df_copy.columns:
            df_copy['TEUs Cũ'] = (df_copy['Tồn Cũ'] * DEFAULT_TEU_FACTOR).astype(int)
    else:
        # Fallback: dùng DEFAULT_TEU_FACTOR
        if 'Tồn Mới' in df_copy.columns:
            df_copy['TEUs Mới'] = (df_copy['Tồn Mới'] * DEFAULT_TEU_FACTOR).astype(int)
        if 'Tồn Cũ' in df_copy.columns:
            df_copy['TEUs Cũ'] = (df_copy['Tồn Cũ'] * DEFAULT_TEU_FACTOR).astype(int)
    
    # Sắp xếp lại cột: TEUs ngay sau Conts tương ứng
    new_cols = []
    seen = set()
    for col in df_copy.columns:
        if col not in seen:
            new_cols.append(col)
            seen.add(col)
        if col == 'Tồn Cũ' and 'TEUs Cũ' in df_copy.columns and 'TEUs Cũ' not in seen:
            new_cols.append('TEUs Cũ')
            seen.add('TEUs Cũ')
        if col == 'Tồn Mới' and 'TEUs Mới' in df_copy.columns and 'TEUs Mới' not in seen:
            new_cols.append('TEUs Mới')
            seen.add('TEUs Mới')
    
    return df_copy[new_cols]
