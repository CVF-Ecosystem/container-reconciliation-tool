# File: advanced_checker.py
import pandas as pd
import logging
from typing import Dict, Set
from config import Col, INBOUND_KEYS, ResultKeys
from utils.schemas import SimpleReconResult


def perform_simple_reconciliation(all_dfs: Dict[str, pd.DataFrame]) -> Dict[str, Set[str]]:
    """
    Thực hiện đối soát đơn giản dựa trên source key của giao dịch cuối cùng.
    """
    logging.info("--- GIAI ĐOẠN 2B: THỰC THI ĐỐI SOÁT ĐƠN GIẢN (SOURCEKEY) ---")

    all_moves_list = [df for key, df in all_dfs.items() if key != 'ton_moi' and not df.empty]
    if not all_moves_list:
        return {"khop": set(), "thieu": set(), "thua": set()}
        
    df_all_moves: pd.DataFrame = pd.concat(all_moves_list, ignore_index=True)
    
    # <<< CẢI TIẾN: Kiểm tra các cột cần thiết trước khi sử dụng >>>
    required_cols = [Col.CONTAINER, Col.TRANSACTION_TIME, Col.SOURCE_KEY]
    if not all(col in df_all_moves.columns for col in required_cols):
        missing = [col for col in required_cols if col not in df_all_moves.columns]
        logging.error(f"[Checker] DataFrame gộp thiếu các cột cần thiết: {missing}.")
        return {"khop": set(), "thieu": set(), "thua": set()}

    df_all_moves_sorted = df_all_moves.sort_values(by=[Col.CONTAINER, Col.TRANSACTION_TIME], ascending=[True, False])
    df_final_state = df_all_moves_sorted.drop_duplicates(subset=[Col.CONTAINER], keep='first')

    df_ton_ly_thuyet_simple = df_final_state[df_final_state[Col.SOURCE_KEY].isin(INBOUND_KEYS)]
    set_lythuyet_simple: Set[str] = set(df_ton_ly_thuyet_simple[Col.CONTAINER])

    df_ton_moi = all_dfs.get('ton_moi', pd.DataFrame())
    if df_ton_moi.empty or Col.CONTAINER not in df_ton_moi.columns:
        return {"khop": set(), "thieu": set_lythuyet_simple, "thua": set()}
        
    set_thucte: Set[str] = set(df_ton_moi[Col.CONTAINER])

    khop: Set[str] = set_lythuyet_simple.intersection(set_thucte)
    thieu: Set[str] = set_lythuyet_simple.difference(set_thucte)
    thua: Set[str] = set_thucte.difference(set_lythuyet_simple)
    
    logging.info(f"[Checker] Kết quả: Khớp={len(khop)}, Thiếu={len(thieu)}, Thừa={len(thua)}")
    
    # <<< THAY ĐỔI: Sử dụng hằng số và TypedDict >>>
    return {
        ResultKeys.KHOP: khop, 
        ResultKeys.THIEU: thieu, 
        ResultKeys.THUA: thua
    }