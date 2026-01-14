# File: reconciliation_engine.py (phiên bản V4.4 - Tái cấu trúc)
import pandas as pd
from pathlib import Path
import logging
from typing import Dict, Any
from datetime import datetime
from config import Col, COMPARE_COLS_FOR_MISMATCH, START_DATE, END_DATE, TIME_PRIORITY_COLS
from utils.schemas import MainReconResult
from core.duplicate_checker import run_all_duplicate_checks, generate_duplicate_summary

def generate_mismatch_notes(row: pd.Series) -> str:
    """Tạo ghi chú chi tiết về các điểm sai lệch thông tin."""
    notes = []
    for col in COMPARE_COLS_FOR_MISMATCH:
        col_lt = f"{col}_lythuyet"
        col_tt = f"{col}_thucte"
        val_lt = str(row.get(col_lt, ''))
        val_tt = str(row.get(col_tt, ''))
        if val_lt != val_tt:
            notes.append(f"Sai {col}: LT='{val_lt}' vs TT='{val_tt}'")
    return '; '.join(notes)

def _find_mismatched_rows(df_merged: pd.DataFrame) -> pd.Series:
    """Tìm các hàng có thông tin bị sai lệch bằng phương pháp vector hóa."""
    mismatch_mask = pd.Series(False, index=df_merged.index)
    for col in COMPARE_COLS_FOR_MISMATCH:
        col_lythuyet = f"{col}_lythuyet"
        col_thucte = f"{col}_thucte"
        
        if col_lythuyet in df_merged.columns and col_thucte in df_merged.columns:
            # <<< SỬA LỖI: Chuyển sang 'str' trước khi fillna >>>
            # Điều này tránh lỗi khi cố gắng fillna một giá trị mới vào cột 'category'
            s1 = df_merged[col_lythuyet].astype(str).fillna('')
            s2 = df_merged[col_thucte].astype(str).fillna('')
            
            mismatch_mask |= (s1 != s2)
            
    return mismatch_mask

def find_suspicious_dates(df: pd.DataFrame, run_time: datetime) -> pd.DataFrame:
    logging.info("Đang kiểm tra các giao dịch có ngày tháng đáng ngờ...")
    time_window = pd.Timedelta(days=60)
    recent_moves = df[(df[Col.TRANSACTION_TIME] > run_time - time_window) & (df[Col.TRANSACTION_TIME] < run_time + time_window)].copy()
    suspicious_mask = (
        (recent_moves[Col.TRANSACTION_TIME].dt.month == run_time.day) &
        (recent_moves[Col.TRANSACTION_TIME].dt.day == run_time.month) &
        (recent_moves[Col.TRANSACTION_TIME].dt.date != run_time.date())
    )
    suspicious_df = recent_moves[suspicious_mask]
    if not suspicious_df.empty:
        logging.warning(f"  -> Phát hiện {len(suspicious_df)} giao dịch có ngày tháng đáng ngờ.")
    return suspicious_df

def correct_future_dates(df: pd.DataFrame, run_time: datetime) -> tuple[pd.DataFrame, pd.DataFrame]:
    logging.info("Đang kiểm tra các giao dịch ngày tương lai (Chế độ: BÁO CÁO - KHÔNG SỬA LỖI)...")
    df_copy = df.copy()
    
    # So sánh theo NGÀY (không phải datetime) để tránh false positive
    # Giao dịch trong cùng ngày với run_time không phải là "tương lai"
    run_date = run_time.date()
    future_mask = df_copy[Col.TRANSACTION_TIME].dt.date > run_date
    df_future_report = df_copy[future_mask].copy()

    if df_future_report.empty:
        return df, df_future_report

    logging.warning(f"  -> Phát hiện {len(df_future_report)} giao dịch ngày tương lai. Vui lòng kiểm tra báo cáo chi tiết.")
    
    # Chỉ tạo báo cáo, KHÔNG tự động sửa dữ liệu gốc
    df_future_report['GhiChu_SuaLoi'] = 'CẢNH BÁO: Ngày giao dịch lớn hơn ngày kiểm tra (Future Date)'
    
    # Trả về df gốc (không sửa) và báo cáo
    return df, df_future_report

