# File: duplicate_checker.py
# Module kiểm tra container trùng lặp và các trường hợp bất thường (B3 + B14 Checklist)
# Version: 4.3.1

import pandas as pd
import logging
from typing import Dict, List, Tuple, Any, Set
from datetime import timedelta
from config import Col

# ============================================================================
# PHẦN 1: KIỂM TRA TRÙNG LẶP (B3 CHECKLIST)
# ============================================================================

def check_duplicate_containers(
    df: pd.DataFrame, 
    source_name: str = "Unknown"
) -> pd.DataFrame:
    """
    B3.3 / B3.5: Kiểm tra container bị trùng lặp trong 1 DataFrame.
    """
    if df.empty or Col.CONTAINER not in df.columns:
        return pd.DataFrame()
    
    duplicate_mask = df.duplicated(subset=[Col.CONTAINER], keep=False)
    df_duplicates = df[duplicate_mask].copy()
    
    if df_duplicates.empty:
        logging.info(f"[B3] {source_name}: Không có container trùng lặp.")
        return pd.DataFrame()
    
    container_counts = df[Col.CONTAINER].value_counts()
    df_duplicates['SoLanXuatHien'] = df_duplicates[Col.CONTAINER].map(container_counts)
    df_duplicates['NguonDuLieu'] = source_name
    df_duplicates['LoaiBatThuong'] = 'B3.3/B3.5 - Container trùng lặp'
    
    unique_dup = df_duplicates[Col.CONTAINER].nunique()
    logging.warning(f"[B3] {source_name}: {unique_dup} container trùng ({len(df_duplicates)} bản ghi).")
    
    return df_duplicates


def check_duplicates_with_position_change(
    df: pd.DataFrame,
    source_name: str = "Unknown"
) -> pd.DataFrame:
    """Kiểm tra container trùng lặp với VỊ TRÍ KHÁC NHAU (có thể là shifting nội bãi)."""
    if df.empty or Col.CONTAINER not in df.columns:
        return pd.DataFrame()
    
    if Col.LOCATION not in df.columns:
        return pd.DataFrame()
    
    duplicate_containers = df[df.duplicated(subset=[Col.CONTAINER], keep=False)][Col.CONTAINER].unique()
    
    if len(duplicate_containers) == 0:
        return pd.DataFrame()
    
    position_change_records = []
    
    for container in duplicate_containers:
        df_cont = df[df[Col.CONTAINER] == container]
        unique_positions = df_cont[Col.LOCATION].dropna().unique()
        
        if len(unique_positions) > 1:
            for _, row in df_cont.iterrows():
                record = row.to_dict()
                record['CacViTriKhacNhau'] = ', '.join(str(p) for p in unique_positions)
                record['SoViTriKhacNhau'] = len(unique_positions)
                record['LoaiBatThuong'] = 'SHIFTING NỘI BÃI hoặc LỖI DỮ LIỆU'
                position_change_records.append(record)
    
    if position_change_records:
        df_result = pd.DataFrame(position_change_records)
        logging.warning(f"[B3] {source_name}: {df_result[Col.CONTAINER].nunique()} container có nhiều vị trí.")
        return df_result
    
    return pd.DataFrame()


