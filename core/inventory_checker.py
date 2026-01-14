# File: inventory_checker.py
import pandas as pd
import logging
from typing import Dict
from config import Col


def categorize_change_source(df_change: pd.DataFrame, all_dfs: Dict[str, pd.DataFrame], direction: str) -> pd.DataFrame:
    """
    Phân loại nguồn gốc của biến động (Vào từ đâu? Ra đi đâu?)
    """
    if df_change.empty or Col.CONTAINER not in df_change.columns:
        return df_change
    
    df_result = df_change.copy()
    df_result['NguonGoc'] = 'Không rõ'
    
    if direction == 'IN':
        checks = [
            ('nhap_tau', 'Tàu Nhập'),
            ('nhap_shifting', 'Shifting (N-Restow)'),
            ('gate_in', 'Cổng (Gate In)'),
        ]
    else: # OUT
        checks = [
            ('xuat_tau', 'Tàu Xuất'),
            ('xuat_shifting', 'Shifting (X-Restow)'),
            ('gate_out', 'Cổng (Gate Out)'),
        ]
        
    for key, label in checks:
        source_df = all_dfs.get(key, pd.DataFrame())
        if not source_df.empty and Col.CONTAINER in source_df.columns:
            # Chỉ cập nhật những dòng đang là 'Không rõ' để ưu tiên thứ tự (nếu cần)
            # Ở đây priority theo thứ tự list `checks`.
            mask = df_result[Col.CONTAINER].isin(source_df[Col.CONTAINER])
            # Update rows where NguonGoc is 'Không rõ' AND container is in source
            df_result.loc[mask & (df_result['NguonGoc'] == 'Không rõ'), 'NguonGoc'] = label
            
    return df_result

def compare_inventories(all_dfs: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """
    So sánh trực tiếp giữa file Tồn Cũ và Tồn Mới để tìm ra các thay đổi.
    """
    logging.info("--- BẮT ĐẦU ĐỐI SOÁT TỒN BÃI TRỰC TIẾP (TỒN CŨ vs TỒN MỚI) ---")

    df_ton_cu = all_dfs.get('ton_cu', pd.DataFrame())
    df_ton_moi = all_dfs.get('ton_moi', pd.DataFrame())

    if df_ton_cu.empty or df_ton_moi.empty:
        logging.warning("[Inventory Checker] Thiếu file Tồn Cũ hoặc Tồn Mới. Bỏ qua bước đối soát trực tiếp.")
        return {
            "da_roi_bai": pd.DataFrame(),
            "moi_vao_bai": pd.DataFrame(),
            "van_con_ton": pd.DataFrame()
        }

    set_cu = set(df_ton_cu[Col.CONTAINER])
    set_moi = set(df_ton_moi[Col.CONTAINER])

    # 1. Container đã rời bãi (có trong Tồn Cũ, không có trong Tồn Mới)
    cont_roi_bai = list(set_cu.difference(set_moi))
    df_da_roi_bai = df_ton_cu[df_ton_cu[Col.CONTAINER].isin(cont_roi_bai)].copy()
    df_da_roi_bai = categorize_change_source(df_da_roi_bai, all_dfs, 'OUT')

    # 2. Container mới vào bãi (có trong Tồn Mới, không có trong Tồn Cũ)
    cont_moi_vao = list(set_moi.difference(set_cu))
    df_moi_vao_bai = df_ton_moi[df_ton_moi[Col.CONTAINER].isin(cont_moi_vao)].copy()
    df_moi_vao_bai = categorize_change_source(df_moi_vao_bai, all_dfs, 'IN')
    
    # 3. Container vẫn còn tồn (có trong cả hai)
    cont_van_ton = list(set_cu.intersection(set_moi))
    df_van_con_ton = df_ton_moi[df_ton_moi[Col.CONTAINER].isin(cont_van_ton)].copy()

    logging.info(f"[Inventory Checker] Kết quả: Rời bãi={len(df_da_roi_bai)}, Mới vào={len(df_moi_vao_bai)}, Vẫn tồn={len(df_van_con_ton)}")
    
    return {
        "da_roi_bai": df_da_roi_bai,
        "moi_vao_bai": df_moi_vao_bai,
        "van_con_ton": df_van_con_ton
    }