def identify_pending_shifting(df_all_moves: pd.DataFrame, df_ton_moi: pd.DataFrame) -> pd.DataFrame:
    """
    Xác định các container Restow (N-Shifting) nhưng chưa có X-Shifting và vẫn đang nằm bãi.
    Logic: Tìm giao dịch Shifting cuối cùng, nếu là 'nhap_shifting' và cont có trong 'ton_moi' -> Pending.
    """
    if df_all_moves.empty or df_ton_moi.empty:
        return pd.DataFrame()
        
    # Chỉ lấy các giao dịch Shifting
    df_shifting = df_all_moves[df_all_moves[Col.SOURCE_KEY].isin(['nhap_shifting', 'xuat_shifting'])].copy()
    if df_shifting.empty:
        return pd.DataFrame()
        
    # Sắp xếp theo thời gian tăng dần để lấy giao dịch mới nhất
    if Col.TRANSACTION_TIME in df_shifting.columns:
        df_shifting = df_shifting.sort_values(by=[Col.CONTAINER, Col.TRANSACTION_TIME])
        
    # Lấy trạng thái shifting cuối cùng
    df_last_shifting = df_shifting.drop_duplicates(subset=[Col.CONTAINER], keep='last')
    
    # Lọc những cont có trạng thái cuối là NHAP_SHIFTING (xuống bãi chưa lên tàu)
    df_pending = df_last_shifting[df_last_shifting[Col.SOURCE_KEY] == 'nhap_shifting'].copy()
    
    # Kiểm tra xem cont có thực sự còn nằm bãi không (có trong TON MOI)
    pending_conts = df_pending[df_pending[Col.CONTAINER].isin(df_ton_moi[Col.CONTAINER])]
    
    if not pending_conts.empty:
        pending_conts['GhiChu_Shifting'] = 'Hàng đảo chuyển đang nằm bãi (Pending Restow)'
        logging.info(f"  -> Phát hiện {len(pending_conts)} container Shifting đang nằm bãi.")
        
    return pending_conts


