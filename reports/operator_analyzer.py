# File: operator_analyzer.py (V5.1.3 - Tách file theo từng hãng)
import pandas as pd
import logging
from typing import Dict, Any
from config import Col, OPERATOR_MAPPING


def analyze_by_operator(all_dfs: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """
    Phân tích và so sánh Tồn Cũ vs Tồn Mới, nhóm theo hãng tàu.
    Trả về cả bảng tổng hợp và danh sách container chi tiết.
    """
    logging.info("--- BẮT ĐẦU PHÂN TÍCH TỒN BÃI CHI TIẾT THEO HÃNG TÀU ---")

    df_ton_cu = all_dfs.get('ton_cu', pd.DataFrame())
    df_ton_moi = all_dfs.get('ton_moi', pd.DataFrame())

    empty_result = {
        "summary": pd.DataFrame(),
        "details_ton_cu": pd.DataFrame(),
        "details_ton_moi": pd.DataFrame(),
        "details_roi_bai": pd.DataFrame(),
        "details_moi_vao": pd.DataFrame(),
    }

    if df_ton_cu.empty or df_ton_moi.empty:
        logging.warning("[Operator Analyzer] Thiếu file Tồn Cũ hoặc Tồn Mới. Bỏ qua phân tích.")
        return empty_result

    reverse_mapping = {code: name for name, codes in OPERATOR_MAPPING.items() for code in codes}
    
    if Col.OPERATOR not in df_ton_cu.columns or Col.OPERATOR not in df_ton_moi.columns:
        logging.warning(f"[Operator Analyzer] Thiếu cột '{Col.OPERATOR}'. Bỏ qua phân tích.")
        return empty_result
    
    # Gán Lines cho cả tồn cũ và tồn mới
    df_ton_cu = df_ton_cu.copy()
    df_ton_moi = df_ton_moi.copy()
    df_ton_cu['Lines'] = df_ton_cu[Col.OPERATOR].apply(lambda x: reverse_mapping.get(x, 'Hang_Khac'))
    df_ton_moi['Lines'] = df_ton_moi[Col.OPERATOR].apply(lambda x: reverse_mapping.get(x, 'Hang_Khac'))

    # Tổng hợp theo Lines
    count_cu = df_ton_cu.groupby('Lines')[Col.CONTAINER].nunique()
    count_moi = df_ton_moi.groupby('Lines')[Col.CONTAINER].nunique()
    summary_df = pd.DataFrame({'Tồn Cũ': count_cu, 'Tồn Mới': count_moi}).fillna(0).astype(int)
    summary_df['Biến Động'] = summary_df['Tồn Mới'] - summary_df['Tồn Cũ']
    summary_df.sort_values(by='Tồn Cũ', ascending=False, inplace=True)

    # Tính biến động
    set_cu = set(df_ton_cu[Col.CONTAINER])
    set_moi = set(df_ton_moi[Col.CONTAINER])

    cont_roi_bai = list(set_cu.difference(set_moi))
    details_roi_bai = df_ton_cu[df_ton_cu[Col.CONTAINER].isin(cont_roi_bai)].copy()

    cont_moi_vao = list(set_moi.difference(set_cu))
    details_moi_vao = df_ton_moi[df_ton_moi[Col.CONTAINER].isin(cont_moi_vao)].copy()
    
    logging.info("--- KẾT THÚC PHÂN TÍCH TỒN BÃI CHI TIẾT THEO HÃNG TÀU ---")
    
    return {
        "summary": summary_df,
        "details_ton_cu": df_ton_cu,      # V5.1.3: Trả về toàn bộ tồn cũ với Lines
        "details_ton_moi": df_ton_moi,    # V5.1.3: Trả về toàn bộ tồn mới với Lines
        "details_roi_bai": details_roi_bai,
        "details_moi_vao": details_moi_vao,
    }