def check_duplicates_with_time_difference(
    df: pd.DataFrame,
    time_threshold_minutes: int = 60,
    source_name: str = "Unknown"
) -> pd.DataFrame:
    """Kiểm tra container trùng lặp với THỜI GIAN KHÁC NHAU đáng kể."""
    if df.empty or Col.CONTAINER not in df.columns or Col.TRANSACTION_TIME not in df.columns:
        return pd.DataFrame()
    
    duplicate_containers = df[df.duplicated(subset=[Col.CONTAINER], keep=False)][Col.CONTAINER].unique()
    
    if len(duplicate_containers) == 0:
        return pd.DataFrame()
    
    time_diff_records = []
    time_threshold = timedelta(minutes=time_threshold_minutes)
    
    for container in duplicate_containers:
        df_cont = df[df[Col.CONTAINER] == container].dropna(subset=[Col.TRANSACTION_TIME])
        
        if len(df_cont) < 2:
            continue
        
        times = df_cont[Col.TRANSACTION_TIME].sort_values()
        time_span = times.max() - times.min()
        
        if time_span > time_threshold:
            for _, row in df_cont.iterrows():
                record = row.to_dict()
                record['KhoangThoiGian'] = str(time_span)
                record['LoaiBatThuong'] = f'Trùng với khoảng cách > {time_threshold_minutes} phút'
                time_diff_records.append(record)
    
    if time_diff_records:
        df_result = pd.DataFrame(time_diff_records)
        logging.warning(f"[B3] {source_name}: {df_result[Col.CONTAINER].nunique()} container cách > {time_threshold_minutes} phút.")
        return df_result
    
    return pd.DataFrame()


# ============================================================================
# PHẦN 2: KIỂM TRA SAI SÓT B14 CHECKLIST
# ============================================================================