def perform_reconciliation(file_dfs: Dict[str, pd.DataFrame], report_folder: Path, run_time: datetime) -> Dict[str, Any]:
    """
    Execute the main reconciliation logic (Rule Engine).
    
    This function compares theoretical inventory (calculated from transaction history)
    against actual inventory (TON MOI) to identify discrepancies.
    
    Args:
        file_dfs: Dictionary of DataFrames keyed by file type (e.g., 'ton_cu', 'gate_in').
        report_folder: Directory to save intermediate reports.
        run_time: Timestamp considered as 'current time' for date validations.
    
    Returns:
        Dictionary containing:
            - 'ton_chuan': Containers that match perfectly
            - 'khop_sai_info': Containers that exist but have mismatched info
            - 'thieu': Containers missing from actual inventory
            - 'thua': Containers in actual but not in theoretical inventory
            - 'van_ton': Containers still present despite having gate-out records
            - 'counts': Summary statistics
            - 'timeline': Transaction timeline per container
    """
    
    all_moves_list = [df for key, df in file_dfs.items() if key != 'ton_moi' and not df.empty]
    if not all_moves_list: return {}
    
    df_all_moves = pd.concat(all_moves_list, ignore_index=True)

    # <<< V4.3: KIỂM TRA CONTAINER TRÙNG LẶP (B3 CHECKLIST) >>>
    duplicate_check_results = run_all_duplicate_checks(file_dfs)
    duplicate_summary = generate_duplicate_summary(duplicate_check_results)
    logging.info(f"[V4.3] Đã kiểm tra container trùng lặp theo B3 Checklist.")
    # <<< END V4.3 >>>

    df_suspicious_dates = find_suspicious_dates(df_all_moves, run_time)
    df_all_moves, df_future_report = correct_future_dates(df_all_moves, run_time)

    if START_DATE and END_DATE:
        start = pd.to_datetime(START_DATE, dayfirst=True)
        end = pd.to_datetime(END_DATE, dayfirst=True).replace(hour=23, minute=59, second=59)
        is_transaction = ~df_all_moves[Col.SOURCE_KEY].isin(['ton_cu'])
        is_in_range = (df_all_moves[Col.TRANSACTION_TIME] >= start) & (df_all_moves[Col.TRANSACTION_TIME] <= end)
        df_all_moves = df_all_moves[~is_transaction | is_in_range]

    df_all_moves_sorted = df_all_moves.sort_values(by=[Col.CONTAINER, Col.TRANSACTION_TIME, Col.MOVE_TYPE], ascending=[True, False, False])
    
    timeline_cols = [Col.CONTAINER, Col.TRANSACTION_TIME, Col.MOVE_TYPE, Col.SOURCE_FILE, Col.FE, Col.PHUONG_AN]
    existing_timeline_cols = [col for col in timeline_cols if col in df_all_moves_sorted.columns]
    df_timeline = df_all_moves_sorted[existing_timeline_cols]

    df_final_state = df_all_moves_sorted.drop_duplicates(subset=[Col.CONTAINER], keep='first')
    df_ton_ly_thuyet = df_final_state[df_final_state[Col.MOVE_TYPE] == 'IN']
    
    df_ton_moi = file_dfs.get('ton_moi', pd.DataFrame())
    if df_ton_moi.empty: return {}
    df_ton_moi = df_ton_moi.drop_duplicates(subset=[Col.CONTAINER])

    set_lythuyet = set(df_ton_ly_thuyet[Col.CONTAINER])
    set_thucte = set(df_ton_moi[Col.CONTAINER])

    cont_khop = list(set_lythuyet.intersection(set_thucte))
    cont_thieu = list(set_lythuyet.difference(set_thucte))
    cont_thua = list(set_thucte.difference(set_lythuyet))

    df_khop_lythuyet = df_ton_ly_thuyet[df_ton_ly_thuyet[Col.CONTAINER].isin(cont_khop)]
    df_khop_thucte = df_ton_moi[df_ton_moi[Col.CONTAINER].isin(cont_khop)]
    df_khop_details = pd.merge(df_khop_lythuyet, df_khop_thucte, on=Col.CONTAINER, how='left', suffixes=('_lythuyet', '_thucte'))
    mismatch_mask = _find_mismatched_rows(df_khop_details)
    df_khop_sai_info = df_khop_details[mismatch_mask].copy()
    df_ton_chuan = df_khop_details[~mismatch_mask].copy()
    
    # Initialize GhiChu column
    df_ton_chuan['GhiChu'] = ''

    # <<< V4.5: Tách Đảo Chuyển Nội Bãi (Position Shift) >>>
    df_dao_chuyen_noi_bai = pd.DataFrame()
    df_sai_thong_tin_thuc = pd.DataFrame()  # Sai thông tin thực sự (không phải đổi vị trí)
    
    if not df_khop_sai_info.empty:
        # Kiểm tra xem sai lệch có phải CHỈ là vị trí hay không
        location_col_lt = f"{Col.LOCATION}_lythuyet"
        location_col_tt = f"{Col.LOCATION}_thucte"
        
        if location_col_lt in df_khop_sai_info.columns and location_col_tt in df_khop_sai_info.columns:
            # Container chỉ sai vị trí = Đảo chuyển nội bãi
            only_location_diff = (
                (df_khop_sai_info[location_col_lt].astype(str) != df_khop_sai_info[location_col_tt].astype(str))
            )
            
            # Kiểm tra các cột khác có giống nhau không
            other_mismatch = pd.Series(False, index=df_khop_sai_info.index)
            for col in COMPARE_COLS_FOR_MISMATCH:
                if col == Col.LOCATION:
                    continue  # Bỏ qua vị trí
                col_lt = f"{col}_lythuyet"
                col_tt = f"{col}_thucte"
                if col_lt in df_khop_sai_info.columns and col_tt in df_khop_sai_info.columns:
                    other_mismatch |= (df_khop_sai_info[col_lt].astype(str).fillna('') != 
                                       df_khop_sai_info[col_tt].astype(str).fillna(''))
            
            # Đảo chuyển nội bãi = Chỉ sai vị trí, các thông tin khác đúng
            is_position_shift = only_location_diff & ~other_mismatch
            
            df_dao_chuyen_noi_bai = df_khop_sai_info[is_position_shift].copy()
            df_sai_thong_tin_thuc = df_khop_sai_info[~is_position_shift].copy()
            
            if not df_dao_chuyen_noi_bai.empty:
                df_dao_chuyen_noi_bai['GhiChu'] = 'Đảo chuyển nội bãi (Position Shift)'
                logging.info(f"  -> Phát hiện {len(df_dao_chuyen_noi_bai)} container đảo chuyển nội bãi.")
            
            if not df_sai_thong_tin_thuc.empty:
                df_sai_thong_tin_thuc['GhiChuSaiLech'] = df_sai_thong_tin_thuc.apply(generate_mismatch_notes, axis=1)
                logging.warning(f"  -> Phát hiện {len(df_sai_thong_tin_thuc)} container sai lệch thông tin thực sự.")
        else:
            # Không có cột vị trí để so sánh
            df_sai_thong_tin_thuc = df_khop_sai_info.copy()
            df_sai_thong_tin_thuc['GhiChuSaiLech'] = df_sai_thong_tin_thuc.apply(generate_mismatch_notes, axis=1)
            logging.warning(f"  -> Phát hiện {len(df_sai_thong_tin_thuc)} container sai lệch thông tin.")
    # <<< END V4.5 >>>

    # <<< V4.4: Smart Shifting Logic (Restow via Quay) >>>
    df_pending_shifting = identify_pending_shifting(df_all_moves, df_ton_moi)
    
    # Cập nhật ghi chú vào df_ton_chuan nếu là pending shifting
    if not df_pending_shifting.empty:
        pending_set = set(df_pending_shifting[Col.CONTAINER])
        mask_pending = df_ton_chuan[Col.CONTAINER].isin(pending_set)
        if mask_pending.any():
            df_ton_chuan.loc[mask_pending, 'GhiChu'] = 'Hàng đảo chuyển qua cầu tàu (Restow via Quay)'
    # <<< END V4.4 >>>

    # V4.5: Đổi tên từ 'thieu/thua' sang 'chenh_lech'
    df_chenh_lech_am = df_ton_ly_thuyet[df_ton_ly_thuyet[Col.CONTAINER].isin(cont_thieu)].copy()  # Có lệnh chưa về
    df_chenh_lech_duong_raw = df_ton_moi[df_ton_moi[Col.CONTAINER].isin(cont_thua)].copy()  # Chưa có lệnh (raw)
    
    # V5.1.1: NHẬN DIỆN CONTAINER CFS (Đóng hàng/Rút hàng) - Không phải "tồn chưa có lệnh"
    # Container CFS có cặp Gate OUT + Gate IN trong ngày, chỉ thay đổi F/E, vẫn tồn bãi
    df_bien_dong_fe = pd.DataFrame()  # Container biến động F/E (CFS)
    df_chenh_lech_duong = df_chenh_lech_duong_raw.copy()  # Tồn thực sự chưa có lệnh
    
    df_gate_in_all = file_dfs.get('gate_in', pd.DataFrame())
    df_gate_out_all = file_dfs.get('gate_out', pd.DataFrame())
    
    if not df_chenh_lech_duong_raw.empty and not df_gate_out_all.empty and not df_gate_in_all.empty:
        # Tìm container có CẢ Gate OUT lẫn Gate IN trong cùng kỳ
        cont_gate_out = set(df_gate_out_all[Col.CONTAINER]) if Col.CONTAINER in df_gate_out_all.columns else set()
        cont_gate_in = set(df_gate_in_all[Col.CONTAINER]) if Col.CONTAINER in df_gate_in_all.columns else set()
        cont_chenh_lech = set(df_chenh_lech_duong_raw[Col.CONTAINER])
        
        # Container có cả OUT + IN = có thể là CFS
        cont_co_ca_out_in = cont_gate_out.intersection(cont_gate_in)
        cont_cfs_candidate = cont_chenh_lech.intersection(cont_co_ca_out_in)
        
        if cont_cfs_candidate:
            # Kiểm tra F/E thay đổi giữa Gate OUT và Gate IN (hoặc TON MOI)
            df_out_check = df_gate_out_all[df_gate_out_all[Col.CONTAINER].isin(cont_cfs_candidate)].copy()
            df_in_check = df_gate_in_all[df_gate_in_all[Col.CONTAINER].isin(cont_cfs_candidate)].copy()
            
            if Col.FE in df_out_check.columns and Col.FE in df_in_check.columns:
                # Lấy F/E từ Gate OUT (lúc ra) và Gate IN (lúc vào lại)
                df_out_fe = df_out_check.drop_duplicates(subset=[Col.CONTAINER], keep='last')[[Col.CONTAINER, Col.FE, Col.PHUONG_AN]]
                df_in_fe = df_in_check.drop_duplicates(subset=[Col.CONTAINER], keep='last')[[Col.CONTAINER, Col.FE, Col.PHUONG_AN]]
                
                df_out_fe.columns = [Col.CONTAINER, 'F/E_OUT', 'PhuongAn_OUT']
                df_in_fe.columns = [Col.CONTAINER, 'F/E_NOW', 'PhuongAn_IN']
                
                df_cfs_compare = pd.merge(df_out_fe, df_in_fe, on=Col.CONTAINER, how='inner')
                
                if not df_cfs_compare.empty:
                    # F/E thay đổi = CFS hợp lệ (Đóng hàng E→F, Rút hàng F→E)
                    df_cfs_compare['FE_Changed'] = df_cfs_compare['F/E_OUT'].astype(str) != df_cfs_compare['F/E_NOW'].astype(str)
                    
                    df_cfs_valid = df_cfs_compare[df_cfs_compare['FE_Changed']].copy()
                    
                    if not df_cfs_valid.empty:
                        # Thêm lý do
                        df_cfs_valid['LyDo'] = df_cfs_valid.apply(
                            lambda r: f"Doi F/E: {r['F/E_OUT']} => {r['F/E_NOW']} ({r['PhuongAn_OUT']} / {r['PhuongAn_IN']})", 
                            axis=1
                        )
                        
                        # Merge với thông tin đầy đủ từ TON MOI
                        cont_cfs_set = set(df_cfs_valid[Col.CONTAINER])
                        df_bien_dong_fe = df_chenh_lech_duong_raw[df_chenh_lech_duong_raw[Col.CONTAINER].isin(cont_cfs_set)].copy()
                        
                        # Thêm thông tin F/E thay đổi
                        df_cfs_info = df_cfs_valid[[Col.CONTAINER, 'F/E_OUT', 'F/E_NOW', 'PhuongAn_OUT', 'PhuongAn_IN', 'LyDo']]
                        df_bien_dong_fe = pd.merge(df_bien_dong_fe, df_cfs_info, on=Col.CONTAINER, how='left')
                        
                        # Loại bỏ container CFS khỏi "tồn chưa có lệnh"
                        df_chenh_lech_duong = df_chenh_lech_duong_raw[~df_chenh_lech_duong_raw[Col.CONTAINER].isin(cont_cfs_set)].copy()
                        
                        logging.info(f"  -> V5.1.1: {len(df_bien_dong_fe)} container CFS (Đóng/Rút hàng - đổi F/E) được tách riêng")
    
    # V4.6: KIỂM TRA CHÉO NHẬP vs XUẤT
    # Container có NHẬP nhưng không tồn → Kiểm tra có XUẤT tương ứng không?
    df_da_xu_ly = pd.DataFrame()  # Có NHẬP + có XUẤT = flow bình thường
    df_nhap_khong_xuat = pd.DataFrame()  # Có NHẬP + KHÔNG có XUẤT = cảnh báo
    
    if not df_chenh_lech_am.empty:
        # Lấy tập container đã XUẤT (từ các nguồn OUT)
        df_xuat_list = []
        for key in ['gate_out', 'xuat_tau', 'xuat_shifting']:
            df_xuat = file_dfs.get(key, pd.DataFrame())
            if not df_xuat.empty and Col.CONTAINER in df_xuat.columns:
                df_xuat_list.append(df_xuat[[Col.CONTAINER]].copy())
        
        set_da_xuat = set()
        if df_xuat_list:
            df_all_xuat = pd.concat(df_xuat_list, ignore_index=True)
            set_da_xuat = set(df_all_xuat[Col.CONTAINER])
        
        # Kiểm tra từng container "thiếu" có chứng từ xuất không
        cont_chenh_lech_am = set(df_chenh_lech_am[Col.CONTAINER])
        
        cont_da_xu_ly = cont_chenh_lech_am.intersection(set_da_xuat)  # Có xuất = OK
        cont_nhap_khong_xuat = cont_chenh_lech_am.difference(set_da_xuat)  # Không có xuất = Cảnh báo
        
        # Tạo DataFrame kết quả
        if cont_da_xu_ly:
            df_da_xu_ly = df_chenh_lech_am[df_chenh_lech_am[Col.CONTAINER].isin(cont_da_xu_ly)].copy()
            df_da_xu_ly['TrangThai'] = '✅ Đã xử lý (có NHẬP + có XUẤT)'
            logging.info(f"  -> {len(df_da_xu_ly)} container đã xử lý xong (NHẬP → XUẤT)")
        
        if cont_nhap_khong_xuat:
            df_nhap_khong_xuat = df_chenh_lech_am[df_chenh_lech_am[Col.CONTAINER].isin(cont_nhap_khong_xuat)].copy()
            df_nhap_khong_xuat['TrangThai'] = '⚠️ CẢNH BÁO: Có NHẬP nhưng không tìm thấy XUẤT'
            logging.warning(f"  -> ⚠️ {len(df_nhap_khong_xuat)} container có NHẬP nhưng KHÔNG CÓ XUẤT (cần kiểm tra!)")
    
    if not df_chenh_lech_duong.empty:
        df_chenh_lech_duong['TrangThai'] = 'Tồn bãi chưa có lệnh trong ngày'
    
    # V5.1.2: Chỉ kiểm tra lỗi nghiêm trọng: Xuất Tàu nhưng vẫn tồn
    df_xuat_tau_van_ton = pd.DataFrame()
    set_ton_moi = set(df_ton_moi[Col.CONTAINER])
    
    for out_key in ['xuat_tau', 'xuat_shifting']:
        df_out = file_dfs.get(out_key, pd.DataFrame())
        if not df_out.empty and Col.CONTAINER in df_out.columns:
            van_ton_via_tau = set(df_out[Col.CONTAINER]).intersection(set_ton_moi)
            if van_ton_via_tau:
                df_temp = df_out[df_out[Col.CONTAINER].isin(van_ton_via_tau)].copy()
                df_temp['LyDo'] = f'XUẤT TÀU ({out_key}) NHƯNG VẪN TỒN - LỖI NGHIÊM TRỌNG'
                df_xuat_tau_van_ton = pd.concat([df_xuat_tau_van_ton, df_temp], ignore_index=True)
    
    if not df_xuat_tau_van_ton.empty:
        logging.error(f"  -> 🔴 {len(df_xuat_tau_van_ton)} container XUẤT TÀU nhưng vẫn tồn - LỖI NGHIÊM TRỌNG!")

    # V5.1.2: Trả về kết quả đã dọn dẹp
    return {
        "ton_chuan": df_ton_chuan,
        "sai_thong_tin": df_sai_thong_tin_thuc,
        "dao_chuyen_noi_bai": df_dao_chuyen_noi_bai,
        "chenh_lech_am": df_chenh_lech_am,
        "chenh_lech_duong": df_chenh_lech_duong,
        "bien_dong_fe": df_bien_dong_fe,  # V5.1.1: Container CFS - đổi F/E trong ngày
        "xuat_tau_van_ton": df_xuat_tau_van_ton,  # V5.1.2: Lỗi nghiêm trọng (Xuất tàu nhưng vẫn tồn)
        "master_log": df_all_moves_sorted,
        "future_moves_report": df_future_report,
        "suspicious_dates": df_suspicious_dates,
        "timeline": df_timeline,
        "pending_shifting": df_pending_shifting,
        "raw_data": file_dfs,
        "duplicate_check_results": duplicate_check_results,
        "duplicate_summary": duplicate_summary,
        "counts": {
            "khop_chuan": len(df_ton_chuan), 
            "sai_thong_tin": len(df_sai_thong_tin_thuc),
            "dao_chuyen_noi_bai": len(df_dao_chuyen_noi_bai),
            "chenh_lech_am": len(cont_thieu), 
            "chenh_lech_duong": len(df_chenh_lech_duong),
            "bien_dong_fe": len(df_bien_dong_fe),
            "xuat_tau_van_ton": len(df_xuat_tau_van_ton),
            "ton_ly_thuyet": len(df_ton_ly_thuyet),
            "ton_moi": len(df_ton_moi), 
            "future_moves": len(df_future_report),
            "suspicious_dates": len(df_suspicious_dates),
            "duplicates_found": sum(len(df) for df in duplicate_check_results.values() if not df.empty)
        }
    }