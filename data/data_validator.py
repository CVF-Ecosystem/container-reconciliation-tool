# File: data_validator.py (phiên bản với logic validation linh hoạt)
import pandas as pd
import logging
from typing import Dict, List, Any

def validate_dataframes_structure(all_dfs: Dict[str, pd.DataFrame], config: Dict[str, List[List[str]]]) -> bool:
    """
    Lớp 1: Kiểm tra cấu trúc tối thiểu, hỗ trợ nhiều tên thay thế.
    Dừng chương trình nếu thất bại.
    """
    is_valid = True
    logging.info("--- BẮT ĐẦU KIỂM TRA LỚP 1: CẤU TRÚC TỐI THIỂU ---")
    
    for key, df in all_dfs.items():
        if df.empty: continue
        required_groups = config.get(key)
        if not required_groups: continue

        df_columns = df.columns.tolist()
        for col_group in required_groups:
            found = any(alias in df_columns for alias in col_group)
            if not found:
                logging.error(f"  -> Lỗi Cấu trúc: File '{df.iloc[0]['SourceFile']}' (key: {key}) thiếu cột bắt buộc. Cần có một trong các cột sau: {col_group}")
                is_valid = False
            
    if not is_valid:
        logging.error("--- KIỂM TRA CẤU TRÚC THẤT BẠI: Dữ liệu không đủ để chạy. ---")
    else:
        logging.info("--- KIỂM TRA CẤU TRÚC HOÀN TẤT: Hợp lệ. ---")
        
    return is_valid
def validate_dataframes_quality(all_dfs: Dict[str, pd.DataFrame], config: Dict[str, Any]) -> List[str]:
    """
    Lớp 2: Kiểm tra chất lượng dữ liệu chuyên sâu (thiếu cột, trống, trùng lặp).
    Chỉ đưa ra cảnh báo, không dừng chương trình.
    """
    all_warnings: List[str] = []
    logging.info("--- BẮT ĐẦU KIỂM TRA LỚP 2: CHẤT LƯỢNG DỮ LIỆU ---")

    for key, df in all_dfs.items():
        if df.empty: continue
        
        file_name = df.iloc[0]['SourceFile']
        warnings_for_file = _validate_one_dataframe_quality(df, key, file_name, config)
        all_warnings.extend(warnings_for_file)

    if not all_warnings:
        logging.info("--- KIỂM TRA CHẤT LƯỢNG HOÀN TẤT: Không tìm thấy vấn đề. ---")
    else:
        logging.warning(f"--- KIỂM TRA CHẤT LƯỢNG PHÁT HIỆN {len(all_warnings)} VẤN ĐỀ. Xem file '0e_Data_Quality_Report.xlsx'. ---")
        
    return all_warnings

def _validate_one_dataframe_quality(df: pd.DataFrame, file_key: str, file_name: str, config: Dict[str, Any]) -> List[str]:
    """Hàm phụ, kiểm tra chất lượng cho một DataFrame."""
    warnings = []
    rules = config.get(file_key, {})
    all_rules = config.get('all', {})

    required_cols = set(all_rules.get('required_columns', []) + rules.get('required_columns', []))
    null_checks = {**all_rules.get('check_nulls', {}), **rules.get('check_nulls', {})}

    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        warnings.append(f"Thiếu các cột quan trọng cho phân tích: {', '.join(missing_cols)}")

    for col, threshold in null_checks.items():
        if col in df.columns and not df.empty:
            null_percentage = df[col].isnull().sum() / len(df)
            if null_percentage > threshold:
                warnings.append(f"Cột '{col}' có hơn {threshold:.0%} dữ liệu bị trống.")

    if df.duplicated().any():
        num_duplicates = df.duplicated().sum()
        warnings.append(f"Phát hiện {num_duplicates} dòng dữ liệu bị trùng lặp hoàn toàn.")

    return [f"[{file_name}] {warning}" for warning in warnings]