def check_th3_missing_transaction_line(
    file_dfs: Dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    TH 3: Cont Gate In và GATE Out bị thiếu 1 dòng biến động.
    (Container CFS thường có 2 dòng E+F: Rỗng Đóng/Rỗng Rút)
    
    Logic: Container có trong Gate In nhưng không có trong Gate Out (hoặc ngược lại)
    trong khi đã có thời gian giao dịch hoàn tất.
    """
    logging.info("[TH3] Kiểm tra container thiếu dòng biến động Gate In/Out...")
    
    df_gate_in = file_dfs.get('gate_in', pd.DataFrame())
    df_gate_out = file_dfs.get('gate_out', pd.DataFrame())
    
    if df_gate_in.empty or df_gate_out.empty:
        return pd.DataFrame()
    
    if Col.CONTAINER not in df_gate_in.columns or Col.CONTAINER not in df_gate_out.columns:
        return pd.DataFrame()
    
    set_gate_in = set(df_gate_in[Col.CONTAINER])
    set_gate_out = set(df_gate_out[Col.CONTAINER])
    
    # Container có Gate Out nhưng không có Gate In
    cont_out_no_in = set_gate_out - set_gate_in
    # Container có Gate In nhưng không có Gate Out (có thể vẫn tồn bãi - cần cross-check với tồn mới)
    
    results = []
    
    if cont_out_no_in:
        df_missing = df_gate_out[df_gate_out[Col.CONTAINER].isin(cont_out_no_in)].copy()
        df_missing['LoaiBatThuong'] = 'TH3 - Gate Out nhưng KHÔNG CÓ Gate In'
        results.append(df_missing)
        logging.warning(f"[TH3] {len(cont_out_no_in)} container có Gate Out nhưng không có Gate In.")
    
    if results:
        return pd.concat(results, ignore_index=True)
    
    return pd.DataFrame()


def check_th4_gateout_but_still_in_inventory(
    file_dfs: Dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    TH 4: Cont Gate Out giao rồi (cột "Container ra bãi" có giá trị) 
    nhưng list tồn bãi mới 8h vẫn còn (Outgoing).
    """
    logging.info("[TH4] Kiểm tra container Gate Out xong nhưng vẫn tồn bãi...")
    
    df_gate_out = file_dfs.get('gate_out', pd.DataFrame())
    df_ton_moi = file_dfs.get('ton_moi', pd.DataFrame())
    
    if df_gate_out.empty or df_ton_moi.empty:
        return pd.DataFrame()
    
    # Lọc container đã giao xong (có thời gian "Container ra bãi" hoặc "Xe ra cổng")
    time_cols = [Col.CONT_RA_BAI, Col.XE_RA_CONG]
    existing_time_cols = [c for c in time_cols if c in df_gate_out.columns]
    
    if not existing_time_cols:
        return pd.DataFrame()
    
    # Container có ít nhất 1 cột thời gian ra không null
    mask = df_gate_out[existing_time_cols].notna().any(axis=1)
    df_giao_xong = df_gate_out[mask]
    
    if df_giao_xong.empty:
        return pd.DataFrame()
    
    # Tìm container vẫn còn trong tồn mới
    set_giao_xong = set(df_giao_xong[Col.CONTAINER])
    set_ton_moi = set(df_ton_moi[Col.CONTAINER])
    
    cont_van_ton = set_giao_xong & set_ton_moi
    
    if cont_van_ton:
        df_result = df_giao_xong[df_giao_xong[Col.CONTAINER].isin(cont_van_ton)].copy()
        df_result['LoaiBatThuong'] = 'TH4 - Gate Out XONG nhưng VẪN TỒN BÃI (Cần kiểm tra)'
        logging.warning(f"[TH4] {len(cont_van_ton)} container Gate Out xong nhưng vẫn tồn bãi.")
        return df_result
    
    return pd.DataFrame()


def check_th5_wrong_method_display(
    file_dfs: Dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    TH 5: List Gate In/Gate Out thể hiện sai phương án XUAT TAU, LUU RONG.
    (Nhiều nhất ở Cấp rỗng và Rỗng đóng hàng)
    
    Logic: Kiểm tra phương án có hợp lệ không dựa trên source key.
    """
    logging.info("[TH5] Kiểm tra phương án sai so với loại giao dịch...")
    
    # Định nghĩa phương án hợp lệ cho từng loại nghiệp vụ
    valid_methods = {
        'gate_in': ['HA BAI', 'TRA RONG', 'DONG HANG', 'RUT HANG', 'VAO'],
        'gate_out': ['LAY NGUYEN', 'CAP RONG', 'DONG HANG', 'RUT HANG', 'RA'],
        'nhap_tau': ['HA BAI', 'NHAP TAU'],
        'xuat_tau': ['XUAT TAU', 'LAY NGUYEN'],
    }
    
    # Phương án không hợp lệ (sai logic)
    invalid_combinations = [
        # Gate In không thể có phương án XUAT TAU
        ('gate_in', ['XUAT TAU', 'LAY NGUYEN', 'CAP RONG']),
        # Gate Out không thể có phương án HA BAI, TRA RONG
        ('gate_out', ['HA BAI', 'TRA RONG', 'NHAP TAU']),
    ]
    
    results = []
    
    for source_key, invalid_methods in invalid_combinations:
        df = file_dfs.get(source_key, pd.DataFrame())
        if df.empty or Col.PHUONG_AN not in df.columns:
            continue
        
        # Tìm container có phương án không hợp lệ
        mask = df[Col.PHUONG_AN].str.upper().isin([m.upper() for m in invalid_methods])
        df_invalid = df[mask].copy()
        
        if not df_invalid.empty:
            df_invalid['LoaiBatThuong'] = f'TH5 - {source_key.upper()} có phương án SAI: {invalid_methods}'
            results.append(df_invalid)
            logging.warning(f"[TH5] {len(df_invalid)} container trong {source_key} có phương án sai.")
    
    if results:
        return pd.concat(results, ignore_index=True)
    
    return pd.DataFrame()


def check_th6_incoming_no_vehicle_time(
    file_dfs: Dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    TH 6.1: Cont Incoming nhưng chưa có giờ xe vào bãi.
    TH 6.2: Cont Stacking có/chưa có giờ xe vào bãi.
    
    Logic: Container có trong Gate In nhưng cột thời gian xe vào bãi/container vào bãi trống.
    """
    logging.info("[TH6] Kiểm tra container vào cổng nhưng chưa có giờ xe/cont vào bãi...")
    
    df_gate_in = file_dfs.get('gate_in', pd.DataFrame())
    
    if df_gate_in.empty:
        return pd.DataFrame()
    
    # Các cột thời gian cần kiểm tra
    time_cols = [Col.XE_VAO_CONG, Col.CONT_VAO_BAI]
    existing_cols = [c for c in time_cols if c in df_gate_in.columns]
    
    if not existing_cols:
        logging.info("[TH6] Không có cột thời gian vào bãi để kiểm tra.")
        return pd.DataFrame()
    
    results = []
    
    # TH 6.1: Không có giờ xe vào cổng
    if Col.XE_VAO_CONG in df_gate_in.columns:
        mask_no_xe = df_gate_in[Col.XE_VAO_CONG].isna()
        df_no_xe = df_gate_in[mask_no_xe].copy()
        if not df_no_xe.empty:
            df_no_xe['LoaiBatThuong'] = 'TH6.1 - Gate In nhưng KHÔNG CÓ GIỜ XE VÀO CỔNG'
            results.append(df_no_xe)
            logging.warning(f"[TH6.1] {len(df_no_xe)} container Gate In không có giờ xe vào cổng.")
    
    # TH 6.2: Không có giờ container vào bãi
    if Col.CONT_VAO_BAI in df_gate_in.columns:
        mask_no_cont = df_gate_in[Col.CONT_VAO_BAI].isna()
        df_no_cont = df_gate_in[mask_no_cont].copy()
        if not df_no_cont.empty:
            df_no_cont['LoaiBatThuong'] = 'TH6.2 - Gate In nhưng KHÔNG CÓ GIỜ CONT VÀO BÃI (Stacking)'
            results.append(df_no_cont)
            logging.warning(f"[TH6.2] {len(df_no_cont)} container Gate In không có giờ cont vào bãi.")
    
    if results:
        return pd.concat(results, ignore_index=True)
    
    return pd.DataFrame()


# ============================================================================
# PHẦN 2B: KIỂM TRA V5.1 - MẤT PHƯƠNG ÁN & ĐỔI THÔNG TIN
# ============================================================================

def check_missing_phuong_an(
    file_dfs: Dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    V5.1: Phát hiện container thiếu phương án (cột Phương án trống/null).
    
    Áp dụng cho: Gate In, Gate Out (các file biến động cần có phương án)
    """
    logging.info("[V5.1] Kiểm tra container THIẾU PHƯƠNG ÁN...")
    
    results = []
    
    # Các file cần kiểm tra phương án
    files_to_check = ['gate_in', 'gate_out', 'nhap_tau', 'xuat_tau']
    
    for source_key in files_to_check:
        df = file_dfs.get(source_key, pd.DataFrame())
        
        if df.empty:
            continue
        
        if Col.PHUONG_AN not in df.columns:
            # Nếu không có cột Phương án -> cảnh báo tất cả
            df_missing = df.copy()
            df_missing['LoaiBatThuong'] = f'V5.1 - {source_key.upper()} KHÔNG CÓ CỘT PHƯƠNG ÁN'
            results.append(df_missing)
            logging.warning(f"[V5.1] {source_key}: Không có cột Phương án!")
            continue
        
        # Tìm container có Phương án trống/null/NaN
        mask = df[Col.PHUONG_AN].isna() | (df[Col.PHUONG_AN].astype(str).str.strip() == '')
        df_missing = df[mask].copy()
        
        if not df_missing.empty:
            df_missing['LoaiBatThuong'] = f'V5.1 - {source_key.upper()} THIẾU PHƯƠNG ÁN (trống)'
            results.append(df_missing)
            logging.warning(f"[V5.1] {source_key}: {len(df_missing)} container thiếu phương án.")
    
    if results:
        return pd.concat(results, ignore_index=True)
    
    logging.info("[V5.1] Tất cả container đều có phương án.")
    return pd.DataFrame()


def check_opr_changes(
    file_dfs: Dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    V5.1: Phát hiện container bị ĐỔI HÃNG KHAI THÁC (OPR) giữa các file.
    
    So sánh: Tồn cũ vs Biến động vs Tồn mới
    """
    logging.info("[V5.1] Kiểm tra container ĐỔI HÃNG KHAI THÁC (OPR)...")
    
    df_ton_cu = file_dfs.get('ton_cu', pd.DataFrame())
    df_ton_moi = file_dfs.get('ton_moi', pd.DataFrame())
    
    if df_ton_cu.empty or df_ton_moi.empty:
        return pd.DataFrame()
    
    if Col.CONTAINER not in df_ton_cu.columns or Col.CONTAINER not in df_ton_moi.columns:
        return pd.DataFrame()
    
    if Col.OPERATOR not in df_ton_cu.columns or Col.OPERATOR not in df_ton_moi.columns:
        logging.info("[V5.1] Không có cột Hãng khai thác để so sánh.")
        return pd.DataFrame()
    
    # Tìm container xuất hiện cả 2 file
    set_ton_cu = set(df_ton_cu[Col.CONTAINER])
    set_ton_moi = set(df_ton_moi[Col.CONTAINER])
    common_containers = set_ton_cu & set_ton_moi
    
    if not common_containers:
        return pd.DataFrame()
    
    # So sánh OPR
    results = []
    
    # Tạo dict để tra cứu nhanh
    opr_ton_cu = df_ton_cu.set_index(Col.CONTAINER)[Col.OPERATOR].to_dict()
    opr_ton_moi = df_ton_moi.set_index(Col.CONTAINER)[Col.OPERATOR].to_dict()
    
    for container in common_containers:
        opr_cu = str(opr_ton_cu.get(container, '')).strip().upper()
        opr_moi = str(opr_ton_moi.get(container, '')).strip().upper()
        
        if opr_cu and opr_moi and opr_cu != opr_moi:
            results.append({
                Col.CONTAINER: container,
                'OPR_TonCu': opr_cu,
                'OPR_TonMoi': opr_moi,
                'LoaiBatThuong': f'V5.1 - ĐỔI OPR: {opr_cu} → {opr_moi}'
            })
    
    if results:
        df_result = pd.DataFrame(results)
        logging.warning(f"[V5.1] {len(df_result)} container đổi OPR.")
        return df_result
    
    logging.info("[V5.1] Không có container đổi OPR.")
    return pd.DataFrame()


def check_size_changes(
    file_dfs: Dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    V5.1: Phát hiện container bị ĐỔI KÍCH CỠ (20 vs 40) giữa các file.
    """
    logging.info("[V5.1] Kiểm tra container ĐỔI KÍCH CỠ (Size)...")
    
    df_ton_cu = file_dfs.get('ton_cu', pd.DataFrame())
    df_ton_moi = file_dfs.get('ton_moi', pd.DataFrame())
    
    if df_ton_cu.empty or df_ton_moi.empty:
        return pd.DataFrame()
    
    if Col.ISO not in df_ton_cu.columns or Col.ISO not in df_ton_moi.columns:
        logging.info("[V5.1] Không có cột Kích cỡ ISO để so sánh.")
        return pd.DataFrame()
    
    # Tìm container xuất hiện cả 2 file
    set_ton_cu = set(df_ton_cu[Col.CONTAINER])
    set_ton_moi = set(df_ton_moi[Col.CONTAINER])
    common_containers = set_ton_cu & set_ton_moi
    
    if not common_containers:
        return pd.DataFrame()
    
    # Helper function để lấy size category
    def get_size_cat(iso):
        if pd.isna(iso):
            return 'Unknown'
        iso_str = str(iso).upper().strip()
        if not iso_str:
            return 'Unknown'
        first = iso_str[0]
        if first == '2' or iso_str.startswith('20'):
            return '20'
        elif first in ['4', '9', 'L', 'M'] or iso_str.startswith('40') or iso_str.startswith('45'):
            return '40'
        return 'Other'
    
    # Tạo dict để tra cứu nhanh
    iso_ton_cu = df_ton_cu.set_index(Col.CONTAINER)[Col.ISO].to_dict()
    iso_ton_moi = df_ton_moi.set_index(Col.CONTAINER)[Col.ISO].to_dict()
    
    results = []
    
    for container in common_containers:
        iso_cu = iso_ton_cu.get(container, '')
        iso_moi = iso_ton_moi.get(container, '')
        
        size_cu = get_size_cat(iso_cu)
        size_moi = get_size_cat(iso_moi)
        
        if size_cu in ['20', '40'] and size_moi in ['20', '40'] and size_cu != size_moi:
            results.append({
                Col.CONTAINER: container,
                'ISO_TonCu': iso_cu,
                'ISO_TonMoi': iso_moi,
                'Size_TonCu': size_cu,
                'Size_TonMoi': size_moi,
                'LoaiBatThuong': f'V5.1 - ĐỔI SIZE: {size_cu}ft → {size_moi}ft'
            })
    
    if results:
        df_result = pd.DataFrame(results)
        logging.warning(f"[V5.1] {len(df_result)} container đổi Size (NGHIÊM TRỌNG!).")
        return df_result
    
    logging.info("[V5.1] Không có container đổi Size.")
    return pd.DataFrame()


def check_fe_changes(
    file_dfs: Dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    V5.1: Phát hiện container bị ĐỔI TRẠNG THÁI E/F (Empty vs Full) giữa các file.
    
    Lưu ý: Đổi F→E hoặc E→F có thể là nghiệp vụ bình thường (đóng/rút hàng)
    """
    logging.info("[V5.1] Kiểm tra container ĐỔI TRẠNG THÁI E/F...")
    
    df_ton_cu = file_dfs.get('ton_cu', pd.DataFrame())
    df_ton_moi = file_dfs.get('ton_moi', pd.DataFrame())
    
    if df_ton_cu.empty or df_ton_moi.empty:
        return pd.DataFrame()
    
    if Col.FE not in df_ton_cu.columns or Col.FE not in df_ton_moi.columns:
        logging.info("[V5.1] Không có cột F/E để so sánh.")
        return pd.DataFrame()
    
    # Tìm container xuất hiện cả 2 file
    set_ton_cu = set(df_ton_cu[Col.CONTAINER])
    set_ton_moi = set(df_ton_moi[Col.CONTAINER])
    common_containers = set_ton_cu & set_ton_moi
    
    if not common_containers:
        return pd.DataFrame()
    
    # Helper function để chuẩn hóa F/E
    def normalize_fe(fe_val):
        if pd.isna(fe_val):
            return 'Unknown'
        fe_str = str(fe_val).upper().strip()
        if fe_str in ['E', 'EMPTY', 'RỖNG', 'RONG', 'R', 'MT']:
            return 'E'
        elif fe_str in ['F', 'FULL', 'HÀNG', 'HANG', 'H', 'FL']:
            return 'F'
        return 'Unknown'
    
    # Tạo dict để tra cứu nhanh
    fe_ton_cu = df_ton_cu.set_index(Col.CONTAINER)[Col.FE].to_dict()
    fe_ton_moi = df_ton_moi.set_index(Col.CONTAINER)[Col.FE].to_dict()
    
    results = []
    
    for container in common_containers:
        fe_cu_raw = fe_ton_cu.get(container, '')
        fe_moi_raw = fe_ton_moi.get(container, '')
        
        fe_cu = normalize_fe(fe_cu_raw)
        fe_moi = normalize_fe(fe_moi_raw)
        
        if fe_cu in ['E', 'F'] and fe_moi in ['E', 'F'] and fe_cu != fe_moi:
            # Xác định loại thay đổi
            if fe_cu == 'E' and fe_moi == 'F':
                change_type = 'ĐÓNG HÀNG (E→F)'
            else:
                change_type = 'RÚT HÀNG (F→E)'
            
            results.append({
                Col.CONTAINER: container,
                'FE_TonCu': fe_cu_raw,
                'FE_TonMoi': fe_moi_raw,
                'FE_Cu_Norm': fe_cu,
                'FE_Moi_Norm': fe_moi,
                'LoaiBatThuong': f'V5.1 - ĐỔI F/E: {change_type}'
            })
    
    if results:
        df_result = pd.DataFrame(results)
        logging.info(f"[V5.1] {len(df_result)} container đổi F/E (có thể là nghiệp vụ bình thường).")
        return df_result
    
    logging.info("[V5.1] Không có container đổi F/E.")
    return pd.DataFrame()


# ============================================================================
# PHẦN 3: HÀM TỔNG HỢP
# ============================================================================

def run_all_duplicate_checks(
    file_dfs: Dict[str, pd.DataFrame]
) -> Dict[str, pd.DataFrame]:
    """
    Chạy TẤT CẢ các kiểm tra sai sót (B3 + B14 + V5.1 Checklist).
    """
    logging.info("=" * 60)
    logging.info("BẮT ĐẦU KIỂM TRA SAI SÓT (B3 + B14 + V5.1 CHECKLIST)")
    logging.info("=" * 60)
    
    results = {}
    
    # === B3: KIỂM TRA TRÙNG LẶP ===
    df_ton_moi = file_dfs.get('ton_moi', pd.DataFrame())
    if not df_ton_moi.empty:
        results['B3_duplicates_ton_moi'] = check_duplicate_containers(df_ton_moi, "TON MOI")
        results['B3_position_changes'] = check_duplicates_with_position_change(df_ton_moi, "TON MOI")
    
    df_ton_cu = file_dfs.get('ton_cu', pd.DataFrame())
    if not df_ton_cu.empty:
        results['B3_duplicates_ton_cu'] = check_duplicate_containers(df_ton_cu, "TON CU")
    
    for key in ['gate_in', 'gate_out']:
        df = file_dfs.get(key, pd.DataFrame())
        if not df.empty:
            results[f'B3_duplicates_{key}'] = check_duplicate_containers(df, key.upper().replace('_', ' '))
    
    # Kiểm tra thời gian bất thường
    all_moves_list = [df for key, df in file_dfs.items() if key != 'ton_moi' and not df.empty]
    if all_moves_list:
        df_all_moves = pd.concat(all_moves_list, ignore_index=True)
        results['B3_time_anomalies'] = check_duplicates_with_time_difference(df_all_moves, 60, "ALL MOVES")
    
    # === B14: KIỂM TRA SAI SÓT ===
    results['TH3_missing_gate_record'] = check_th3_missing_transaction_line(file_dfs)
    results['TH4_gateout_still_in_inventory'] = check_th4_gateout_but_still_in_inventory(file_dfs)
    results['TH5_wrong_method'] = check_th5_wrong_method_display(file_dfs)
    results['TH6_no_vehicle_time'] = check_th6_incoming_no_vehicle_time(file_dfs)
    
    # === V5.1: KIỂM TRA MỚI ===
    results['V51_missing_phuong_an'] = check_missing_phuong_an(file_dfs)
    results['V51_opr_changes'] = check_opr_changes(file_dfs)
    results['V51_size_changes'] = check_size_changes(file_dfs)
    results['V51_fe_changes'] = check_fe_changes(file_dfs)
    
    logging.info("=" * 60)
    logging.info("KẾT THÚC KIỂM TRA SAI SÓT")
    logging.info("=" * 60)
    
    return results


def generate_duplicate_summary(
    check_results: Dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """Tạo bảng tóm tắt kết quả kiểm tra."""
    summary_data = []
    
    for check_name, df_result in check_results.items():
        if df_result is not None and not df_result.empty and Col.CONTAINER in df_result.columns:
            summary_data.append({
                'MaKiemTra': check_name,
                'SoContainerBatThuong': df_result[Col.CONTAINER].nunique(),
                'TongSoBanGhi': len(df_result)
            })
    
    if summary_data:
        df_summary = pd.DataFrame(summary_data)
        df_summary = df_summary.sort_values('SoContainerBatThuong', ascending=False)
        return df_summary
    
    return pd.DataFrame({
        'MaKiemTra': ['Không có bất thường'], 
        'SoContainerBatThuong': [0], 
        'TongSoBanGhi': [0]
    })
