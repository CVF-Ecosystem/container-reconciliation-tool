# File: delta_checker.py (phiên bản sửa lỗi ValueError)
import pandas as pd
from pathlib import Path
import logging
from typing import Dict

def find_latest_report_folder(output_dir: Path, current_report_folder_name: str) -> Path | None:
    """Tìm thư mục báo cáo gần nhất trước đó."""
    try:
        report_folders = [d for d in output_dir.iterdir() if d.is_dir() and d.name.startswith('Report_')]
        report_folders = [d for d in report_folders if d.name != current_report_folder_name]
        if not report_folders:
            return None
        latest_folder = sorted(report_folders, key=lambda d: d.name)[-1]
        return latest_folder
    except Exception as e:
        logging.error(f"Lỗi khi tìm thư mục báo cáo cũ: {e}")
        return None

def read_summary_from_report(report_folder: Path) -> pd.DataFrame | None:
    """Đọc file 0. Summary.xlsx từ một thư mục báo cáo."""
    summary_path = report_folder / "0. Summary.xlsx"
    if not summary_path.exists():
        return None
    try:
        df = pd.read_excel(summary_path).set_index('Hang muc')
        return df
    except Exception as e:
        logging.error(f"Lỗi khi đọc file summary cũ từ {summary_path}: {e}")
        return None

def perform_delta_analysis(
    current_summary_indexed_df: pd.DataFrame, # Đổi tên để rõ ràng hơn
    output_dir: Path, 
    current_report_folder_name: str
) -> pd.DataFrame:
    """Thực hiện phân tích Delta giữa lần chạy hiện tại và lần chạy trước."""
    logging.info("--- BẮT ĐẦU PHÂN TÍCH DELTA (SO SÁNH VỚI LẦN CHẠY TRƯỢC) ---")
    
    latest_report_folder = find_latest_report_folder(output_dir, current_report_folder_name)
    
    if not latest_report_folder:
        return pd.DataFrame()
        
    logging.info(f"[Delta Analysis] Tìm thấy báo cáo cũ để so sánh: {latest_report_folder.name}")
    
    df_old_summary = read_summary_from_report(latest_report_folder)
    if df_old_summary is None:
        return pd.DataFrame()

    # <<< SỬA LỖI: Không cần set_index nữa vì đã được thực hiện bên ngoài >>>
    df_current_numeric = current_summary_indexed_df[pd.to_numeric(current_summary_indexed_df['So luong'], errors='coerce').notna()]

    df_comparison = pd.merge(
        df_current_numeric.rename(columns={'So luong': 'Hien tai'}),
        df_old_summary.rename(columns={'So luong': 'Lan truoc'}),
        left_index=True,
        right_index=True,
        how='outer'
    )
    
    df_comparison['Hien tai'] = pd.to_numeric(df_comparison['Hien tai'], errors='coerce')
    df_comparison['Lan truoc'] = pd.to_numeric(df_comparison['Lan truoc'], errors='coerce')
    df_comparison = df_comparison.fillna(0).astype(int)
    df_comparison['Chenh lech'] = df_comparison['Hien tai'] - df_comparison['Lan truoc']
    
    # <<< CẢI TIẾN: Lọc bỏ các dòng toàn số 0 không cần thiết >>>
    df_comparison = df_comparison[
        (df_comparison['Hien tai'] != 0) | (df_comparison['Lan truoc'] != 0)
    ]
    
    # Sắp xếp lại theo thứ tự của file summary hiện tại
    category_order = current_summary_indexed_df.index.tolist()
    df_comparison = df_comparison.reset_index()
    # Chỉ giữ lại các hạng mục có trong category_order để tránh lỗi
    df_comparison = df_comparison[df_comparison['Hang muc'].isin(category_order)]
    df_comparison['Hang muc'] = pd.Categorical(df_comparison['Hang muc'], categories=category_order, ordered=True)
    df_comparison = df_comparison.sort_values('Hang muc')
    
    logging.info("--- KẾT THÚC PHÂN TÍCH DELTA ---")
    return df_comparison